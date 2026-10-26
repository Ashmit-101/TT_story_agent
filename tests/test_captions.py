from ttagent.captions.align import Word, even_alignment, merge_script_with_timings
from ttagent.captions.ass import build_ass, group_words


def test_even_alignment_covers_duration():
    words = even_alignment("This is a short test sentence.", 6.0)
    assert words[0].start == 0 and abs(words[-1].end - 6.0) < 1e-6
    assert all(a.end <= b.start + 1e-9 for a, b in zip(words, words[1:]))


def test_merge_keeps_script_text_when_counts_match():
    timed = [Word("hello", 0, 1), Word("world", 1, 2)]
    assert [w.text for w in merge_script_with_timings("Hello, World.", timed)] == ["Hello,", "World."]
    assert merge_script_with_timings("one two three", timed) == timed


def test_group_breaks_on_punctuation():
    words = [Word(t, i, i + 1) for i, t in enumerate(["a", "b.", "c", "d", "e", "f"])]
    assert [len(g) for g in group_words(words)] == [2, 3, 1]


def test_ass_has_one_event_per_word_and_valid_header():
    words = even_alignment("Quiet houses make loud noises.", 4.0)
    ass = build_ass(words, 1080, 1920)
    assert "PlayResX: 1080" in ass and ass.count("Dialogue:") == 5
    assert "QUIET" in ass
