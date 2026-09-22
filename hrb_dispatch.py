"""Online-Regeln, lokale Suche und Vorausplanung - Kern bitgleich aus yard-demo/yard_heuristic.py
übernommen, dazu die Erweiterung auf variablen Fahrzeug-Startzustand und störungsbewusste
Online-Regeln aus hof-planung/vorab_robust/vorab_robust.py (wörtlich, nur als eigenständige Kopie
ohne Laufzeit-Import, siehe Plan Abschnitt 10).

Zwei Klassen von Verfahren: ONLINE-REGELN (fifo/edd/atc) entscheiden erst, wenn ein Fahrzeug frei
wird; VORAUSPLANUNG (`improve_plan`) kennt alle Aufträge im Voraus und verbessert per Umhängen +
Tauschen (lokale Suche) sowie Iterated Local Search. `_from`-Varianten generalisieren dieselbe
Kostenfunktion/Suche auf einen variablen Start (frei ab, letzter Ort) statt fest (0, Depot) - nötig,
um ab einem Störzeitpunkt neu zu planen (siehe hrb_disruption.py)."""

import math
import random

import hrb_constants as C
from hrb_evaluation import sequence_cost, sequences_to_plan

# --------------------------------------------------------------------------------- Online-Regeln


def _dispatch(instance, choose):
    jobs = instance.jobs
    m = instance.n_vehicles
    free_at = [0] * m
    loc = [None] * m
    sequences = [[] for _ in range(m)]
    plan = {}
    unassigned = set(range(len(jobs)))
    t = 0

    while unassigned:
        idle = [v for v in range(m) if free_at[v] <= t]
        avail = sorted(j for j in unassigned if jobs[j].release <= t)
        if idle and avail:
            v, j = choose(t, idle, avail, loc)
            start = t + instance.approach_time(loc[v], j)
            plan[j] = (v, start)
            free_at[v] = start + jobs[j].service
            loc[v] = j
            sequences[v].append(j)
            unassigned.remove(j)
        else:
            future = [free_at[v] for v in range(m) if free_at[v] > t]
            future += [jobs[j].release for j in unassigned if jobs[j].release > t]
            t = min(future)
    return plan, sequences


def _nearest_idle(instance, idle, loc, j):
    return min(idle, key=lambda v: (instance.approach_time(loc[v], j), v))


def dispatch_fifo(instance):
    def choose(t, idle, avail, loc):
        j = min(avail, key=lambda a: (instance.jobs[a].release, a))
        return _nearest_idle(instance, idle, loc, j), j

    return _dispatch(instance, choose)


def dispatch_edd(instance):
    def choose(t, idle, avail, loc):
        j = min(avail, key=lambda a: (instance.jobs[a].deadline, a))
        return _nearest_idle(instance, idle, loc, j), j

    return _dispatch(instance, choose)


def dispatch_atc(instance, k=C.ATC_K):
    jobs = instance.jobs
    mean_service = sum(j.service for j in jobs) / len(jobs)

    def choose(t, idle, avail, loc):
        best, best_key = None, None
        for j in avail:
            job = jobs[j]
            for v in idle:
                tau = instance.approach_time(loc[v], j)
                slack = job.deadline - (t + tau + job.service)
                index = job.weight / (job.service + tau) * math.exp(-max(0, slack) / (k * mean_service))
                key = (-index, j, v)
                if best_key is None or key < best_key:
                    best, best_key = (v, j), key
        return best

    return _dispatch(instance, choose)


# ---------------------------------------------------------------- störungsbewusste Online-Regeln
# 1:1 dieselbe choose-Logik wie oben (FIFO/EDD/ATC), als eigenständige Funktionen: `dispatch_disrupted`
# braucht `choose(instance, t, idle, avail, loc)` (mit `instance` statt Closure), weil ein Fahrzeug
# während des Ausfallfensters aus der Menge der "idle"-Fahrzeuge herausfällt.


