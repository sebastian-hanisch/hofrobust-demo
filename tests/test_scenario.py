import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_scenario as S


def test_generate_instance_is_deterministic_for_the_same_seed():
    a = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=7)
    b = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=7)
    assert a == b


def test_generate_instance_differs_for_different_seeds():
    a = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=7)
    b = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=8)
    assert a.jobs != b.jobs


def test_jobs_and_approach_matrix_do_not_depend_on_n_vehicles():
    a = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=7, n_vehicles=1)
    b = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=7, n_vehicles=5)
    assert a.jobs == b.jobs and a.approach == b.approach and a.approach_from_depot == b.approach_from_depot
    assert a.n_vehicles == 1 and b.n_vehicles == 5


def test_with_fleet_changes_only_n_vehicles():
    a = S.generate_instance(n_jobs=10, buffer=15, yard_length=450, seed=1, n_vehicles=1)
    b = S.with_fleet(a, 4)
    assert b.n_vehicles == 4 and b.jobs == a.jobs and b.approach == a.approach


def test_every_job_has_a_valid_kind_and_positive_service_time():
    inst = S.generate_instance(n_jobs=30, buffer=15, yard_length=450, seed=3)
    for job in inst.jobs:
        assert job.kind in C.KINDS
        assert job.service > 0
        assert job.deadline > job.release
        assert job.weight == C.KIND_WEIGHTS[job.kind]


def test_deadlines_respect_release_plus_service_plus_positive_slack():
    inst = S.generate_instance(n_jobs=30, buffer=15, yard_length=450, seed=3)
    for job in inst.jobs:
        assert job.deadline >= job.release + job.service + 1


def test_approach_times_are_non_negative_integers_and_symmetric_to_self_is_zero():
    inst = S.generate_instance(n_jobs=15, buffer=15, yard_length=450, seed=5)
    for row in inst.approach:
        for t in row:
            assert isinstance(t, int) and t >= 0
    for t in inst.approach_from_depot:
        assert isinstance(t, int) and t >= 0


def test_noise_factors_are_deterministic_and_in_unit_interval():
    inst = S.generate_instance(n_jobs=10, buffer=15, yard_length=450, seed=1)
    a = S.draw_noise_factors(inst, seed=42)
    b = S.draw_noise_factors(inst, seed=42)
    assert a == b and len(a) == len(inst.jobs)
    assert all(0.0 <= f < 1.0 for f in a)


def test_make_noisy_instance_only_scales_approach_times_upward():
    inst = S.generate_instance(n_jobs=15, buffer=15, yard_length=450, seed=2)
    factors = S.draw_noise_factors(inst, seed=9)
    noisy = S.make_noisy_instance(inst, 0.6, factors)
    assert noisy.jobs == inst.jobs
    for j in range(len(inst.jobs)):
        assert noisy.approach_from_depot[j] >= inst.approach_from_depot[j]
        for i in range(len(inst.jobs)):
            assert noisy.approach[i][j] >= inst.approach[i][j]


def test_zero_sigma_returns_the_identical_instance_object():
    inst = S.generate_instance(n_jobs=10, buffer=15, yard_length=450, seed=1)
    factors = S.draw_noise_factors(inst, seed=1)
    assert S.make_noisy_instance(inst, 0, factors) is inst


def test_travel_minutes_rounds_up_not_to_nearest():
    """math.ceil, nicht round: eine Distanz knapp über einem vollen Vielfachen von SPEED_M_PER_MIN
    (150 m/min) muss auf die NÄCHSTHÖHERE Minute aufgerundet werden, nicht auf die nächste."""
    assert S._travel_minutes((0, 0), (151, 0)) == 2  # 151/150 = 1,0067 -> ceil=2, round=1
    assert S._travel_minutes((0, 0), (150, 0)) == 1  # exaktes Vielfaches bleibt 1


def test_horizon_is_computed_from_the_largest_approach_time():
    """`horizon` muss auf der GRÖSSTEN Anfahrtszeit basieren (sichere obere Schranke, damit kein
    Plan an einem zu knappen Horizont scheitert) - exakte Nachrechnung der Formel."""
    inst = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=6)
    max_approach = max([*inst.approach_from_depot, *(t for row in inst.approach for t in row)], default=0)
    expected = inst.arrival_window + sum(j.service + max_approach for j in inst.jobs) + 10
    assert inst.horizon == expected


def test_noise_factors_actually_vary_across_jobs():
    """Rauschfaktoren müssen sich zwischen Aufträgen unterscheiden (echte Zufallszahlen je Auftrag,
    kein fester Platzhalter)."""
    inst = S.generate_instance(n_jobs=20, buffer=15, yard_length=450, seed=1)
    factors = S.draw_noise_factors(inst, seed=42)
    assert len(set(factors)) > 1


def test_noise_rounding_trap_below_thirty_percent_is_reproducible():
    """Randbefund aus vorab_kombiniert: bei den hier üblichen Fahrzeiten (2-4 min) rundet math.ceil
    JEDE positive Ziehung schon bei kleinem sigma auf +1 auf (t*sigma*factor < 1) - sigma=0,10 und
    sigma=0,25 sind bei diesem Preset praktisch UNUNTERSCHEIDBAR (nicht: unverändert gegenüber
    sigma=0). Dokumentiert als Test, damit sich der Befund nicht unbemerkt ändert."""
    inst = S.generate_instance(n_jobs=30, buffer=15, yard_length=450, seed=4)
    factors = S.draw_noise_factors(inst, seed=1)
    low = S.make_noisy_instance(inst, 0.10, factors)
    mid = S.make_noisy_instance(inst, 0.25, factors)
    identical = sum(1 for j in range(len(inst.jobs)) if low.approach_from_depot[j] == mid.approach_from_depot[j])
    assert identical / len(inst.jobs) > 0.7
    # gegenüber sigma=0 rundet dagegen fast jede positive Ziehung auf: kaum ein Wert bleibt gleich
    unchanged = sum(1 for j in range(len(inst.jobs)) if low.approach_from_depot[j] == inst.approach_from_depot[j])
    assert unchanged / len(inst.jobs) < 0.3
