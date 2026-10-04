"""
Robuste Hof-Disposition + Flottengröße – interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Yard-Management-Linie: hält ein vorab berechneter Hof-Einsatzplan, wenn ein Fahrzeug ausfällt oder
die Fahrzeiten schwanken - und wie viele Fahrzeuge braucht der Hof dafür? Baut auf dem Fachmodell
von yard-demo auf (Aufträge, Fristen, Anfahrtszeiten, online-Regeln, Vorausplanung).

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import hrb_constants as C
import hrb_evaluation as E
import hrb_fleet as F
import hrb_ui_panel as UI
import hrb_visualization as V
from hrb_pdf_export import generate_hrb_pdf
from hrb_presets import (SETTING_SPECS, apply_preset, bounds, init_session_state_defaults, load_permalink_settings,
                         randomize_seed, sync_query_params)

st.set_page_config(page_title="Robuste Hof-Disposition - Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)


@st.cache_data(show_spinner=False, max_entries=64)
def _compute_day(key):
    n_jobs, buffer, yard_length, seed, fleet_delta, disruption, strength = key
    p = E.Params(n_jobs, buffer, yard_length)
    return E.compute_day(p, seed, fleet_delta, disruption, strength)


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_winner_table(key):
    n_jobs, buffer, yard_length, seed, fail_duration, noise_sigma = key
    p = E.Params(n_jobs, buffer, yard_length)
    return E.winner_table(p, seed, fail_duration, noise_sigma / 100.0)


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_curve(key):
    n_jobs, buffer, yard_length, seed, fleet_delta, disruption = key
    p = E.Params(n_jobs, buffer, yard_length)
    return E.strength_curve(p, seed, fleet_delta, disruption)


@st.cache_data(show_spinner=False, max_entries=200)
def _compute_sample_row(key):
    n_jobs, buffer, yard_length, seed, fleet_delta, disruption, strength = key
    p = E.Params(n_jobs, buffer, yard_length)
    r = E.day_scalars(p, seed, fleet_delta, disruption, strength)
    return E.SampleRow(seed, *r) if r is not None else None


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_cross_check(key):
    n_jobs, buffer, yard_length, seed, fleet_delta = key
    p = E.Params(n_jobs, buffer, yard_length)
    base = E.base_instance(p, seed)
    kmin = E.kmin_for(p, seed)
    from hrb_scenario import with_fleet

    return F.cross_check(with_fleet(base, kmin + fleet_delta)) if kmin is not None else None


st.title("🚚 Robuste Hof-Disposition: Hält der Einsatzplan, wenn etwas dazwischenkommt?")
st.markdown(
    """
Der Hof-Einsatzplan aus **yard-demo** kennt alle Aufträge im Voraus und plant vor - aber was, wenn ein **Fahrzeug ausfällt**
oder die **Fahrzeiten schwanken**? Diese Demo zeigt, wie unterschiedlich der starre Plan je nach Störungsart bricht, was
**reaktives Nachplanen** bringt, und wie viele Fahrzeuge der Hof braucht, damit sich das überhaupt lohnt. Wie das Modell
funktioniert, steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Beschreibung im Expander
"📐 Mathematische Formulierung"; das Basismodell (Aufträge, Fristen, Online-Regeln, Vorausplanung) stammt aus **yard-demo**,
die Flottenregler-Idee ("Abstand zum Minimum") ist dieselbe wie bei **fahrzeugflotte-demo** (nur als Analogie, keine
gemeinsame Rechnung).
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Ausfall am Minimum": "Ein Fahrzeug fällt aus, der starre Plan bricht - online (ohne jedes Vorwissen) schlägt ihn klar, reaktiv nochmal deutlich.",
    "Rauschen am Minimum": "Bei Fahrzeit-Rauschen ist am Minimum kein Verfahren verlässlich im Vorteil (Münzwurf zwischen starr und online) - nur reaktiv ist zuverlässig gut.",
    "Leichter Ausfall": "Der Umschlag beginnt früh: im Mittel liegt online schon vorn, aber noch nicht auf jedem einzelnen Tag.",
    "Reserve gegen Ausfall": "Ein Reservefahrzeug macht online und reaktiv praktisch wartefrei - der starre Plan bleibt teuer, weil er die Reserve nicht nutzt.",
    "Reserve gegen Rauschen": "Ab einem Reservefahrzeug verschwindet der Münzwurf: online gewinnt jetzt verlässlich auch bei Rauschen.",
}
preset_names = list(C.PRESETS.keys())
for row in (preset_names[:3], preset_names[3:]):
    cols = st.columns(3)
    for col, name in zip(cols, row):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()
