from __future__ import annotations

from core.fuzzy import best_match, fuzzy_score, is_subsequence, levenshtein, rank, similarity


def test_exact_and_prefix():
    assert fuzzy_score("discord", "Discord") == 1.0
    assert fuzzy_score("dis", "Discord") > 0.9
    assert fuzzy_score("code", "Visual Studio Code") >= 0.8


def test_substring_and_subsequence():
    assert fuzzy_score("studio", "Visual Studio Code") > 0.7
    assert fuzzy_score("vsc", "Visual Studio Code") > 0.4
    assert fuzzy_score("zzz", "Visual Studio Code") == 0.0


def test_typo_tolerance():
    assert fuzzy_score("discrod", "Discord", typo_tolerance=True) > 0.5
    assert fuzzy_score("discrod", "Discord", typo_tolerance=False) == 0.0
    assert fuzzy_score("calcualtor", "Calculator") > 0.5


def test_multiword_tokens():
    assert fuzzy_score("raspberry pi", "raspberry-pi-guide.pdf") > 0.7
    assert fuzzy_score("visual code", "Visual Studio Code") > 0.8


def test_distance_helpers():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("abc", "acb") == 1  # transposition
    assert similarity("abc", "abc") == 1.0
    assert is_subsequence("vsc", "visual studio code")
    assert not is_subsequence("csv", "visual studio code")


def test_rank_orders_and_limits():
    items = ["Discord", "Discordance", "Calculator", "Visual Studio Code"]
    ranked = rank("disc", items, lambda value: value, limit=2)
    assert len(ranked) == 2
    assert ranked[0][1] == "Discord"
    assert best_match("calc", items)[0] == "Calculator"


def test_empty_query_scores_zero():
    assert fuzzy_score("", "Discord") == 0.0
    assert fuzzy_score("   ", "Discord") == 0.0
