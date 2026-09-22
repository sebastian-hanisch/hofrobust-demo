"""Testhilfen: kleine Instanzen und unabhängige Nachrechnungen."""

import pathlib
import sys
from itertools import permutations, product

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_scenario as S  # noqa: E402


def tiny_instance(broken_free=False):
    """3-Auftrags-Instanz mit Anfahrtszeiten=0, 2 Fahrzeuge - aus hof-planung/vorab_robust/hand_check.py
    (unabhängig von Hand nachgerechnet: starr=3, online=0, reaktiv=0 bei Ausfall Fahrzeug 0, [2, 12))."""
    jobs = (
        S.Job(index=0, name="J0", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
             release=0, deadline=100, service=5, weight=1),
        S.Job(index=1, name="J1", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
             release=0, deadline=14, service=5, weight=1),
        S.Job(index=2, name="J2", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
             release=0, deadline=100, service=5, weight=1),
    )
    return S.Instance(jobs=jobs, n_vehicles=2, yard_length=100, yard_width=100, depot_xy=(0, 0), doors=(),
                      arrival_window=20, approach_from_depot=(0, 0, 0), approach=((0, 0, 0), (0, 0, 0), (0, 0, 0)), horizon=200)


def brute_force_min_fleet(inst, max_k=6):
    """Kleinste Flottengröße, mit der IRGENDEINE Zuordnung+Reihenfolge 0 Verspätung erreicht (volle
    Enumeration, nur für winzige Instanzen). Unabhängig von hrb_fleet geschrieben."""
    n = len(inst.jobs)

    def zero_tardy(perm):
        t, prev = 0, None
        for j in perm:
            job = inst.jobs[j]
            start = max(job.release, t + inst.approach_time(prev, j))
            end = start + job.service
            if end > job.deadline:
                return False
            t, prev = end, j
        return True

    for k in range(1, max_k + 1):
        for assign in product(range(k), repeat=n):
            groups = [[] for _ in range(k)]
            for idx, v in enumerate(assign):
                groups[v].append(idx)
            if all((not g) or any(zero_tardy(p) for p in permutations(g)) for g in groups):
                return k
    return None


def reference_sequence_cost(instance, seq, free_at0=0, prev0=None):
    """Unabhängige Nachrechnung von sequence_cost_from (dieselbe Formel, separat getippt)."""
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
    return weighted * 100_000 + empty
