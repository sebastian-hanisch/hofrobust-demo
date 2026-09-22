"""Abnahmekriterien der Presets: welche Geschichte erzählt jedes Beispielszenario, und woran erkennt
man, dass sie trägt? Einzige Quelle für `tools/tune_presets.py` (Abstimmung) und
`tests/test_preset_stories.py` (Abnahme an echten Daten). Jedes Kriterium ist eine Aussage über ein
Tupel von `SampleRow`s (hrb_evaluation) - über viele Tage (`criteria`) GENAUSO wie über den EINEN
Tag, den das Preset zeigt (`holds`, ein Tupel mit einer Zeile). Deshalb bestehen alle Kriterien aus
Median/Mittelwert-Vergleichen (die für ein Tupel der Länge 1 auf den Einzelwert selbst zusammenfallen)
- KEINE Tage-Anteile (die für einen einzelnen Tag nur 0 % oder 100 % sein können und `holds` für jedes
Preset unerfüllbar machen würden; ein früherer Entwurf hatte das, siehe Git-Historie/PRESET_SWEEP.md).

Startwerte aus dem freigegebenen Plan (plan_hofrobust.py Abschnitt 7, dort ausdrücklich als vorläufig
markiert, nur 8 kombinierte Seeds aus vorab_kombiniert). Hier mit 60 unabhängigen Tagen nachgemessen
(`tools/PRESET_SWEEP.md`) - zwei ehrliche Korrekturen gegenüber dem Plan:

  - "Leichter Ausfall": der MEDIAN von starr/online liegt bei so leichter Störung fast immer bei 0
    (die meisten Tage bleiben ohne Verspätung) - die schiefe Verteilung versteckt den Effekt im
    Median (siehe feedback_skewed_gains_show_distribution). Das Kriterium nutzt hier bewusst den
    MITTELWERT (wie im Plan selbst: "im Mittel liegt online schon vorn"). Dass starr an vielen,
    aber nicht allen Tagen noch gewinnt (35 % der 60 Tage), steht im README/PRESET_SWEEP als
    Zusatzbefund, ist aber kein Pass/Fail-Kriterium (siehe oben).
  - "Rauschen am Minimum": die im Plan behauptete Richtung ("starr robuster als online am Minimum")
    trägt bei 60 unabhängigen Tagen NICHT verlässlich (Anteil "online gewinnt" 48 %, "starr gewinnt"
    48 % - ein Münzwurf, auch bei über zehn Rauschziehungen je einzelnem Tag gemittelt). Das
    Kriterium prüft stattdessen ehrlich genau das: starr und online liegen nah beieinander (kein
    verlässlicher Sieger), aber reaktiv ist verlässlich besser als beide - siehe README."""

import hrb_evaluation as E

TYPICAL = ("starr", "online", "reaktiv")


def criteria(name, rows):
    med = E.median_of
    mean = E.mean_of
    starr_med, online_med, reaktiv_med = med(rows, "starr"), med(rows, "online"), med(rows, "reaktiv")
    if name == "Ausfall am Minimum":
        return [(starr_med >= 6.0, f"starr (Median) >= 6,0 min/Auftrag: {starr_med:.2f}"),
               (starr_med - online_med >= 3.0, f"starr - online (Median) >= 3,0: {starr_med - online_med:.2f}"),
               (reaktiv_med <= 4.0, f"reaktiv (Median) <= 4,0 min/Auftrag: {reaktiv_med:.2f}"),
               (online_med - reaktiv_med >= 0.0, f"online - reaktiv (Median) >= 0,0: {online_med - reaktiv_med:.2f}")]
    if name == "Rauschen am Minimum":
        return [(reaktiv_med <= 1.2, f"reaktiv (Median) <= 1,2 min/Auftrag: {reaktiv_med:.2f}"),
               (starr_med - reaktiv_med >= 0.2, f"starr - reaktiv (Median) >= 0,2: {starr_med - reaktiv_med:.2f}"),
               (online_med - reaktiv_med >= 0.2, f"online - reaktiv (Median) >= 0,2: {online_med - reaktiv_med:.2f}"),
               (abs(starr_med - online_med) <= 0.6,
                f"starr und online liegen nah beieinander (kein verlässlicher Sieger): |{starr_med:.2f} - {online_med:.2f}| = {abs(starr_med - online_med):.2f}")]
    if name == "Leichter Ausfall":
        starr_mean, online_mean, reaktiv_mean = mean(rows, "starr"), mean(rows, "online"), mean(rows, "reaktiv")
        return [(starr_mean >= 1.0, f"starr (Mittel) >= 1,0 min/Auftrag: {starr_mean:.2f}"),
               (online_mean <= 1.0, f"online (Mittel) <= 1,0 min/Auftrag: {online_mean:.2f}"),
               (online_mean < starr_mean, f"online (Mittel) < starr (Mittel): {online_mean:.2f} < {starr_mean:.2f}"),
               (reaktiv_mean <= 0.5, f"reaktiv (Mittel) <= 0,5 min/Auftrag: {reaktiv_mean:.2f}")]
    if name == "Reserve gegen Ausfall":
        return [(starr_med >= 1.0, f"starr (Median) >= 1,0 min/Auftrag: {starr_med:.2f}"),
               (online_med <= 0.3, f"online (Median) <= 0,3 min/Auftrag: {online_med:.2f}"),
               (reaktiv_med <= 0.2, f"reaktiv (Median) <= 0,2 min/Auftrag: {reaktiv_med:.2f}")]
    if name == "Reserve gegen Rauschen":
        return [(starr_med >= 0.2, f"starr (Median) >= 0,2 min/Auftrag: {starr_med:.2f}"),
               (starr_med - online_med >= 0.1, f"starr - online (Median) >= 0,1: {starr_med - online_med:.2f}"),
               (reaktiv_med <= 0.2, f"reaktiv (Median) <= 0,2 min/Auftrag: {reaktiv_med:.2f}")]
    raise KeyError(name)


def holds(name, row):
    return all(ok for ok, _ in criteria(name, (row,)))


def share_starr_wins(rows):
    """Nur für Text/Dokumentation (kein Pass/Fail-Kriterium, siehe Modul-Docstring)."""
    return E.share_wins(rows, "starr", "online")


def share_online_wins(rows):
    return E.share_wins(rows, "online", "starr")
