"""Abnahme der Presets an ECHTEN Daten: jede Geschichte trägt im Median/Mittel über 40 Tage (Seeds
9000-9039; die Abstimmung in tools/PRESET_SWEEP.md nutzt 60) UND an dem einen Tag, den das Preset
zeigt. Ohne Zeitlimit; geprüft werden Kennzahlen mit Abstand zur Schwelle."""

import concurrent.futures
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_evaluation as E
import hrb_stories as ST

POPULATION = range(9000, 9040)
NAMES = list(C.PRESETS)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["n_jobs"], p["buffer"], p["yard_length"])


def strength_of(name):
    p = C.PRESETS[name]
    return p["fail_duration"] if p["disruption"] == C.DISRUPTION_AUSFALL else p["noise_sigma"] / 100.0


def _row(args):
    name, seed = args
    p = C.PRESETS[name]
    r = E.day_scalars(params(name), seed, p["fleet_delta"], p["disruption"], strength_of(name))
    return E.SampleRow(seed, *r) if r is not None else None


@pytest.fixture(scope="module")
def populations():
    jobs = [(name, seed) for name in NAMES for seed in POPULATION]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        rows = list(pool.map(_row, jobs, chunksize=2))
    out = {n: [] for n in NAMES}
    for (n, _), r in zip(jobs, rows):
        if r is not None:
            out[n].append(r)
    return {n: tuple(v) for n, v in out.items()}


@pytest.fixture(scope="module")
def shown():
    return {n: _row((n, C.PRESETS[n]["seed"])) for n in NAMES}


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_over_the_population(name, populations):
    for ok, text in ST.criteria(name, populations[name]):
        assert ok, f"{name}: {text}"


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_at_the_week_the_preset_shows(name, shown):
    assert shown[name] is not None
    assert ST.holds(name, shown[name]), [t for ok, t in ST.criteria(name, (shown[name],)) if not ok]


def test_all_presets_share_one_seed_outside_the_populations_and_the_sample():
    seeds = {p["seed"] for p in C.PRESETS.values()}
    assert len(seeds) == 1
    seed = next(iter(seeds))
    assert seed not in POPULATION and not (C.SAMPLE_BASE <= seed < C.SAMPLE_BASE + C.SAMPLE_DAYS_DEFAULT)


@pytest.mark.parametrize("name", NAMES)
def test_the_shown_day_is_typical_for_every_key_measure(name, populations, shown):
    """Jede Kennzahl aus ST.TYPICAL des gezeigten Tages liegt zwischen dem 5. und 95. Perzentil der
    Grundgesamtheit (40 Tage)."""
    for field in ST.TYPICAL:
        vals = sorted(E.values(populations[name], field))
        lo, hi = vals[int(0.05 * len(vals))], vals[int(0.95 * len(vals)) - 1]
        v = getattr(shown[name], field)
        assert lo <= v <= hi, (name, field, v, (lo, hi))


def test_the_population_reproduces_the_measured_orders_of_magnitude(populations):
    """Ausfall am Minimum: starr klar zweistellig, online/reaktiv klein (tools/PRESET_SWEEP.md, 60
    Tage: Median starr 12,4 / online 1,2 / reaktiv 0,3); hier 40 Tage mit Abstand."""
    rows = populations["Ausfall am Minimum"]
    assert 6 < E.median_of(rows, "starr") < 25 and E.median_of(rows, "online") < 4 and E.median_of(rows, "reaktiv") < 2


def test_reserve_plus_one_makes_online_and_reactive_almost_waitfree(populations):
    for name in ("Reserve gegen Ausfall", "Reserve gegen Rauschen"):
        rows = populations[name]
        assert E.median_of(rows, "online") < 0.5 and E.median_of(rows, "reaktiv") < 0.3
