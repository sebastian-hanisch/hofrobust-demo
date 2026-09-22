"""Plotly-Figuren: Gantt je Fahrzeug (Störfenster/verrauschte Anfahrten markiert), Sieger-Tabelle,
Umschlagpunkt-Kurve, Verteilung/Spannweite der Stichprobe.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Legende
unten. Plotly wird erst in den Funktionen importiert, damit die reine Rechnung ohne Plotly testbar
bleibt (siehe feedback_plotly_fixedrange_convention)."""

import hrb_constants as C

LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _job_hover(instance, idx, info):
    job = instance.jobs[idx]
    late = f"<br><b>Verspätung: {info['tardiness']} min</b>" if info["tardiness"] > 0 else "<br>pünktlich"
    return (f"<b>Auftrag {idx + 1}</b> ({job.kind}, Gewicht {job.weight})<br>{job.pick_label} -> {job.drop_label}<br>"
           f"Freigabe {job.release} min | Start {info['start']} min | Ende {info['end']} min | Frist {job.deadline} min{late}")


def gantt_figure(day, strategy_key, title=""):
    """Gantt-Diagramm einer Strategie: Balken je Auftrag (Farbe nach Art), Leerfahrt grau, Frist als
    Dreieck. Bei Ausfall: Störfenster des betroffenen Fahrzeugs schraffiert. Bei Rauschen: Leerfahrt-
    Balken mit orangem Rand, wenn die tatsächliche Anfahrt länger als nominal war."""
    import plotly.graph_objects as go

    from hrb_evaluation import evaluate

    outcome = day[strategy_key]
    instance = outcome.instance
    result = evaluate(instance, outcome.plan)
    plan = result["plan"]
    bar_height = 0.55

    fig = go.Figure()
    if day.failure is not None:
        broken_vehicle, bstart, bend = day.failure
        if bend > bstart:
            fig.add_shape(type="rect", x0=bstart, x1=bend, y0=broken_vehicle - bar_height / 2 - 0.1,
                          y1=broken_vehicle + bar_height / 2 + 0.1, fillcolor="rgba(192,57,43,0.15)",
                          line=dict(color="rgba(192,57,43,0.5)", width=1, dash="dot"), layer="below")
            fig.add_annotation(x=(bstart + bend) / 2, y=broken_vehicle + bar_height / 2 + 0.22, showarrow=False,
                               text=f"Ausfall Fahrzeug {broken_vehicle + 1} ({bend - bstart:.0f} min)",
                               font=dict(size=9, color="#c0392b"))

    noisy_jobs = set()
    if day.noisy_instance is not None:
        by_vehicle = {}
        for idx, info in plan.items():
            by_vehicle.setdefault(info["vehicle"], []).append(idx)
        for v, idxs in by_vehicle.items():
            idxs.sort(key=lambda i: plan[i]["start"])
            prev = None
            for idx in idxs:
                nominal = day.instance.approach_time(prev, idx)
                actual = instance.approach_time(prev, idx)
                if actual > nominal:
                    noisy_jobs.add(idx)
                prev = idx

    approach_x, approach_base, approach_y, approach_hover, approach_line = [], [], [], [], []
    for idx, info in plan.items():
        if info["approach"] > 0:
            approach_x.append(info["approach"])
            approach_base.append(info["start"] - info["approach"])
            approach_y.append(info["vehicle"])
            noisy = idx in noisy_jobs
            approach_hover.append(f"Anfahrt zu Auftrag {idx + 1}: {info['approach']} min" + (" (verrauscht)" if noisy else ""))
            approach_line.append("#c77700" if noisy else "white")
    fig.add_trace(go.Bar(x=approach_x, base=approach_base, y=approach_y, orientation="h", name="Anfahrt", width=bar_height,
                         marker=dict(color="rgba(150,150,150,0.35)", line=dict(color=approach_line, width=2)),
                         hovertext=approach_hover, hoverinfo="text"))

    for kind in C.KINDS:
        idxs = [i for i, info in plan.items() if instance.jobs[i].kind == kind]
        if not idxs:
            continue
        fig.add_trace(go.Bar(x=[instance.jobs[i].service for i in idxs], base=[plan[i]["start"] for i in idxs],
                             y=[plan[i]["vehicle"] for i in idxs], orientation="h", name=kind, width=bar_height,
                             text=[str(i + 1) for i in idxs], textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="white", size=11),
                             marker=dict(color=C.KIND_COLORS[kind],
                                        line=dict(color=["#ff9800" if plan[i]["tardiness"] > 0 else "white" for i in idxs],
                                                  width=[3 if plan[i]["tardiness"] > 0 else 1 for i in idxs])),
                             hovertext=[_job_hover(instance, i, plan[i]) for i in idxs], hoverinfo="text"))

    x_max = max(result["makespan"], max((j.deadline for j in instance.jobs), default=1), 1)
    fig.update_layout(title=dict(text=title, font=dict(size=13), x=0.02), barmode="overlay", template="plotly_white",
                      height=130 + 60 * instance.n_vehicles, xaxis_title="Minuten ab Schichtbeginn",
                      legend=LEGEND_BOTTOM, margin=dict(t=36, b=90))
    fig.update_yaxes(tickmode="array", tickvals=list(range(instance.n_vehicles)),
                     ticktext=[f"Fahrzeug {v + 1}" for v in range(instance.n_vehicles)],
                     range=[instance.n_vehicles - 0.4, -0.55], showgrid=False)
    fig.update_xaxes(range=[0, x_max * 1.02])
    return _lock_axes(fig)


