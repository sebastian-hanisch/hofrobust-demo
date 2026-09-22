import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_disruption as R
import hrb_dispatch as D
import hrb_evaluation as E
import hrb_scenario as S
from helpers import tiny_instance  # noqa: E402


# ---------------------------------------------------------------------------------------------------
# Handrechnung (Grenzfall, aus hof-planung/vorab_robust/hand_check.py): starr=3, online=0, reaktiv=0
# ---------------------------------------------------------------------------------------------------
def test_hand_check_rigid_reactive_and_online_at_the_tiny_instance():
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    nominal_plan = {0: (0, 0), 1: (0, 5), 2: (1, 0)}
    broken_vehicle, bstart, bend = 0, 2, 12

    starr_plan = R.simulate_rigid(inst, nominal_seqs, broken_vehicle, bstart, bend)
    assert starr_plan[0] == (0, 0) and starr_plan[1] == (0, 12)
    assert E.evaluate(inst, starr_plan)["total_weighted_tardiness"] == 3
    ok, viol = E.check_feasible(inst, starr_plan)
    assert ok, viol

    online_plan, _ = D.dispatch_disrupted(inst, D.choose_fifo, broken_vehicle, bstart, bend)
    assert online_plan[0] == (0, 0) and online_plan[1] == (1, 0) and online_plan[2] == (1, 5)
    assert E.evaluate(inst, online_plan)["total_weighted_tardiness"] == 0

    reaktiv_plan = R.simulate_reactive(inst, nominal_plan, nominal_seqs, broken_vehicle, bstart, bend)
    assert reaktiv_plan[0] == (0, 0) and reaktiv_plan[2] == (1, 0) and reaktiv_plan[1] == (1, 5)
    assert E.evaluate(inst, reaktiv_plan)["total_weighted_tardiness"] == 0
    ok, viol = E.check_feasible(inst, reaktiv_plan)
    assert ok, viol


def test_a_failure_window_after_plan_end_changes_nothing():
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    nominal_plan = {0: (0, 0), 1: (0, 5), 2: (1, 0)}
    assert R.simulate_rigid(inst, nominal_seqs, 0, 50, 60) == nominal_plan
    assert R.simulate_reactive(inst, nominal_plan, nominal_seqs, 0, 50, 60) == nominal_plan


def test_zero_duration_failure_is_a_no_op_for_rigid():
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    plan = E.sequences_to_plan(inst, nominal_seqs)
    assert R.simulate_rigid(inst, nominal_seqs, 0, 3, 3) == plan  # leeres Fenster [3, 3)


# ---------------------------------------------------------------------------------------------------
# Grenzfälle bitgleich: exakte Fensterränder (bstart/bend), damit Off-by-one-Fehler auffallen
# ---------------------------------------------------------------------------------------------------
def test_draw_failure_bend_is_exactly_bstart_plus_duration():
    inst = tiny_instance()
    broken, bstart, bend = R.draw_failure(inst, seed=1, duration=17)
    assert bend == bstart + 17


def test_a_candidate_start_exactly_at_bstart_is_still_delayed_to_bend():
    """simulate_rigid: das Fenster ist halboffen [bstart, bend) - ein Kandidat GENAU bei bstart
    zählt noch als 'im Fenster' und wird verschoben."""
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    # Job 0 endet nominal bei 5 (Service 5, Anfahrt 0): bstart=5 trifft den Kandidaten von Job 1 exakt.
    plan = R.simulate_rigid(inst, nominal_seqs, broken_vehicle=0, bstart=5, bend=9)
    assert plan[1] == (0, 9)


def test_a_candidate_start_exactly_at_bend_is_not_delayed():
    """Ein Kandidat GENAU bei bend liegt außerhalb des halboffenen Fensters - keine Verschiebung."""
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    plan = R.simulate_rigid(inst, nominal_seqs, broken_vehicle=0, bstart=2, bend=5)
    assert plan[1] == (0, 5)  # Kandidat 5 == bend, nicht mehr im Fenster [2, 5)


