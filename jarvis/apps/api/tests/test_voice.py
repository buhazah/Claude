"""Voice: segmentation, wake words, and the barge-in state machine."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import replace

import httpx
import pytest

from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.base import Chunk, CompletionRequest, ModelSpec, Role, ToolSchema, Usage
from jarvis.llm.providers.echo import ECHO_MODEL, EchoProvider
from jarvis.voice.models import VoiceState
from jarvis.voice.ports import ScriptedTranscriber, SilentSpeaker
from jarvis.voice.providers.hosted import HostedSpeaker, HostedTranscriber
from jarvis.voice.segment import SpeechSegmenter
from jarvis.voice.wake import WakeWordDetector

SLOW_MODEL = replace(ECHO_MODEL, id="slow-1", provider="slow")


class SlowProvider:
    """Emits tokens with a real gap, so an interruption has something to catch.

    An instantaneous provider would make every barge-in test pass vacuously —
    the generation would be over before the interrupt arrived.
    """

    name = "slow"

    def __init__(self, text: str, *, delay: float = 0.02) -> None:
        self._text = text
        self._delay = delay
        self.completed = False

    def models(self) -> list[ModelSpec]:
        return [SLOW_MODEL]

    def is_available(self) -> bool:
        return True

    async def stream(
        self, request: CompletionRequest, model: ModelSpec, tools: list[ToolSchema] | None = None
    ) -> AsyncIterator[Chunk]:
        for word in self._text.split(" "):
            await asyncio.sleep(self._delay)
            yield Chunk(text=word + " ")
        self.completed = True  # never reached if the turn was cancelled
        yield Chunk(done=True, usage=Usage(input_tokens=5, output_tokens=5))


def _system(settings, clock: FrozenClock, provider):
    return container.build(settings, providers=[provider], clock=clock)


# ── Segmentation ──────────────────────────────────────────────────────────────


def test_a_sentence_is_released_as_soon_as_it_completes() -> None:
    """The whole point: speak sentence one while sentence two is generating."""
    segmenter = SpeechSegmenter()
    ready: list[str] = []
    for token in ["The launch ", "is on Friday. ", "We should tell ", "the team."]:
        ready.extend(segmenter.push(token))

    assert ready == ["The launch is on Friday."]
    assert segmenter.flush() == "We should tell the team."


@pytest.mark.parametrize(
    "text",
    [
        "Dr. Smith will present the findings shortly and then we continue. ",
        "The revenue was 3.5 million dollars last quarter which is good news. ",
        "Use the API, e.g. the search endpoint, to fetch the current records. ",
    ],
)
def test_abbreviations_and_decimals_do_not_split_a_sentence(text: str) -> None:
    """A fragment spoken aloud cannot be un-said, so splitting must be careful."""
    segmenter = SpeechSegmenter()
    ready = segmenter.push(text)
    assert len(ready) == 1
    assert ready[0].endswith((".", "!", "?"))


def test_a_long_clause_flushes_rather_than_leaving_silence() -> None:
    segmenter = SpeechSegmenter(clause_flush_after=60)
    ready = segmenter.push(
        "This is a long stretch of speech with no full stop in sight, "
        "which would otherwise leave the listener waiting in silence "
    )
    assert ready
    assert ready[0].rstrip().endswith(",")


def test_a_very_short_fragment_waits_for_more() -> None:
    segmenter = SpeechSegmenter()
    assert segmenter.push("Hi. ") == []
    assert segmenter.push("How are you doing today? ") != []


def test_flush_returns_nothing_when_empty() -> None:
    assert SpeechSegmenter().flush() is None


# ── Wake words ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("said", "detected"),
    [
        ("Jarvis", True),
        ("jarvis what is on today", True),
        ("Hey Jarvis, remind me later", True),
        ("Jervis are you there", True),  # one substitution: a recogniser slip
        ("Harvis are you there", True),  # one substitution
        ("Arvis are you there", True),  # a dropped leading consonant
        ("Travis, what's next", False),  # three edits away — a different name
        ("Charvis, hello", False),  # two edits: past the threshold
        ("I was telling Jarvis about it", False),  # a mention, not a summons
        ("nothing to see here", False),
        ("", False),
    ],
)
def test_wake_detection(said: str, detected: bool) -> None:
    assert WakeWordDetector().detect(said).detected is detected


def test_the_request_after_the_wake_word_is_kept() -> None:
    """ "Jarvis, what's on today" is one breath, not two turns."""
    result = WakeWordDetector().detect("Jarvis, what is on my calendar")
    assert result.remainder == "what is on my calendar"


def test_the_longest_wake_phrase_wins() -> None:
    result = WakeWordDetector(("jarvis", "hey jarvis")).detect("hey jarvis do the thing")
    assert result.matched == "hey jarvis"
    assert result.remainder == "do the thing"


def test_two_substitutions_are_a_different_word() -> None:
    assert WakeWordDetector().detect("harvest the crops").detected is False


# ── The session ───────────────────────────────────────────────────────────────


async def _drain(session, *, until: str, timeout: float = 5.0) -> list:
    """Collect events until one of ``until`` type arrives."""
    seen: list = []
    events = session.events()
    async with asyncio.timeout(timeout):
        async for event in events:
            seen.append(event)
            if event.type == until:
                return seen
    return seen


async def test_a_turn_runs_through_the_expected_states(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Yes. That is done."))
    session = system.voice_session()

    await session.hear("what is my next meeting")
    events = await _drain(session, until="done")
    states = [e.data["state"] for e in events if e.type == "state"]

    assert states[:2] == ["thinking", "speaking"]
    assert session.state is VoiceState.LISTENING
    await session.close()


async def test_speech_begins_before_generation_finishes(settings, clock) -> None:
    """Latency is the product here: the first sentence must not wait."""
    system = _system(settings, clock, SlowProvider("First sentence here. " + "word " * 40))
    session = system.voice_session()

    await session.hear("tell me something")
    first_speech = None
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                first_speech = event
                break

    assert first_speech is not None
    provider = next(iter(system.router.providers.values()))
    assert provider.completed is False, "audio should start before generation ends"
    await session.close()


async def test_interrupting_cancels_generation_not_just_playback(settings, clock) -> None:
    """The property that matters: the model stops too, not only the speaker."""
    provider = SlowProvider("This is a long answer that will be cut off partway through. " * 4)
    system = _system(settings, clock, provider)
    session = system.voice_session()

    await session.hear("tell me a long story")
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                break

    await session.interrupt()
    await asyncio.sleep(0.15)

    assert provider.completed is False, "generation must be cancelled, not left running"
    assert session.state is VoiceState.LISTENING
    await session.close()


async def test_history_records_what_was_heard_not_what_was_generated(settings, clock) -> None:
    """Otherwise the next turn reasons about a conversation that never happened."""
    provider = SlowProvider("Sentence one is done. " + "and more words follow " * 20)
    system = _system(settings, clock, provider)
    session = system.voice_session()

    await session.hear("say something long")
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                break
    await session.interrupt()

    turn = session.turns[-1]
    assert turn.interrupted is True
    assert turn.spoken
    assert len(turn.spoken) < len(turn.generated), "the user heard less than was produced"
    assert turn.truncated is True
    await session.close()


async def test_an_interrupted_turn_is_replayed_as_interrupted(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("A long answer that gets cut off here. " * 6))
    session = system.voice_session()

    await session.hear("first question")
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                break
    await session.interrupt()

    # Reaching past the public surface on purpose: replayed history is the
    # contract under test, and nothing else exposes it.
    history = session._history()
    assistant = [m for m in history if m.role is Role.ASSISTANT]
    assert assistant and assistant[-1].content.endswith("[interrupted here]")
    await session.close()


async def test_speaking_while_jarvis_speaks_interrupts_it(settings, clock) -> None:
    """Barge-in as it actually happens: a partial transcript arrives mid-reply."""
    provider = SlowProvider("I will keep talking for quite a while now. " * 5)
    system = _system(settings, clock, provider)
    session = system.voice_session()

    await session.hear("start talking")
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                break

    # A partial is a signal someone is talking — enough to stop, never to answer.
    await session.hear("actually", final=False)
    await asyncio.sleep(0.1)

    assert provider.completed is False
    assert session.turns[-1].interrupted is True
    await session.close()


async def test_a_partial_transcript_is_never_answered(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Answer."))
    session = system.voice_session()

    await session.hear("what is the", final=False)
    await asyncio.sleep(0.1)

    assert session.state is VoiceState.IDLE
    assert session.turns == []
    await session.close()


async def test_a_new_question_interrupts_and_is_answered(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Talking at length about something. " * 4))
    session = system.voice_session()

    await session.hear("first question")
    async with asyncio.timeout(5):
        async for event in session.events():
            if event.type == "speech":
                break

    await session.hear("no, different question")
    await asyncio.sleep(0.15)

    assert session.turns[0].interrupted is True
    assert session.turns[0].user == "first question"
    await session.close()


async def test_wake_word_gating(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Sure."))
    session = system.voice_session(require_wake_word=True)

    assert session.state is VoiceState.WAITING_FOR_WAKE

    await session.hear("what is the weather")  # no wake word
    await asyncio.sleep(0.05)
    assert session.turns == []
    assert session.state is VoiceState.WAITING_FOR_WAKE

    await session.hear("jarvis")
    await asyncio.sleep(0.05)
    assert session.state is VoiceState.LISTENING
    await session.close()


async def test_a_wake_word_with_a_request_answers_immediately(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Two meetings."))
    session = system.voice_session(require_wake_word=True)

    await session.hear("jarvis what is on my calendar")
    await _drain(session, until="done")

    assert session.turns[-1].user == "what is on my calendar"
    await session.close()


async def test_session_events_stop_after_close(settings, clock) -> None:
    system = _system(settings, clock, SlowProvider("Done."))
    session = system.voice_session()
    await session.close()

    assert session.state is VoiceState.ENDED
    collected = [event async for event in session.events()]
    assert all(e.type == "state" for e in collected)


# ── Offline adapters ──────────────────────────────────────────────────────────


async def test_the_scripted_transcriber_emits_partials_then_a_final() -> None:
    transcriber = ScriptedTranscriber()
    await transcriber.say("hello there friend")
    await transcriber.close()

    segments = [segment async for segment in transcriber.stream()]
    assert [s.final for s in segments] == [False, False, True]
    assert segments[-1].text == "hello there friend"


async def test_the_silent_speaker_frames_its_output_without_losing_text() -> None:
    chunks = [chunk async for chunk in SilentSpeaker().synthesise("a" * 100)]
    assert chunks[-1].done is True
    assert "".join(c.text for c in chunks[:-1]) == "a" * 100


async def test_a_realtime_speaker_plays_at_speaking_pace() -> None:
    """Pacing is not cosmetic: an instant speaker cannot be interrupted."""
    speaker = SilentSpeaker(realtime=True)
    started = time.monotonic()
    async for _ in speaker.synthesise("a" * 56):
        pass
    elapsed = time.monotonic() - started

    # 56 chars at ~14 chars/second, allowing for scheduler slop.
    assert elapsed >= 56 / SilentSpeaker.CHARS_PER_SECOND * 0.8


def test_a_served_session_speaks_in_realtime_by_default() -> None:
    """The default deployment must be interruptible by a human, not just by a
    test that drives the session directly."""
    jarvis = container.build(Settings(environment="test"), providers=[EchoProvider()])
    speaker = jarvis.speaker
    assert isinstance(speaker, SilentSpeaker)
    assert speaker.realtime is True


# ── Hosted adapters ───────────────────────────────────────────────────────────


async def test_hosted_transcription_returns_the_recognised_text() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"text": "  book a table  "})
    )
    transcriber = HostedTranscriber("sk-test", client=httpx.AsyncClient(transport=transport))

    segment = await transcriber.transcribe(b"audio")
    assert segment.text == "book a table"
    assert segment.final is True


async def test_a_transcription_failure_is_an_empty_turn_not_a_crash() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="nope"))
    transcriber = HostedTranscriber("sk-test", client=httpx.AsyncClient(transport=transport))

    segment = await transcriber.transcribe(b"audio")
    assert segment.text == ""
    assert segment.confidence == 0.0


async def test_hosted_synthesis_streams_audio_frames() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"\x01\x02" * 10_000)
    )
    speaker = HostedSpeaker("sk-test", client=httpx.AsyncClient(transport=transport))

    chunks = [chunk async for chunk in speaker.synthesise("hello")]
    assert len(chunks) > 1
    assert chunks[-1].done is True
    # Only the first frame carries the text: a byte range of mp3 is not a slice
    # of the input string, and pretending otherwise would corrupt the record.
    assert chunks[0].text == "hello"
    assert chunks[1].text == ""


async def test_a_synthesis_failure_degrades_to_no_audio() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable"))
    speaker = HostedSpeaker("sk-test", client=httpx.AsyncClient(transport=transport))

    chunks = [chunk async for chunk in speaker.synthesise("hello")]
    assert chunks == [chunks[-1]]
    assert chunks[-1].done is True


def test_adapters_report_availability_from_configuration() -> None:
    assert HostedSpeaker(None).is_available() is False
    assert HostedSpeaker("sk-test").is_available() is True
    assert HostedTranscriber(None).is_available() is False
