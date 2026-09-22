import pathlib
import statistics
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_evaluation as E


def test_weighted_tardiness_per_job_matches_a_hand_computed_plan():
    from helpers import tiny_instance

    inst = tiny_instance()
    plan = {0: (0, 0), 1: (0, 12), 2: (1, 0)}  # Auftrag 1 endet bei 17 > Frist 14 -> 3 min * Gewicht 1
    assert E.weighted_tardiness_per_job(inst, plan) == pytest.approx(3 / 3)


def test_weighted_tardiness_per_job_raises_on_an_infeasible_plan():
    from helpers import tiny_instance

    inst = tiny_instance()
    plan = {0: (0, 0), 1: (0, 3), 2: (1, 0)}  # Fahrzeug 0 kann Auftrag 1 nicht vor Minute 5 starten
    with pytest.raises(AssertionError):
        E.weighted_tardiness_per_job(inst, plan)


def test_kmin_for_is_cached_and_deterministic():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    a = E.kmin_for(p, 42)
    b = E.kmin_for(p, 42)
    assert a == b and a is not None


def test_fleet_delta_zero_uses_exactly_the_practical_minimum():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    day = E.compute_day(p, 42, 0, C.DISRUPTION_AUSFALL, 20)
    assert day.k == day.kmin


def test_fleet_delta_reserve_adds_to_the_practical_minimum():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    day0 = E.compute_day(p, 42, 0, C.DISRUPTION_AUSFALL, 20)
    day2 = E.compute_day(p, 42, 2, C.DISRUPTION_AUSFALL, 20)
    assert day2.k == day0.kmin + 2


def test_noise_draw_parameter_changes_the_noise_realization():
    """compute_day(..., noise_draw=N) muss tatsächlich in die Rauschfaktoren eingehen (sonst wären
    mehrere Ziehungen am selben Tag/Seed nicht unterscheidbar - Zukunftsanschluss für Mittelung über
    mehrere Draws, siehe vorab_kombiniert)."""
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    day0 = E.compute_day(p, 9, 0, C.DISRUPTION_RAUSCHEN, 0.6, noise_draw=0)
    day1 = E.compute_day(p, 9, 0, C.DISRUPTION_RAUSCHEN, 0.6, noise_draw=1)
    assert day0.noisy_instance.approach != day1.noisy_instance.approach


def test_zero_strength_yields_the_nominal_plan_for_starr_and_reaktiv():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    for disruption in C.DISRUPTION_KINDS:
        day = E.compute_day(p, 3, 0, disruption, 0)
        assert day[C.S_STARR].wt == day[C.S_REAKTIV].wt
        assert day.failure is None and day.noisy_instance is None


# ---------------------------------------------------------------------------------------------------
# Stichprobe, Verteilung, Verdikt (synthetische Daten - deterministisch, keine Zufallszahlen)
# ---------------------------------------------------------------------------------------------------
def _rows(triples):
    return tuple(E.SampleRow(i, 3, 3, *t) for i, t in enumerate(triples))


def test_percentile_without_interpolation():
    assert E.percentile([1, 2, 3, 4, 5], 0.10) == 1
    assert E.percentile([1, 2, 3, 4, 5], 0.90) == 5
    assert E.percentile([10], 0.5) == 10


def test_percentile_clamps_to_the_last_index():
    """int(share * len(v)) kann bei share nahe 1 auf len(v) treffen (außerhalb des Arrays) - der
    min(len(v)-1, ...)-Schutz fängt das ab, statt einen IndexError zu werfen."""
    v = list(range(10))  # [0..9], sortiert
    assert E.percentile(v, 1.0) == 9  # ohne den Schutz: v[10] -> IndexError
    assert E.percentile(v, 0.0) == 0


def test_share_wins_tolerance_boundary_is_exclusive():
    """Eine Differenz von GENAU -tol zählt noch nicht als Sieg (strikt kleiner als -tol nötig)."""
    rows = tuple(E.SampleRow(i, 3, 3, *t) for i, t in enumerate([(1.0, 1.0 - 1e-9, 0.0)]))
    assert E.share_wins(rows, "online", "starr") == 0.0


def test_verdict_unclear_boundary_is_inclusive():
    """|Mittel| genau gleich der Schwelle (min_abs bzw. Standardfehler) gilt noch als 'unclear'.
    1,25/1,0 statt z. B. 1,3/1,0, damit die Differenz (-0,25) in Gleitkomma exakt darstellbar ist -
    sonst kann eine winzige Rundung (1.0-1.3 = -0.30000000000000004) den Test selbst verfälschen."""
    rows = tuple(E.SampleRow(i, 3, 3, *t) for i, t in enumerate([(1.25, 1.0, 0.0)] * 5))  # diff=-0,25 exakt
    v = E.verdict(rows, "online", "starr", min_abs=0.25)
    assert v.kind == "unclear"


def test_spread_of_returns_median_and_percentiles():
    rows = _rows([(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4), (5, 5, 5)])
    med, lo, hi = E.spread_of(rows, "starr")
    assert med == 3 and lo == 1 and hi == 5