def choose_fifo(instance, t, idle, avail, loc):
    j = min(avail, key=lambda a: (instance.jobs[a].release, a))
    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))
    return v, j


def choose_edd(instance, t, idle, avail, loc):
    j = min(avail, key=lambda a: (instance.jobs[a].deadline, a))
    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))
    return v, j


def choose_atc(instance, t, idle, avail, loc, k=C.ATC_K):
    jobs = instance.jobs
    mean_service = sum(j.service for j in jobs) / len(jobs)
    best, best_key = None, None
    for j in avail:
        job = jobs[j]
        for v in idle:
            tau = instance.approach_time(loc[v], j)
            slack = job.deadline - (t + tau + job.service)
            index = job.weight / (job.service + tau) * math.exp(-max(0, slack) / (k * mean_service))
            key = (-index, j, v)
            if best_key is None or key < best_key:
                best, best_key = (v, j), key
    return best


ONLINE_RULES = {"FIFO": dispatch_fifo, "EDD": dispatch_edd, "ATC": dispatch_atc}
ONLINE_CHOOSERS = (choose_fifo, choose_edd, choose_atc)


def dispatch_disrupted(instance, choose, broken_vehicle, bstart, bend):
    """Wie `_dispatch`, aber `broken_vehicle` ist im Fenster [bstart, bend) nie frei (kann keinen
    neuen Auftrag antreten; eine schon laufende Fahrt wird nicht unterbrochen)."""
    jobs = instance.jobs
    m = instance.n_vehicles
    free_at = [0] * m
    loc = [None] * m
    sequences = [[] for _ in range(m)]
    plan = {}
    unassigned = set(range(len(jobs)))
    t = 0

    def down(v, tt):
        return v == broken_vehicle and bstart <= tt < bend

    while unassigned:
        idle = [v for v in range(m) if free_at[v] <= t and not down(v, t)]
        avail = sorted(j for j in unassigned if jobs[j].release <= t)
        if idle and avail:
            v, j = choose(instance, t, idle, avail, loc)
            start = t + instance.approach_time(loc[v], j)
            plan[j] = (v, start)
            free_at[v] = start + jobs[j].service
            loc[v] = j
            sequences[v].append(j)
            unassigned.remove(j)
        else:
            future = [free_at[v] for v in range(m) if free_at[v] > t]
            future += [jobs[j].release for j in unassigned if jobs[j].release > t]
            if t < bstart:
                future.append(bstart)
            if t < bend:
                future.append(bend)
            future = [x for x in future if x > t]
            t = min(future)
    return plan, sequences


# ------------------------------------------------------------------ Vorausplanung / lokale Suche
# (fester Start bei (0, Depot), wörtlich aus yard_heuristic.py)


def _relocate_pass(instance, seqs, costs):
    improved = False
    for v1 in range(len(seqs)):
        pos1 = 0
        while pos1 < len(seqs[v1]):
            j = seqs[v1][pos1]
            removed = seqs[v1][:pos1] + seqs[v1][pos1 + 1:]
            cost_removed = sequence_cost(instance, removed)
            gain_base = costs[v1]

            best_delta, best_move = 0, None
            for v2 in range(len(seqs)):
                target = removed if v2 == v1 else seqs[v2]
                old_v2 = 0 if v2 == v1 else costs[v2]
                for pos2 in range(len(target) + 1):
                    if v2 == v1 and pos2 == pos1:
                        continue
                    candidate = target[:pos2] + [j] + target[pos2:]
                    new_cost = sequence_cost(instance, candidate)
                    delta = (new_cost - gain_base) if v2 == v1 else ((cost_removed + new_cost) - (gain_base + old_v2))
                    if delta < best_delta:
                        best_delta, best_move = delta, (v2, pos2, candidate, new_cost)

            if best_move is not None:
                v2, _, candidate, new_cost = best_move
                if v2 == v1:
                    seqs[v1], costs[v1] = candidate, new_cost
                else:
                    seqs[v1], costs[v1] = removed, cost_removed
                    seqs[v2], costs[v2] = candidate, new_cost
                improved = True
            else:
                pos1 += 1
    return improved


