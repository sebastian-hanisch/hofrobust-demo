import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
from hrb_presets import PRESET_STATE_KEYS, SETTING_SPECS, bounds, parse_setting


def test_every_setting_spec_has_a_preset_state_key_except_where_not_applicable():
    for field, state_key in PRESET_STATE_KEYS.items():
        assert state_key in SETTING_SPECS


def test_every_preset_uses_only_keys_covered_by_preset_state_keys():
    for name, values in C.PRESETS.items():
        assert set(values) == set(PRESET_STATE_KEYS), name


def test_bounds_matches_the_spec():
    lo, hi = bounds("n_jobs_slider")
    assert (lo, hi) == C.N_JOBS_RANGE


def test_parse_setting_clamps_to_bounds():
    spec = SETTING_SPECS["n_jobs_slider"]
    assert parse_setting(spec, "999") == C.N_JOBS_RANGE[1]
    assert parse_setting(spec, "-5") == C.N_JOBS_RANGE[0]


def test_parse_setting_snaps_to_the_step():
    spec = SETTING_SPECS["fail_duration_slider"]
    assert parse_setting(spec, "23") == 25  # Schritt 5, naechstgelegen
    assert parse_setting(spec, "22") == 20


def test_parse_setting_rejects_garbage():
    spec = SETTING_SPECS["n_jobs_slider"]
    assert parse_setting(spec, "abc") is None
    assert parse_setting(spec, "nan") is None
    assert parse_setting(spec, "inf") is None


def test_parse_setting_for_fleet_delta_only_accepts_zero_one_two():
    spec = SETTING_SPECS["fleet_delta_radio"]
    assert parse_setting(spec, "0") == 0
    assert parse_setting(spec, "1") == 1
    assert parse_setting(spec, "2") == 2  # der höchste gültige Wert - leicht zu vergessen
    assert parse_setting(spec, "3") is None
    assert parse_setting(spec, "abc") is None


def test_parse_setting_for_disruption_only_accepts_known_kinds():
    spec = SETTING_SPECS["disruption_radio"]
    assert parse_setting(spec, C.DISRUPTION_AUSFALL) == C.DISRUPTION_AUSFALL
    assert parse_setting(spec, "unbekannt") is None


def test_seed_default_is_within_its_own_bounds():
    lo, hi = C.SEED_RANGE
    assert lo <= C.SEED_DEFAULT <= hi


def test_all_presets_have_settings_within_their_widget_bounds():
    for name, values in C.PRESETS.items():
        for field, state_key in PRESET_STATE_KEYS.items():
            spec = SETTING_SPECS[state_key]
            value = values[field]
            if spec.lo is not None:
                assert spec.lo <= value <= spec.hi, (name, field, value)
