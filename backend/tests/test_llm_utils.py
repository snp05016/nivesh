from services.llm_utils import contains_devanagari


def test_contains_devanagari_detects_hindi_text():
    assert contains_devanagari("प्रातःकालीन सारांश")


def test_contains_devanagari_allows_english_text():
    assert not contains_devanagari("Morning brief: market data loaded.")