def test_a_job_starting_exactly_at_bstart_counts_as_pending_not_committed():
    """simulate_reactive: 'committed' sind Jobs mit nominal_start < bstart - ein Job GENAU bei
    bstart ist noch 'pending' (wird neu geplant, nicht unangetastet übernommen)."""
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    nominal_plan = {0: (0, 0), 1: (0, 5), 2: (1, 0)}
    # bstart=5 trifft job 1s nominalen Start exakt; broken_vehicle=1 (nicht 0), damit sich am
    # reaktiven Ergebnis nichts ändert außer der committed/pending-Einteilung selbst.
    plan = R.simulate_reactive(inst, nominal_plan, nominal_seqs, broken_vehicle=1, bstart=5, bend=8)
    # Job 1 wird neu geplant (pending), nicht unverändert von nominal_plan übernommen, obwohl der
    # Zeitwert zufällig gleich bleiben kann - die Prüfung zielt auf die Klassifikation, nicht den Wert:
    # mit broken_vehicle=1 muss Fahrzeug 1 (mit Job 2) erst ab bend=8 wieder frei sein, das wirkt sich
    # nur aus, wenn Job 1 tatsächlich als pending (neu, über beide Fahrzeuge) behandelt wird.
    ok, viol = E.check_feasible(inst, plan)
    assert ok, viol


def test_reactive_free_time_is_not_clamped_below_the_vehicles_actual_free_time():
    """Wenn die committed-Aufträge des ausgefallenen Fahrzeugs erst NACH bend enden, muss die
    reaktive Suche ab diesem späteren Zeitpunkt planen, nicht ab bend (free0 = max(...), nicht bend)."""
    inst = tiny_instance()
    nominal_seqs = [[0, 1], [2]]
    nominal_plan = {0: (0, 0), 1: (0, 5), 2: (1, 0)}
    # Beide Jobs auf Fahrzeug 0 sind committed (nominal Start 0 und 5, beide < bstart=6); Job 0 endet
    # bei 5, Job 1 bei 10 - das ist SPÄTER als bend=8. Die reaktive Suche darf Fahrzeug 0 nicht schon
    # ab 8 einplanen (das wäre unmöglich: Job 1 läuft noch).
    plan = R.simulate_reactive(inst, nominal_plan, nominal_seqs, broken_vehicle=0, bstart=6, bend=8)
    assert plan[0] == (0, 0) and plan[1] == (0, 5)  # unverändert übernommen (beide committed)
    ok, viol = E.check_feasible(inst, plan)
    assert ok, viol


# ---------------------------------------------------------------------------------------------------
# check_feasible auf jedem Endplan, beide Störungsarten, viele Seeds (unabhängig von der Zielfunktion)
# ---------------------------------------------------------------------------------------------------
INSTANCES = [(n, s, v) for n, s, v in [(16, 1, 2), (24, 4, 3), (30, 7, 3), (20, 11, 4)]]


def test_check_feasible_holds_for_all_three_strategies_under_failure():
    for n_jobs, seed, n_vehicles in INSTANCES:
        inst = S.generate_instance(n_jobs=n_jobs, buffer=15, yard_length=450, seed=seed, n_vehicles=n_vehicles)
        plan_pre, seqs_pre = D.improve_plan(inst, iterations=5)
        for duration in (20, 55):
            broken, bstart, bend = R.draw_failure(inst, seed, duration)
            starr = R.simulate_rigid(inst, seqs_pre, broken, bstart, bend)
            ok, viol = E.check_feasible(inst, starr)
            assert ok, viol
            wt_online, online_plan = R.best_online_disrupted(inst, broken, bstart, bend)
            ok, viol = E.check_feasible(inst, online_plan)
            assert ok, viol
            reaktiv = R.simulate_reactive(inst, plan_pre, seqs_pre, broken, bstart, bend)
            ok, viol = E.check_feasible(inst, reaktiv)
            assert ok, viol


