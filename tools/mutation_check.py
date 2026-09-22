"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prüft, ob die Tests (ohne AppTests
per Default) sie finden. Schwerpunkt Plan Abschnitt 11: vor allem `hrb_disruption.py` und
`hrb_fleet.py`, dazu die übrigen neuen Module.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N] [--indices 1,5,10-20] [--with-app] [--dry-run]
Jeder Mutant ersetzt genau eine Stelle; Überlebende sind entweder gleichwertig (kein sichtbarer
Unterschied) oder eine Lücke der Tests. Die Kopie liegt je Mutant in einem temporären Ordner;
PYTHONDONTWRITEBYTECODE=1, Quelltexte als LF normalisiert (Windows-Python schreibt sonst CRLF und
die Zeichenketten unten finden nichts). Ein Mutant kann in eine Endlosschleife laufen; nach TIMEOUT
Sekunden gilt er als gefunden. `--with-app` nimmt die AppTests hinzu. `--dry-run` prüft nur, ob jede
Zeichenkette genau einmal vorkommt."""
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WITH_APP = "--with-app" in sys.argv
TIMEOUT = 240
# test_preset_stories.py bewusst NICHT dabei: es rechnet 5 Presets x 40 echte Tage über einen eigenen
# ProcessPoolExecutor (bis zu 8 Worker) - multipliziert mit --jobs parallelen Mutanten überlastet das
# jede Maschine (gemessen: 10 Mutanten parallel x 8 interne Worker = 80 Prozesse, Laufzeit explodiert,
# viele Mutanten schlagen nur durch TIMEOUT als "gefunden" durch, nicht durch echte Testtreffer). Die
# Kriterienlogik selbst ist durch test_stories.py (künstliche Werte an jeder Schwelle) abgedeckt, ohne
# die teure Neuberechnung. test_preset_stories.py läuft separat in `pytest tests/`.
TEST_ORDER = ["test_scenario.py", "test_presets.py", "test_stories.py", "test_dispatch.py", "test_fleet.py",
             "test_disruption.py", "test_evaluation.py", "test_visualization.py", "test_pdf_export.py"]

MUTANTS = [
    # ---------------------------------------------------------------------------- hrb_disruption.py
    ("hrb_disruption.py", "rng = random.Random(1_000_003 * seed + 17 + delta)", "rng = random.Random(1_000_003 * seed + 17)"),
    ("hrb_disruption.py", "return broken_vehicle, bstart, bstart + duration", "return broken_vehicle, bstart, bstart + duration + 1"),
    ("hrb_disruption.py", "start = bend if (v == broken_vehicle and bstart <= candidate < bend) else candidate",
     "start = bend if (v == broken_vehicle and bstart < candidate < bend) else candidate"),
    ("hrb_disruption.py", "start = bend if (v == broken_vehicle and bstart <= candidate < bend) else candidate",
     "start = candidate"),
    ("hrb_disruption.py", "if nominal_plan[j][1] < bstart:\n                committed[v].append(j)",
     "if nominal_plan[j][1] <= bstart:\n                committed[v].append(j)"),
    ("hrb_disruption.py", "if v == broken_vehicle:\n            free0[v] = max(free0[v], bend)",
     "if v == broken_vehicle:\n            free0[v] = bend"),
    ("hrb_disruption.py", "pending_seed = [[j for j in nominal_seqs[v] if j in pending_ids] for v in range(m)]",
     "pending_seed = [[j for j in nominal_seqs[v] if j not in pending_ids] for v in range(m)]"),
    ("hrb_disruption.py", "if best_wt is None or wt < best_wt:\n            best_wt, best_plan = wt, plan\n    return best_wt, best_plan\n\n\ndef best_online_disrupted",
     "if best_wt is None or wt <= best_wt:\n            best_wt, best_plan = wt, plan\n    return best_wt, best_plan\n\n\ndef best_online_disrupted"),
    ("hrb_disruption.py", "if best_wt is None or wt < best_wt:\n            best_wt, best_plan = wt, plan\n    return best_wt, best_plan\n\n\n# --------",
     "if best_wt is None or wt <= best_wt:\n            best_wt, best_plan = wt, plan\n    return best_wt, best_plan\n\n\n# --------"),
    ("hrb_disruption.py", "candidate = max(job.release, t + approach)\n            start = bend if",
     "candidate = min(job.release, t + approach)\n            start = bend if"),
    # ---------------------------------------------------------------------------- hrb_fleet.py
    ("hrb_fleet.py", "earliest_finish_j = a.release + a.service", "earliest_finish_j = a.release"),
    ("hrb_fleet.py", "latest_start_k = b.deadline - b.service", "latest_start_k = b.deadline"),
    ("hrb_fleet.py", "return earliest_finish_j + instance.approach[j][k] <= latest_start_k",
     "return earliest_finish_j + instance.approach[j][k] < latest_start_k"),
    ("hrb_fleet.py", "return n - size", "return n - size + 1"),
    ("hrb_fleet.py", "if match_to[k] == -1 or try_augment(match_to[k], seen):", "if match_to[k] == -1 and try_augment(match_to[k], seen):"),
    ("hrb_fleet.py", "for k in range(1, max_k + 1):\n        inst = with_fleet(base_instance, k)", "for k in range(2, max_k + 1):\n        inst = with_fleet(base_instance, k)"),
    ("hrb_fleet.py", "if best_weighted_tardiness_total(inst) == 0:\n            return k, inst", "if best_weighted_tardiness_total(inst) <= 0:\n            return k, inst"),
    ("hrb_fleet.py", "best = wt if best is None else min(best, wt)\n    plan, _ = improve_plan(instance)", "best = wt if best is None else max(best, wt)\n    plan, _ = improve_plan(instance)"),
    ("hrb_fleet.py", "return min(best, wt)", "return max(best, wt)"),
    ("hrb_fleet.py", "model.Add(sum(lit[(None, j.index)] for j in jobs) <= instance.n_vehicles)", "model.Add(sum(lit[(None, j.index)] for j in jobs) <= instance.n_vehicles + 1)"),
    ("hrb_fleet.py", "model.Minimize(weighted * C.OBJ_BIG + sum(empty_terms))", "model.Minimize(weighted + sum(empty_terms))"),
    # ---------------------------------------------------------------------------- hrb_dispatch.py
    ("hrb_dispatch.py", "j = min(avail, key=lambda a: (instance.jobs[a].release, a))\n    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))\n    return v, j\n\n\ndef choose_edd",
     "j = max(avail, key=lambda a: (instance.jobs[a].release, a))\n    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))\n    return v, j\n\n\ndef choose_edd"),
    ("hrb_dispatch.py", "j = min(avail, key=lambda a: (instance.jobs[a].deadline, a))\n    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))\n    return v, j\n\n\ndef choose_atc",
     "j = max(avail, key=lambda a: (instance.jobs[a].deadline, a))\n    v = min(idle, key=lambda vv: (instance.approach_time(loc[vv], j), vv))\n    return v, j\n\n\ndef choose_atc"),
    ("hrb_dispatch.py", "def down(v, tt):\n        return v == broken_vehicle and bstart <= tt < bend", "def down(v, tt):\n        return v == broken_vehicle and bstart < tt <= bend"),
    ("hrb_dispatch.py", "idle = [v for v in range(m) if free_at[v] <= t and not down(v, t)]", "idle = [v for v in range(m) if free_at[v] <= t]"),
    ("hrb_dispatch.py", "if end > job.deadline:\n            weighted += job.weight * (end - job.deadline)\n        empty += approach\n        t, prev = end, j\n    return weighted * C.OBJ_BIG + empty\n\n\ndef sequence_plan_from",
     "if end >= job.deadline:\n            weighted += job.weight * (end - job.deadline)\n        empty += approach\n        t, prev = end, j\n    return weighted * C.OBJ_BIG + empty\n\n\ndef sequence_plan_from"),
    ("hrb_dispatch.py", "if new_cost < costs[v1]:\n                            seqs[v1], costs[v1] = cand, new_cost\n                            improved = True\n                    else:\n                        cand1, cand2 = list(seqs[v1]), list(seqs[v2])\n                        cand1[i], cand2[k] = cand2[k], cand1[i]\n                        c1 = sequence_cost_from",
     "if new_cost <= costs[v1]:\n                            seqs[v1], costs[v1] = cand, new_cost\n                            improved = True\n                    else:\n                        cand1, cand2 = list(seqs[v1]), list(seqs[v2])\n                        cand1[i], cand2[k] = cand2[k], cand1[i]\n                        c1 = sequence_cost_from"),
    ("hrb_dispatch.py", "if c1 + c2 < costs[v1] + costs[v2]:\n                            seqs[v1], seqs[v2] = cand1, cand2\n                            costs[v1], costs[v2] = c1, c2\n                            improved = True\n    return improved\n\n\ndef local_search_from",
     "if c1 + c2 <= costs[v1] + costs[v2]:\n                            seqs[v1], seqs[v2] = cand1, cand2\n                            costs[v1], costs[v2] = c1, c2\n                            improved = True\n    return improved\n\n\ndef local_search_from"),
    ("hrb_dispatch.py", "if cost <= current_cost:\n            current, current_cost = candidate, cost", "if cost < current_cost:\n            current, current_cost = candidate, cost"),
    # ---------------------------------------------------------------------------- hrb_evaluation.py
    ("hrb_evaluation.py", "if not 0 <= vehicle < instance.n_vehicles:", "if not 0 < vehicle < instance.n_vehicles:"),
    ("hrb_evaluation.py", "if start < jobs[idx].release:", "if start <= jobs[idx].release:"),
    ("hrb_evaluation.py", "if start < free_at + approach:", "if start <= free_at + approach:"),
    ("hrb_evaluation.py", "tardiness = max(0, end - job.deadline)", "tardiness = max(0, end - job.deadline - 1)"),
    ("hrb_evaluation.py", "k = kmin + fleet_delta\n    instance = with_fleet(base_instance(p, seed), k)", "k = kmin + fleet_delta + 1\n    instance = with_fleet(base_instance(p, seed), k)"),
    ("hrb_evaluation.py", "if duration <= 0:", "if duration < 0:"),
    ("hrb_evaluation.py", "if sigma <= 0:", "if sigma < 0:"),
    ("hrb_evaluation.py", "factors = draw_noise_factors(instance, seed * 10_000 + fleet_delta * 100 + noise_draw)",
     "factors = draw_noise_factors(instance, seed * 10_000 + fleet_delta * 100)"),
    ("hrb_evaluation.py", "return v[min(len(v) - 1, int(share * len(v)))]", "return v[min(len(v) - 1, int(share * len(v)) - 1)]"),
    ("hrb_evaluation.py", "return v[min(len(v) - 1, int(share * len(v)))]", "return v[int(share * len(v))]"),
    ("hrb_evaluation.py", "return [getattr(r, field_a) - getattr(r, field_b) for r in rows]", "return [getattr(r, field_b) - getattr(r, field_a) for r in rows]"),
    ("hrb_evaluation.py", "return sum(1 for x in d if x < -tol) / len(d)", "return sum(1 for x in d if x <= -tol) / len(d)"),
    ("hrb_evaluation.py", "if abs(diff) <= max(min_abs, se):\n        kind = \"unclear\"", "if abs(diff) < max(min_abs, se):\n        kind = \"unclear\""),
    ("hrb_evaluation.py", "kind = \"better\" if diff < 0 else \"worse\"", "kind = \"worse\" if diff < 0 else \"better\""),
    ("hrb_evaluation.py", "elif online < DIAGNOSIS_ALMOST_ZERO and reaktiv < DIAGNOSIS_ALMOST_ZERO and starr >= 0.3:",
     "elif online < DIAGNOSIS_ALMOST_ZERO or reaktiv < DIAGNOSIS_ALMOST_ZERO and starr >= 0.3:"),
    ("hrb_evaluation.py", "elif starr <= online + DIAGNOSIS_MARGIN:", "elif starr < online + DIAGNOSIS_MARGIN:"),
    ("hrb_evaluation.py", "if day.strength <= 0:\n        kind = \"calm\"", "if day.strength < 0:\n        kind = \"calm\""),
    # ---------------------------------------------------------------------------- hrb_scenario.py
    ("hrb_scenario.py", "return math.ceil((abs(a[0] - b[0]) + abs(a[1] - b[1])) / C.SPEED_M_PER_MIN)", "return round((abs(a[0] - b[0]) + abs(a[1] - b[1])) / C.SPEED_M_PER_MIN)"),
    ("hrb_scenario.py", "deadline=release + service + slack,", "deadline=release + service,"),
    ("hrb_scenario.py", "slack = max(1, round(buffer * C.KIND_SLACK_FACTOR[kind] * rng.uniform(0.5, 1.5)))", "slack = max(1, round(buffer * C.KIND_SLACK_FACTOR[kind] * rng.uniform(0.5, 1.0)))"),
    ("hrb_scenario.py", "def scale(t, j):\n        return math.ceil(t * (1 + sigma * factors[j]))", "def scale(t, j):\n        return round(t * (1 + sigma * factors[j]))"),
    ("hrb_scenario.py", "if sigma == 0:\n        return instance", "if sigma <= 0:\n        return instance"),
    ("hrb_scenario.py", "n_cols = max(3, yard_length // C.PARK_COL_SPACING)", "n_cols = max(3, yard_length // C.PARK_COL_SPACING + 1)"),
    ("hrb_scenario.py", "max_approach = max([*approach_from_depot, *(t for row in approach for t in row)], default=0)",
     "max_approach = min([*approach_from_depot, *(t for row in approach for t in row)], default=0)"),
    ("hrb_scenario.py", "return tuple(rng.random() for _ in instance.jobs)", "return tuple(0.5 for _ in instance.jobs)"),
    # ---------------------------------------------------------------------------- hrb_presets.py
    ("hrb_presets.py", "value = spec.lo + round((value - spec.lo) / spec.step) * spec.step", "value = spec.lo + int((value - spec.lo) / spec.step) * spec.step"),
    ("hrb_presets.py", "if value not in (0, 1, 2):\n        raise ValueError(raw)", "if value not in (0, 1):\n        raise ValueError(raw)"),
    ("hrb_presets.py", "if spec.lo is not None:\n        value = max(spec.lo, value)", "if spec.lo is not None:\n        value = min(spec.lo, value)"),
    ("hrb_presets.py", "if spec.hi is not None:\n        value = min(spec.hi, value)", "if spec.hi is not None:\n        value = max(spec.hi, value)"),
    ("hrb_presets.py", "if isinstance(value, float) and not math.isfinite(value):\n        return None", "if isinstance(value, float) and math.isfinite(value):\n        return None"),
    # ---------------------------------------------------------------------------- hrb_stories.py
    ("hrb_stories.py", "(starr_med >= 6.0, f\"starr (Median) >= 6,0 min/Auftrag: {starr_med:.2f}\"),", "(starr_med > 6.0, f\"starr (Median) >= 6,0 min/Auftrag: {starr_med:.2f}\"),"),
    ("hrb_stories.py", "(starr_med - online_med >= 3.0,", "(starr_med - online_med > 3.0,"),
    ("hrb_stories.py", "(reaktiv_med <= 4.0, f\"reaktiv (Median) <= 4,0 min/Auftrag: {reaktiv_med:.2f}\"),", "(reaktiv_med < 4.0, f\"reaktiv (Median) <= 4,0 min/Auftrag: {reaktiv_med:.2f}\"),"),
    ("hrb_stories.py", "(reaktiv_med <= 1.2, f\"reaktiv (Median) <= 1,2 min/Auftrag: {reaktiv_med:.2f}\"),", "(reaktiv_med < 1.2, f\"reaktiv (Median) <= 1,2 min/Auftrag: {reaktiv_med:.2f}\"),"),
    ("hrb_stories.py", "(starr_med - reaktiv_med >= 0.2,", "(starr_med - reaktiv_med > 0.2,"),
    ("hrb_stories.py", "(online_med - reaktiv_med >= 0.2,", "(online_med - reaktiv_med > 0.2,"),
    ("hrb_stories.py", "(abs(starr_med - online_med) <= 0.6,", "(abs(starr_med - online_med) < 0.6,"),
    ("hrb_stories.py", "(starr_mean >= 1.0, f\"starr (Mittel) >= 1,0 min/Auftrag: {starr_mean:.2f}\"),", "(starr_mean > 1.0, f\"starr (Mittel) >= 1,0 min/Auftrag: {starr_mean:.2f}\"),"),
    ("hrb_stories.py", "(online_mean <= 1.0, f\"online (Mittel) <= 1,0 min/Auftrag: {online_mean:.2f}\"),", "(online_mean < 1.0, f\"online (Mittel) <= 1,0 min/Auftrag: {online_mean:.2f}\"),"),
    ("hrb_stories.py", "(online_mean < starr_mean,", "(online_mean <= starr_mean,"),
    ("hrb_stories.py", "(reaktiv_mean <= 0.5, f\"reaktiv (Mittel) <= 0,5 min/Auftrag: {reaktiv_mean:.2f}\")]", "(reaktiv_mean < 0.5, f\"reaktiv (Mittel) <= 0,5 min/Auftrag: {reaktiv_mean:.2f}\")]"),
    ("hrb_stories.py", "(starr_med >= 1.0, f\"starr (Median) >= 1,0 min/Auftrag: {starr_med:.2f}\"),\n               (online_med <= 0.3,", "(starr_med > 1.0, f\"starr (Median) >= 1,0 min/Auftrag: {starr_med:.2f}\"),\n               (online_med <= 0.3,"),
    ("hrb_stories.py", "(online_med <= 0.3, f\"online (Median) <= 0,3 min/Auftrag: {online_med:.2f}\"),", "(online_med < 0.3, f\"online (Median) <= 0,3 min/Auftrag: {online_med:.2f}\"),"),
    ("hrb_stories.py", "(reaktiv_med <= 0.2, f\"reaktiv (Median) <= 0,2 min/Auftrag: {reaktiv_med:.2f}\")]\n    if name == \"Reserve gegen Rauschen\"",
     "(reaktiv_med < 0.2, f\"reaktiv (Median) <= 0,2 min/Auftrag: {reaktiv_med:.2f}\")]\n    if name == \"Reserve gegen Rauschen\""),
    ("hrb_stories.py", "(starr_med >= 0.2, f\"starr (Median) >= 0,2 min/Auftrag: {starr_med:.2f}\"),\n               (starr_med - online_med >= 0.1,",
     "(starr_med > 0.2, f\"starr (Median) >= 0,2 min/Auftrag: {starr_med:.2f}\"),\n               (starr_med - online_med >= 0.1,"),
    ("hrb_stories.py", "(starr_med - online_med >= 0.1,", "(starr_med - online_med > 0.1,"),
    ("hrb_stories.py", "return all(ok for ok, _ in criteria(name, (row,)))", "return any(ok for ok, _ in criteria(name, (row,)))"),
    # ---------------------------------------------------------------------------- hrb_visualization.py
    ("hrb_visualization.py", "def _lock_axes(fig):\n    fig.update_xaxes(fixedrange=True)", "def _lock_axes(fig):\n    fig.update_xaxes(fixedrange=False)"),
    ("hrb_visualization.py", "    fig.update_yaxes(fixedrange=True)\n    return fig", "    fig.update_yaxes(fixedrange=False)\n    return fig"),
    ("hrb_visualization.py", "score = 1 if online < starr - 1e-9 else (-1 if starr < online - 1e-9 else 0)", "score = 1 if online < starr - 1e-9 else (-1 if starr <= online - 1e-9 else 0)"),
    ("hrb_visualization.py", "if actual > nominal:\n                    noisy_jobs.add(idx)", "if actual >= nominal:\n                    noisy_jobs.add(idx)"),
    # ---------------------------------------------------------------------------- hrb_pdf_export.py
    ("hrb_pdf_export.py", "\"σ\": \"sigma\", ", ""),
    ("hrb_pdf_export.py", "\"€\": \"EUR\", ", ""),
    ("hrb_pdf_export.py", "\"–\": \"-\", \"—\": \"-\",", "\"—\": \"-\","),
    ("hrb_pdf_export.py", "\"**\": \"\",\n}", "}"),
]


def check_unique():
    bad = []
    for n, (name, old, new) in enumerate(MUTANTS, 1):
        text = (ROOT / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            bad.append((n, name, old[:70], text.count(old)))
        if old == new:
            bad.append((n, name, "alt == neu", 0))
    return bad


def run_one(args):
    n, name, old, new, base = args
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"hrb_mut{n}_"))
    try:
        shutil.copytree(base, tmp, dirs_exist_ok=True)
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        files = [f"tests/{f}" for f in TEST_ORDER + (["test_app.py"] if WITH_APP else [])]
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *files], cwd=tmp, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
            return n, name, old, new, r.returncode == 0, False
        except subprocess.TimeoutExpired:
            return n, name, old, new, False, True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else ""
    jobs = 8
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
        only = "" if only == str(jobs) else only
    wanted = None
    if "--indices" in sys.argv:
        spec = sys.argv[sys.argv.index("--indices") + 1]
        only = "" if only == spec else only
        wanted = set()
        for part in spec.split(","):
            lo, _, hi = part.partition("-")
            wanted.update(range(int(lo), int(hi or lo) + 1))
    bad = check_unique()
    for b in bad:
        print("FEHLER (Stelle nicht eindeutig gefunden):", b)
    if "--dry-run" in sys.argv:
        print(f"{len(MUTANTS)} Mutanten, {len(bad)} Fehler in der Mutantenliste")
        return
    base = pathlib.Path(tempfile.mkdtemp(prefix="hrb_mut_base_"))
    for f in ROOT.glob("*.py"):
        (base / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copytree(ROOT / "tests", base / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    for f in (base / "tests").glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    bad_ids = {b[0] for b in bad}
    work = [(n, name, old, new, base) for n, (name, old, new) in enumerate(MUTANTS, 1)
           if n not in bad_ids and (not only or only in name) and (wanted is None or n in wanted)]
    survivors, killed = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for n, name, old, new, survived, timeout in pool.map(run_one, work):
            if timeout:
                print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
            if survived:
                survivors.append((n, name, old[:70], new[:70]))
                print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:70]!r} -> {new[:70]!r}", flush=True)
            else:
                killed += 1
                print(f"[{n:3d}] gefunden  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} überlebt, {len(bad)} Fehler in der Mutantenliste")
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
