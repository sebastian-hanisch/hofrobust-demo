"""Regler-Spezifikation, Permalink, Presets und Seed-Knopf (Standardmuster des OR-Demo-Portfolios,
siehe blz_presets.py/gate_presets.py)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import hrb_constants as C


def _int_text(value):
    return str(int(value))


def _fleet_delta(raw):
    value = int(round(float(raw)))
    if value not in (0, 1, 2):
        raise ValueError(raw)
    return value


def _disruption(raw):
    if raw not in C.DISRUPTION_KINDS:
        raise ValueError(raw)
    return raw


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    step: Optional[int] = None
    encoder: Callable = _int_text


SETTING_SPECS = {
    "n_jobs_slider": SettingSpec("nj", int, C.N_JOBS_DEFAULT, *C.N_JOBS_RANGE, 1),
    "fleet_delta_radio": SettingSpec("fd", _fleet_delta, C.FLEET_DELTA_DEFAULT, encoder=str),
    "disruption_radio": SettingSpec("st", _disruption, C.DISRUPTION_DEFAULT, encoder=str),
    "fail_duration_slider": SettingSpec("fD", int, C.FAIL_DURATION_DEFAULT, *C.FAIL_DURATION_RANGE, C.FAIL_DURATION_STEP),
    "noise_sigma_slider": SettingSpec("ns", int, C.NOISE_SIGMA_DEFAULT, *C.NOISE_SIGMA_RANGE, C.NOISE_SIGMA_STEP),
    "buffer_slider": SettingSpec("bf", int, C.BUFFER_DEFAULT, *C.BUFFER_RANGE, 1),
    "yard_length_slider": SettingSpec("yl", int, C.YARD_LENGTH_DEFAULT, *C.YARD_LENGTH_RANGE, 1),
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE, 1),
}

PRESET_STATE_KEYS = {
    "n_jobs": "n_jobs_slider", "fleet_delta": "fleet_delta_radio", "disruption": "disruption_radio",
    "fail_duration": "fail_duration_slider", "noise_sigma": "noise_sigma_slider", "buffer": "buffer_slider",
    "yard_length": "yard_length_slider", "seed": "seed_input",
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def parse_setting(spec, raw):
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.step > 1 and spec.lo is not None:
        value = spec.lo + round((value - spec.lo) / spec.step) * spec.step
        value = min(spec.hi, value)
    return value


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = parse_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = SETTING_SPECS[state_key].encoder(value)
    except Exception:
        pass


def apply_preset(name):
    for field, state_key in PRESET_STATE_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][field]


def randomize_seed():
    st.session_state["seed_input"] = random.randint(*C.SEED_RANGE)