ss = st.session_state

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_jobs = st.slider("Aufträge", *bounds("n_jobs_slider"), key="n_jobs_slider",
                       help="Zahl der Fahraufträge im Schichtfenster. Mehr Aufträge = mehr Zeit für die Minimum-Suche (mehrere volle Vorausplanungen).")
    fleet_delta = st.radio("Flottenabstand zum praktischen Minimum", (0, 1, 2), format_func=lambda d: "Minimum" if d == 0 else f"+{d}",
                           key="fleet_delta_radio", horizontal=True,
                           help="Flotte = praktisches Minimum K (unten angezeigt) + Abstand. Kein Minus: unterhalb des Minimums gibt es keinen Vorausplan ohne Verspätung, und diese Zone wurde nicht gemessen.")
    disruption = st.radio("Störungsart", C.DISRUPTION_KINDS, format_func=lambda d: C.DISRUPTION_LABELS[d], key="disruption_radio",
                          help="Umschalter, kein Mischbetrieb: beide Störungsarten wurden nur einzeln gemessen (siehe 'Wie funktioniert diese Demo?').")
    if disruption == C.DISRUPTION_AUSFALL:
        fail_duration = st.slider("Ausfalldauer (min)", *bounds("fail_duration_slider"), step=C.FAIL_DURATION_STEP, key="fail_duration_slider",
                                  help="Ein zufälliges Fahrzeug fällt für diese Dauer ab einem zufälligen Zeitpunkt aus. Gemessene Stützpunkte: 0, 20, 55 min; Zwischenwerte sind interpoliert, nicht einzeln geprüft.")
        noise_sigma = ss.get("noise_sigma_slider", C.NOISE_SIGMA_DEFAULT)
    else:
        noise_sigma = st.slider("Rauschstärke σ (%)", *bounds("noise_sigma_slider"), step=C.NOISE_SIGMA_STEP, format="%d%%", key="noise_sigma_slider",
                                help="Jede Anfahrt dauert ⌈t · (1 + σ·U)⌉ - nur verspätend. Gemessene Stützpunkte: 0, 25, 60 %. Bei kleinen Fahrzeiten (2-4 min) rundet math.ceil viele Ziehungen unter etwa 30 % auf denselben Wert: der Regler wirkt dort kaum, das ist keine Störung im Code.")
        fail_duration = ss.get("fail_duration_slider", C.FAIL_DURATION_DEFAULT)
    buffer = st.slider("Ø Fristpuffer (min)", *bounds("buffer_slider"), key="buffer_slider", help="Wie viel Luft die Fristen im Mittel gegenüber der Servicezeit lassen (wie yard-demo).")
    yard_length = st.slider("Hoflänge (m)", *bounds("yard_length_slider"), key="yard_length_slider", help="Länge des Hofs; bestimmt die Anfahrtswege (wie yard-demo).")
    seed = st.number_input("Seed", *bounds("seed_input"), key="seed_input", step=1, help="Bestimmt Aufträge, Anfahrtsmatrix und Störungsdraw des Tages (eigener Zufallsstrom für die Störung).")
    st.button("🎲 Neuer Tag", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed für den Tag.")

sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

strength = float(fail_duration) if disruption == C.DISRUPTION_AUSFALL else noise_sigma / 100.0
day_key = (int(n_jobs), int(buffer), int(yard_length), int(seed), int(fleet_delta), disruption, strength)
with st.spinner("Suche das praktische Minimum und rechne den Tag..."):
    day = _compute_day(day_key)

if day is None:
    st.error(f"Kein praktisches Minimum bis K = {C.MAX_K} gefunden. Bitte andere Einstellungen wählen (z. B. mehr Aufträge oder mehr Fristpuffer).")
    st.stop()

diag = E.diagnose(day)

# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🎯 Hält der Vorausplan die Störung aus?")
strength_text = f"Ausfalldauer {fail_duration} min" if disruption == C.DISRUPTION_AUSFALL else f"Rauschstärke σ = {noise_sigma} %"
st.caption(f"{n_jobs} Aufträge, praktisches Minimum K = {day.kmin}, eingesetzte Flotte {day.k} Fahrzeuge (Abstand +{fleet_delta}); "
          f"{C.DISRUPTION_LABELS[disruption]}, {strength_text}.")

m1, m2 = st.columns(2)
m3, m4 = st.columns(2)
m1.metric("gew. Verspätung starr", f"{day[C.S_STARR].wt:.2f} min/Auftrag", help="Der vorab berechnete Plan, unter der Störung unverändert durchgezogen.")
m2.metric("gew. Verspätung online", f"{day[C.S_ONLINE].wt:.2f} min/Auftrag", delta=f"{day[C.S_ONLINE].wt - day[C.S_STARR].wt:+.2f}", delta_color="inverse",
         help="Beste von FIFO/EDD/ATC, live entschieden, kein Vorwissen über die Störung. Delta gegen starr.")
m3.metric("gew. Verspätung reaktiv", f"{day[C.S_REAKTIV].wt:.2f} min/Auftrag", delta=f"{day[C.S_REAKTIV].wt - day[C.S_STARR].wt:+.2f}", delta_color="inverse",
         help="Vorausplan als Start, ab Störung per lokaler Suche neu verteilt. Delta gegen starr.")
m4.metric("praktisches Minimum K", str(day.kmin), help="Kleinste Flottengröße, bei der eine der vier Methoden 0 gewichtete Verspätung erreicht (gefunden, nicht bewiesen - siehe Tab 🔗 Mindestflotte).")

text = E.diagnosis_text(diag, day)
if diag.kind in ("starr_haelt", "calm"):
    st.info(f"ℹ️ {text}")
elif diag.kind == "reserve_wartefrei":
    st.success(f"✅ {text}")
else:
    st.warning(f"⚠️ {text}")

st.markdown("#### 🔍 Blick in den Tag: Einsatzplan je Fahrzeug")
gcols = st.columns(3)
for col, key in zip(gcols, C.STRATEGY_KEYS):
    with col:
        st.plotly_chart(V.gantt_figure(day, key, C.STRATEGY_LABELS[key]), width="stretch", key=f"main_gantt_{key}")
st.caption("Balken: Fahraufträge je Fahrzeug (Farbe nach Art, oranger Rand = verspätet). Grau: Anfahrt (bei Rauschen orange umrandet, wenn "
          "die tatsächliche Anfahrt länger als nominal war). Rot schraffiert: Ausfallfenster des betroffenen Fahrzeugs.")

pdf_slot = st.container()

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.subheader("📐 Wer gewinnt am praktischen Minimum – und ab wann dreht sich das?")
st.markdown(
    """
Kernfrage dieser Demo: Am **praktischen Minimum** widersprechen sich starr und online je nach Störungsart - bei
**Fahrzeugausfall** verliert starr klar gegen online, bei **Fahrzeit-Rauschen** gibt es dort keinen verlässlichen Sieger
(ein Münzwurf, siehe README). **Reaktiv** verdeckt diesen Widerspruch nicht, sondern gewinnt trotzdem - in fast jeder
Konstellation. Hier für Ihren Tag bzw. für Ihre Einstellungen gerechnet:
"""
)

wt_key = (int(n_jobs), int(buffer), int(yard_length), int(seed), int(fail_duration), int(noise_sigma))
st.markdown("**Sieger-Tabelle: Flottenabstand × Störungsart, derselbe Tag**")
if st.button("🏆 Sieger-Tabelle rechnen (6 Kombinationen, ein paar Sekunden)", key="winner_button"):
    with st.spinner("Rechne alle 3x2 Kombinationen..."):
        st.session_state["winner_result"] = (wt_key, _compute_winner_table(wt_key))
stored_winner = st.session_state.get("winner_result")
winner = stored_winner[1] if stored_winner and stored_winner[0] == wt_key else None
if winner is None:
    st.info("ℹ️ Die Sieger-Tabelle ist für diese Einstellung noch nicht gerechnet: Knopf oben.")
else:
    st.plotly_chart(V.winner_heatmap(winner), width="stretch", key="winner_heatmap_chart")
    st.caption("Grün: online schlägt starr klar; rot: starr schlägt online klar; grau: kein klarer Unterschied an diesem Tag. "
              "Zahlen je Zelle: starr / online / reaktiv (min/Auftrag). Am Minimum (oberste Zeile) zeigen die beiden Spalten oft "
              "unterschiedliche Farben - das ist der Widerspruch.")

st.markdown("**Umschlagpunkt-Kurve: gewichtete Verspätung über die Störstärke**")
curve_key_a = (int(n_jobs), int(buffer), int(yard_length), int(seed), int(fleet_delta), C.DISRUPTION_AUSFALL)
curve_key_b = (int(n_jobs), int(buffer), int(yard_length), int(seed), int(fleet_delta), C.DISRUPTION_RAUSCHEN)
if st.button("📈 Kurven rechnen (beide Störungsarten, ein paar Sekunden)", key="curve_button"):
    with st.spinner("Rechne die Störstärke-Kurven..."):
        st.session_state["curve_result"] = ((curve_key_a, curve_key_b), (_compute_curve(curve_key_a), _compute_curve(curve_key_b)))
stored_curve = st.session_state.get("curve_result")
curves = stored_curve[1] if stored_curve and stored_curve[0] == (curve_key_a, curve_key_b) else None
if curves is None:
    st.info("ℹ️ Die Kurven sind für diese Einstellung (Flottenabstand, Aufträge, Seed) noch nicht gerechnet: Knopf oben.")
else:
    ccol1, ccol2 = st.columns(2)
    with ccol1:
        st.markdown(f"**{C.DISRUPTION_LABELS[C.DISRUPTION_AUSFALL]}**")
        st.plotly_chart(V.curve_figure(curves[0], C.DISRUPTION_AUSFALL), width="stretch", key="curve_ausfall_chart")
    with ccol2:
        st.markdown(f"**{C.DISRUPTION_LABELS[C.DISRUPTION_RAUSCHEN]}**")
        st.plotly_chart(V.curve_figure(curves[1], C.DISRUPTION_RAUSCHEN), width="stretch", key="curve_rauschen_chart")
    st.caption(f"Beide Kurven bei Flottenabstand +{fleet_delta} (Ihr eingestellter Wert), Seed {int(seed)}. Zeigt, ob und wann sich starr "
              "und online mit wachsender Störstärke kreuzen.")

st.markdown(f"**Stichprobe** ({C.SAMPLE_DAYS_DEFAULT} andere Tage, Ihre Einstellungen)")
sample_key = (int(n_jobs), int(buffer), int(yard_length), int(fleet_delta), disruption, strength)
if st.button(f"📊 Stichprobe rechnen ({C.SAMPLE_DAYS_DEFAULT} Tage)", key="sample_button"):
    bar = st.progress(0.0, text="Rechne die Stichprobe...")
    rows_done = []
    for i in range(C.SAMPLE_DAYS_DEFAULT):
        s = C.SAMPLE_BASE + i
        row = _compute_sample_row((int(n_jobs), int(buffer), int(yard_length), s, int(fleet_delta), disruption, strength))
        if row is not None:
            rows_done.append(row)
        bar.progress((i + 1) / C.SAMPLE_DAYS_DEFAULT, text=f"Tag {i + 1} von {C.SAMPLE_DAYS_DEFAULT}")
    bar.empty()
    st.session_state["sample_result"] = (sample_key, tuple(rows_done))
stored_sample = st.session_state.get("sample_result")
sample_rows = stored_sample[1] if stored_sample and stored_sample[0] == sample_key else None

st.markdown("**Urteil über die Stichprobe** (gepaarte Differenz je Tag)")
if sample_rows is None:
    st.info("ℹ️ Die Stichprobe ist für diese Einstellungen noch nicht gerechnet: Knopf oben. Sie hängt nicht vom Seed ab.")
else:
    for label_a, label_b, field_a, field_b in (("online", "starr", C.S_ONLINE, C.S_STARR), ("reaktiv", "starr", C.S_REAKTIV, C.S_STARR),
                                                ("reaktiv", "online", C.S_REAKTIV, C.S_ONLINE)):
        kind, sentence = E.verdict_text(sample_rows, label_a, label_b, field_a, field_b)
        if kind == "better":
            st.success(f"✅ {sentence}")
        elif kind == "worse":
            st.warning(f"⚠️ {sentence}")
        else:
            st.info(f"ℹ️ {sentence}")
    st.markdown("**Verteilung über die Tage: Median [10. bis 90. Perzentil]** (die Kennzahl ist schief, das Mittel allein täuscht)")
    import pandas as pd

    rows_t = [{"Strategie": C.STRATEGY_LABELS[k], "gew. Verspätung (min/Auftrag)": "{:.2f} [{:.2f}; {:.2f}]".format(*E.spread_of(sample_rows, k))}
             for k in C.STRATEGY_KEYS]
    st.dataframe(pd.DataFrame(rows_t), width="stretch", hide_index=True)
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown("**Spannweite je Strategie**")
        st.plotly_chart(V.spread_figure(sample_rows, "starr", "gew. Verspätung (min/Auftrag)"), width="stretch", key="spread_chart")
    with dcol2:
        st.markdown("**online gegen starr** (Anteil der Tage)")
        st.plotly_chart(V.distribution_figure(sample_rows, C.S_ONLINE, C.S_STARR, "online", "starr"), width="stretch", key="distribution_chart")
    st.caption(f"Basis: {len(sample_rows)} Tage (Seeds {sample_rows[0].seed}-{sample_rows[-1].seed}, nicht Ihr Seed) mit Ihren Einstellungen.")

with pdf_slot:
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_hrb_pdf(dict(n_jobs=int(n_jobs), fleet_delta=int(fleet_delta), disruption=disruption, fail_duration=int(fail_duration),
                                   noise_sigma=int(noise_sigma), buffer=int(buffer), yard_length=int(yard_length), seed=int(seed)),
                              day, E.base_instance(E.Params(int(n_jobs), int(buffer), int(yard_length)), int(seed)),
                              winner or {}, curve=curves[0] if curves else None, sample_rows=sample_rows),
        file_name="hofrobust_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Szenario, Ergebnis des Tages, Sieger-Tabelle und, falls schon gerechnet, Kurve und Stichprobe mit Urteil.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Verfahrensvergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – Verfahren im Vergleich"):
    tabs = st.tabs([C.STRATEGY_LABELS[k] for k in C.STRATEGY_KEYS] + ["🔗 Mindestflotte", "📊 Vergleich"])
    for tab, key in zip(tabs, C.STRATEGY_KEYS):
        with tab:
            UI.render_strategy_panel(f"method_{key}", day, key)
    base_instance = E.base_instance(E.Params(int(n_jobs), int(buffer), int(yard_length)), int(seed))
    with tabs[3]:
        cc_key = (int(n_jobs), int(buffer), int(yard_length), int(seed), int(fleet_delta))
        cross_result = None
        if st.button("🔎 CP-SAT-Cross-Check rechnen (bis zu 20 s)", key="cross_check_button"):
            with st.spinner("Löse K und K-1 exakt mit CP-SAT..."):
                st.session_state["cross_check_result"] = (cc_key, _compute_cross_check(cc_key))
        stored_cc = st.session_state.get("cross_check_result")
        if stored_cc and stored_cc[0] == cc_key:
            cross_result = stored_cc[1]
        UI.render_fleet_panel("fleet", day, base_instance, cross_result)
    with tabs[4]:
        UI.render_comparison("comparison", day)
        st.caption("Eine Konstellation (Flotte, Störungsart, Störstärke, Seed), drei Strategien. Delta gegen starr bzw. online.")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Hof, Aufträge, Fristen, Anfahrtszeiten** wie in yard-demo: Fahraufträge (Bereitstellung, Abfahrt, Abräumen) mit Freigabe,
