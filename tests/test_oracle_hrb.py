"""Unabhängige Orakel (anderer Rechenweg als der Demo-Code), klein und schnell.

* Kleinste Flotte ohne Verspätung: Teilmengen-DP über früheste Kettenenden (statt Zuordnungs-/Permutationsenumeration und statt
  Heuristik/Matching): praktisches Minimum und Matching-Untergrenze müssen sie von oben bzw. unten einschließen.
* Online-Regeln FIFO/EDD/ATC (auch mit Fahrzeugausfall): Minutenschritt-Simulation statt Ereignissprüngen.
* Starrer Plan unter Ausfall und Rauschen: Neuausführung je Fahrzeug von Hand.
"""

import math
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C  # noqa: E402
import hrb_dispatch as D  # noqa: E402
import hrb_disruption as DI  # noqa: E402
import hrb_fleet as F  # noqa: E402
import hrb_scenario as S  # noqa: E402

INF = float("inf")


def _tiny(rng, n):
    return S.generate_instance(n_jobs=n, buffer=rng.choice([3, 6, 10, 15]), yard_length=rng.choice([200, 300, 450]), seed=rng.randint(0, 10 ** 6),
                               n_vehicles=rng.randint(1, 3), arrival_window=rng.choice([10, 40, 120]), peak_pct=rng.choice([0, 50, 90]),
                               departure_pct=rng.choice([20, 45, 70]), n_doors=rng.choice([2, 3, 10]))


def _min_fleet_dp(inst):
    """g[(Teilmenge, letzter)] = frühestes Ende einer verspätungsfreien Kette über genau diese Teilmenge; dann Minimum über Zerlegungen."""
    n = len(inst.jobs)
    full = (1 << n) - 1
    g = {}
    for j, job in enumerate(inst.jobs):
        end = max(job.release, inst.approach_from_depot[j]) + job.service
        if end <= job.deadline:
            g[(1 << j, j)] = end
    for mask in range(1, full + 1):
        for j in range(n):
            if (mask, j) not in g:
                continue
            for k, job in enumerate(inst.jobs):
                if mask >> k & 1:
                    continue
                end = max(job.release, g[(mask, j)] + inst.approach[j][k]) + job.service
                if end <= job.deadline and end < g.get((mask | 1 << k, k), INF):
                    g[(mask | 1 << k, k)] = end
    chains = {m for m, _ in g}
    best = [INF] * (full + 1)
    best[0] = 0
    for mask in range(1, full + 1):
        sub = mask
        while sub:
            if sub in chains:
                best[mask] = min(best[mask], best[mask ^ sub] + 1)
            sub = (sub - 1) & mask
    return best[full]


def _minute_dispatch(inst, rule, broken=None, bstart=0, bend=0):
    jobs, m = inst.jobs, inst.n_vehicles
    free_at, loc, plan, left = [0] * m, [None] * m, {}, set(range(len(jobs)))
    mean_service = sum(j.service for j in jobs) / len(jobs)
    t = 0
    while left:
        while True:
            idle = [v for v in range(m) if free_at[v] <= t and not (v == broken and bstart <= t < bend)]
            avail = sorted(j for j in left if jobs[j].release <= t)
            if not idle or not avail:
                break
            if rule == "atc":
                best = None
                for j in avail:
                    for v in idle:
                        tau = inst.approach_time(loc[v], j)
                        slack = jobs[j].deadline - (t + tau + jobs[j].service)
                        index = jobs[j].weight / (jobs[j].service + tau) * math.exp(-max(0, slack) / (C.ATC_K * mean_service))
                        best = min(best or (INF, 0, 0), (-index, j, v))
                j, v = best[1], best[2]
            else:
                j = min(avail, key=lambda a: ((jobs[a].release if rule == "fifo" else jobs[a].deadline), a))
                v = min(idle, key=lambda vv: (inst.approach_time(loc[vv], j), vv))
            start = t + inst.approach_time(loc[v], j)
            plan[j] = (v, start)
            free_at[v], loc[v] = start + jobs[j].service, j
            left.remove(j)
        t += 1
    return plan


def test_min_fleet_dp_hand_case():
    from helpers import tiny_instance
    inst = tiny_instance()                   # 3 Aufträge je 5 min, Anfahrt 0, Frist von J1 = 14: Reihenfolge J1, J0, J2 endet bei 5/10/15
    assert _min_fleet_dp(inst) == 1
    tight = S.Instance(**{**inst.__dict__, "jobs": tuple(S.Job(**{**j.__dict__, "deadline": 5}) for j in inst.jobs)})
    assert _min_fleet_dp(tight) == 3         # alle drei müssen bis Minute 5 fertig sein: nur parallel


def test_practical_minimum_and_matching_bound_bracket_the_true_minimum():
    rng = random.Random(41)
    for _ in range(25):
        inst = _tiny(rng, rng.randint(3, 7))
        exact = _min_fleet_dp(inst)
        practical, _ = F.practical_min_fleet(inst, max_k=8)
        if exact == INF:
            assert practical is None
            continue
        assert practical is not None and practical >= exact
        assert F.matching_lower_bound(inst) <= exact


def test_online_rules_match_minute_by_minute_simulation_with_and_without_failure():
    rng = random.Random(42)
    for _ in range(25):
        inst = _tiny(rng, rng.randint(2, 12))
        broken, bstart = rng.randrange(inst.n_vehicles), rng.randint(0, 40)
        bend = bstart + rng.choice([0, 5, 20, 60])
        for rule, plain, choose in (("fifo", D.dispatch_fifo, D.choose_fifo), ("edd", D.dispatch_edd, D.choose_edd), ("atc", D.dispatch_atc, D.choose_atc)):
            assert plain(inst)[0] == _minute_dispatch(inst, rule)
            assert D.dispatch_disrupted(inst, choose, broken, bstart, bend)[0] == _minute_dispatch(inst, rule, broken, bstart, bend)


def test_rigid_plan_under_failure_and_noise_matches_manual_execution():
    rng = random.Random(43)
    for _ in range(25):
        inst = S.with_fleet(_tiny(rng, rng.randint(4, 12)), rng.randint(1, 3))
        _, seqs = D.improve_plan(inst, iterations=2)
        broken, bstart, bend = DI.draw_failure(inst, rng.randint(0, 99), rng.choice([0, 10, 30, 60]), rng.randint(0, 2))
        rigid = DI.simulate_rigid(inst, seqs, broken, bstart, bend)
        noisy = S.make_noisy_instance(inst, rng.choice([0.1, 0.3, 0.6]), S.draw_noise_factors(inst, rng.randint(0, 99)))
        rigid_noise = DI.rigid_under_noise(noisy, seqs)
        for v, seq in enumerate(seqs):
            t, prev, tn, prevn = 0, None, 0, None
            for j in seq:
                job = inst.jobs[j]
                candidate = max(job.release, t + inst.approach_time(prev, j))
                start = bend if (v == broken and bstart <= candidate < bend) else candidate
                assert rigid[j] == (v, start)
                t, prev = start + job.service, j
                start_n = max(job.release, tn + noisy.approach_time(prevn, j))
                assert rigid_noise[j] == (v, start_n)
                tn, prevn = start_n + job.service, j
