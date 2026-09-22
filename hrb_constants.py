"""Regler-Grenzen, feste Modellannahmen, Störstärken-Stützpunkte, Presets und Farben.

Fachmodell wörtlich aus yard-demo übernommen (siehe C.KIND_*, C.OBJ_BIG, C.ATC_K, C.ILS_ITERATIONS -
identische Werte, damit improve_plan/dispatch_* dieselben Zahlen liefern wie in den drei
Vorab-Checks). Neu sind nur die Störungs- und Flottenkonstanten."""

# --- Regler ------------------------------------------------------------------------------------
N_JOBS_RANGE, N_JOBS_DEFAULT = (12, 40), 30

FLEET_DELTA_RANGE, FLEET_DELTA_DEFAULT = (0, 2), 0  # kein Minus (Abschnitt 15 des Plans)
MAX_K = 8  # Suchgrenze für das praktische Minimum (wie vorab_flotte.practical_min_fleet)

DISRUPTION_AUSFALL, DISRUPTION_RAUSCHEN = "ausfall", "rauschen"
DISRUPTION_KINDS = (DISRUPTION_AUSFALL, DISRUPTION_RAUSCHEN)
DISRUPTION_DEFAULT = DISRUPTION_AUSFALL
DISRUPTION_LABELS = {DISRUPTION_AUSFALL: "🚧 Fahrzeugausfall", DISRUPTION_RAUSCHEN: "🌊 Fahrzeit-Rauschen"}

FAIL_DURATION_RANGE, FAIL_DURATION_DEFAULT, FAIL_DURATION_STEP = (0, 60), 20, 5  # Minuten
NOISE_SIGMA_RANGE, NOISE_SIGMA_DEFAULT, NOISE_SIGMA_STEP = (0, 60), 25, 5  # Prozent

BUFFER_RANGE, BUFFER_DEFAULT = (5, 60), 15  # Minuten, wie yard-demo
YARD_LENGTH_RANGE, YARD_LENGTH_DEFAULT = (200, 900), 450  # Meter, wie yard-demo

SEED_RANGE, SEED_DEFAULT = (0, 9999), 7039  # AP6: Kandidatenpool (7000-7059) gegen Grundgesamtheit 6000-6059
# nachgemessen (tools/PRESET_SWEEP.md) - der Plan schlug Seed 4 vor, das trägt hier keine der fünf
# Geschichten (siehe README "Befunde und Korrekturen"); 7039 ist der einzige Kandidat mit vernünftigem
# Abstand zum Median, an dem alle fünf Presets tragen.

# --- Feste Modellannahmen (bewusst keine Regler, siehe Plan Abschnitt 5) ------------------------
ARRIVAL_WINDOW = 120
PEAK_PCT = 70
DEPARTURE_PCT = 45
N_DOORS = 10

COUPLING_MIN = 4
SPEED_M_PER_MIN = 150
YARD_WIDTH = 170
PARK_ROW_YS = (55, 80, 105, 130)
PARK_COL_SPACING = 15

KIND_DEPARTURE = "Abfahrt"
KIND_SETUP = "Bereitstellung"
KIND_CLEAR = "Abräumen"
KINDS = (KIND_DEPARTURE, KIND_SETUP, KIND_CLEAR)
KIND_WEIGHTS = {KIND_DEPARTURE: 4, KIND_SETUP: 2, KIND_CLEAR: 1}
KIND_SLACK_FACTOR = {KIND_DEPARTURE: 0.6, KIND_SETUP: 1.0, KIND_CLEAR: 2.5}
KIND_COLORS = {KIND_DEPARTURE: "#d62728", KIND_SETUP: "#1f77b4", KIND_CLEAR: "#7f7f7f"}

OBJ_BIG = 100_000
ATC_K = 1.0
ILS_ITERATIONS = 40
EXACT_SOLVE_TIME_LIMIT_SECONDS = 10

# --- Strategien --------------------------------------------------------------------------------
S_STARR, S_ONLINE, S_REAKTIV = "starr", "online", "reaktiv"
STRATEGY_KEYS = (S_STARR, S_ONLINE, S_REAKTIV)
STRATEGY_LABELS = {S_STARR: "🔒 starr", S_ONLINE: "🔄 online (beste Regel)", S_REAKTIV: "⚡ reaktiv"}
STRATEGY_SHORT = {S_STARR: "starr", S_ONLINE: "online", S_REAKTIV: "reaktiv"}
STRATEGY_COLORS = {S_STARR: "#c0392b", S_ONLINE: "#8a94a3", S_REAKTIV: "#2e7d4f"}
STRATEGY_DESCRIPTIONS = {
    S_STARR: "der vorab berechnete Vorausplan (ILS), unter der Störung stur durchgezogen - kein Vorwissen über den genauen Störungsverlauf, keine Reaktion.",
    S_ONLINE: "beste von FIFO / Frist zuerst (EDD) / ATC, live entschieden - sieht die Störung nur als 'Fahrzeug nicht frei' bzw. tatsächliche Fahrzeiten, kein Vorausplan.",
    S_REAKTIV: "Vorausplan als Startlösung, ab Störbeginn (Ausfall) bzw. von Anfang an (Rauschen) per lokaler Suche neu verteilt - Vorwissen UND Reaktion.",
}

# --- Auswertung ----------------------------------------------------------------------------------
SAMPLE_DAYS_DEFAULT = 20  # ~1 s/Tag bei gecachtem K, aber ~2 s Minimum-Suche je neuem Seed (siehe README)
SAMPLE_BASE = 5000  # Seeds der Stichprobe, unabhängig vom eingestellten Seed
PCT_LO, PCT_HI = 0.10, 0.90
VERDICT_MIN_ABS = 0.3  # min/Auftrag: eine gepaarte Differenz unter diesem Betrag gilt nie als "klar"
CURVE_STEPS_AUSFALL = (0, 10, 20, 30, 40, 55, 60)
CURVE_STEPS_RAUSCHEN = (0, 10, 25, 40, 60)

# --- Darstellung ---------------------------------------------------------------------------------
CHART_HEIGHT = 320
OUTCOME_COLORS = {"better": "#2e7d4f", "equal": "#8a94a3", "worse": "#c0392b"}

# --- Presets (gemeinsamer Seed, siehe tools/PRESET_SWEEP.md) -------------------------------------
_BASE = dict(n_jobs=N_JOBS_DEFAULT, buffer=BUFFER_DEFAULT, yard_length=YARD_LENGTH_DEFAULT, seed=SEED_DEFAULT)
PRESETS = {
    "Ausfall am Minimum": dict(_BASE, fleet_delta=0, disruption=DISRUPTION_AUSFALL, fail_duration=55, noise_sigma=NOISE_SIGMA_DEFAULT),
    "Rauschen am Minimum": dict(_BASE, fleet_delta=0, disruption=DISRUPTION_RAUSCHEN, fail_duration=FAIL_DURATION_DEFAULT, noise_sigma=60),
    "Leichter Ausfall": dict(_BASE, fleet_delta=0, disruption=DISRUPTION_AUSFALL, fail_duration=20, noise_sigma=NOISE_SIGMA_DEFAULT),
    "Reserve gegen Ausfall": dict(_BASE, fleet_delta=1, disruption=DISRUPTION_AUSFALL, fail_duration=55, noise_sigma=NOISE_SIGMA_DEFAULT),
    "Reserve gegen Rauschen": dict(_BASE, fleet_delta=1, disruption=DISRUPTION_RAUSCHEN, fail_duration=FAIL_DURATION_DEFAULT, noise_sigma=60),
}