Frist und Gewicht, Hoffahrzeuge fahren zwischen Toren und Stellplätzen. Ziel: gewichtete Verspätung minimieren.

**Drei Strategien:**
- **🔒 starr:** der vorab berechnete Vorausplan (Iterated Local Search über Umhängen und Tauschen, wie yard-demo), unter der Störung unverändert ausgeführt.
- **🔄 online:** die beste von FIFO / Frist zuerst (EDD) / ATC, live entschieden - sieht die Störung nur als "Fahrzeug nicht frei" bzw. tatsächliche Fahrzeiten.
- **⚡ reaktiv:** der Vorausplan als Startlösung; ab Störbeginn (Ausfall) bzw. von Anfang an (Rauschen) werden die noch offenen Aufträge per derselben lokalen Suche neu verteilt - ausgehend vom echten Zustand jedes Fahrzeugs.

**Das praktische Minimum K** ist die kleinste Flottengröße, bei der eine der vier Methoden 0 gewichtete Verspätung
erreicht (Suche über k = 1, 2, ... mit je einer vollen Vorausplanung). Das ist ein **gefundenes**, kein **bewiesenes**
Minimum: die Matching-Untergrenze (Zusatzinfo im Tab "🔗 Mindestflotte") ist bei echten Zeitfenstern nur eine gültige,
nicht immer scharfe Bedingung (anders als bei der Fahrzeugflotte-Demo mit festen Kran-Aufnahmezeiten).

