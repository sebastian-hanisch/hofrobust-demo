# Preset-Abstimmung (AP 6)

Werkzeug: `tools/tune_presets.py` (Modi `population`, `seeds`, `shown`); Kriterien in `hrb_stories.py`, Abnahme in `tests/test_preset_stories.py` (echte Daten, 40 Tage) und `tests/test_stories.py` (künstliche Werte an
den Schwellen). Deterministisch, kein Zeitlimit: geprüft werden Kennzahlen mit Abstand zur Schwelle, nie die Auswahl unter mehreren gleich guten Vorausplänen.

Messbasis: 60 Tage je Preset als Grundgesamtheit (Seeds 6000-6059), 60 Kandidaten (Seeds 7000-7059) für den gemeinsamen Seed; Abnahme in `test_preset_stories.py` nochmal unabhängig mit 40 Tagen (Seeds
9000-9039). Das ist bereits deutlich mehr als der Plan (Abschnitt 7: 8 kombinierte Seeds aus `vorab_kombiniert`) - ausdrücklich als vorläufig markiert und hier nachgemessen, wie in AP 6 vorgesehen.

## Grundgesamtheit (60 Tage je Preset; Median [10.; 90. Perzentil], min/Auftrag)

| Preset | starr | online | reaktiv |
|---|---:|---:|---:|
| Ausfall am Minimum | 12,40 [0,00; 29,91] | 1,20 [0,00; 8,19] | 0,34 [0,00; 4,70] |
| Rauschen am Minimum | 1,80 [0,67; 2,93] | 1,70 [0,13; 4,97] | 0,13 [0,00; 1,23] |
| Leichter Ausfall (Mittelwert!) | 1,68 | 0,55 | 0,18 |
| Reserve gegen Ausfall | 6,24 [0,00; 18,01] | 0,00 [0,00; 0,47] | 0,00 [0,00; 0,00] |
| Reserve gegen Rauschen | 0,67 [0,13; 1,40] | 0,00 [0,00; 0,40] | 0,00 [0,00; 0,00] |

Praktisches Minimum K liegt über alle 60 Tage bei 3, 4 oder 5 (n_jobs=30, Standardeinstellungen).

## Kriterien (`hrb_stories.py`): alle tragen über die Grundgesamtheit UND am gezeigten Tag (Seed 7039)

| Preset | Kriterium (Schwelle) | Grundgesamtheit (60 Tage) | Tag 7039 |
|---|---|---:|---:|
| Ausfall am Minimum | starr (Median) >= 6,0 | 12,40 | 22,24 |
| Ausfall am Minimum | starr - online (Median) >= 3,0 | 11,20 | 18,10 |
| Ausfall am Minimum | reaktiv (Median) <= 4,0 | 0,34 | 2,33 |
| Ausfall am Minimum | online - reaktiv (Median) >= 0,0 | 0,86 | 1,80 |
| Rauschen am Minimum | reaktiv (Median) <= 1,2 | 0,13 | 0,00 |
| Rauschen am Minimum | starr - reaktiv (Median) >= 0,2 | 1,67 | 1,50 |
| Rauschen am Minimum | online - reaktiv (Median) >= 0,2 | 1,57 | 1,87 |
| Rauschen am Minimum | \|starr - online\| <= 0,6 (kein Sieger) | 0,10 | 0,37 |
| Leichter Ausfall | starr (Mittel) >= 1,0 | 1,68 | 3,57 |
| Leichter Ausfall | online (Mittel) <= 1,0 | 0,55 | 0,92 |
| Leichter Ausfall | online (Mittel) < starr (Mittel) | 0,55 < 1,68 | 0,92 < 3,57 |
| Leichter Ausfall | reaktiv (Mittel) <= 0,5 | 0,18 | 0,08 |
| Reserve gegen Ausfall | starr (Median) >= 1,0 | 6,24 | 1,03 |
| Reserve gegen Ausfall | online (Median) <= 0,3 | 0,00 | 0,00 |
| Reserve gegen Ausfall | reaktiv (Median) <= 0,2 | 0,00 | 0,00 |
| Reserve gegen Rauschen | starr (Median) >= 0,2 | 0,67 | 1,20 |
| Reserve gegen Rauschen | starr - online (Median) >= 0,1 | 0,67 | 1,20 |
| Reserve gegen Rauschen | reaktiv (Median) <= 0,2 | 0,00 | 0,00 |

## Gewählter Seed

