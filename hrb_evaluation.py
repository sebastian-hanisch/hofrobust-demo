"""Machbarkeitsprüfung und Kennzahlen - bitgleiche Kopie von yard-demo/yard_evaluation.py (kein
Laufzeit-Import, siehe Plan Abschnitt 10). `hrb_dispatch.py`/`hrb_disruption.py`/`hrb_fleet.py`
nutzen ausschließlich diese Funktionen zur Prüfung, damit Konstruktion und Prüfung nie
auseinanderlaufen können - wie im Original."""

import statistics
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

import hrb_constants as C


def sequences_to_plan(instance, sequences):
    plan = {}
    for v, seq in enumerate(sequences):
        t, prev = 0, None
        for j in seq:
            job = instance.jobs[j]
            start = max(job.release, t + instance.approach_time(prev, j))
            plan[j] = (v, start)
            t, prev = start + job.service, j
    return plan


def sequence_cost(instance, seq):
    t, prev = 0, None
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
    return weighted * C.OBJ_BIG + empty


def check_feasible(instance, plan):
    violations = []
    jobs = instance.jobs

    if set(plan.keys()) != {j.index for j in jobs}:
        violations.append("Nicht jeder Auftrag genau einmal eingeplant.")
        return False, violations

    by_vehicle = defaultdict(list)
    for idx, (vehicle, start) in plan.items():
        if not 0 <= vehicle < instance.n_vehicles:
            violations.append(f"{jobs[idx].name}: unbekanntes Fahrzeug {vehicle}.")
            continue
        if start < jobs[idx].release:
            violations.append(f"{jobs[idx].name}: Start {start} min liegt vor der Freigabe {jobs[idx].release} min.")
        by_vehicle[vehicle].append((start, idx))

    for vehicle, entries in by_vehicle.items():
        entries.sort()
        free_at, prev = 0, None
        for start, idx in entries:
            approach = instance.approach_time(prev, idx)
            if start < free_at + approach:
                violations.append(
                    f"Fahrzeug {vehicle + 1}: {jobs[idx].name} beginnt bei {start} min, das Fahrzeug kann "
                    f"frühestens bei {free_at + approach} min (frei ab {free_at} min + {approach} min Anfahrt) dort sein."
                )
            free_at, prev = start + jobs[idx].service, idx
    return len(violations) == 0, violations


def evaluate(instance, plan, label=""):
    per_job = {}
    by_vehicle = defaultdict(list)
    for idx, (vehicle, start) in plan.items():
        by_vehicle[vehicle].append((start, idx))

    weighted_tardiness = 0
    total_tardiness = 0
    n_late = 0
    empty_minutes = 0
    makespan = 0
    vehicle_sequences = [[] for _ in range(instance.n_vehicles)]

    for vehicle, entries in by_vehicle.items():
        entries.sort()
        prev = None
        for start, idx in entries:
            job = instance.jobs[idx]
            approach = instance.approach_time(prev, idx)
            end = start + job.service
            tardiness = max(0, end - job.deadline)
            per_job[idx] = {"vehicle": vehicle, "start": start, "end": end, "approach": approach, "tardiness": tardiness}
            weighted_tardiness += job.weight * tardiness
            total_tardiness += tardiness
            n_late += tardiness > 0
            empty_minutes += approach
            makespan = max(makespan, end)
            vehicle_sequences[vehicle].append(idx)
            prev = idx

    return {
        "label": label, "plan": per_job, "sequences": vehicle_sequences,
        "total_weighted_tardiness": weighted_tardiness, "total_tardiness": total_tardiness,
        "n_late": n_late, "n_jobs": len(plan), "empty_minutes": empty_minutes, "makespan": makespan,
    }


def weighted_tardiness_per_job(instance, plan):
    """Gewichtete Verspätung je Auftrag (min/Auftrag) - die durchgehende Einheit dieser Demo.
    Prüft den Plan zusätzlich mit `check_feasible` (unabhängig von der Zielfunktion selbst)."""
    ok, violations = check_feasible(instance, plan)
    if not ok:
        raise AssertionError(f"Plan verletzt check_feasible: {violations[:3]}")
    n = len(instance.jobs)
    return evaluate(instance, plan)["total_weighted_tardiness"] / n if n else 0.0


# =================================================================================================
# Ein Tag: alle drei Strategien für eine Einstellung (Flottenabstand, Störungsart, Störstärke)
# =================================================================================================
class Params(NamedTuple):
    """Alles, was die Aufträge/Anfahrtsmatrix eines Tages bestimmt (ohne Seed, Flotte, Störung)."""
    n_jobs: int
    buffer: int
    yard_length: int


def base_instance(p, seed):
    from hrb_scenario import generate_instance

    return generate_instance(n_jobs=p.n_jobs, buffer=p.buffer, yard_length=p.yard_length, seed=seed, n_vehicles=1)


