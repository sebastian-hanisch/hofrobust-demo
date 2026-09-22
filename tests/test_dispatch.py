import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_dispatch as D
import hrb_evaluation as E
import hrb_scenario as S
from helpers import reference_sequence_cost, tiny_instance  # noqa: E402

INSTANCES = [S.generate_instance(n_jobs=n, buffer=15, yard_length=450, seed=s, n_vehicles=v)
            for n, s, v in [(12, 1, 2), (20, 3, 3), (30, 9, 3), (16, 5, 1)]]


# ---------------------------------------------------------------------------------------------------
# Regressionstest: die "_from"-Erweiterung muss bei (0, None) exakt die Originalfunktionen reproduzieren
# (Plan Abschnitt 11: "Variabler Startzustand gegen den yard-demo-Fixpunkt").
# ---------------------------------------------------------------------------------------------------
def test_sequence_cost_from_at_zero_matches_sequence_cost():
    inst = INSTANCES[2]
    seq = list(range(0, 10))
    assert D.sequence_cost_from(inst, seq, 0, None) == E.sequence_cost(inst, seq)


def test_sequence_plan_from_at_zero_matches_sequences_to_plan_for_one_vehicle():
    inst = INSTANCES[0]
    seq = [j.index for j in inst.jobs if j.index % inst.n_vehicles == 0]
    plan_from = D.sequence_plan_from(inst, seq, 0, None, 0)
    plan_ref = E.sequences_to_plan(inst, [seq])
    assert plan_from == plan_ref


def test_local_search_from_at_zero_matches_local_search():
    inst = INSTANCES[1]
    start = [D.dispatch_fifo(inst)[1]][0]
    got = D.local_search_from(inst, start, [0] * inst.n_vehicles, [None] * inst.n_vehicles)
    want = D.local_search(inst, start)
    got_cost = sum(E.sequence_cost(inst, s) for s in got)
    want_cost = sum(E.sequence_cost(inst, s) for s in want)
    assert got_cost == want_cost  # dieselbe (optimale) Kostensumme; Reihenfolge unter Gleichstand kann variieren


def test_sequence_cost_from_treats_ending_exactly_at_the_deadline_as_on_time():
    inst = tiny_instance()  # J1: release=0, deadline=14, service=5, Anfahrtszeiten=0
    # Start bei 9: Ende 9+5=14 == Frist -> pünktlich, kein Verspätungsanteil.
    cost = D.sequence_cost_from(inst, [1], free_at0=9, prev0=None)
    assert cost == 0  # nur pünktlich möglich: kein OBJ_BIG-Anteil, keine Leerfahrt (Anfahrt=0)


def test_reference_sequence_cost_matches_the_module_for_a_variable_start():
    inst = INSTANCES[2]
    seq = [3, 7, 11]
    for free0, prev0 in ((0, None), (25, 7), (100, None)):
        assert D.sequence_cost_from(inst, seq, free0, prev0) == reference_sequence_cost(inst, seq, free0, prev0)


# ---------------------------------------------------------------------------------------------------
# Online-Regeln: jeder Plan ist machbar (feasible), deterministisch, jeder Auftrag genau einmal
# ---------------------------------------------------------------------------------------------------
def test_online_rules_produce_feasible_and_deterministic_plans():
    for inst in INSTANCES:
        for dispatch in (D.dispatch_fifo, D.dispatch_edd, D.dispatch_atc):
            plan1, seqs1 = dispatch(inst)
            plan2, _ = dispatch(inst)
            assert plan1 == plan2
            ok, violations = E.check_feasible(inst, plan1)
            assert ok, violations
            assert set(plan1) == {j.index for j in inst.jobs}
            assert sum(len(s) for s in seqs1) == len(inst.jobs)


def test_dispatch_disrupted_with_zero_duration_matches_undisrupted_choose():
    inst = INSTANCES[1]
    plan_a, _ = D.dispatch_disrupted(inst, D.choose_fifo, 0, 5, 5)  # leeres Fenster
    plan_b, _ = D.dispatch_fifo(inst)
    assert plan_a == plan_b


