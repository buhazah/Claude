"""The rule of three, and where it honestly cannot reach."""

from __future__ import annotations

from ops import patterns


def test_tokens_drop_stopwords_but_never_everything():
    assert patterns.tokens("I don't know what's working") == {"know", "working"}
    # A phrase that is nothing but stopwords still has to compare as something.
    assert patterns.tokens("what is it") == {"what", "is", "it"}


def test_similarity_matches_the_same_claim_phrased_differently():
    assert patterns.similarity("I don't know what's working", "no idea what is working") >= 0.5


def test_filler_words_do_not_break_a_match():
    """Regression: this is the case a live smoke test caught and Jaccard failed.

    Three clients said the same thing with different padding and the tool
    reported no finding, because a longer statement was penalised for the extra
    word rather than credited for containing the claim.
    """
    claim = "I don't know what's working"
    assert patterns.similarity(claim, "no idea what is working honestly") >= 0.5
    assert patterns.similarity(claim, "we genuinely don't know what's working") >= 0.5


def test_one_word_statements_never_match():
    # Containment would score a bare "working" at 1.0 against anything.
    assert patterns.similarity("working", "I don't know what's working") == 0.0


def test_similarity_uses_prefixes_so_work_and_working_agree():
    assert patterns.similarity("the creative stopped working", "creative work has stalled") > 0


def test_similarity_does_not_join_unrelated_claims():
    assert patterns.similarity("I'm flying blind", "your fees are too high") == 0.0


def test_short_words_never_prefix_match():
    # "we" must not match "were" — that is how everything collapses into one cluster.
    assert patterns.similarity("we", "were") == 0.0


def test_three_distinct_clients_makes_a_finding():
    """The exact three statements the smoke test used, which must now group."""
    rows = [
        (1, 10, "pain", "I don't know what's working"),
        (2, 11, "pain", "no idea what is working honestly"),
        (3, 12, "pain", "we genuinely don't know what's working"),
    ]
    found = patterns.findings(patterns.cluster(rows))
    assert len(found) == 1
    assert found[0].client_count == 3


def test_one_client_repeating_itself_is_not_a_finding():
    rows = [
        (1, 10, "pain", "I don't know what's working"),
        (2, 10, "pain", "no idea what is working"),
        (3, 10, "pain", "I don't know what's working at all"),
    ]
    assert patterns.findings(patterns.cluster(rows)) == []


def test_merging_is_preferred_over_splitting_and_stays_inspectable():
    """Two claims sharing one word of two do merge — accepted, by design.

    Containment biases toward merging. The cost is visible: the finding lists
    both statements, so a human dismisses it in a second. The alternative bias
    hides real patterns, and nothing surfaces those.
    """
    assert patterns.similarity("creative is stale", "creative is expensive") == 0.5
    cluster = patterns.cluster(
        [(1, 10, "pain", "creative is stale"), (2, 11, "pain", "creative is expensive")]
    )[0]
    assert [text for _, _, text in cluster.members] == [
        "creative is stale",
        "creative is expensive",
    ]


def test_kinds_never_merge():
    rows = [
        (1, 10, "pain", "the reporting is opaque"),
        (2, 11, "objection", "the reporting is opaque"),
        (3, 12, "pain", "reporting is totally opaque"),
    ]
    clusters = patterns.cluster(rows)
    kinds = {c.kind for c in clusters}
    assert kinds == {"pain", "objection"}
    assert patterns.findings(clusters) == []


def test_clusters_are_ordered_by_client_count():
    rows = [
        (1, 10, "pain", "creative is stale"),
        (2, 11, "pain", "our creative feels stale"),
        (3, 12, "pain", "stale creative everywhere"),
        (4, 13, "pain", "attribution is broken"),
    ]
    clusters = patterns.cluster(rows)
    assert clusters[0].client_count == 3


def test_label_is_the_shortest_phrasing():
    rows = [
        (1, 10, "pain", "we genuinely have no idea at all what is working for us"),
        (2, 11, "pain", "no idea what is working"),
    ]
    assert patterns.cluster(rows)[0].label == "no idea what is working"


def test_clustering_is_stable_regardless_of_input_order():
    rows = [
        (3, 12, "pain", "stale creative everywhere"),
        (1, 10, "pain", "creative is stale"),
        (2, 11, "pain", "our creative feels stale"),
    ]
    forward = patterns.cluster(rows)
    backward = patterns.cluster(list(reversed(rows)))
    assert [c.label for c in forward] == [c.label for c in backward]


def test_documented_limitation_holds():
    """Two phrasings with no shared words do not join, and that is by design.

    If this ever starts passing, the threshold has been lowered too far and
    unrelated claims will be merging silently.
    """
    assert patterns.similarity("I'm flying blind", "I don't know what's working") == 0.0