- **Ein gemeinsamer Seed 7039** für alle fünf Presets. Von 60 Kandidaten (7000-7059, außerhalb der Grundgesamtheit 6000-6059 und der Stichprobe 5000-5019) tragen nur **2** alle fünf Geschichten
  gleichzeitig (7039 und 7052) - die Kriterien sind bewusst eng (jede der fünf Geschichten muss an genau demselben Tag gelten). 7052 hat eine winzige Interquartilsbreite bei einer der Kennzahlen
  (praktisch 0 in der Grundgesamtheit), was den Abstandswert explodieren lässt (66666,67 Interquartilsbreiten) - ein Artefakt der Normierung, kein echter Ausreißer, aber **7039** ist mit Abstand
  6,90 (schlechtester Einzelabstand 1,15 Interquartilsbreiten über die sechs Kennzahlen aus `ST.TYPICAL`) klar der robustere Kandidat und wurde gewählt.
- **Abweichung vom Plan:** Abschnitt 7/15 schlug Seed 4 vor ("praktisches Minimum K=3 bei 6 von 8 kombinierten Seeds, liegt mittig in dieser Mehrheitsgruppe"). Bei Seed 4 ist die Flotte am
  Minimum jedoch so leistungsfähig, dass **starr = online = reaktiv = 0,0** für Ausfall UND Rauschen am Minimum gilt (siehe `hof-planung/vorab_kombiniert/rows.json`, Zeile seed=4/delta=0/ausfall/stark:
  alle drei 0,0) - keine der beiden Kernaussagen-Presets hätte an diesem Tag etwas zu zeigen. Das war mit nur 8 Seeds nicht vorherzusehen; AP 6 sollte genau das fangen, und hat es hier getan.

## Befunde und Korrekturen gegenüber dem Plan

- **"Rauschen am Minimum" trägt nicht wie im Plan behauptet.** Der Plan (gestützt auf 8 kombinierte Seeds aus `vorab_kombiniert`) behauptete "am Minimum ist bei Rauschen der starre Plan robuster
  als online" (starr 2,13 gegen online 2,86 im 8-Seed-Mittel). Bei 60 unabhängigen Tagen zeigt sich: **kein verlässlicher Sieger** - online gewinnt an 48 % der Tage, starr an 48 % (± Ties), ein
  Münzwurf. Das bleibt so, auch wenn man je Tag über zehn Rauschziehungen mittelt (einzeln geprüft: die Richtung kippt von Seed zu Seed). Nur **reaktiv ist verlässlich am besten**. Das Preset,
  der Text im Expander und die Sieger-Tabelle wurden entsprechend umformuliert ("Münzwurf" statt "starr ist robuster").
- **"Leichter Ausfall" braucht den Mittelwert, nicht den Median.** Bei so leichter Störung (20 min) bleiben die meisten Tage bei 0 Verspätung (Median starr/online praktisch 0) - die schiefe
  Verteilung versteckt den Effekt im Median (wie in `feedback_skewed_gains_show_distribution` gewarnt). Der Plan selbst formulierte die Geschichte bereits als Mittelwert-Aussage
  ("im Mittel liegt online schon vorn"); die Kriterien nutzen deshalb bewusst `E.mean_of`.
- **Der geplante Seed 4 trägt keine der fünf Geschichten** (siehe oben) - ersetzt durch 7039.
- **Die Tage-Anteil-Kriterien der ersten Fassung waren unerfüllbar für einen einzelnen Tag** (ein früherer Entwurf von `hrb_stories.criteria` nutzte `share_wins` als Pass/Fail-Kriterium; für ein
  Tupel der Länge 1 kann ein Anteil nur 0 % oder 100 % sein, nie z. B. "zwischen 15 % und 50 %" - dadurch hätte `holds()` für jeden einzelnen Tag scheitern müssen. Behoben: alle Kriterien sind jetzt
  Median-/Mittelwert-Vergleiche, die für ein Tupel der Länge 1 auf den Einzelwert selbst zusammenfallen; die Tage-Anteile stehen nur noch als Dokumentation in `hrb_stories.share_*_wins`.)
- **Die Invariante "reaktiv ist nie schlechter als starr" aus Plan Abschnitt 11 gilt nicht strikt** (siehe README "Befunde und Korrekturen" und `tests/test_disruption.py`): sie gilt in der großen
  Mehrheit der Tage (>= 80 % in den Tests), aber nicht immer - eine Modelleigenschaft von `simulate_rigid` (siehe README), keine Verletzung in `hrb_disruption.py` selbst.

## Nicht geändert

Die übrigen drei Schwellen (Ausfall am Minimum, Reserve gegen Ausfall, Reserve gegen Rauschen) tragen mit deutlichem Sicherheitsabstand sowohl über die Grundgesamtheit als auch am gezeigten Tag - hier
wurden nur die Werte aus den 60 Tagen übernommen, keine Konzeptänderung nötig.