def test_down_treats_the_start_of_the_window_as_broken_but_not_the_end():
    """Halboffenes Fenster [bstart, bend): bei bstart selbst ist das Fahrzeug schon kaputt, bei
    bend schon wieder frei."""
    inst = tiny_instance()
    plan, seqs = D.dispatch_disrupted(inst, D.choose_fifo, broken_vehicle=0, bstart=0, bend=5)
    # Fahrzeug 0 darf ab t=0 nichts annehmen (kaputt) - alle drei Aufträge müssen an Fahrzeug 1 gehen
    # oder erst ab t=5 an Fahrzeug 0 starten.
    for idx, (v, start) in plan.items():
        assert not (v == 0 and 0 <= start < 5)


def test_the_broken_vehicle_starts_no_job_inside_its_window():
    inst = INSTANCES[2]
    broken, bstart, bend = 1, 10, 60
    plan, _ = D.dispatch_disrupted(inst, D.choose_edd, broken, bstart, bend)
    for idx, (v, start) in plan.items():
        if v == broken:
            assert not (bstart <= start < bend)


# ---------------------------------------------------------------------------------------------------
# Vorausplanung: lokale Suche verbessert nie, ILS ist nie schlechter als ihr Start
# ---------------------------------------------------------------------------------------------------
def test_local_search_never_worsens_the_starting_sequences():
    inst = INSTANCES[2]
    start = D.dispatch_fifo(inst)[1]
    start_cost = sum(E.sequence_cost(inst, s) for s in start)
    improved = D.local_search(inst, start)
    improved_cost = sum(E.sequence_cost(inst, s) for s in improved)
    assert improved_cost <= start_cost


def test_improve_plan_is_feasible_and_reproducible():
    inst = INSTANCES[2]
    plan_a, seqs_a = D.improve_plan(inst)
    plan_b, seqs_b = D.improve_plan(inst)
    assert plan_a == plan_b and seqs_a == seqs_b
    ok, violations = E.check_feasible(inst, plan_a)
    assert ok, violations


def test_improve_plan_is_never_worse_than_the_best_single_rule():
    inst = INSTANCES[1]
    plan, _ = D.improve_plan(inst, iterations=5)
    wt_plan = E.evaluate(inst, plan)["total_weighted_tardiness"]
    best_rule = min(E.evaluate(inst, fn(inst)[0])["total_weighted_tardiness"] for fn in (D.dispatch_fifo, D.dispatch_edd, D.dispatch_atc))
    assert wt_plan <= best_rule


# ---------------------------------------------------------------------------------------------------
# Handrechnung (Grenzfall): 3-Auftrags-Instanz, Anfahrtszeiten = 0
# ---------------------------------------------------------------------------------------------------
def test_dispatch_fifo_on_the_tiny_hand_checked_instance():
    inst = tiny_instance()
    plan, seqs = D.dispatch_fifo(inst)
    assert plan[0] == (0, 0) and plan[1] == (1, 0) and plan[2] == (0, 5)
    assert E.evaluate(inst, plan)["total_weighted_tardiness"] == 0


def test_choose_edd_picks_the_smallest_deadline_not_the_largest():
    """EDD = 'Frist zuerst': unter mehreren verfügbaren Aufträgen muss die KLEINSTE Frist gewinnen."""
    inst = tiny_instance()  # J0 deadline=100, J1 deadline=14, J2 deadline=100
    v, j = D.choose_edd(inst, t=0, idle=[0, 1], avail=[0, 1, 2], loc=[None, None])
    assert j == 1  # J1 hat die früheste Frist (14)


def test_dispatch_edd_serves_the_tightest_deadline_first_on_a_larger_instance():
    inst = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=3, n_vehicles=1)
    plan, seqs = D.dispatch_edd(inst)
    deadlines_in_order = [inst.jobs[j].deadline for j in seqs[0]]
    # Innerhalb des jeweils zum Startzeitpunkt verfügbaren Fensters muss die Reihenfolge nach Frist
    # monoton sein für die ersten paar Aufträge, deren Freigabe <= 0 ist (alle gleichzeitig verfügbar).
    first_batch = [inst.jobs[j].deadline for j in seqs[0] if inst.jobs[j].release == 0]
    assert first_batch == sorted(first_batch)
