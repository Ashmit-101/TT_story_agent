from ttagent.script.filters import ai_score, banned_hits, clean_for_tts, split_sentences

HUMAN = (
    "The baby monitor picked up a second voice at 3:12. Not mine. Not my wife's. "
    "I checked the crib first, because that's what you do. Empty except for Max, asleep, one fist in his mouth. "
    "Then I heard it again, a woman humming the song my mother used to sing. "
    "My mother died in 2009. I turned the monitor off and sat on the stairs until it got light."
)
AI = (
    "Buckle up, because what happened next will send shivers down your spine. "
    "It was a dark and stormy night, and I was walking home. It was a quiet street, and I felt a sense of dread. "
    "It was a long walk, and I couldn't help but feel watched. It was a strange feeling, and it was growing. "
    "It was then that I realized the true lesson here. Little did I know, this was a testament to fear. "
    "At the end of the day, follow for more!"
)


def test_human_scores_lower_than_ai():
    assert ai_score(HUMAN).score < 0.3
    assert ai_score(AI).score > 0.6


def test_banned_hits_includes_channel_extras():
    assert "chilling" in banned_hits("A chilling sound.", ["chilling"])
    assert banned_hits("Plain words only.") == []


def test_clean_for_tts_strips_markup():
    out = clean_for_tts("Hook: **It started** [pause] at noon — really (beat).")
    assert "[" not in out and "*" not in out and "—" not in out and "Hook" not in out


def test_split_sentences():
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]