def _swap_pass(instance, seqs, costs):
    improved = False
    m = len(seqs)
    for v1 in range(m):
        for i in range(len(seqs[v1])):
            for v2 in range(v1, m):
                start_k = i + 1 if v2 == v1 else 0
                for k in range(start_k, len(seqs[v2])):
                    if i >= len(seqs[v1]) or k >= len(seqs[v2]):
                        continue
                    if v1 == v2:
                        cand = list(seqs[v1])
                        cand[i], cand[k] = cand[k], cand[i]
                        new_cost = sequence_cost(instance, cand)
                        if new_cost < costs[v1]:
                            seqs[v1], costs[v1] = cand, new_cost
                            improved = True
                    else:
                        cand1, cand2 = list(seqs[v1]), list(seqs[v2])
                        cand1[i], cand2[k] = cand2[k], cand1[i]
                        c1, c2 = sequence_cost(instance, cand1), sequence_cost(instance, cand2)
                        if c1 + c2 < costs[v1] + costs[v2]:
                            seqs[v1], seqs[v2] = cand1, cand2
                            costs[v1], costs[v2] = c1, c2
                            improved = True
    return improved


def local_search(instance, sequences, max_passes=30):
    seqs = [list(s) for s in sequences]
    costs = [sequence_cost(instance, s) for s in seqs]
    for _ in range(max_passes):
        a = _relocate_pass(instance, seqs, costs)
        b = _swap_pass(instance, seqs, costs)
        if not (a or b):
            break
    return seqs


def iterated_local_search(instance, sequences, iterations=C.ILS_ITERATIONS, seed=0):
    rng = random.Random(seed)
    current = [list(s) for s in sequences]
    current_cost = sum(sequence_cost(instance, s) for s in current)
    best, best_cost = current, current_cost
    for _ in range(iterations):
        candidate = [list(s) for s in current]
        for _ in range(3):
            filled = [v for v in range(len(candidate)) if candidate[v]]
            v = rng.choice(filled)
            job = candidate[v].pop(rng.randrange(len(candidate[v])))
            target = rng.randrange(len(candidate))
            candidate[target].insert(rng.randint(0, len(candidate[target])), job)
        candidate = local_search(instance, candidate)
        cost = sum(sequence_cost(instance, s) for s in candidate)
        if cost <= current_cost:
            current, current_cost = candidate, cost
            if cost < best_cost:
                best, best_cost = candidate, cost
    return best


def improve_plan(instance, iterations=C.ILS_ITERATIONS):
    starts = [dispatch_atc(instance)[1], dispatch_edd(instance)[1], dispatch_fifo(instance)[1]]
    best_seqs, best_cost = None, None
    for seqs in starts:
        polished = local_search(instance, seqs)
        cost = sum(sequence_cost(instance, s) for s in polished)
        if best_cost is None or cost < best_cost:
            best_seqs, best_cost = polished, cost
    best_seqs = iterated_local_search(instance, best_seqs, iterations=iterations)
    return sequences_to_plan(instance, best_seqs), best_seqs


# ------------------------------------------------------------- variabler Fahrzeug-Startzustand
# Wörtlich aus vorab_robust.py: dieselbe Kostenfunktion/Suche, aber Fahrzeug v startet bei
# (free_at0[v], prev0[v]) statt fest (0, None) - einzige echte Erweiterung ggü. yard-demo
# (Plan Abschnitt 2).