@lru_cache(maxsize=1024)
def kmin_for(p, seed):
    """Praktisches Minimum K (gecacht je (Params, Seed) - hängt nicht vom Flottenabstand ab)."""
    from hrb_fleet import practical_min_fleet

    kmin, _ = practical_min_fleet(base_instance(p, seed))
    return kmin


@dataclass(frozen=True, eq=False)
class Outcome:
    key: str
    wt: float          # gewichtete Verspätung je Auftrag (min)
    plan: dict          # job_index -> (vehicle, start), am AUSGEFÜHRTEN Zeitbild
    instance: object    # die tatsächlich ausgeführte Instanz (bei Rauschen: die verrauschte)


@dataclass(frozen=True, eq=False)
class DayResult:
    p: Params
    seed: int
    fleet_delta: int
    disruption: str
    strength: float      # Ausfalldauer (min) oder Rauschstärke sigma (Anteil, 0..0.6)
    kmin: int
    k: int
    instance: object      # nominale Instanz bei Flotte k (ohne Rauschen)
    nominal_plan: dict
    nominal_seqs: list
    outcomes: dict        # Strategie -> Outcome
    failure: object        # (broken_vehicle, bstart, bend) bei Ausfall>0, sonst None
    noisy_instance: object  # verrauschte Instanz bei Rauschen>0, sonst None

    def __getitem__(self, key):
        return self.outcomes[key]


def compute_day(p, seed, fleet_delta, disruption, strength, noise_draw=0):
    """Ein Tag mit der eingestellten Flotte (K + Abstand), Störungsart und -stärke, alle drei
    Strategien - gepaart (derselbe Störungsdraw/dieselben Rauschfaktoren für alle drei)."""
    from hrb_dispatch import improve_plan
    from hrb_disruption import (best_online_disrupted, best_online_no_disruption, best_online_under_noise,
                                draw_failure, reactive_under_noise, rigid_under_noise, simulate_reactive,
                                simulate_rigid)
    from hrb_scenario import draw_noise_factors, make_noisy_instance, with_fleet

    kmin = kmin_for(p, seed)
    if kmin is None:
        return None
    k = kmin + fleet_delta
    instance = with_fleet(base_instance(p, seed), k)
    plan_pre, seqs_pre = improve_plan(instance)
    wt_pre = weighted_tardiness_per_job(instance, plan_pre)

    failure, noisy_instance = None, None
    if disruption == C.DISRUPTION_AUSFALL:
        duration = strength
        if duration <= 0:
            wt_online, online_plan = best_online_no_disruption(instance)
            outcomes = {
                C.S_STARR: Outcome(C.S_STARR, wt_pre, plan_pre, instance),
                C.S_ONLINE: Outcome(C.S_ONLINE, wt_online, online_plan, instance),
                C.S_REAKTIV: Outcome(C.S_REAKTIV, wt_pre, plan_pre, instance),
            }
        else:
            broken_vehicle, bstart, bend = draw_failure(instance, seed, duration, fleet_delta)
            failure = (broken_vehicle, bstart, bend)
            starr_plan = simulate_rigid(instance, seqs_pre, broken_vehicle, bstart, bend)
            wt_starr = weighted_tardiness_per_job(instance, starr_plan)
            wt_online, online_plan = best_online_disrupted(instance, broken_vehicle, bstart, bend)
            reaktiv_plan = simulate_reactive(instance, plan_pre, seqs_pre, broken_vehicle, bstart, bend)
            wt_reaktiv = weighted_tardiness_per_job(instance, reaktiv_plan)
            outcomes = {
                C.S_STARR: Outcome(C.S_STARR, wt_starr, starr_plan, instance),
                C.S_ONLINE: Outcome(C.S_ONLINE, wt_online, online_plan, instance),
                C.S_REAKTIV: Outcome(C.S_REAKTIV, wt_reaktiv, reaktiv_plan, instance),
            }
    else:
        sigma = strength
        if sigma <= 0:
            wt_online, online_plan = best_online_no_disruption(instance)
            outcomes = {
                C.S_STARR: Outcome(C.S_STARR, wt_pre, plan_pre, instance),
                C.S_ONLINE: Outcome(C.S_ONLINE, wt_online, online_plan, instance),
                C.S_REAKTIV: Outcome(C.S_REAKTIV, wt_pre, plan_pre, instance),
            }
        else:
            factors = draw_noise_factors(instance, seed * 10_000 + fleet_delta * 100 + noise_draw)
            noisy_instance = make_noisy_instance(instance, sigma, factors)
            starr_plan = rigid_under_noise(noisy_instance, seqs_pre)
            wt_starr = weighted_tardiness_per_job(noisy_instance, starr_plan)
            wt_online, online_plan = best_online_under_noise(noisy_instance)
            reaktiv_plan = reactive_under_noise(noisy_instance, seqs_pre)
            wt_reaktiv = weighted_tardiness_per_job(noisy_instance, reaktiv_plan)
            outcomes = {
                C.S_STARR: Outcome(C.S_STARR, wt_starr, starr_plan, noisy_instance),
                C.S_ONLINE: Outcome(C.S_ONLINE, wt_online, online_plan, noisy_instance),
                C.S_REAKTIV: Outcome(C.S_REAKTIV, wt_reaktiv, reaktiv_plan, noisy_instance),
            }

    return DayResult(p, seed, fleet_delta, disruption, strength, kmin, k, instance, plan_pre, seqs_pre,
                     outcomes, failure, noisy_instance)