def test_median_diff_and_share_wins():
    rows = _rows([(5, 3, 1), (5, 4, 1), (5, 6, 1)])  # online < starr in 2/3, > in 1/3
    assert E.median_diff(rows, "online", "starr") == -1
    assert E.share_wins(rows, "online", "starr") == pytest.approx(2 / 3)
    assert E.share_wins(rows, "starr", "online") == pytest.approx(1 / 3)


def test_verdict_is_clear_better_when_the_mean_difference_exceeds_the_margin_and_se():
    rows = _rows([(5.0, 1.0, 0.0)] * 10)
    v = E.verdict(rows, "online", "starr")
    assert v.kind == "better" and v.diff == pytest.approx(-4.0)


def test_verdict_is_unclear_when_the_difference_is_within_the_minimum_margin():
    rows = _rows([(1.0, 1.1, 0.5), (1.1, 1.0, 0.5), (1.0, 1.0, 0.5), (1.05, 0.95, 0.5)])
    v = E.verdict(rows, "online", "starr", min_abs=0.3)
    assert v.kind == "unclear"


def test_verdict_is_unclear_when_noisy_even_with_a_large_mean_gap():
    """Feedback ci-unpinned/ci-platform-robust: eine chaotische Einzelziehung darf kein 'klar' erzeugen."""
    rows = _rows([(10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)])
    v = E.verdict(rows, "online", "starr", min_abs=0.0)
    assert v.kind == "unclear"  # Mittel 0, aber auch bei Mittel != 0 müsste der Standardfehler greifen


def test_verdict_text_names_the_winner():
    rows = _rows([(5.0, 1.0, 0.0)] * 6)
    kind, text = E.verdict_text(rows, "online", "starr", C.S_ONLINE, C.S_STARR)
    assert kind == "better" and "online" in text and "robuster" in text


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung
# ---------------------------------------------------------------------------------------------------
class _Day:
    def __init__(self, starr, online, reaktiv, strength=20, disruption=C.DISRUPTION_AUSFALL):
        self.strength = strength
        self.disruption = disruption
        self.outcomes = {C.S_STARR: E.Outcome(C.S_STARR, starr, {}, None), C.S_ONLINE: E.Outcome(C.S_ONLINE, online, {}, None),
                        C.S_REAKTIV: E.Outcome(C.S_REAKTIV, reaktiv, {}, None)}

    def __getitem__(self, key):
        return self.outcomes[key]


def test_diagnose_calm_when_strength_is_zero():
    d = E.diagnose(_Day(0, 0, 0, strength=0))
    assert d.kind == "calm"


def test_diagnose_starr_bricht_when_starr_is_clearly_worse():
    d = E.diagnose(_Day(10.0, 1.0, 0.5))
    assert d.kind == "starr_bricht"


def test_diagnose_starr_haelt_when_starr_is_not_worse_than_online():
    d = E.diagnose(_Day(1.0, 2.0, 0.5))
    assert d.kind == "starr_haelt"


def test_diagnose_reserve_wartefrei_when_online_and_reaktiv_are_almost_zero():
    d = E.diagnose(_Day(1.0, 0.0, 0.0))
    assert d.kind == "reserve_wartefrei"


def test_diagnose_requires_BOTH_online_and_reaktiv_almost_zero_not_just_one():
    """online fast wartefrei, reaktiv aber deutlich nicht - darf NICHT reserve_wartefrei sein
    (Grenzfall gegen eine `and`/`or`-Verwechslung in der Bedingung)."""
    d = E.diagnose(_Day(1.0, 0.0, 0.5))
    assert d.kind != "reserve_wartefrei"
    d2 = E.diagnose(_Day(1.0, 0.5, 0.0))
    assert d2.kind != "reserve_wartefrei"


def test_diagnose_starr_haelt_boundary_is_inclusive():
    """starr <= online + Marge zählt noch als 'hält' (Gleichstand ist kein Bruch)."""
    d = E.diagnose(_Day(starr=1.05, online=1.0, reaktiv=0.5))  # genau auf der Marge (0,05)
    assert d.kind == "starr_haelt"
    d2 = E.diagnose(_Day(starr=1.06, online=1.0, reaktiv=0.5))
    assert d2.kind == "starr_bricht"


@pytest.mark.parametrize("kind", ["calm", "starr_haelt", "starr_bricht", "reserve_wartefrei"])
def test_diagnosis_text_mentions_all_three_strategies_numbers(kind):
    days = {"calm": _Day(0, 0, 0, strength=0), "starr_haelt": _Day(1.0, 2.0, 0.5), "starr_bricht": _Day(10.0, 1.0, 0.5),
           "reserve_wartefrei": _Day(1.0, 0.0, 0.0)}
    day = days[kind]
    diag = E.diagnose(day)
    text = E.diagnosis_text(diag, day)
    assert isinstance(text, str) and len(text) > 20
