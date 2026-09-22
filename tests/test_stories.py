"""Künstliche Werte an den Schwellen von hrb_stories.criteria (keine echte Rechnung - siehe
test_preset_stories.py dafür). Jedes Kriterium ist ein Median-/Mittelwert-Vergleich, der auch für
ein Tupel der Länge 1 (der gezeigte Tag) sinnvoll bleibt - siehe hrb_stories-Docstring."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_evaluation as E
import hrb_stories as ST


def rows_of(triples):
    return tuple(E.SampleRow(i, 3, 3, *t) for i, t in enumerate(triples))


def all_ok(name, rows):
    return all(ok for ok, _ in ST.criteria(name, rows))


# ---------------------------------------------------------------------------------------------------
# Ausfall am Minimum: starr >= 6.0 (Median), starr-online >= 3.0, reaktiv <= 4.0, online >= reaktiv
# ---------------------------------------------------------------------------------------------------
def test_ausfall_am_minimum_holds_comfortably_above_threshold():
    rows = rows_of([(12.0, 1.0, 0.3)] * 5)
    assert all_ok("Ausfall am Minimum", rows)


def test_ausfall_am_minimum_holds_for_a_single_shown_day():
    assert ST.holds("Ausfall am Minimum", E.SampleRow(0, 3, 3, 12.0, 1.0, 0.3))


def test_ausfall_am_minimum_fails_when_starr_is_too_low():
    rows = rows_of([(5.9, 1.0, 0.3)] * 5)
    assert not all_ok("Ausfall am Minimum", rows)


def test_ausfall_am_minimum_fails_when_the_gap_to_online_is_too_small():
    rows = rows_of([(6.5, 4.0, 0.3)] * 5)
    assert not all_ok("Ausfall am Minimum", rows)


# ---------------------------------------------------------------------------------------------------
# Rauschen am Minimum: reaktiv reliably best, starr/online nah beieinander (kein verlässlicher Sieger)
# ---------------------------------------------------------------------------------------------------
def test_rauschen_am_minimum_holds_when_starr_and_online_are_close():
    rows = rows_of([(1.8, 1.7, 0.1)] * 5)
    assert all_ok("Rauschen am Minimum", rows)


def test_rauschen_am_minimum_holds_for_a_single_shown_day():
    assert ST.holds("Rauschen am Minimum", E.SampleRow(0, 3, 3, 1.8, 1.7, 0.1))


def test_rauschen_am_minimum_fails_when_online_is_far_ahead_of_starr():
    rows = rows_of([(2.0, 0.5, 0.1)] * 5)  # zu großer Abstand: kein "Münzwurf" mehr
    assert not all_ok("Rauschen am Minimum", rows)


def test_rauschen_am_minimum_fails_when_reaktiv_is_not_clearly_the_best():
    rows = rows_of([(2.0, 1.9, 1.85)] * 2)
    assert not all_ok("Rauschen am Minimum", rows)


# ---------------------------------------------------------------------------------------------------
# Leichter Ausfall: Mittelwert-Schwellen, online im Mittel schon vor starr
# ---------------------------------------------------------------------------------------------------
def test_leichter_ausfall_holds_with_the_expected_shape():
    rows = rows_of([(3.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)])
    assert all_ok("Leichter Ausfall", rows)


def test_leichter_ausfall_holds_for_a_single_shown_day():
    assert ST.holds("Leichter Ausfall", E.SampleRow(0, 3, 3, 1.5, 0.3, 0.0))


def test_leichter_ausfall_fails_when_online_is_not_ahead_of_starr():
    rows = rows_of([(1.5, 1.5, 0.0)] * 5)
    assert not all_ok("Leichter Ausfall", rows)


def test_leichter_ausfall_fails_when_starr_is_too_low():
    rows = rows_of([(0.5, 0.1, 0.0)] * 5)
    assert not all_ok("Leichter Ausfall", rows)


# ---------------------------------------------------------------------------------------------------
# Reserve gegen Ausfall / Reserve gegen Rauschen
# ---------------------------------------------------------------------------------------------------
def test_reserve_gegen_ausfall_holds_when_online_and_reaktiv_are_waitfree():
    rows = rows_of([(2.0, 0.0, 0.0)] * 5)
    assert all_ok("Reserve gegen Ausfall", rows)


def test_reserve_gegen_ausfall_fails_when_online_still_waits():
    rows = rows_of([(2.0, 0.5, 0.0)] * 5)
    assert not all_ok("Reserve gegen Ausfall", rows)


def test_reserve_gegen_rauschen_holds_when_starr_still_costs_something():
    rows = rows_of([(0.5, 0.0, 0.0)] * 5)
    assert all_ok("Reserve gegen Rauschen", rows)


def test_reserve_gegen_rauschen_fails_when_starr_is_also_waitfree():
    rows = rows_of([(0.05, 0.0, 0.0)] * 5)
    assert not all_ok("Reserve gegen Rauschen", rows)


# ---------------------------------------------------------------------------------------------------
# Sonstiges
# ---------------------------------------------------------------------------------------------------
def test_holds_checks_a_single_row_the_same_way_as_criteria():
    row = E.SampleRow(0, 3, 3, 12.0, 1.0, 0.3)
    assert ST.holds("Ausfall am Minimum", row)
    row_bad = E.SampleRow(0, 3, 3, 1.0, 1.0, 0.3)
    assert not ST.holds("Ausfall am Minimum", row_bad)


def test_unknown_preset_name_raises():
    import pytest

    with pytest.raises(KeyError):
        ST.criteria("Nicht vorhanden", rows_of([(1.0, 1.0, 1.0)]))


def test_share_helpers_are_documentation_only_and_match_share_wins():
    rows = rows_of([(5, 3, 1), (5, 4, 1), (5, 6, 1)])
    assert ST.share_online_wins(rows) == E.share_wins(rows, "online", "starr")
    assert ST.share_starr_wins(rows) == E.share_wins(rows, "starr", "online")