def day_scalars(p, seed, fleet_delta, disruption, strength):
    """(kmin, k, starr, online, reaktiv) - leichtgewichtig für Stichprobe/Kurve (ohne Pläne)."""
    r = compute_day(p, seed, fleet_delta, disruption, strength)
    if r is None:
        return None
    return r.kmin, r.k, r[C.S_STARR].wt, r[C.S_ONLINE].wt, r[C.S_REAKTIV].wt


# =================================================================================================
# Sieger-Tabelle: 3 (Flottenabstand) x 2 (Störungsart) am eingestellten Tag
# =================================================================================================
def winner_table(p, seed, fail_duration, noise_sigma):
    """{(delta, disruption): (starr, online, reaktiv)} für alle 3x2-Kombinationen am selben Tag,
    mit der jeweils eingestellten Störstärke der Störungsart."""
    out = {}
    for delta in (0, 1, 2):
        for disruption, strength in ((C.DISRUPTION_AUSFALL, fail_duration), (C.DISRUPTION_RAUSCHEN, noise_sigma)):
            row = day_scalars(p, seed, delta, disruption, strength)
            out[(delta, disruption)] = row[2:] if row else None
    return out


# =================================================================================================
# Umschlagpunkt-Kurve: gewichtete Verspätung über die Störstärke, für alle drei Strategien
# =================================================================================================
class CurvePoint(NamedTuple):
    strength: float
    starr: float
    online: float
    reaktiv: float


def strength_curve(p, seed, fleet_delta, disruption):
    steps = C.CURVE_STEPS_AUSFALL if disruption == C.DISRUPTION_AUSFALL else C.CURVE_STEPS_RAUSCHEN
    unit = 1.0 if disruption == C.DISRUPTION_AUSFALL else 0.01
    points = []
    for step in steps:
        row = day_scalars(p, seed, fleet_delta, disruption, step * unit)
        if row is not None:
            points.append(CurvePoint(step, row[2], row[3], row[4]))
    return tuple(points)


# =================================================================================================
# Stichprobe, gepaarte Differenz, Verteilung, Urteil in drei Zuständen
# =================================================================================================
class SampleRow(NamedTuple):
    seed: int
    kmin: int
    k: int
    starr: float
    online: float
    reaktiv: float


def sample(p, fleet_delta, disruption, strength, n=C.SAMPLE_DAYS_DEFAULT, base=C.SAMPLE_BASE):
    """n Tage (Seeds `base` .. `base+n-1`, unabhängig vom eingestellten Seed) an derselben
    Einstellung."""
    rows = []
    for i in range(n):
        r = day_scalars(p, base + i, fleet_delta, disruption, strength)
        if r is not None:
            rows.append(SampleRow(base + i, *r))
    return tuple(rows)


def values(rows, field):
    return [getattr(r, field) for r in rows]


def percentile(vals, share):
    v = sorted(vals)
    return v[min(len(v) - 1, int(share * len(v)))]


def spread_of(rows, field):
    v = values(rows, field)
    return statistics.median(v), percentile(v, C.PCT_LO), percentile(v, C.PCT_HI)


def median_of(rows, field):
    return statistics.median(values(rows, field))


def mean_of(rows, field):
    return statistics.fmean(values(rows, field))


def paired(rows, field_a, field_b):
    """Gepaarte Differenz field_a minus field_b je Tag (negativ = field_a besser)."""
    return [getattr(r, field_a) - getattr(r, field_b) for r in rows]


def median_diff(rows, field_a, field_b):
    return statistics.median(paired(rows, field_a, field_b))


def share_wins(rows, field_a, field_b, tol=1e-9):
    """Anteil der Tage, an denen field_a echt kleiner als field_b ist."""
    d = paired(rows, field_a, field_b)
    return sum(1 for x in d if x < -tol) / len(d)


def _se(d):
    return statistics.stdev(d) / len(d) ** 0.5 if len(d) > 1 else 0.0


@dataclass(frozen=True)
class Verdict:
    kind: str  # "better" (field_a kleiner) | "worse" | "unclear"
    diff: float
    se: float
    n: int
    share_a_wins: float
    share_b_wins: float