def sequence_cost_from(instance, seq, free_at0, prev0):
    t, prev = free_at0, prev0
    weighted, empty = 0, 0
    for j in seq:
        job = instance.jobs[j]
        approach = instance.approach_time(prev, j)
        start = max(job.release, t + approach)
        end = start + job.service
        if end > job.deadline:
            weighted += job.weight * (end - job.deadline)
        empty += approach
        t, prev = end, j
    return weighted * C.OBJ_BIG + empty


def sequence_plan_from(instance, seq, free_at0, prev0, vehicle_id):
    plan = {}
    t, prev = free_at0, prev0
    for j in seq:
        job = instance.jobs[j]
        approach = instance.approach_time(prev, j)
        start = max(job.release, t + approach)
        plan[j] = (vehicle_id, start)
        t, prev = start + job.service, j
    return plan


def _relocate_pass_from(instance, seqs, costs, free0, prev0):
    improved = False
    for v1 in range(len(seqs)):
        pos1 = 0
        while pos1 < len(seqs[v1]):
            j = seqs[v1][pos1]
            removed = seqs[v1][:pos1] + seqs[v1][pos1 + 1:]
            cost_removed = sequence_cost_from(instance, removed, free0[v1], prev0[v1])
            gain_base = costs[v1]

            best_delta, best_move = 0, None
            for v2 in range(len(seqs)):
                target = removed if v2 == v1 else seqs[v2]
                old_v2 = 0 if v2 == v1 else costs[v2]
                for pos2 in range(len(target) + 1):
                    if v2 == v1 and pos2 == pos1:
                        continue
                    candidate = target[:pos2] + [j] + target[pos2:]
                    new_cost = sequence_cost_from(instance, candidate, free0[v2], prev0[v2])
                    delta = (new_cost - gain_base) if v2 == v1 else ((cost_removed + new_cost) - (gain_base + old_v2))
                    if delta < best_delta:
                        best_delta, best_move = delta, (v2, pos2, candidate, new_cost)

            if best_move is not None:
                v2, _, candidate, new_cost = best_move
                if v2 == v1:
                    seqs[v1], costs[v1] = candidate, new_cost
                else:
                    seqs[v1], costs[v1] = removed, cost_removed
                    seqs[v2], costs[v2] = candidate, new_cost
                improved = True
            else:
                pos1 += 1
    return improved


def _swap_pass_from(instance, seqs, costs, free0, prev0):
    improved = False
    m = len(seqs)
    for v1 in range(m):
        for i in range(len(seqs[v1])):
            for v2 in range(v1, m):
                start_k = i + 1 if v2 == v1 else 0
                for k in range(start_k, len(seqs[v2])):
                    if i >= len(seqs[v1]) or k >= len(seqs[v2]):
                        continue
                    if v1 == v2:
                        cand = list(seqs[v1])
                        cand[i], cand[k] = cand[k], cand[i]
                        new_cost = sequence_cost_from(instance, cand, free0[v1], prev0[v1])
                        if new_cost < costs[v1]:
                            seqs[v1], costs[v1] = cand, new_cost
                            improved = True
                    else:
                        cand1, cand2 = list(seqs[v1]), list(seqs[v2])
                        cand1[i], cand2[k] = cand2[k], cand1[i]
                        c1 = sequence_cost_from(instance, cand1, free0[v1], prev0[v1])
                        c2 = sequence_cost_from(instance, cand2, free0[v2], prev0[v2])
                        if c1 + c2 < costs[v1] + costs[v2]:
                            seqs[v1], seqs[v2] = cand1, cand2
                            costs[v1], costs[v2] = c1, c2
                            improved = True
    return improved


def local_search_from(instance, sequences, free0, prev0, max_passes=30):
    seqs = [list(s) for s in sequences]
    costs = [sequence_cost_from(instance, seqs[v], free0[v], prev0[v]) for v in range(len(seqs))]
    for _ in range(max_passes):
        a = _relocate_pass_from(instance, seqs, costs, free0, prev0)
        b = _swap_pass_from(instance, seqs, costs, free0, prev0)
        if not (a or b):
            break
    return seqs
