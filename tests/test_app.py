"""AppTest: Skelett und Footer, jedes Preset, Umschalter (mode-conditional ohne toten Regler),
Permalink, Knöpfe (Sieger-Tabelle, Kurven, Stichprobe, Cross-Check), PDF, Texte."""

import pathlib
import re

import pytest
from streamlit.testing.v1 import AppTest

import hrb_constants as C
from hrb_presets import SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = (
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Hof- und Yard-Management optimieren](https://sebastianhanisch.net/yard-management-optimierung.html)."
)


@pytest.fixture(autouse=True)
def clean_cache():
    import streamlit as st

    st.cache_data.clear()
    yield


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        if key.endswith("_input"):
            widget = at.number_input(key=key)
        elif key.endswith("_radio"):
            widget = at.radio(key=key)
        else:
            widget = at.slider(key=key)
        widget.set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at, label=None, key=None):
    next(b for b in at.button if (b.label == label if label else b.key == key)).click().run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value, m.delta) for m in at.metric[:4]]


def num(text):
    return float(re.match(r"[-+]?[\d.]+", text).group())


def message(at, needle):
    for group in (at.success, at.warning, at.info):
        for x in group:
            if needle in x.value:
                return x
    return None


def all_texts(at):
    return [x.value for group in (at.markdown, at.caption, at.success, at.info, at.warning) for x in group]


@pytest.fixture(scope="module")
def default_app():
    import streamlit as st

    st.cache_data.clear()
    return fresh()


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer(default_app):
    at = default_app
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]
    assert len(at.title) == 1 and "Robuste Hof-Disposition" in at.title[0].value
    assert any(v.value.startswith("## 🎯") for v in at.markdown)
    assert [s.value for s in at.subheader] == ["📐 Wer gewinnt am praktischen Minimum – und ab wann dreht sich das?"]
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – Verfahren im Vergleich", "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5
    assert all(b.help for b in at.button if b.label in C.PRESETS)


def test_sidebar_has_exactly_one_control_per_setting_and_no_dead_widgets(default_app):
    at = default_app
    labels = [s.label for s in at.sidebar.slider]
    assert "Ausfalldauer (min)" in labels and "Rauschstärke σ (%)" not in labels  # Default: Ausfall
    assert len(labels) == 4  # Aufträge, Ausfalldauer, Fristpuffer, Hoflänge (kein zweiter Störstärke-Regler)
    assert [r.label for r in at.sidebar.radio] == ["Flottenabstand zum praktischen Minimum", "Störungsart"]
    assert [n.label for n in at.sidebar.number_input] == ["Seed"]
    assert any(b.label == "🎲 Neuer Tag" for b in at.sidebar.button)


def test_switching_disruption_swaps_the_strength_slider_entirely():
    at = fresh()
    assert "Ausfalldauer (min)" in [s.label for s in at.sidebar.slider]
    at = at.sidebar.radio(key="disruption_radio").set_value(C.DISRUPTION_RAUSCHEN).run()
    labels = [s.label for s in at.sidebar.slider]
    assert "Rauschstärke σ (%)" in labels and "Ausfalldauer (min)" not in labels and len(labels) == 4


def test_main_metrics_are_2x2(default_app):
    m = main_metrics(default_app)
    assert [x[0] for x in m] == ["gew. Verspätung starr", "gew. Verspätung online", "gew. Verspätung reaktiv", "praktisches Minimum K"]
    assert all(x[1].endswith("min/Auftrag") or x[0] == "praktisches Minimum K" for x in m)


def test_no_dead_file_links_in_any_markdown(default_app):
    for text in all_texts(default_app):
        assert not re.search(r"\]\((?!https?://)", text), text
    math = "\n".join(m.value for m in default_app.expander[2].markdown)
    assert not re.search(r"\]\((?!https?://)", math)


def test_pdf_download_button_is_offered(default_app):
    buttons = default_app.get("download_button")
    assert len(buttons) == 1 and buttons[0].proto.label == "📄 Ergebnis als PDF herunterladen"


def test_texts_state_the_methods_and_the_limits(default_app):
    text = "\n".join(m.value for m in default_app.expander[1].markdown)
    for needle in ("starr", "online", "reaktiv", "praktische", "Ausfall", "Rauschen", "Münzwurf", "math.ceil",
                  "Leerfahrt", "yard-demo", "fahrzeugflotte-demo"):
        assert needle in text, needle
    math = "\n".join(m.value for m in default_app.expander[2].markdown)
    for needle in ("sequence_cost_from", "lceil", "hrb_fleet.py", "hrb_evaluation.py"):
        assert needle in math, needle


def test_charts_have_unique_keys(default_app):
    charts = default_app.get("plotly_chart")
    keys = [c.key for c in charts]
    assert len(keys) == len(set(keys)) and all(keys)
    assert len(charts) >= 3  # mindestens die drei Haupt-Gantts


