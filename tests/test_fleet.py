import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_fleet as F
import hrb_scenario as S
from helpers import brute_force_min_fleet  # noqa: E402


def _pair_instance(release0, service0, deadline0, release1, service1, deadline1, approach01):
    """Zwei Aufträge, Anfahrtszeiten frei wählbar (approach[0][1] = approach01, Rest 0) - für die
    exakte Grenzfallprüfung von `_optimistic_can_follow` (kein Bezug zu generate_instance)."""
    import hrb_scenario as SC

    jobs = (
        SC.Job(index=0, name="J0", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
              release=release0, deadline=deadline0, service=service0, weight=1),
        SC.Job(index=1, name="J1", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
              release=release1, deadline=deadline1, service=service1, weight=1),
    )
    return SC.Instance(jobs=jobs, n_vehicles=1, yard_length=100, yard_width=100, depot_xy=(0, 0), doors=(),
                       arrival_window=20, approach_from_depot=(0, 0), approach=((0, approach01), (0, 0)), horizon=200)

TINY_SEEDS = range(500, 512)


def _tiny_args(seed):
    return dict(n_jobs=5, buffer=6, yard_length=200, seed=seed, arrival_window=40, peak_pct=50, departure_pct=40, n_doors=3)


def test_practical_minimum_matches_brute_force_on_tiny_instances():
    for seed in TINY_SEEDS:
        base = S.generate_instance(n_vehicles=1, **_tiny_args(seed))
        practical, _ = F.practical_min_fleet(base, max_k=5)
        bf = brute_force_min_fleet(base, max_k=5)
        assert practical == bf, (seed, practical, bf)


def test_matching_lower_bound_never_exceeds_the_brute_force_minimum():
    """Notwendige, nicht hinreichende Bedingung: darf zu niedrig sein, nie zu hoch (Plan Abschnitt 11)."""
    for seed in TINY_SEEDS:
        base = S.generate_instance(n_vehicles=1, **_tiny_args(seed))
        lb = F.matching_lower_bound(base)
        bf = brute_force_min_fleet(base, max_k=5)
        assert lb <= bf, (seed, lb, bf)


def test_matching_lower_bound_never_exceeds_the_practical_minimum_on_larger_instances():
    for seed in range(600, 610):
        base = S.generate_instance(n_jobs=30, buffer=15, yard_length=450, seed=seed, n_vehicles=1)
        kmin, _ = F.practical_min_fleet(base)
        lb = F.matching_lower_bound(base)
        assert lb <= kmin, (seed, lb, kmin)


# ---------------------------------------------------------------------------------------------------
# Grenzfälle bitgleich: die Formel von `_optimistic_can_follow` selbst, Term für Term isoliert
# (frühestes Ende von j = release + service, spätester Start von k = deadline - service, <=)
# ---------------------------------------------------------------------------------------------------
def test_optimistic_can_follow_is_true_exactly_at_the_boundary():
    # frühestes Ende von J0 = 0+5=5, +Anfahrt 2 = 7; spätester Start von J1 = 10-3 = 7 -> 7 <= 7
    inst = _pair_instance(release0=0, service0=5, deadline0=100, release1=0, service1=3, deadline1=10, approach01=2)
    assert F._optimistic_can_follow(inst, 0, 1) is True


def test_optimistic_can_follow_is_false_one_minute_past_the_boundary():
    inst = _pair_instance(release0=0, service0=6, deadline0=100, release1=0, service1=3, deadline1=10, approach01=2)
    assert F._optimistic_can_follow(inst, 0, 1) is False  # 0+6+2=8 > 10-3=7


def test_optimistic_can_follow_uses_the_full_service_time_of_j():
    # Mit Servicezeit von J0 (8) ist es zu spät (0+8+2=10 > 7); ohne sie (nur release=0) wäre 0+2=2 <= 7.
    inst = _pair_instance(release0=0, service0=8, deadline0=100, release1=0, service1=3, deadline1=10, approach01=2)
    assert F._optimistic_can_follow(inst, 0, 1) is False


def test_optimistic_can_follow_uses_the_full_service_time_of_k():
    # Mit Servicezeit von J1 (2) ist der späteste Start 4-2=2, 0+2+1=3 > 2 -> False; ohne sie (nur
    # deadline=4) wäre 3 <= 4 -> True.
    inst = _pair_instance(release0=0, service0=2, deadline0=100, release1=0, service1=2, deadline1=4, approach01=1)
    assert F._optimistic_can_follow(inst, 0, 1) is False


