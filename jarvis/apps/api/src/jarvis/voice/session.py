"""The voice session.

One conversation, driven by a state machine, whose defining behaviour is
interruption.

**Barge-in cancels two things, not one.** Stopping playback alone leaves the
model generating into a void — burning tokens on words nobody will hear, and
finishing after the user has already asked something else. So an interruption
cancels the generation task *and* the speech task, together.

**What is remembered is what was heard.** History records the spoken prefix,
not the generated whole, and marks the turn as interrupted. Anything else means
the next turn reasons about a conversation the user did not have.

**Answers are short by construction.** The voice agent's spec caps output, and
this session speaks sentence by sentence so the reply starts immediately rather
than after the model finishes.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import structlog

from jarvis.agents.orchestrator import Orchestrator
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentRuntime
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.llm.base import Message, Role
from jarvis.voice.models import Turn, VoiceEvent, VoiceState
from jarvis.voice.ports import Speaker
from jarvis.voice.segment import SpeechSegmenter
from jarvis.voice.wake import WakeWordDetector

log = structlog.get_logger(__name__)

MAX_HISTORY_TURNS = 12


class VoiceSession:
    """A single voice conversation."""

    def __init__(
        self,
        *,
        orchestrator: Orchestrator,
        runtime: AgentRuntime,
        agents: AgentRegistry,
        speaker: Speaker,
        bus: EventBus,
        clock: Clock = SYSTEM_CLOCK,
        agent_id: str = "voice",
        require_wake_word: bool = False,
        wake: WakeWordDetector | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._runtime = runtime
        self._agents = agents
        self._speaker = speaker
        self._bus = bus
        self._clock = clock
        self._agent_id = agent_id
        self._wake = wake or WakeWordDetector()
        self._require_wake_word = require_wake_word

        self.state = VoiceState.WAITING_FOR_WAKE if require_wake_word else VoiceState.IDLE
        self.turns: list[Turn] = []
        self._events: asyncio.Queue[VoiceEvent] = asyncio.Queue()
        self._work: asyncio.Task[None] | None = None
        self._current: Turn | None = None

    # ── Output ────────────────────────────────────────────────────────────────

    def _emit(self, event: VoiceEvent) -> None:
        self._events.put_nowait(event)

    def _set_state(self, state: VoiceState) -> None:
        self.state = state
        self._emit(VoiceEvent("state", data={"state": state.value}))
        self._bus.publish("voice.state", {"state": state.value})

    async def events(self) -> AsyncIterator[VoiceEvent]:
        while self.state is not VoiceState.ENDED or not self._events.empty():
            try:
                yield await asyncio.wait_for(self._events.get(), timeout=0.25)
            except TimeoutError:
                continue

    # ── Input ─────────────────────────────────────────────────────────────────

    async def hear(self, text: str, *, final: bool = True) -> None:
        """Feed in recognised speech."""
        if not final:
            # A partial is a signal that someone is talking — which is exactly
            # what barge-in needs — but never something to answer.
            self._emit(VoiceEvent("partial", text=text))
            if self.state in (VoiceState.THINKING, VoiceState.SPEAKING):
                await self.interrupt()
            return

        spoken = text.strip()
        if not spoken:
            return

        if self._require_wake_word and self.state is VoiceState.WAITING_FOR_WAKE:
            result = self._wake.detect(spoken)
            if not result.detected:
                return
            self._emit(VoiceEvent("wake", text=result.matched))
            self._bus.publish("voice.wake", {"matched": result.matched})
            # "Jarvis, what's on today" is one breath: if a request followed the
            # wake word, answer it rather than making the user repeat themselves.
            if not result.remainder:
                self._set_state(VoiceState.LISTENING)
                return
            spoken = result.remainder

        if self.state in (VoiceState.THINKING, VoiceState.SPEAKING):
            await self.interrupt()

        self._emit(VoiceEvent("transcript", text=spoken))
        self._work = asyncio.create_task(self._respond(spoken))

    async def interrupt(self) -> None:
        """Stop speaking and stop generating. Both, or neither is useful."""
        if self._work is None or self._work.done():
            return

        self._work.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._work
        self._work = None

        if self._current is not None:
            self._current.interrupted = True
            self.turns.append(self._current)
            self._emit(
                VoiceEvent(
                    "interrupted",
                    text=self._current.spoken,
                    data={"truncated": self._current.truncated},
                )
            )
            self._bus.publish(
                "voice.interrupted",
                {"spoken_chars": len(self._current.spoken), "truncated": self._current.truncated},
            )
            self._current = None

        self._set_state(
            VoiceState.WAITING_FOR_WAKE if self._require_wake_word else VoiceState.LISTENING
        )

    # ── The turn ──────────────────────────────────────────────────────────────

    def _history(self) -> list[Message]:
        """Replay only what was actually heard."""
        messages: list[Message] = []
        for turn in self.turns[-MAX_HISTORY_TURNS:]:
            messages.append(Message(role=Role.USER, content=turn.user))
            if turn.spoken:
                content = turn.spoken
                if turn.truncated:
                    # Tell the model it was cut off, so it does not later claim
                    # to have said something the user never heard.
                    content += " [interrupted here]"
                messages.append(Message(role=Role.ASSISTANT, content=content))
        return messages

    async def _respond(self, request: str) -> None:
        turn = Turn(user=request)
        self._current = turn
        segmenter = SpeechSegmenter()
        spec = self._agents.get(self._agent_id)

        try:
            self._set_state(VoiceState.THINKING)
            speaking = False

            async for delta in self._runtime.stream(
                spec, request, history=self._history(), remember=False
            ):
                if delta.type == "error":
                    self._emit(VoiceEvent("error", text=delta.text))
                    return
                if delta.type != "token":
                    continue

                turn.generated += delta.text
                self._emit(VoiceEvent("token", text=delta.text))

                for unit in segmenter.push(delta.text):
                    if not speaking:
                        speaking = True
                        self._set_state(VoiceState.SPEAKING)
                    await self._speak(unit, turn)

            if tail := segmenter.flush():
                if not speaking:
                    self._set_state(VoiceState.SPEAKING)
                await self._speak(tail, turn)

            self.turns.append(turn)
            self._current = None
            self._emit(VoiceEvent("done", text=turn.spoken))
            self._set_state(
                VoiceState.WAITING_FOR_WAKE if self._require_wake_word else VoiceState.LISTENING
            )
        except asyncio.CancelledError:
            # Interruption. `interrupt` owns recording the turn, because it
            # knows this was deliberate rather than a failure.
            raise

    async def _speak(self, text: str, turn: Turn) -> None:
        """Play one unit, recording it only as it is actually played."""
        async for chunk in self._speaker.synthesise(text):
            if chunk.done:
                break
            # Appended per chunk, not per unit: if the user interrupts halfway
            # through a sentence, the turn records the half they heard.
            turn.spoken += chunk.text
            self._emit(VoiceEvent("speech", text=chunk.text, data={"bytes": len(chunk.audio)}))

    async def close(self) -> None:
        if self._work and not self._work.done():
            self._work.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._work
        self._set_state(VoiceState.ENDED)
