"""Wiederverwendbares Panel je Verfahren im Verfahrensvergleich (ein Tab je Strategie, dazu die
Tabs Mindestflotte und Vergleich)."""

import pandas as pd
import streamlit as st

import hrb_constants as C
import hrb_evaluation as E
import hrb_fleet as F
import hrb_visualization as V


def render_strategy_panel(prefix, day, key):
    """Beschreibung, Kennzahl (Delta gegen starr) und Gantt einer Strategie."""
    st.markdown(C.STRATEGY_DESCRIPTIONS[key])
    outcome = day[key]
    baseline = day[C.S_STARR]
    delta = None if key == C.S_STARR else outcome.wt - baseline.wt
    st.metric("gewichtete Verspätung je Auftrag", f"{outcome.wt:.2f} min", delta=None if delta is None else f"{delta:+.2f} min",
             delta_color="off" if delta is None else "inverse", help="Delta gegen starr (Referenz); weniger ist besser.")
    st.plotly_chart(V.gantt_figure(day, key, f"{C.STRATEGY_SHORT[key]}: Einsatzplan je Fahrzeug"), width="stretch", key=f"{prefix}_gantt")


def render_fleet_panel(prefix, day, base_instance, cross_check_result):
    """Praktisches Minimum, Matching-Untergrenze (mit Einschränkung) und CP-SAT-Cross-Check
    (nur bei Klick, `cross_check_result`: dict aus hrb_fleet.cross_check oder None)."""
    lb = F.matching_lower_bound(base_instance)
    st.markdown(
        f"Praktisches Minimum **K = {day.kmin}**: kleinste Flottengröße, bei der FIFO, Frist zuerst (EDD), ATC oder die "
        f"Vorausplanung 0 gewichtete Verspätung erreichen (Suche über k = 1, 2, ...). Zusatzinfo: die Matching-Untergrenze "
        f"liegt bei **{lb}** - eine notwendige, aber bei echten Zeitfenstern **nicht immer scharfe** Bedingung (bei 12 kleinen "
        f"Testinstanzen 6 exakt, 6 zu niedrig, nie zu hoch, siehe `tests/test_fleet.py`; anders als bei der Fahrzeugflotte-Demo, "
        f"wo feste Kran-Aufnahmezeiten den Beweis exakt machen)."
    )
    if cross_check_result is None:
        st.info("ℹ️ CP-SAT-Cross-Check noch nicht gerechnet: Knopf unten (nur auf Klick, ein Zeitlimit von "
               f"{C.EXACT_SOLVE_TIME_LIMIT_SECONDS} s je Instanz).")
    else:
        r = cross_check_result
        bew = "bewiesen optimal" if r["optimal_at_min"] else "beste gefundene Lösung (Zeitlimit erreicht)"
        st.success(f"✅ CP-SAT bei K = {r['kmin']}: gewichtete Verspätung {r['wt_at_min']} ({bew}).")
        if r["wt_below"] is not None:
            bew2 = "bewiesen optimal" if r["optimal_below"] else "beste gefundene Lösung"
            st.warning(f"⚠️ CP-SAT bei K-1 = {r['kmin'] - 1}: gewichtete Verspätung {r['wt_below']} ({bew2}) - "
                      "ein Fahrzeug zu wenig lässt sich nicht auf 0 drücken.")


def render_comparison(prefix, day):
    rows = [{"Strategie": C.STRATEGY_LABELS[k], "gew. Verspätung (min/Auftrag)": round(day[k].wt, 2),
            "Delta gegen starr": round(day[k].wt - day[C.S_STARR].wt, 2),
            "Delta gegen online": round(day[k].wt - day[C.S_ONLINE].wt, 2)} for k in C.STRATEGY_KEYS]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