def winner_heatmap(table):
    """3 (Flottenabstand) x 2 (Störungsart) Zellen: starr/online/reaktiv als Text, Hintergrund nach
    wer gewinnt (starr gegen online - die Pointe des Plans; reaktiv separat genannt)."""
    import plotly.graph_objects as go

    rows_delta = [0, 1, 2]
    cols = [C.DISRUPTION_AUSFALL, C.DISRUPTION_RAUSCHEN]
    z, text = [], []
    for delta in rows_delta:
        zrow, trow = [], []
        for disruption in cols:
            cell = table.get((delta, disruption))
            if cell is None:
                zrow.append(0)
                trow.append("-")
                continue
            starr, online, reaktiv = cell
            score = 1 if online < starr - 1e-9 else (-1 if starr < online - 1e-9 else 0)
            zrow.append(score)
            trow.append(f"starr {starr:.2f}<br>online {online:.2f}<br>reaktiv {reaktiv:.2f}")
        z.append(zrow)
        text.append(trow)
    fig = go.Figure(go.Heatmap(z=z, x=[C.DISRUPTION_LABELS[d] for d in cols], y=[f"+{d}" if d else "Minimum" for d in rows_delta],
                               text=text, texttemplate="%{text}", textfont=dict(size=11),
                               colorscale=[[0, "#c0392b"], [0.5, "#8a94a3"], [1, "#2e7d4f"]], zmin=-1, zmax=1, showscale=False,
                               xgap=2, ygap=2, hovertemplate="%{y}, %{x}<br>%{text}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=280, margin=dict(t=15, b=15, l=10, r=8))
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


def curve_figure(points, disruption):
    """Gewichtete Verspätung über die Störstärke für starr/online/reaktiv (Umschlagpunkt-Kurve).
    `points[i].strength` ist bereits in der Anzeigeeinheit (Minuten bzw. Prozent), siehe
    hrb_evaluation.strength_curve - hier nicht nochmal skalieren."""
    import plotly.graph_objects as go

    unit = "min" if disruption == C.DISRUPTION_AUSFALL else "%"
    fig = go.Figure()
    for key in C.STRATEGY_KEYS:
        fig.add_trace(go.Scatter(x=[p.strength for p in points], y=[getattr(p, key) for p in points], mode="lines+markers",
                                 name=C.STRATEGY_SHORT[key], line=dict(color=C.STRATEGY_COLORS[key], width=2.5),
                                 marker=dict(color=C.STRATEGY_COLORS[key], size=8),
                                 hovertemplate=f"<b>{C.STRATEGY_SHORT[key]}</b><br>Störstärke %{{x}} {unit}<br>%{{y:.2f}} min/Auftrag<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, legend=LEGEND_BOTTOM, margin=dict(t=15, b=70),
                      xaxis_title=f"Störstärke ({unit})", yaxis_title="gew. Verspätung (min/Auftrag)", hovermode="closest")
    fig.update_yaxes(rangemode="tozero")
    return _lock_axes(fig)


def spread_figure(rows, field, axis_title):
    """Median und 10./90. Perzentil je Strategie über die Stichprobe (schiefe Kennzahl)."""
    import plotly.graph_objects as go

    import hrb_evaluation as E

    fig = go.Figure()
    for key in C.STRATEGY_KEYS:
        med, lo, hi = E.spread_of(rows, key)
        fig.add_trace(go.Scatter(x=[med], y=[C.STRATEGY_SHORT[key]], mode="markers", showlegend=False,
                                 marker=dict(color=C.STRATEGY_COLORS[key], size=11),
                                 error_x=dict(type="data", symmetric=False, array=[hi - med], arrayminus=[med - lo],
                                             color=C.STRATEGY_COLORS[key], thickness=2.5, width=6),
                                 hovertemplate=f"<b>{C.STRATEGY_SHORT[key]}</b><br>Median {med:.2f}<br>10.-90. Perzentil {lo:.2f}-{hi:.2f}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=220, margin=dict(t=10, b=40, l=10, r=10), xaxis_title=axis_title)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(rangemode="tozero")
    return _lock_axes(fig)


def distribution_figure(rows, field_a, field_b, label_a, label_b):
    """Gestapelter Balken: Anteil der Tage, an denen field_a weniger/gleich/mehr als field_b hat."""
    import plotly.graph_objects as go

    import hrb_evaluation as E

    d = E.paired(rows, field_a, field_b)
    n = len(d)
    better = sum(1 for x in d if x < -1e-9) / n
    worse = sum(1 for x in d if x > 1e-9) / n
    equal = 1 - better - worse
    fig = go.Figure()
    for share, name, color in ((better, f"{label_a} besser", C.OUTCOME_COLORS["better"]),
                               (equal, "gleich", C.OUTCOME_COLORS["equal"]),
                               (worse, f"{label_b} besser", C.OUTCOME_COLORS["worse"])):
        fig.add_trace(go.Bar(y=[f"{label_a} gegen {label_b}"], x=[share * 100], orientation="h", name=name,
                             marker_color=color, text=[f"{share * 100:.0f} %" if share >= 0.06 else ""],
                             textposition="inside", insidetextanchor="middle"))
    fig.update_layout(barmode="stack", template="plotly_white", height=150, legend=dict(LEGEND_BOTTOM, y=-0.5),
                      margin=dict(t=15, b=70, l=10), xaxis_title="Anteil der Tage (%)")
    fig.update_xaxes(range=[0, 100])
    return _lock_axes(fig)
