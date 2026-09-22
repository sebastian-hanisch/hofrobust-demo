"""Zwei Störungsarten und die drei Strategien starr/online/reaktiv unter ihnen - wörtlich aus den
drei Vorab-Checks übernommen (vorab_robust.py: Ausfall; vorab_flotte/measure.py: Rauschen;
vorab_kombiniert/combined_check.py: `reactive_under_noise`, die fehlende Kreuzung reaktiv x
Rauschen). Gemeinsame Zufallszahlen (ein Störungsdraw je Instanz) für alle drei Strategien -
gepaarter Vergleich, siehe Plan Abschnitt 12."""

import random

from hrb_dispatch import ONLINE_CHOOSERS, ONLINE_RULES, dispatch_disrupted, local_search_from, sequence_plan_from
from hrb_evaluation import weighted_tardiness_per_job


# --------------------------------------------------------------------------- Störungsart: Ausfall


def draw_failure(instance, seed, duration, delta=0):
    """Zufälliges Fahrzeug, zufälliger Startzeitpunkt im Ankunftsfenster; `duration=0` -> kein
    Ausfall (bstart=bend). Eigener Zufallsstrom (siehe Plan: getrennt vom Auftrags-Seed); `delta`
    (Flottenabstand) geht mit ein, wie in vorab_kombiniert/combined_check.py, damit der Draw nicht
    zufällig über die drei Flottenstufen identisch ist."""
    rng = random.Random(1_000_003 * seed + 17 + delta)
    broken_vehicle = rng.randrange(instance.n_vehicles)
    bstart = rng.uniform(0, instance.arrival_window)
    return broken_vehicle, bstart, bstart + duration


def simulate_rigid(instance, sequences, broken_vehicle, bstart, bend):
    """Feste Fahrzeug-Reihenfolge trotz Ausfall unverändert ausgeführt: fällt der nächstmögliche
    Start in das Ausfallfenster des betroffenen Fahrzeugs, verschiebt er sich ans Fensterende."""
    plan = {}
    for v, seq in enumerate(sequences):
        t, prev = 0, None
        for j in seq:
            job = instance.jobs[j]
            approach = instance.approach_time(prev, j)
            candidate = max(job.release, t + approach)
            start = bend if (v == broken_vehicle and bstart <= candidate < bend) else candidate
            plan[j] = (v, start)
            t, prev = start + job.service, j
    return plan


def simulate_reactive(instance, nominal_plan, nominal_seqs, broken_vehicle, bstart, bend):
    """Ab bstart: Aufträge, die im Nominalplan noch nicht gestartet waren, werden per lokaler Suche
    neu verteilt (auch auf andere Fahrzeuge) - ausgehend vom echten Zustand jedes Fahrzeugs. Bereits
    laufende/erledigte Aufträge bleiben unangetastet; das betroffene Fahrzeug ist erst ab `bend`
    wieder verfügbar."""
    m = instance.n_vehicles
    committed = [[] for _ in range(m)]
    pending_ids = set()
    for v, seq in enumerate(nominal_seqs):
        for j in seq:
            if nominal_plan[j][1] < bstart:
                committed[v].append(j)
            else:
                pending_ids.add(j)

    free0, prev0 = [0] * m, [None] * m
    plan = {}
    for v in range(m):
        t, prev = 0, None
        for j in committed[v]:
            start = nominal_plan[j][1]
            plan[j] = (v, start)
            t, prev = start + instance.jobs[j].service, j
        free0[v], prev0[v] = t, prev
        if v == broken_vehicle:
            free0[v] = max(free0[v], bend)

    pending_seed = [[j for j in nominal_seqs[v] if j in pending_ids] for v in range(m)]
    pending_solved = local_search_from(instance, pending_seed, free0, prev0)
    for v in range(m):
        plan.update(sequence_plan_from(instance, pending_solved[v], free0[v], prev0[v], v))
    return plan


def best_online_no_disruption(instance):
    """(wt je Auftrag, Plan) der besten von FIFO/EDD/ATC ohne Störung."""
    best_wt, best_plan = None, None
    for dispatch in ONLINE_RULES.values():
        plan, _ = dispatch(instance)
        wt = weighted_tardiness_per_job(instance, plan)
        if best_wt is None or wt < best_wt:
            best_wt, best_plan = wt, plan
    return best_wt, best_plan


def best_online_disrupted(instance, broken_vehicle, bstart, bend):
    """(wt je Auftrag, Plan) der besten von FIFO/EDD/ATC unter Ausfall."""
    best_wt, best_plan = None, None
    for choose in ONLINE_CHOOSERS:
        plan, _ = dispatch_disrupted(instance, choose, broken_vehicle, bstart, bend)
        wt = weighted_tardiness_per_job(instance, plan)
        if best_wt is None or wt < best_wt:
            best_wt, best_plan = wt, plan
    return best_wt, best_plan


# ------------------------------------------------------------------ Störungsart: Fahrzeit-Rauschen
# make_noisy_instance/draw_noise_factors leben in hrb_scenario.py (Instanzerzeugung).


def best_online_under_noise(noisy_instance):
    """(wt je Auftrag, Plan) der besten von FIFO/EDD/ATC unter den tatsächlichen (verrauschten)
    Fahrzeiten - live entschieden, kein Forecast-vs-Ist-Unterschied nötig."""
    best_wt, best_plan = None, None
    for dispatch in ONLINE_RULES.values():
        plan, _ = dispatch(noisy_instance)
        wt = weighted_tardiness_per_job(noisy_instance, plan)
        if best_wt is None or wt < best_wt:
            best_wt, best_plan = wt, plan
    return best_wt, best_plan


def rigid_under_noise(noisy_instance, sequences):
    """Feste Reihenfolge je Fahrzeug (aus der Vorausplanung auf der NOMINALEN Instanz) unter dem
    verrauschten Anfahrtsbild frühestmöglich ausgeführt."""
    from hrb_evaluation import sequences_to_plan

    return sequences_to_plan(noisy_instance, sequences)


def reactive_under_noise(noisy_instance, nominal_seqs):
    """Generalisierung von `simulate_reactive` auf Rauschen statt Ausfall (aus
    vorab_kombiniert/combined_check.py): es gibt kein Störfenster - die 'Störung' (die wahren,
    verrauschten Fahrzeiten) ist schon vor Ausführungsbeginn bekannt (wie online_under_noise auch
    ab t=0 mit den echten Zeiten entscheidet). Reaktiv heißt daher: dieselbe lokale Suche für ALLE
    Aufträge ab leerem Zustand, mit der Vorausplan-Reihenfolge als Startlösung."""
    m = noisy_instance.n_vehicles
    free0, prev0 = [0] * m, [None] * m
    seqs = local_search_from(noisy_instance, nominal_seqs, free0, prev0)
    plan = {}
    for v in range(m):
        plan.update(sequence_plan_from(noisy_instance, seqs[v], free0[v], prev0[v], v))
    return plan
