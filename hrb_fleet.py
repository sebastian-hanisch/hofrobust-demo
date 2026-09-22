"""Praktisches Minimum der Flottengröße, Matching-Untergrenze (Zusatzinfo) und CP-SAT-Cross-Check
- aus hof-planung/vorab_flotte/measure.py übernommen. Die generische Bipartit-Matching-Routine ist
hier NEU geschrieben (gleicher Algorithmus wie fahrzeugflotte-demo/fz_dispatch.max_matching), weil
sie ein reiner Graphalgorithmus ist, unabhängig vom Hof- oder Kran-Modell - keine Verrechnung der
beiden Domänen, nur derselbe Algorithmus zweimal implementiert (Plan Abschnitt 15).

Kein exakter Beweis wie bei fahrzeugflotte-demo möglich: yard-demo hat echte Zeitfenster statt
fester Kran-Aufnahmezeiten, die optimistische Kettenkompatibilität kann in beide Richtungen gelten
(Zyklen, DAG-Voraussetzung verletzt) - die Matching-Untergrenze ist daher gültig, aber nicht scharf
(siehe vorab_flotte/ERGEBNIS.md: 20/26 exakt, 6/26 zu niedrig, nie zu hoch)."""

import hrb_constants as C
from hrb_dispatch import dispatch_atc, dispatch_edd, dispatch_fifo, improve_plan
from hrb_evaluation import evaluate
from hrb_scenario import with_fleet

RULES = (dispatch_fifo, dispatch_edd, dispatch_atc)


# ---------------------------------------------------------------------------------- Matching (Hopcroft-artig, einfach)


def max_matching(n, adj):
    """Größtes Matching im gerichteten Kompatibilitätsgraphen (j kann vor k liegen): klassischer
    augmentierender-Pfad-Algorithmus (Kuhn), O(n * E). `adj[j]` = Liste möglicher Nachfolger k."""
    match_to = [-1] * n  # match_to[k] = j, das k als Nachfolger hat

    def try_augment(j, seen):
        for k in adj[j]:
            if not seen[k]:
                seen[k] = True
                if match_to[k] == -1 or try_augment(match_to[k], seen):
                    match_to[k] = j
                    return True
        return False

    size = 0
    for j in range(n):
        seen = [False] * n
        if try_augment(j, seen):
            size += 1
    return size, match_to


def _optimistic_can_follow(instance, j, k):
    """Notwendige (nicht hinreichende) Bedingung: frühestmögliches Ende von j plus Anfahrt zu k
    passt noch in ks spätesten Start. Liefert eine UNTERGRENZE der Mindestflotte (n - Matching kann
    unterschätzen, nie überschätzen)."""
    a, b = instance.jobs[j], instance.jobs[k]
    earliest_finish_j = a.release + a.service
    latest_start_k = b.deadline - b.service
    return earliest_finish_j + instance.approach[j][k] <= latest_start_k


def matching_lower_bound(instance):
    n = len(instance.jobs)
    adj = [[k for k in range(n) if k != j and _optimistic_can_follow(instance, j, k)] for j in range(n)]
    size, _ = max_matching(n, adj)
    return n - size


# ----------------------------------------------------------------------------- praktisches Minimum


def best_weighted_tardiness_total(instance):
    """Kleinste (nicht normierte) gewichtete Verspätung über FIFO/EDD/ATC und Vorausplanung."""
    best = None
    for fn in RULES:
        plan, _ = fn(instance)
        wt = evaluate(instance, plan)["total_weighted_tardiness"]
        best = wt if best is None else min(best, wt)
    plan, _ = improve_plan(instance)
    wt = evaluate(instance, plan)["total_weighted_tardiness"]
    return min(best, wt)


def practical_min_fleet(base_instance, max_k=C.MAX_K):
    """Kleinste Flottengröße, bei der eine der vier Methoden 0 gewichtete Verspätung erreicht - Suche
    über k=1,2,..., je eine volle Vorausplanung pro Stufe. `base_instance`: Instanz mit beliebigem
    n_vehicles (Aufträge/Anfahrtsmatrix hängen nicht davon ab, siehe hrb_scenario.with_fleet)."""
    for k in range(1, max_k + 1):
        inst = with_fleet(base_instance, k)
        if best_weighted_tardiness_total(inst) == 0:
            return k, inst
    return None, None


# --------------------------------------------------------------------------------- CP-SAT-Cross-Check


