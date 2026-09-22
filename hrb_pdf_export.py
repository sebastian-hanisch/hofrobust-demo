"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute sind erlaubt, aber "-" (Gedankenstrich), "-" (Minus),
"EUR", "sigma", Emoji usw. lassen fpdf2 abstürzen (feedback_fpdf2_umlauts_are_fine) - deshalb läuft
jeder Text durch `pdf_text()`. Der Regler "Störstärke σ" macht das hier besonders wichtig."""

import time

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "σ": "sigma", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR", "·": "*",
    "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "±": "+-", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "", "🔒": "", "🔄": "",
    "⚡": "", "🔗": "", "**": "",
}


def pdf_text(text):
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_hrb_pdf(settings, day, base_instance, winner_table_data, curve=None, sample_rows=None, compress=True):
    """`settings`: dict der aktuellen Einstellungen (n_jobs, fleet_delta, disruption, fail_duration,
    noise_sigma, buffer, yard_length, seed); `day`: hrb_evaluation.DayResult; `winner_table_data`:
    Rückgabe von hrb_evaluation.winner_table; `curve`: Tupel CurvePoint oder None; `sample_rows`:
    Tupel SampleRow oder None."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    import hrb_constants as C
    import hrb_evaluation as E

    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(38, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    def note(text, size=8):
        pdf.set_font("Helvetica", "I", size)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "B", 16)
    line("Robuste Hof-Disposition: Haelt der Einsatzplan die Stoerung aus?", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    s = settings
    strength = s["fail_duration"] if s["disruption"] == C.DISRUPTION_AUSFALL else s["noise_sigma"]
    strength_unit = "min Ausfalldauer" if s["disruption"] == C.DISRUPTION_AUSFALL else "% Rauschstaerke"
    heading("Szenario")
    pairs([("Aufträge", f"{s['n_jobs']} Aufträge, Ø Fristpuffer {s['buffer']} min, Hoflänge {s['yard_length']} m"),
          ("Flotte", f"praktisches Minimum K = {day.kmin}, Abstand +{s['fleet_delta']}, eingesetzt {day.k} Fahrzeuge"),
          ("Störung", f"{C.DISRUPTION_LABELS[s['disruption']].split(' ', 1)[1]}, Stärke {strength} {strength_unit}"),
          ("Seed", str(s["seed"]))])
    pdf.ln(3)

    heading("Ergebnis (dieser Tag)")
    rows = [[C.STRATEGY_SHORT[k], f"{day[k].wt:.2f}", f"{day[k].wt - day[C.S_STARR].wt:+.2f}"] for k in C.STRATEGY_KEYS]
    table(["Strategie", "gew. Verspätung (min/Auftrag)", "Delta gegen starr"], [45, 60, 45], rows)
    note("Gewichtete Verspätung je Auftrag; starr = Vorausplan unverändert durchgezogen, online = beste von FIFO/EDD/ATC live, "
        "reaktiv = Vorausplan als Start, ab Störung per lokaler Suche neu verteilt.")
    pdf.ln(3)

    keep_together(60)
    heading("Sieger-Tabelle: Flottenabstand x Störungsart (derselbe Tag)")
    wt_rows = []
    for delta in (0, 1, 2):
        row = [f"+{delta}" if delta else "Minimum"]
        for disruption in (C.DISRUPTION_AUSFALL, C.DISRUPTION_RAUSCHEN):
            cell = winner_table_data.get((delta, disruption))
            row.append("-" if cell is None else f"starr {cell[0]:.2f} / online {cell[1]:.2f} / reaktiv {cell[2]:.2f}")
        wt_rows.append(row)
    table(["Flotte", "Ausfall", "Rauschen"], [24, 80, 80], wt_rows)
    pdf.ln(3)

    if curve is not None:
        keep_together(90)
        heading("Umschlagpunkt-Kurve")
        table(["Störstärke", "starr", "online", "reaktiv"],
             [30, 30, 30, 30], [[f"{p.strength:g}", f"{p.starr:.2f}", f"{p.online:.2f}", f"{p.reaktiv:.2f}"] for p in curve])
        note("Gewichtete Verspätung je Auftrag über die Störstärke, bei der eingestellten Flotte, für die eingestellte Störungsart.")
        pdf.ln(3)

    if sample_rows is not None:
        keep_together(80)
        heading("Stichprobe und Urteil")
        srows = []
        for key in C.STRATEGY_KEYS:
            med, lo, hi = E.spread_of(sample_rows, key)
            srows.append([C.STRATEGY_SHORT[key], f"{med:.2f} [{lo:.2f}; {hi:.2f}]"])
        table(["Strategie", "Median [10.; 90. Perzentil]"], [40, 70], srows)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        for label_a, label_b, field_a, field_b in (("online", "starr", C.S_ONLINE, C.S_STARR), ("reaktiv", "starr", C.S_REAKTIV, C.S_STARR)):
            pdf.multi_cell(0, 5, pdf_text("- " + E.verdict_text(sample_rows, label_a, label_b, field_a, field_b)[1]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        note(f"Basis: {len(sample_rows)} Tage (Seeds {sample_rows[0].seed}-{sample_rows[-1].seed}, nicht der eingestellte Seed), "
            "Median [10. bis 90. Perzentil].")
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Das praktische Minimum ist gefunden, nicht bewiesen; die Matching-Untergrenze ist eine gültige, aber bei echten Zeitfenstern nicht immer scharfe Zusatzinfo.",
        "Fahrzeit-Rauschen wirkt nur auf die Leerfahrt, nicht auf Kupplung/Servicezeit; das ausgefallene Fahrzeug ist ab Fensterende sofort wieder voll verfügbar.",
        "Die Reihenfolge starr gegen online hängt an der Störungsart und ist am praktischen Minimum nicht robust gegen die Wahl des Störszenarios.",
        "Bei kleinen Fahrzeiten (2-4 min) rundet math.ceil viele Rauschziehungen unter etwa 30 % Stärke auf denselben Wert.",
        "Alle Zahlen sind Größenordnungen aus einer Simulation, keine Messung an einem echten Hof; jeder Endplan ist unabhängig auf Machbarkeit geprüft.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
