import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_evaluation as E
import hrb_visualization as V


def _day(disruption=C.DISRUPTION_AUSFALL, strength=40, delta=0, seed=3):
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    return E.compute_day(p, seed, delta, disruption, strength)


def test_gantt_figure_builds_for_every_strategy_under_failure():
    day = _day(C.DISRUPTION_AUSFALL, 40)
    for key in C.STRATEGY_KEYS:
        fig = V.gantt_figure(day, key, "Titel")
        assert len(fig.data) > 0


def test_gantt_figure_builds_for_every_strategy_under_noise():
    day = _day(C.DISRUPTION_RAUSCHEN, 0.5)
    for key in C.STRATEGY_KEYS:
        fig = V.gantt_figure(day, key, "Titel")
        assert len(fig.data) > 0


def test_gantt_figure_has_a_shape_when_there_is_a_failure_window():
    day = _day(C.DISRUPTION_AUSFALL, 40)
    fig = V.gantt_figure(day, C.S_STARR, "")
    assert day.failure is not None
    assert len(fig.layout.shapes) >= 1


def test_gantt_figure_has_no_failure_shape_without_disruption():
    day = _day(C.DISRUPTION_AUSFALL, 0)
    fig = V.gantt_figure(day, C.S_STARR, "")
    assert len(fig.layout.shapes) == 0


def test_winner_heatmap_builds_from_a_winner_table():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    table = E.winner_table(p, 3, 20, 0.25)
    fig = V.winner_heatmap(table)
    assert len(fig.data) == 1


def test_curve_figure_builds_for_both_disruption_kinds():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    for disruption in C.DISRUPTION_KINDS:
        points = E.strength_curve(p, 3, 0, disruption)
        fig = V.curve_figure(points, disruption)
        assert len(fig.data) == 3  # eine Linie je Strategie


def test_spread_and_distribution_figures_build_from_a_sample():
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    rows = E.sample(p, 0, C.DISRUPTION_AUSFALL, 30, n=5, base=800)
    assert len(rows) == 5
    fig1 = V.spread_figure(rows, "starr", "x")
    assert len(fig1.data) == 3
    fig2 = V.distribution_figure(rows, C.S_ONLINE, C.S_STARR, "online", "starr")
    assert len(fig2.data) == 3


def test_all_plotly_charts_lock_their_axes():
    day = _day(C.DISRUPTION_AUSFALL, 40)
    fig = V.gantt_figure(day, C.S_STARR, "")
    assert fig.layout.xaxis.fixedrange and fig.layout.yaxis.fixedrange