# ---------------------------------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds(name):
    at = click(fresh(), name)
    p = C.PRESETS[name]
    assert at.slider(key="n_jobs_slider").value == p["n_jobs"]
    assert at.radio(key="fleet_delta_radio").value == p["fleet_delta"]
    assert at.radio(key="disruption_radio").value == p["disruption"]
    assert at.slider(key="buffer_slider").value == p["buffer"]
    assert at.slider(key="yard_length_slider").value == p["yard_length"]
    assert at.number_input(key="seed_input").value == p["seed"]
    if p["disruption"] == C.DISRUPTION_AUSFALL:
        assert at.slider(key="fail_duration_slider").value == p["fail_duration"]
    else:
        assert at.slider(key="noise_sigma_slider").value == p["noise_sigma"]
    assert len(at.metric) >= 4 and not at.exception


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(nj="99", fd="1", st="rauschen", ns="200", bf="200", yl="9999", seed="99999")
    assert at.slider(key="n_jobs_slider").value == C.N_JOBS_RANGE[1]
    assert at.radio(key="fleet_delta_radio").value == 1
    assert at.radio(key="disruption_radio").value == C.DISRUPTION_RAUSCHEN
    assert at.slider(key="noise_sigma_slider").value == C.NOISE_SIGMA_RANGE[1]
    assert at.slider(key="buffer_slider").value == C.BUFFER_RANGE[1]
    assert at.slider(key="yard_length_slider").value == C.YARD_LENGTH_RANGE[1]
    assert at.number_input(key="seed_input").value == C.SEED_RANGE[1]
    assert fresh(nj="abc", st="unbekannt").slider(key="n_jobs_slider").value == C.N_JOBS_DEFAULT


def test_permalink_roundtrip_reflects_settings():
    at = fresh(nj="20", fd="2", st="rauschen", ns="40", bf="20", yl="500", seed="11")
    values = {k: at.session_state[k] for k in SETTING_SPECS}
    assert values["n_jobs_slider"] == 20 and values["fleet_delta_radio"] == 2 and values["disruption_radio"] == C.DISRUPTION_RAUSCHEN
    assert values["noise_sigma_slider"] == 40 and values["buffer_slider"] == 20 and values["yard_length_slider"] == 500 and values["seed_input"] == 11
    for key, spec in SETTING_SPECS.items():
        got = at.query_params[spec.url_param]
        got = got[0] if isinstance(got, list) else got
        assert got == spec.encoder(values[key]), key


def test_new_day_button_changes_only_the_seed():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    click(at, "🎲 Neuer Tag")
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before
    assert 0 <= at.session_state["seed_input"] <= 9999


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung
# ---------------------------------------------------------------------------------------------------
def test_message_calm_when_strength_is_zero():
    at = set_and_run(fresh(), fail_duration_slider=0)
    assert message(at, "Keine Störung eingestellt") is not None


def test_message_is_one_of_the_known_kinds_for_extreme_settings():
    at = fresh(nj="12", fd="2", st="rauschen", ns="60")
    needles = ["Keine Störung eingestellt", "hält der Störung", "bricht unter der Störung", "macht online und reaktiv praktisch wartefrei"]
    assert any(message(at, n) is not None for n in needles)


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [("n_jobs_slider", 12), ("n_jobs_slider", 40), ("fail_duration_slider", 0),
                                       ("fail_duration_slider", 60), ("buffer_slider", 5), ("buffer_slider", 60),
                                       ("yard_length_slider", 200), ("yard_length_slider", 900), ("seed_input", 0),
                                       ("seed_input", 9999)])
def test_every_control_works_at_its_minimum_and_maximum(key, value):
    at = set_and_run(fresh(), **{key: value})
    assert at.session_state[key] == value and len(at.metric) >= 4 and not at.exception


def test_fleet_delta_at_every_step():
    for delta in (0, 1, 2):
        at = set_and_run(fresh(), fleet_delta_radio=delta)
        assert at.session_state["fleet_delta_radio"] == delta and not at.exception


# ---------------------------------------------------------------------------------------------------
# Knöpfe: Sieger-Tabelle, Kurven, Stichprobe, Cross-Check
# ---------------------------------------------------------------------------------------------------
def test_winner_table_button_computes_the_heatmap():
    at = fresh(nj="12")
    assert message(at, "Die Sieger-Tabelle ist für diese Einstellung noch nicht gerechnet") is not None
    at = click(at, key="winner_button")
    assert "winner_heatmap_chart" in [c.key for c in at.get("plotly_chart")]
    assert message(at, "Die Sieger-Tabelle ist für diese Einstellung noch nicht gerechnet") is None


def test_curve_button_computes_both_curves():
    at = fresh(nj="12")
    at = click(at, key="curve_button")
    keys = [c.key for c in at.get("plotly_chart")]
    assert "curve_ausfall_chart" in keys and "curve_rauschen_chart" in keys


def test_sample_button_computes_verdicts_and_charts():
    at = fresh(nj="12")
    at = click(at, key="sample_button")
    texts = all_texts(at)
    assert any("robuster als" in t or "Kein klarer Unterschied" in t for t in texts)
    keys = [c.key for c in at.get("plotly_chart")]
    assert "spread_chart" in keys and "distribution_chart" in keys


def test_sample_result_is_dropped_when_settings_change():
    at = fresh(nj="12")
    at = click(at, key="sample_button")
    assert "spread_chart" in [c.key for c in at.get("plotly_chart")]
    at = set_and_run(at, seed_input=77)
    # Stichprobe hängt nicht vom Seed ab -> bleibt erhalten
    assert "spread_chart" in [c.key for c in at.get("plotly_chart")]
    at = set_and_run(at, buffer_slider=40)
    assert "spread_chart" not in [c.key for c in at.get("plotly_chart")]


def test_cross_check_button_shows_cp_sat_results():
    at = click(fresh(nj="12"), key="cross_check_button")
    assert message(at, "CP-SAT bei K") is not None
