"""Instanzerzeugung: Fahraufträge für Wechselbrücken auf einem Betriebshof.

Angepasste Kopie von yard-demo/yard_scenario.py (kein Laufzeit-Import, siehe Plan Abschnitt 10 -
jeder Streamlit-Cloud-Deploy bleibt eigenständig). `generate_instance` ist bitgleich zur Quelle
(gleicher Algorithmus, gleiche Konstanten aus hrb_constants), nur ohne `n_vehicles`-Parameter: die
Flottengröße wird in der Demo erst nach der Minimum-Suche festgelegt (siehe hrb_fleet.py) - dieselbe
Instanz (Aufträge, Anfahrtsmatrix) hängt nicht von n_vehicles ab, `with_fleet` hängt nur noch ein
`n_vehicles` an.

Dazu die Rauschfaktoren für Störungsart 2 (Fahrzeit-Rauschen): ein Faktor je ZIEL-Auftrag, wie in
fahrzeugflotte-demo/vorab_flotte.make_noisy_instance - gemeinsame Zufallszahlen für alle drei
Strategien (gepaarter Vergleich)."""

import math
import random
from dataclasses import dataclass, replace

import hrb_constants as C


@dataclass(frozen=True)
class Job:
    index: int
    name: str
    kind: str
    pick_xy: tuple
    drop_xy: tuple
    pick_label: str
    drop_label: str
    release: int
    deadline: int
    service: int
    weight: int


@dataclass(frozen=True)
class Instance:
    jobs: tuple
    n_vehicles: int
    yard_length: int
    yard_width: int
    depot_xy: tuple
    doors: tuple
    arrival_window: int
    approach_from_depot: tuple
    approach: tuple
    horizon: int

    def approach_time(self, prev, job):
        return self.approach_from_depot[job] if prev is None else self.approach[prev][job]


def _travel_minutes(a, b):
    return math.ceil((abs(a[0] - b[0]) + abs(a[1] - b[1])) / C.SPEED_M_PER_MIN)


def generate_instance(n_jobs, buffer, yard_length, seed, n_vehicles=1, arrival_window=C.ARRIVAL_WINDOW,
                      peak_pct=C.PEAK_PCT, departure_pct=C.DEPARTURE_PCT, n_doors=C.N_DOORS):
    """Wie yard_scenario.generate_instance; arrival_window/peak_pct/departure_pct/n_doors sind in
    dieser Demo keine Regler (Abschnitt 5 des Plans), bleiben aber als Parameter für Tests/Vorab-
    Check-Vergleich erhalten. `n_vehicles` beeinflusst nur das Feld `Instance.n_vehicles`, nicht die
    Aufträge oder die Anfahrtsmatrix (wie in yard-demo geprüft)."""
    rng = random.Random(seed)

    door_xs = [round(yard_length * (0.08 + 0.84 * i / max(1, n_doors - 1))) for i in range(n_doors)]
    doors = tuple((x, 0, f"Tor {i + 1}") for i, x in enumerate(door_xs))

    n_cols = max(3, yard_length // C.PARK_COL_SPACING)
    zone_cols = {
        "Ankunft": range(0, int(n_cols * 0.3)),
        "Mittelfeld": range(int(n_cols * 0.3), int(n_cols * 0.7)),
        "Abfahrt": range(int(n_cols * 0.7), n_cols),
    }

    def random_slot(zone):
        col = rng.choice(list(zone_cols[zone]))
        row = rng.randrange(len(C.PARK_ROW_YS))
        return (col * C.PARK_COL_SPACING + C.PARK_COL_SPACING // 2, C.PARK_ROW_YS[row]), f"{zone} {row + 1}-{col + 1:02d}"

    depot_xy = (yard_length // 2, C.YARD_WIDTH)

    def draw_release():
        if rng.random() < peak_pct / 100:
            value = rng.gauss(arrival_window / 2, arrival_window / 8)
        else:
            value = rng.uniform(0, arrival_window)
        return int(min(arrival_window, max(0, round(value))))

    p_departure = departure_pct / 100
    p_setup = (1 - p_departure) * 0.6

    jobs = []
    for i in range(n_jobs):
        draw = rng.random()
        if draw < p_departure:
            kind = C.KIND_DEPARTURE
        elif draw < p_departure + p_setup:
            kind = C.KIND_SETUP
        else:
            kind = C.KIND_CLEAR

        door_x, door_y, door_label = rng.choice(doors)
        if kind == C.KIND_SETUP:
            pick_xy, pick_label = random_slot("Ankunft")
            drop_xy, drop_label = (door_x, door_y), door_label
        elif kind == C.KIND_DEPARTURE:
            pick_xy, pick_label = (door_x, door_y), door_label
            drop_xy, drop_label = random_slot("Abfahrt")
        else:
            pick_xy, pick_label = (door_x, door_y), door_label
            drop_xy, drop_label = random_slot("Mittelfeld")

        release = draw_release()
        service = C.COUPLING_MIN + _travel_minutes(pick_xy, drop_xy)
        slack = max(1, round(buffer * C.KIND_SLACK_FACTOR[kind] * rng.uniform(0.5, 1.5)))
        jobs.append(
            Job(index=i, name=f"Auftrag {i + 1}", kind=kind, pick_xy=pick_xy, drop_xy=drop_xy,
                pick_label=pick_label, drop_label=drop_label, release=release,
                deadline=release + service + slack, service=service, weight=C.KIND_WEIGHTS[kind])
        )

    approach_from_depot = tuple(_travel_minutes(depot_xy, j.pick_xy) for j in jobs)
    approach = tuple(tuple(_travel_minutes(a.drop_xy, b.pick_xy) for b in jobs) for a in jobs)

    max_approach = max([*approach_from_depot, *(t for row in approach for t in row)], default=0)
    horizon = arrival_window + sum(j.service + max_approach for j in jobs) + 10

    return Instance(jobs=tuple(jobs), n_vehicles=n_vehicles, yard_length=yard_length, yard_width=C.YARD_WIDTH,
                    depot_xy=depot_xy, doors=doors, arrival_window=arrival_window,
                    approach_from_depot=approach_from_depot, approach=approach, horizon=horizon)


def with_fleet(instance, n_vehicles):
    """Dieselbe Instanz mit anderer Flottengröße (Aufträge/Anfahrtsmatrix unverändert)."""
    return replace(instance, n_vehicles=n_vehicles)


def draw_noise_factors(instance, seed):
    """Ein Zufallsfaktor je Auftrag (Ziel der Anfahrt) aus [0, 1) - gemeinsame Zufallszahlen für
    starr/online/reaktiv, wie in vorab_flotte.make_noisy_instance."""
    rng = random.Random(seed)
    return tuple(rng.random() for _ in instance.jobs)


def make_noisy_instance(instance, sigma, factors):
    """Fahrzeit-Rauschen auf die Leerfahrt (Anfahrt), nicht auf die Servicezeit: Faktor je
    ZIEL-Auftrag j, ⌈t · (1 + σ · factor[j])⌉ - nur verspätend, aufgerundet. sigma=0 gibt dieselbe
    Instanz zurück (keine Kopie nötig, approach bleibt identisch)."""
    if sigma == 0:
        return instance

    def scale(t, j):
        return math.ceil(t * (1 + sigma * factors[j]))

    new_from_depot = tuple(scale(t, j) for j, t in enumerate(instance.approach_from_depot))
    new_approach = tuple(tuple(scale(t, j) for j, t in enumerate(row)) for row in instance.approach)
    return replace(instance, approach_from_depot=new_from_depot, approach=new_approach)