**Zwei Störungsarten, ein Umschalter:** Ein **Fahrzeugausfall** bricht die feste Vorausplan-Reihenfolge direkt (Kaskade
auf alle Folgeaufträge des Fahrzeugs); **Fahrzeit-Rauschen** verschiebt nur Zeiten, ohne die Reihenfolge unmöglich zu
machen. Deshalb wirken sie unterschiedlich: bei Ausfall verliert der starre Plan am Minimum klar gegen online; bei
Rauschen gibt es am Minimum **keinen verlässlichen Sieger** zwischen starr und online (siehe unten). Beide Störungsarten
wurden nur EINZELN gemessen, nie gleichzeitig (kein Mischbetrieb in dieser Version).

**Warum starr und online sich am Minimum widersprechen können - und warum reaktiv trotzdem verlässlich ist:** ein
Fahrzeugausfall trifft den starren Plan hart, weil er keine Reihenfolge mehr anpassen kann; unter Rauschen dagegen hilft
das Vorwissen des Vorausplans (Vorpositionieren) manchmal mehr, als die fehlende Reaktionsfähigkeit schadet - welches
Verfahren gewinnt, hängt vom einzelnen Tag ab (bei 60 unabhängigen Tagen: online gewinnt an 48 %, starr an 48 % - ein
Münzwurf). Reaktiv hat beides (Vorwissen UND Reaktion) und ist in praktisch keiner Konstellation schlechter.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- Fahrzeit-Rauschen wirkt nur auf die **Leerfahrt** (Anfahrt), nicht auf Kupplung/Servicezeit - eine vereinfachte Annahme.
- Das ausgefallene Fahrzeug ist **ab Fensterende sofort wieder voll verfügbar** (kein Reparaturaufschlag, keine Nachwirkung).
- Die reaktive Suche kennt die Störung erst **ab ihrem Beginn** (kein Vorwissen, kein Forecast).
- Bei kleinen Fahrzeiten (2-4 min) rundet `math.ceil` viele Rauschziehungen unter etwa 30 % Stärke auf denselben Wert -
  der Regler wirkt dort kaum unterscheidbar (Randbefund aus dem Vorab-Check, kein Fehler im Code).