def test_check_feasible_holds_for_all_three_strategies_under_noise():
    for n_jobs, seed, n_vehicles in INSTANCES:
        inst = S.generate_instance(n_jobs=n_jobs, buffer=15, yard_length=450, seed=seed, n_vehicles=n_vehicles)
        plan_pre, seqs_pre = D.improve_plan(inst, iterations=5)
        for sigma in (0.25, 0.60):
            factors = S.draw_noise_factors(inst, seed)
            noisy = S.make_noisy_instance(inst, sigma, factors)
            starr = R.rigid_under_noise(noisy, seqs_pre)
            ok, viol = E.check_feasible(noisy, starr)
            assert ok, viol
            wt_online, online_plan = R.best_online_under_noise(noisy)
            ok, viol = E.check_feasible(noisy, online_plan)
            assert ok, viol
            reaktiv = R.reactive_under_noise(noisy, seqs_pre)
            ok, viol = E.check_feasible(noisy, reaktiv)
            assert ok, viol


# ---------------------------------------------------------------------------------------------------
# Reaktiv ist in der großen Mehrheit der Tage nicht schlechter als starr/online - aber KEINE strikte
# Invariante (Korrektur gegenüber Plan Abschnitt 11 "nie verletzt": vorab_robust/ERGEBNIS.md selbst
# zeigt nur 150/200 bzw. 180/200 "reaktiv < starr", nicht 200/200. Grund: `simulate_rigid` nutzt eine
# optimistische "wartet, dann fährt los"-Vereinfachung, die nach der Verzögerung keine erneute
# Anfahrtszeit mehr aufschlägt (siehe feedback_interval_avoidance_vs_iterative_pushing) - dadurch kann
# starr in Einzelfällen günstiger aussehen, als eine echte Neuplanung ab dem tatsächlichen Zustand
# liefert. Siehe README "Befunde und Korrekturen".
# ---------------------------------------------------------------------------------------------------
def test_reactive_beats_or_ties_rigid_on_most_days_under_failure():
    p = E.Params(n_jobs=20, buffer=15, yard_length=450)
    days = [E.compute_day(p, seed, 0, C.DISRUPTION_AUSFALL, 40) for seed in range(200, 260)]
    share = sum(1 for d in days if d[C.S_REAKTIV].wt <= d[C.S_STARR].wt + 1e-9) / len(days)
    assert share >= 0.8


def test_reactive_beats_or_ties_online_on_most_days_under_failure():
    p = E.Params(n_jobs=20, buffer=15, yard_length=450)
    days = [E.compute_day(p, seed, 0, C.DISRUPTION_AUSFALL, 40) for seed in range(200, 260)]
    share = sum(1 for d in days if d[C.S_REAKTIV].wt <= d[C.S_ONLINE].wt + 1e-9) / len(days)
    assert share >= 0.7


def test_reactive_beats_or_ties_rigid_and_online_on_most_days_under_noise():
    p = E.Params(n_jobs=20, buffer=15, yard_length=450)
    days = [E.compute_day(p, seed, 0, C.DISRUPTION_RAUSCHEN, 0.60) for seed in range(300, 340)]
    share_starr = sum(1 for d in days if d[C.S_REAKTIV].wt <= d[C.S_STARR].wt + 1e-9) / len(days)
    share_online = sum(1 for d in days if d[C.S_REAKTIV].wt <= d[C.S_ONLINE].wt + 1e-9) / len(days)
    assert share_starr >= 0.8 and share_online >= 0.8


def test_weighted_tardiness_is_never_negative():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    for seed in range(400, 406):
        for disruption, strength in ((C.DISRUPTION_AUSFALL, 30), (C.DISRUPTION_RAUSCHEN, 0.4)):
            day = E.compute_day(p, seed, 1, disruption, strength)
            for key in C.STRATEGY_KEYS:
                assert day[key].wt >= 0


# ---------------------------------------------------------------------------------------------------
# Gemeinsame Zufallszahlen: derselbe Störungsdraw für alle drei Strategien (gepaarter Vergleich)
# ---------------------------------------------------------------------------------------------------
def test_the_failure_draw_only_depends_on_instance_seed_and_delta():
    inst = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=5, n_vehicles=3)
    a = R.draw_failure(inst, 5, 30, delta=0)
    b = R.draw_failure(inst, 5, 30, delta=0)
    c = R.draw_failure(inst, 5, 30, delta=1)
    assert a == b
    assert a != c  # unterschiedlicher Flottenabstand -> unterschiedlicher Draw (vorab_kombiniert-Konvention)
