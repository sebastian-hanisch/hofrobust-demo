import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hrb_constants as C
import hrb_evaluation as E
from hrb_pdf_export import generate_hrb_pdf, pdf_text


def test_pdf_text_replaces_characters_that_crash_fpdf2():
    assert pdf_text("Preis: 5 € – Rauschstärke σ = 5 %") == "Preis: 5 EUR - Rauschstärke sigma = 5 %"
    # encodierbar in latin-1
    pdf_text("Preis: 5 € – Rauschstärke σ = 5 %").encode("latin-1")


def test_pdf_text_handles_emoji_and_markdown_bold():
    assert "⚠️" not in pdf_text("⚠️ Achtung **wichtig**")
    assert "**" not in pdf_text("**wichtig**")


def _settings(**overrides):
    base = dict(n_jobs=16, fleet_delta=0, disruption=C.DISRUPTION_AUSFALL, fail_duration=40, noise_sigma=25, buffer=15, yard_length=450, seed=3)
    base.update(overrides)
    return base


def _day(**kwargs):
    p = E.Params(n_jobs=16, buffer=15, yard_length=450)
    return E.compute_day(p, 3, kwargs.get("fleet_delta", 0), kwargs.get("disruption", C.DISRUPTION_AUSFALL), kwargs.get("strength", 40))


def test_generate_pdf_without_curve_or_sample():
    settings = _settings()
    day = _day()
    base = E.base_instance(E.Params(16, 15, 450), 3)
    table = E.winner_table(E.Params(16, 15, 450), 3, 40, 0.25)
    pdf_bytes = generate_hrb_pdf(settings, day, base, table)
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_with_curve_and_sample():
    settings = _settings()
    day = _day()
    base = E.base_instance(E.Params(16, 15, 450), 3)
    table = E.winner_table(E.Params(16, 15, 450), 3, 40, 0.25)
    curve = E.strength_curve(E.Params(16, 15, 450), 3, 0, C.DISRUPTION_AUSFALL)
    sample_rows = E.sample(E.Params(16, 15, 450), 0, C.DISRUPTION_AUSFALL, 40, n=3, base=900)
    pdf_bytes = generate_hrb_pdf(settings, day, base, table, curve=curve, sample_rows=sample_rows)
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_under_noise_with_sigma_in_the_settings():
    settings = _settings(disruption=C.DISRUPTION_RAUSCHEN, noise_sigma=60)
    day = _day(disruption=C.DISRUPTION_RAUSCHEN, strength=0.6)
    base = E.base_instance(E.Params(16, 15, 450), 3)
    table = E.winner_table(E.Params(16, 15, 450), 3, 40, 0.60)
    pdf_bytes = generate_hrb_pdf(settings, day, base, table)
    assert pdf_bytes[:4] == b"%PDF"