def solve_exact(instance, time_limit_seconds=C.EXACT_SOLVE_TIME_LIMIT_SECONDS):
    """Exakter Referenzlöser (OR-Tools CP-SAT), wörtlich aus yard-demo/yard_cp_solver.py (eigene
    Kopie, kein Laufzeit-Import). Nur im Exakt-Tab, auf Klick (Abschnitt 15 des Plans)."""
    import os
    import time
    from dataclasses import dataclass

    from ortools.sat.python import cp_model

    from hrb_evaluation import sequences_to_plan

    @dataclass
    class ExactResult:
        feasible: bool
        optimal: bool
        plan: dict
        sequences: list
        wall_time_ms: float

    t0 = time.perf_counter()
    jobs = instance.jobs
    model = cp_model.CpModel()

    start = [model.NewIntVar(j.release, instance.horizon, f"s_{j.index}") for j in jobs]
    late = [model.NewIntVar(0, instance.horizon, f"t_{j.index}") for j in jobs]
    for j in jobs:
        model.Add(late[j.index] >= start[j.index] + j.service - j.deadline)

    arcs = []
    lit = {}
    empty_terms = []
    for j in jobs:
        a = model.NewBoolVar(f"from_depot_{j.index}")
        lit[(None, j.index)] = a
        arcs.append((0, j.index + 1, a))
        model.Add(start[j.index] >= instance.approach_from_depot[j.index]).OnlyEnforceIf(a)
        empty_terms.append(instance.approach_from_depot[j.index] * a)

        b = model.NewBoolVar(f"to_depot_{j.index}")
        lit[(j.index, None)] = b
        arcs.append((j.index + 1, 0, b))

    for i in jobs:
        for j in jobs:
            if i.index == j.index:
                continue
            a = model.NewBoolVar(f"arc_{i.index}_{j.index}")
            lit[(i.index, j.index)] = a
            arcs.append((i.index + 1, j.index + 1, a))
            model.Add(start[j.index] >= start[i.index] + i.service + instance.approach[i.index][j.index]).OnlyEnforceIf(a)
            empty_terms.append(instance.approach[i.index][j.index] * a)

    model.AddMultipleCircuit(arcs)
    model.Add(sum(lit[(None, j.index)] for j in jobs) <= instance.n_vehicles)

    weighted = sum(j.weight * late[j.index] for j in jobs)
    model.Minimize(weighted * C.OBJ_BIG + sum(empty_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = min(8, os.cpu_count() or 1)
    status = solver.Solve(model)
    wall_time_ms = (time.perf_counter() - t0) * 1000

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ExactResult(False, False, {}, [], wall_time_ms)

    successor = {}
    firsts = []
    for (i, j), var in lit.items():
        if solver.Value(var):
            if i is None:
                firsts.append(j)
            elif j is not None:
                successor[i] = j
    sequences = []
    for first in sorted(firsts, key=lambda j: solver.Value(start[j])):
        seq, cur = [], first
        while cur is not None:
            seq.append(cur)
            cur = successor.get(cur)
        sequences.append(seq)
    sequences += [[] for _ in range(instance.n_vehicles - len(sequences))]

    return ExactResult(feasible=True, optimal=status == cp_model.OPTIMAL, plan=sequences_to_plan(instance, sequences),
                       sequences=sequences, wall_time_ms=wall_time_ms)


def cross_check(base_instance, seed_tag=""):
    """K und K-1 mit CP-SAT geprüft: bei K sollte wt=0 sein (bewiesen oder nicht), bei K-1 wt>0.
    Für den Exakt-Tab (auf Klick, siehe Plan Abschnitt 15)."""
    kmin, inst_at_min = practical_min_fleet(base_instance)
    if kmin is None:
        return None
    res_min = solve_exact(inst_at_min)
    wt_min = evaluate(inst_at_min, res_min.plan)["total_weighted_tardiness"] if res_min.feasible else None
    res_below, wt_below = None, None
    if kmin > 1:
        inst_below = with_fleet(base_instance, kmin - 1)
        res_below = solve_exact(inst_below)
        wt_below = evaluate(inst_below, res_below.plan)["total_weighted_tardiness"] if res_below.feasible else None
    return dict(kmin=kmin, optimal_at_min=res_min.optimal, wt_at_min=wt_min,
               optimal_below=(res_below.optimal if res_below else None), wt_below=wt_below)