- **Die Reihenfolge "starr gegen online" hängt an der Störungsart** und ist am praktischen Minimum nicht robust gegen die
  Wahl des Störszenarios - das steht hier ausdrücklich im Text, nicht nur im Kleingedruckten.
- Alle Zahlen sind **Größenordnungen aus einer Simulation**, keine Messung an einem echten Hof; jeder Endplan wird
  unabhängig mit einer echten Machbarkeitsprüfung (Freigaben, Anfahrtszeiten) geprüft.
- Verwandt: **yard-demo** (dasselbe Fachmodell ohne Störung), **fahrzeugflotte-demo** (dieselbe "Abstand zum Minimum"-Idee
  in der Kran-Domäne, hier nur als Analogie, keine gemeinsame Rechnung).
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Basismodell** wörtlich wie in yard-demo: Aufträge $j$ mit Freigabe $r_j$, Frist $d_j$, Servicezeit $p_j$, Gewicht
$w_j$; Anfahrtsmatrix $\tau_{ij}$ (Manhattan, aufgerundet). Ziel lexikografisch: zuerst die gewichtete Verspätung
$\sum_j w_j \max(0, C_j - d_j)$ minimieren (Ankunftszeit $C_j$), erst danach die gesamte Leerfahrtzeit
(`OBJ_BIG`-Konstruktion wie in yard-demo, damit Leerfahrt nie eine Verspätung aufwiegen kann).