def test_max_matching_on_a_hand_built_bipartite_graph():
    # 0->{1,2}, 1->{2}, 2->{} : größtes Matching hat Größe 2 (z. B. 0->1, 1->2)
    adj = [[1, 2], [2], []]
    size, match_to = F.max_matching(3, adj)
    assert size == 2


def test_practical_min_fleet_returns_none_when_max_k_is_too_small():
    base = S.generate_instance(n_jobs=30, buffer=1, yard_length=900, seed=1, n_vehicles=1, arrival_window=300, peak_pct=100)
    kmin, inst = F.practical_min_fleet(base, max_k=1)
    if kmin is None:
        assert inst is None
    else:
        assert kmin == 1  # falls schon 1 Fahrzeug reicht, ist der Test trivial erfüllt


def test_cp_sat_cross_check_finds_zero_at_the_practical_minimum_on_a_small_instance():
    base = S.generate_instance(**_tiny_args(500), n_vehicles=1)
    result = F.cross_check(base)
    assert result is not None
    assert result["wt_at_min"] == 0


def test_best_weighted_tardiness_total_takes_the_best_of_fifo_edd_atc_not_the_worst():
    """Unabhängige Nachrechnung: das Minimum über FIFO/EDD/ATC (und die Vorausplanung) - ein
    Umdrehen zu 'Maximum' in der Regel-Schleife darf das Ergebnis nicht verschlechtern."""
    import hrb_dispatch as D
    import hrb_evaluation as E

    for seed in (501, 503, 507):
        inst = S.generate_instance(n_jobs=8, buffer=6, yard_length=250, seed=seed, n_vehicles=1,
                                   arrival_window=40, peak_pct=50, departure_pct=40, n_doors=3)
        rule_values = []
        for dispatch in (D.dispatch_fifo, D.dispatch_edd, D.dispatch_atc):
            plan, _ = dispatch(inst)
            rule_values.append(E.evaluate(inst, plan)["total_weighted_tardiness"])
        plan, _ = D.improve_plan(inst)
        ils_value = E.evaluate(inst, plan)["total_weighted_tardiness"]
        expected = min(min(rule_values), ils_value)
        assert F.best_weighted_tardiness_total(inst) == expected, (seed, rule_values, ils_value)


def test_solve_exact_prefers_zero_tardiness_over_less_empty_travel():
    """CP-SAT-Lexikografie (feedback_cp_sat_lexicographic_tiebreak): gewichtete Verspätung muss VOR
    der Leerfahrtzeit entscheiden. Konstruierte 2-Auftrags-Instanz mit einem echten Zielkonflikt:
    - Depot -> A -> B: 5 min Leerfahrt gesamt, 0 Verspätung (A knapp rechtzeitig erreicht).
    - Depot -> B -> A: 0 min Leerfahrt gesamt, aber A kommt 4 min zu spät (B braucht lange Servicezeit).
    Ohne die OBJ_BIG-Gewichtung wäre der Pfad ohne Leerfahrt (aber mit Verspätung) günstiger
    (unnormiert: 0+1=1 gegen 5+0=5) - das ist genau der Fehler, den diese Konstruktion aufdeckt."""
    import hrb_scenario as SC

    jobs = (
        SC.Job(index=0, name="A", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="a", drop_label="a",
              release=0, deadline=7, service=1, weight=1),
        SC.Job(index=1, name="B", kind="Abräumen", pick_xy=(0, 0), drop_xy=(0, 0), pick_label="b", drop_label="b",
              release=0, deadline=1000, service=10, weight=1),
    )
    inst = SC.Instance(jobs=jobs, n_vehicles=1, yard_length=100, yard_width=100, depot_xy=(0, 0), doors=(),
                       arrival_window=20, approach_from_depot=(5, 0), approach=((0, 0), (0, 0)), horizon=50)
    result = F.solve_exact(inst)
    assert result.feasible
    from hrb_evaluation import evaluate

    ev = evaluate(inst, result.plan)
    assert ev["total_weighted_tardiness"] == 0  # A darf nicht zu spät ankommen, auch wenn das mehr Leerfahrt kostet