def verdict(rows, field_a, field_b, min_abs=C.VERDICT_MIN_ABS):
    """field_a gegen field_b (z. B. 'online' gegen 'starr'): "klar", wenn |Mittel| über min_abs UND
    über einem Standardfehler liegt - siehe feedback_ci_platform_robust_tests (keine Bänder um eine
    chaotische Einzelziehung)."""
    d = paired(rows, field_a, field_b)
    diff, se = statistics.fmean(d), _se(d)
    share_a = sum(1 for x in d if x < -1e-9) / len(d)
    share_b = sum(1 for x in d if x > 1e-9) / len(d)
    if abs(diff) <= max(min_abs, se):
        kind = "unclear"
    else:
        kind = "better" if diff < 0 else "worse"
    return Verdict(kind, diff, se, len(d), share_a, share_b)


# =================================================================================================
# Bedingte Meldung (Hauptansicht)
# =================================================================================================
@dataclass(frozen=True)
class Diagnosis:
    kind: str  # "calm" | "starr_haelt" | "starr_bricht" | "reserve_wartefrei"
    starr: float
    online: float
    reaktiv: float


DIAGNOSIS_ALMOST_ZERO = 0.05
DIAGNOSIS_MARGIN = 0.05


def diagnose(day):
    starr, online, reaktiv = day[C.S_STARR].wt, day[C.S_ONLINE].wt, day[C.S_REAKTIV].wt
    if day.strength <= 0:
        kind = "calm"
    elif online < DIAGNOSIS_ALMOST_ZERO and reaktiv < DIAGNOSIS_ALMOST_ZERO and starr >= 0.3:
        kind = "reserve_wartefrei"
    elif starr <= online + DIAGNOSIS_MARGIN:
        kind = "starr_haelt"
    else:
        kind = "starr_bricht"
    return Diagnosis(kind, starr, online, reaktiv)


def diagnosis_text(diag, day):
    art = "Ausfall" if day.disruption == C.DISRUPTION_AUSFALL else "Rauschen"
    if diag.kind == "calm":
        return (f"Keine Störung eingestellt: starr und reaktiv sind bitgleich dem Vorausplan ({diag.starr:.2f} "
                f"min/Auftrag) - es gibt nichts zu bewältigen. Online (ohne Vorausplanung) kommt unabhängig davon "
                f"auf {diag.online:.2f} min/Auftrag: schon ohne Störung ist der Vorausplan der besten Einzelregel "
                f"meist überlegen.")
    if diag.kind == "starr_haelt":
        return (f"Der starre Plan hält der Störung ({art}) stand: {diag.starr:.2f} min/Auftrag gegen {diag.online:.2f} "
                f"bei online, {diag.reaktiv:.2f} bei reaktiv. Das ist am praktischen Minimum unter Fahrzeit-Rauschen "
                f"möglich (starr bricht dort nicht sofort) - bei Fahrzeugausfall dagegen kaum, weil ein Ausfall die feste "
                f"Reihenfolge direkt bricht.")
    if diag.kind == "starr_bricht":
        return (f"Der starre Plan bricht unter der Störung ({art}): {diag.starr:.2f} min/Auftrag gegenüber {diag.online:.2f} "
                f"bei online und {diag.reaktiv:.2f} bei reaktiv. Reaktives Nachplanen federt das am stärksten ab.")
    return (f"Ein Reservefahrzeug macht online und reaktiv praktisch wartefrei ({diag.online:.2f} bzw. {diag.reaktiv:.2f} "
           f"min/Auftrag) - der starre Plan bleibt bei {diag.starr:.2f}, weil er die Reserve nicht nutzt.")


def verdict_text(rows, label_a, label_b, field_a, field_b):
    v = verdict(rows, field_a, field_b)
    if v.kind == "unclear":
        return v.kind, (f"Kein klarer Unterschied zwischen {label_a} und {label_b}: die mittlere Differenz "
                        f"({v.diff:+.2f} min/Auftrag über {v.n} Tage, Standardfehler {v.se:.2f}) liegt innerhalb "
                        f"des Rauschens. {label_a} gewinnt an {v.share_a_wins * 100:.0f} %, {label_b} an "
                        f"{v.share_b_wins * 100:.0f} % der Tage.")
    winner, loser = (label_a, label_b) if v.kind == "better" else (label_b, label_a)
    share = v.share_a_wins if v.kind == "better" else v.share_b_wins
    return v.kind, (f"**{winner}** ist robuster als {loser}: im Mittel {abs(v.diff):.2f} min/Auftrag weniger "
                    f"gewichtete Verspätung ({v.n} Tage, Standardfehler {v.se:.2f}). {winner} gewinnt an "
                    f"{share * 100:.0f} % der Tage.")