**Variabler Fahrzeug-Startzustand.** `sequence_cost_from`/`sequence_plan_from`/`local_search_from` generalisieren
dieselbe Kostenfunktion und Umhängen-und-Tauschen-Suche auf einen Start bei $(t_0^v, \text{Ort}_0^v)$ statt fest
$(0, \text{Depot})$ - dieselbe Formel, verschobener Startpunkt; das ist die einzige echte Erweiterung gegenüber yard-demo.

**Störung 1 (Ausfall):** Fahrzeug $v$ ist im Fenster $[b_{\text{start}}, b_{\text{end}})$ nie "frei". starr verschiebt
einen in das Fenster fallenden Start ans Fensterende; reaktiv plant ab $b_{\text{start}}$ alle noch nicht gestarteten
Aufträge (auch anderer Fahrzeuge) mit `local_search_from` neu, ausgehend vom echten Zustand jedes Fahrzeugs.

**Störung 2 (Rauschen):** Anfahrt $\tau_{ij}' = \lceil \tau_{ij} \cdot (1 + \sigma \cdot U) \rceil$ mit $U \in [0, 1)$,
je Ziel-Auftrag gezogen (gemeinsame Zufallszahlen für alle drei Strategien). reaktiv plant hier ALLE Aufträge ab
$t = 0$ neu (kein Störfenster), mit der Vorausplan-Reihenfolge als Startlösung.

**Praktisches Minimum:** $K = \min\{k : \text{bestes Ergebnis von FIFO/EDD/ATC/Vorausplanung bei } k \text{ Fahrzeugen} = 0\}$.
**Matching-Untergrenze** (Zusatzinfo): $j$ kann optimistisch vor $k$ liegen, wenn $r_j + p_j + \tau_{jk} \le d_k - p_k$ -
eine notwendige, aber bei echten Zeitfenstern nicht hinreichende Kettenkompatibilität (Zyklen möglich, DAG-Voraussetzung
verletzt) - $n$ minus Größe des maximalen Matchings ist daher eine gültige, aber nicht immer scharfe Untergrenze.

Implementiert in `hrb_scenario.py` (Instanzen, Rauschfaktoren), `hrb_dispatch.py` (Online-Regeln, lokale Suche, fest und
variabel), `hrb_disruption.py` (Ausfall, Rauschen, reaktive Strategien), `hrb_fleet.py` (Minimum-Suche, Matching,
CP-SAT-Cross-Check) und `hrb_evaluation.py` (Kennzahlen, Stichprobe, Urteil, bedingte Meldung).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Hof- und Yard-Management optimieren](https://sebastianhanisch.net/yard-management-optimierung.html)."
)
