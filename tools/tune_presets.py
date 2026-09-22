"""Preset-Abstimmung per Sweep (AP 6): trägt die Geschichte jedes Presets im MEDIAN über viele Tage,
und am EINEN Tag, den das Preset zeigt? Die Zahlen aus dem freigegebenen Plan (Abschnitt 7) beruhen
auf nur 8 kombinierten Seeds aus vorab_kombiniert und sind dort ausdrücklich als vorläufig markiert -
dieses Werkzeug misst mit einer größeren Stichprobe nach.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py <modus>
  population   Grundgesamtheit (Seeds 6000-6059): Median-Kriterien aller Presets, Kennzahlen je Strategie
  seeds        Kandidaten (Seeds 7000-7059, außerhalb der Grundgesamtheit): welcher gemeinsame Seed
               trägt alle fünf Geschichten und liegt nahe am Median?
  shown        die gezeigte Woche (C.SEED_DEFAULT): Kriterien, Kennzahlen und ihre Lage in der Grundgesamtheit

Rechnet parallel (ein Tag kostet bei kaltem Cache rund 2 s: Minimum-Suche + Tagesrechnung)."""
import concurrent.futures
import os
import statistics
import sys

sys.path.insert(0, ".")
import hrb_constants as C
import hrb_evaluation as E
import hrb_stories as ST

NAMES = list(C.PRESETS)
POPULATION = range(6000, 6060)
CANDIDATES = range(7000, 7060)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["n_jobs"], p["buffer"], p["yard_length"])


def strength_of(name):
    p = C.PRESETS[name]
    return p["fail_duration"] if p["disruption"] == C.DISRUPTION_AUSFALL else p["noise_sigma"] / 100.0


def _row(args):
    name, seed = args
    p = C.PRESETS[name]
    r = E.day_scalars(params(name), seed, p["fleet_delta"], p["disruption"], strength_of(name))
    return E.SampleRow(seed, *r) if r is not None else None


def rows_for(seeds):
    jobs = [(n, s) for n in NAMES for s in seeds]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        rows = list(pool.map(_row, jobs, chunksize=2))
    table = {n: {} for n in NAMES}
    for (n, s), r in zip(jobs, rows):
        if r is not None:
            table[n][s] = r
    return table


def cmd_population():
    table = rows_for(POPULATION)
    for name in NAMES:
        rows = tuple(table[name].values())
        print(f"\n### {name} ({len(rows)} Tage)")
        for ok, text in ST.criteria(name, rows):
            print(("  OK   " if ok else "  FAIL ") + text)
        for field in ST.TYPICAL:
            med, lo, hi = E.spread_of(rows, field)
            print(f"    {field:8s} Median {med:7.2f}  [{lo:7.2f}; {hi:7.2f}]")
        kmins = sorted({r.kmin for r in rows})
        print("    kmin je Tag:", kmins)


def _iqr(vals):
    v = sorted(vals)
    return max(1e-6, v[int(0.75 * len(v))] - v[int(0.25 * len(v))])


def cmd_seeds():
    pop = rows_for(POPULATION)
    cand = rows_for(CANDIDATES)
    scale = {(n, f): (statistics.median(E.values(tuple(pop[n].values()), f)), _iqr(E.values(tuple(pop[n].values()), f)))
            for n in NAMES for f in ST.TYPICAL}

    def dist(seed):
        d = []
        for n in NAMES:
            row = cand[n].get(seed)
            if row is None:
                return None
            for f in ST.TYPICAL:
                med, iqr = scale[(n, f)]
                d.append(abs(getattr(row, f) - med) / iqr)
        return sum(d), max(d)

    for n in NAMES:
        print(f"{n}: trägt an {sum(ST.holds(n, cand[n][s]) for s in CANDIDATES if s in cand[n])} von {len(cand[n])} Tagen")
    good = []
    for s in CANDIDATES:
        if all(ST.holds(n, cand[n][s]) for n in NAMES if s in cand[n]) and all(s in cand[n] for n in NAMES):
            d = dist(s)
            if d is not None:
                good.append((s, d))
    good.sort(key=lambda x: x[1][0])
    print(f"\nalle fünf tragen an: {[s for s, _ in good[:12]]} ({len(good)} von {len(CANDIDATES)})")
    for s, (tot, worst) in good[:8]:
        print(f"  seed {s} | Summe {tot:.2f} | schlechtester Abstand {worst:.2f} Interquartilsbreiten")


def cmd_shown():
    seed = C.SEED_DEFAULT
    pop = rows_for(POPULATION)
    for name in NAMES:
        row = _row((name, seed))
        print(f"\n### {name}, Seed {seed}: {'trägt' if row and ST.holds(name, row) else 'TRÄGT NICHT'}")
        if row is None:
            print("  (kein praktisches Minimum gefunden)")
            continue
        for ok, text in ST.criteria(name, (row,)):
            print(("  OK   " if ok else "  FAIL ") + text)
        rows = tuple(pop[name].values())
        for f in ST.TYPICAL:
            vals = E.values(rows, f)
            v = getattr(row, f)
            rank = sum(1 for x in vals if x <= v) / len(vals)
            print(f"    {f:8s} Tag {v:8.2f} | Median {statistics.median(vals):8.2f} | Rang {rank * 100:3.0f} %")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "population"
    {"population": cmd_population, "seeds": cmd_seeds, "shown": cmd_shown}.get(mode, lambda: sys.exit(__doc__))()
