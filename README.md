# Robuste Hof-Disposition + Flottengröße – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-hofrobust-demo.streamlit.app/)**

Interaktive Fall-Demo der Yard-Management-Linie: Ein Hof-Einsatzplan für Wechselbrücken kennt alle Fahraufträge im Voraus und plant vor - aber was, wenn ein **Hoffahrzeug ausfällt** oder die **Fahrzeiten
schwanken**? Die Demo zeigt, wie unterschiedlich der starre Vorausplan je nach Störungsart bricht, was **reaktives Nachplanen** bringt, und wie viele Fahrzeuge der Hof braucht, damit sich das überhaupt lohnt
(**praktisches Minimum**). Baut auf dem Fachmodell von `yard-demo` auf (Aufträge, Fristen, Anfahrtszeiten, FIFO/EDD/ATC, Vorausplanung per Iterated Local Search); die Flottenregler-Idee ("Abstand zum
praktischen Minimum") ist dieselbe wie bei `fahrzeugflotte-demo`, hier nur als Analogie referenziert, keine gemeinsame Rechnung.

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning", verschmilzt zwei geprüfte Vorab-Check-Ideen (`hof-planung/vorab_robust`: Fahrzeugausfall,
`hof-planung/vorab_flotte`: Flottengröße + Fahrzeit-Rauschen) zu **einer** Demo mit einem Umschalter, wie es der dritte Check `hof-planung/vorab_kombiniert` empfahl.

## Warum dieses Problem

Die naheliegende Geschichte wäre "starrer Plan bricht unter Störung, reaktives Nachplanen gewinnt" - das bekannte Muster aus `fahrzeugflotte-demo`, der Robusten Kaiplatzplanung und der Blockzuweisung. Sie
trägt auch hier, aber mit einem **Twist, der die anderen drei Demos nicht haben**: Am **praktischen Minimum** widersprechen sich starr und online je nach **Störungsart**. Bei einem **Fahrzeugausfall** verliert
der starre Plan klar gegen die beste Online-Regel (im Beispiel-Tag 3,57 gegen 0,92 min/Auftrag). Bei **Fahrzeit-Rauschen** gibt es am selben Punkt **keinen verlässlichen Sieger** zwischen starr und online -
gemessen an 60 unabhängigen Tagen gewinnt online an 48 %, starr an 48 % (ein Münzwurf, siehe "Befunde und Korrekturen" unten). Nur **reaktiv** ist über beide Störungsarten und alle Flottenstufen hinweg
verlässlich gut. Eine einzelne nahtlose Demo hätte diesen Gegensatz verwischt - deshalb der Umschalter Störungsart statt zwei getrennter kleiner Demos.

## Modell

Fachmodell wörtlich aus `yard-demo`: ein Betriebshof mit Toren, Stellplatzfeldern (Ankunft/Mittelfeld/Abfahrt) und Hoffahrzeugen, die Wechselbrücken zwischen ihnen verschieben. Jeder Fahrauftrag hat eine
Freigabezeit, eine Frist und ein Gewicht (Abfahrt 4, Bereitstellung 2, Abräumen 1); Ziel ist die **gewichtete Verspätung je Auftrag** (min), lexikografisch vor der Leerfahrtzeit. Anfahrtszeiten Manhattan,
aufgerundet. **Einzige echte Erweiterung** gegenüber `yard-demo`: `sequence_cost_from`/`sequence_plan_from`/`local_search_from` generalisieren dieselbe Kostenfunktion und Umhängen-und-Tauschen-Suche auf einen
**variablen Fahrzeug-Startzustand** (frei ab, letzter Ort) statt fest (0, Depot) - nötig, um ab einem Störzeitpunkt neu zu planen.

**Praktisches Minimum K:** kleinste Flottengröße, bei der FIFO, Frist zuerst (EDD), ATC oder die Vorausplanung 0 gewichtete Verspätung erreichen (Suche über k = 1, 2, ...). Anders als bei `fahrzeugflotte-demo`
(feste Kran-Aufnahmezeiten, exakter Matching-Beweis) hat `yard-demo` echte Zeitfenster: die Matching-Untergrenze ist deshalb nur eine **gültige, nicht immer scharfe** Zusatzinfo (Cross-Check auf 12 Kleinstinstanzen:
6/12 exakt, 6/12 zu niedrig, nie zu hoch - siehe `tests/test_fleet.py`). Der Flottenregler steht deshalb auf **Abstand zum Minimum (0/+1/+2, kein Minus)**.

**Störungsart 1 (Ausfall):** ein zufälliges Fahrzeug fällt für eine gewählte Dauer (0-60 min) ab einem zufälligen Zeitpunkt im Ankunftsfenster aus; laufende Fahrten enden normal, das Fahrzeug kann während
der Störung nur nicht neu losfahren. Bricht die feste Vorausplan-Reihenfolge direkt (Kaskade auf alle Folgeaufträge des Fahrzeugs).

**Störungsart 2 (Rauschen):** jede Anfahrt dauert ⌈t · (1 + σ·U)⌉ mit U ∈ [0, 1) und Störstärke σ (0-60 %), nur verspätend, je Ziel-Auftrag gezogen (gemeinsame Zufallszahlen für alle drei Strategien - gepaarter
Vergleich). Wirkt nur auf die Leerfahrt, nicht auf Kupplung/Servicezeit (vereinfachte Annahme). Verschiebt nur Zeiten, macht die Reihenfolge nicht unmöglich - deshalb ein anderes Bruchmuster als der Ausfall.

Formal im Expander „📐 Mathematische Formulierung" der App.

## Methodik – drei Strategien

- **🔒 starr:** der vorab berechnete ILS-Plan (`improve_plan`, unverändert aus `yard-demo`), unter der Störung stur durchgezogen. Bei Ausfall verschiebt sich ein in das Störfenster fallender Start ans
  Fensterende ("wartet, dann fährt los" - eine optimistische Vereinfachung, siehe "Befunde und Korrekturen").
- **🔄 online (beste Regel):** FIFO / Frist zuerst (EDD) / ATC, live entschieden, kein Vorwissen über die Störung - sieht ein ausgefallenes Fahrzeug einfach als "nicht frei" bzw. entscheidet mit den
  tatsächlichen (verrauschten) Fahrzeiten.
- **⚡ reaktiv:** der Vorausplan als Startlösung; ab Störbeginn (Ausfall) bzw. von Anfang an (Rauschen, da es kein Störfenster gibt) werden die noch offenen Aufträge (auch über Fahrzeuge hinweg) per derselben
  lokalen Suche neu verteilt - ausgehend vom echten Zustand jedes Fahrzeugs.

Dazu **🔗 Mindestflotte**: die Minimum-Suche, die Matching-Untergrenze (Zusatzinfo mit Einschränkung) und ein CP-SAT-Cross-Check (OR-Tools, nur auf Klick, Zeitlimit 10 s je Instanz - siehe Löser-Hinweis in
`hrb_fleet.solve_exact`, eigene Kopie ohne Laufzeit-Import aus `yard-demo`).

Live rechnet die App nur den eingestellten Tag mit allen drei Strategien (die Minimum-Suche kostet bei kaltem Cache rund 2 s je Seed, danach ist sie gecacht); **Sieger-Tabelle** (6 Kombinationen),
**Umschlagpunkt-Kurven** (beide Störungsarten) und die **Stichprobe** (20 Tage, Fortschrittsbalken, rund 1 s je Tag bei gecachtem Minimum) laufen hinter je einem Knopf.

## Befunde (gemessen, keine Behauptungen)

30 Aufträge, Fristpuffer 15 min, Hoflänge 450 m (Standardeinstellungen), Flottenabstand 0 (Minimum) wenn nicht anders angegeben. Zahlen aus **60 unabhängigen Tagen** (Seeds 6000-6059, `tools/PRESET_SWEEP.md`)
bzw. dem gezeigten Tag (Seed 7039), im Code dieser Demo selbst gerechnet und als Test festgehalten (`tests/test_preset_stories.py`, unabhängig mit 40 weiteren Tagen).

| Frage | Befund |
|---|---|
| **Trägt der Aufhänger überhaupt?** | Ja: bei Ausfall (stark, 55 min, Minimum) Median starr 12,40 gegen online 1,20 gegen reaktiv 0,34 min/Auftrag (60 Tage). |
| **Der Widerspruch am Minimum, Ausfall** | starr bricht klar: Tag 7039, Ausfalldauer 20 min: starr 3,57, online 0,92, reaktiv 0,08 min/Auftrag. |
| **Der Widerspruch am Minimum, Rauschen** | **Kein verlässlicher Sieger:** starr 1,50, online 1,87 min/Auftrag (Tag 7039, σ = 60 %); über 60 Tage gewinnt online an 48 %, starr an 48 % der Tage - auch über zehn Rauschziehungen je Tag gemittelt bleibt die Richtung von Seed zu Seed unterschiedlich. |
| **Reserve gegen Ausfall (+1)** | starr 1,03, online 0,00, reaktiv 0,00 min/Auftrag (Tag 7039, 55 min) - online/reaktiv praktisch wartefrei, starr bleibt teuer (nutzt die Reserve nicht). |
| **Reserve gegen Rauschen (+1)** | starr 1,20, online 0,00 min/Auftrag bei σ = 60 % (Tag 7039) - der Widerspruch verschwindet ab einer Reserve, online gewinnt jetzt auch bei Rauschen. |
| **Reaktiv ist der rote Faden** | Über 60 Tage (Ausfall, stark): reaktiv ≤ starr an ≥ 80 % der Tage, reaktiv ≤ online an ≥ 70 % - **keine strikte Invariante** (siehe unten). |
| **Praktisches Minimum ist kein Beweis** | Matching-Untergrenze ≤ praktisches Minimum in allen 22 Cross-Checks (12 Kleinstinstanzen gegen Brute-Force + 10 größere gegen das praktische Minimum, nie verletzt), aber nur 6/12 exakt bei den Kleinstinstanzen (`tests/test_fleet.py`). |
| **Rechenzeit** | Minimum-Suche rund 2 s je (Aufträge, Seed) bei kaltem Cache, danach gecacht; ein Tag rund 0,3-0,4 s; Stichprobe von 20 Tagen rund 45 s bei kaltem Cache (Fortschrittsbalken). |
| **Presets** | Ein gemeinsamer Seed (**7039**) für alle fünf; jede Kennzahl zwischen dem 5. und 95. Perzentil der Grundgesamtheit. Von 60 Kandidaten tragen nur **2** alle fünf Geschichten gleichzeitig (`tools/PRESET_SWEEP.md`). |

## Ehrliche Grenzen

- **Fahrzeit-Rauschen wirkt nur auf die Leerfahrt**, nicht auf Kupplung/Servicezeit - eine vereinfachte Annahme (aus `fahrzeugflotte-demo` übernommen).
- **Das ausgefallene Fahrzeug ist ab Fensterende sofort wieder voll verfügbar** (kein Reparaturaufschlag, keine Nachwirkung).
- **Die reaktive Suche kennt die Störung erst ab ihrem Beginn** (kein Vorwissen, kein Forecast).
- Bei kleinen Fahrzeiten (2-4 min) rundet `math.ceil` Rauschziehungen unter etwa 30 % Stärke auf denselben Wert wie höhere Stärken - der Regler wirkt dort kaum unterscheidbar (kein Fehler, ein Randbefund aus
  `vorab_kombiniert`, als Test festgehalten, siehe `tests/test_scenario.py::test_noise_rounding_trap_below_thirty_percent_is_reproducible`).
- **Die Reihenfolge "starr gegen online" hängt an der Störungsart** und ist am praktischen Minimum nicht robust gegen die Wahl des Störszenarios - im Text der App ausdrücklich benannt, nicht nur im
  Kleingedruckten.
- Das praktische Minimum ist **gefunden, nicht bewiesen**; die Matching-Untergrenze ist nur eine notwendige, keine hinreichende Bedingung bei echten Zeitfenstern.
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an einem echten Hof**; jeder Endplan wird unabhängig mit der echten `check_feasible`-Prüfung (Freigaben, Anfahrtszeiten) geprüft.

## Befunde und Korrekturen gegenüber dem Plan

Der freigegebene Plan (`hof-planung/plan_hofrobust.py`/`.html`) beruhte auf nur **8 kombinierten Seeds** aus `vorab_kombiniert` und markierte seine Presets ausdrücklich als vorläufig ("in AP 6 selbst mit
größerer Stichprobe nachmessen"). Das ist hier geschehen (60 Tage, `tools/PRESET_SWEEP.md`) - mit drei ehrlichen Korrekturen:

- **"Rauschen am Minimum" trägt nicht wie im Plan behauptet.** Der Plan (8 Seeds) behauptete "am Minimum ist bei Rauschen der starre Plan robuster als online" (starr 2,13 gegen online 2,86 im 8-Seed-Mittel).
  Bei 60 unabhängigen Tagen zeigt sich: **kein verlässlicher Sieger** - online gewinnt an 48 % der Tage, starr an 48 %, ein Münzwurf, auch wenn man je Tag über zehn Rauschziehungen mittelt (die Richtung kippt
  von Seed zu Seed). Nur **reaktiv ist verlässlich am besten.** Der Text der App, das Preset und die Sieger-Tabelle sind entsprechend umformuliert ("Münzwurf" statt "starr ist robuster").
- **Der im Plan vorgeschlagene Seed 4 trägt keine der fünf Preset-Geschichten.** Bei Seed 4 ist die Flotte am praktischen Minimum so leistungsfähig, dass starr = online = reaktiv = 0,0 min/Auftrag gilt - sowohl
  für Ausfall als auch für Rauschen (stark), siehe `hof-planung/vorab_kombiniert/rows.json`. Ersetzt durch **Seed 7039** (Kandidatenpool 7000-7059 gegen Grundgesamtheit 6000-6059 geprüft; von 60 Kandidaten
  tragen nur 2 alle fünf Geschichten gleichzeitig).
- **Die Invariante "reaktiv ≤ starr, reaktiv ≤ online, nie verletzt" aus dem Plan (Abschnitt 11) gilt nicht strikt.** Schon `vorab_robust/ERGEBNIS.md` selbst zeigt nur 150/200 bzw. 180/200 "reaktiv < starr",
  nicht 200/200. Grund: `simulate_rigid` nutzt eine **optimistische "wartet, dann fährt los"-Vereinfachung** - nach der erzwungenen Verzögerung auf `bend` wird keine erneute Anfahrtszeit mehr aufgeschlagen
  (siehe `feedback_interval_avoidance_vs_iterative_pushing`). Dadurch kann der starre Plan in Einzelfällen günstiger aussehen, als eine echte Neuplanung ab dem tatsächlichen (physikalisch korrekten) Zustand
  liefert. Die Tests prüfen deshalb einen Anteil (≥ 70-80 % der Tage), keine strikte Invariante (`tests/test_disruption.py`).
- **Ein früherer Entwurf der Preset-Kriterien nutzte Tage-Anteile (`share_wins`) als Pass/Fail-Maß** - für den einen gezeigten Tag (ein Tupel der Länge 1) kann ein Anteil aber nur 0 % oder 100 % sein, nie z. B.
  "zwischen 15 % und 50 %". Dadurch war `holds()` für jedes Preset unerfüllbar (0 von 60 Kandidaten trugen "Rauschen am Minimum" oder "Leichter Ausfall" an einem Einzeltag). Behoben: alle Kriterien in
  `hrb_stories.py` sind jetzt Median-/Mittelwert-Vergleiche, die für ein Tupel der Länge 1 auf den Einzelwert selbst zusammenfallen; die Tage-Anteile stehen nur noch als Dokumentation (`hrb_stories.share_*_wins`).
- **"Leichter Ausfall" braucht den Mittelwert, nicht den Median** (der Plan formuliert die Geschichte selbst als Mittelwert-Aussage: "im Mittel liegt online schon vorn"). Bei so leichter Störung (20 min)
  bleiben die meisten Tage bei 0 Verspätung; der Median versteckt den Effekt (siehe `feedback_skewed_gains_show_distribution`).
- Der Plotly-Umschlagpunkt-Kurve für Rauschen hatte in einer frühen Bauversion einen Skalierungsfehler (Störstärke fälschlich × 100 auf der Achse, "6000 %" statt "60 %") - beim Browser-Test gefunden und behoben,
  bevor die App fertig war.
- Die bedingte Meldung stand versehentlich als Ternary-Ausdruck-Anweisung (`st.info(...) if ... else st.success(...)`) im Code: Streamlits "magic" schreibt den Rückgabewert eines nackten Ausdrucks automatisch
  auf die Seite, und ein `DeltaGenerator`-Objektrepr erschien sichtbar unter der Meldung. Beim realen Browser-Test gefunden (AppTests prüfen nur auf den erwarteten Text, nicht auf zusätzliche Elemente) und
  durch eine gewöhnliche `if`/`elif`/`else`-Kette ersetzt.
- Im Browser erscheinen bei Plotly-Diagrammen unter hoher Rechenlast vereinzelt Konsolenfehler (`<rect> attribute width: A negative value is not valid`, `<text> attribute y: Expected length, "-Infinity"`);
  das fertig gerenderte DOM enthält danach keine negativen Werte mehr (per `document.querySelectorAll` geprüft) - dieselbe bereits root-verursachte Plotly.js-Layout-Race wie in
  `feedback_plotly_infinity_console_error_investigated`, keine neue Ursache in diesem Code.

## Tests

`python -m pytest tests/ -v` – **177 Tests**, lokal (Windows) rund 4 Minuten (keine feste Zeitgrenze außer je Mutant, siehe unten; die Minimum-Suche macht viele Tests rechenintensiv). Zusammensetzung:

- **Szenario (`test_scenario.py`):** Determinismus, Unabhängigkeit von `n_vehicles`, gültige Aufträge/Fristen, Rauschfaktoren, Rundungsfalle als Test festgehalten.
- **Dispatch (`test_dispatch.py`):** Regressionstest der `_from`-Erweiterung gegen den `yard-demo`-Fixpunkt ((0, None) reproduziert `sequence_cost`/`sequences_to_plan` exakt), Online-Regeln machbar und
  deterministisch, lokale Suche verschlechtert nie, Handrechnung.
- **Störung (`test_disruption.py`):** Handrechnung aus `hof-planung/vorab_robust/hand_check.py` (starr=3, online=0, reaktiv=0 exakt), `check_feasible` auf jedem Endplan beider Störungsarten, reaktiv-Anteile
  statt strikter Invarianten (siehe "Befunde und Korrekturen"), gemeinsame Zufallszahlen je (Seed, Flottenabstand).
- **Mindestflotte (`test_fleet.py`):** praktisches Minimum gegen Brute-Force auf Kleinstinstanzen, Matching-Untergrenze nie über dem Minimum, CP-SAT-Cross-Check.
- **Auswertung (`test_evaluation.py`):** Kennzahlen, Perzentil/Verteilung, Verdikt mit künstlichen Daten (klar/uneindeutig, auch bei großem, aber verrauschtem Mittel), bedingte Meldung in allen vier Arten.
- **Presets (`test_stories.py`, `test_preset_stories.py`):** künstliche Werte an jeder Schwelle; echte Daten (40 Tage, parallel gerechnet), Geschichte im Median UND am gezeigten Tag, Typizität je Kennzahl.
- **Figuren, PDF, End-to-End (`test_visualization.py`, `test_pdf_export.py`, `test_app.py`):** Achsen fest, Störfenster/Rauschmarkierung im Gantt, Sonderzeichen im PDF (`σ`, `–`, `€`), Skelett und Footer, jedes
  Preset, mode-conditional Regler (kein toter Zweitregler), Permalink, alle Regler an Min/Max, bedingte Meldung, alle Knopf-Pfade (Sieger-Tabelle, Kurven, Stichprobe, CP-SAT-Cross-Check), PDF, keine toten
  Dateilinks.

**Mutationstest** (`tools/mutation_check.py`, 84 Mutanten, Schwerpunkt `hrb_disruption.py`/`hrb_fleet.py` wie vom Plan gefordert, dazu die übrigen neuen Module, ohne `test_preset_stories.py` - dessen eigener
Prozess-Pool multipliziert sich sonst mit den parallelen Mutanten und überlastet die Maschine): **52 gefunden, 32 überlebt** (ein erster Lauf fand 34/50; die Differenz sind echte Lücken, die während des Baus
geschlossen wurden, siehe unten). Davon sind:

- **Echte Lücken geschlossen (neue/erweiterte Tests):** ein EDD-Tippfehler (`max` statt `min` bei der Fristauswahl in `choose_edd` - hätte die Regel in "späteste Frist zuerst" verkehrt), die fehlende
  `OBJ_BIG`-Gewichtung im CP-SAT-Modell wäre unbemerkt geblieben (Verspätung hätte gegen Leerfahrt verlieren können - eigens konstruierte Instanz mit echtem Zielkonflikt), eine `and`/`or`-Verwechslung in der
  bedingten Meldung (`starr_haelt`/`reserve_wartefrei`), ein fehlender Schutz vor `IndexError` in `percentile`, drei Terme der Matching-Untergrenzen-Formel (`_optimistic_can_follow`) einzeln geprüft,
  `math.ceil` gegen `round` bei den Anfahrtszeiten, `max` gegen `min` beim Planungshorizont, Grenzfälle des Ausfallfensters (`down`), `isfinite`/Bereichsgrenzen der Permalink-Regler, `€`-Ersetzung im PDF
  (der eigene Test rief `pdf_text` nie mit einem echten `€`-Zeichen auf).
- **Bekannte Äquivalente (beweisbar, keine Lücke):** #17 (`== 0` gegen `<= 0` für eine Größe, die nie negativ wird), #26 (Verspätung *genau* auf der Frist trägt `(Ende − Frist) = 0` bei - der Vergleichsoperator
  ändert das Produkt nicht, unabhängig von `>` oder `>=`), #51 (`sigma == 0` gegen `sigma <= 0`; der Regler erlaubt nie negative Werte), #59 (der `isfinite`-Zweig in `parse_setting` ist mit den aktuellen
  `SETTING_SPECS` toter Code - keine Einstellung hat einen `float`-wertigen Caster).
- **Akzeptierte, dokumentierte Lücken (geringes Risiko, nicht geschlossen):** 16 `>=`/`>`-Grenzfälle der Preset-Schwellen in `hrb_stories.py` (betreffen nur die Abnahme-Kriterien selbst, nicht das
  Laufzeitverhalten der App); Unentschieden-Tiebreaks in der lokalen Suche/ILS (`<` gegen `<=`, ändert nur, welche von mehreren gleich guten Lösungen behalten wird, nie die Kosten); zwei Online-Regel-Ties
  (`best_online_*`, bei exaktem Gleichstand wird die zuerst geprüfte statt irgendeiner Regel gewählt - nur der angezeigte Plan ändert sich, nicht die Kennzahl); die `min`/`max`-Verwechslung in
  `best_weighted_tardiness_total`s Regel-Schleife (wird in der Praxis fast immer von der anschließenden Vorausplanung überdeckt - drei gezielt konstruierte Testinstanzen haben sie nicht ausgelöst); zwei
  Rundungsfälle bei der Instanzerzeugung (`n_cols`, `slack`-Verteilung) und zwei rein optische Grenzfälle in den Diagrammen (Sieger-Heatmap-Farbe, Rausch-Markierung eines Balkens bei exaktem Gleichstand).

Die CI (`.github/workflows/tests.yml`, Linux, wöchentlich sowie bei jedem Push/PR) installiert die neuesten Versionen von `streamlit`/`plotly`/`ortools`/`fpdf2` (`requirements.txt` ist nicht gepinnt); die Tests
prüfen deshalb Kennzahlen mit Abstand zur Schwelle, nie exakte Extremwerte verrauschter Größen (siehe `feedback_ci_unpinned_numeric_asserts`, `feedback_ci_platform_robust_tests`).

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar (mode-conditional Störstärke-Regler), Hauptansicht, Blick in den Tag, Kernabschnitt mit Knöpfen, Verfahrensvergleich, Texte |
| `hrb_constants.py` | Regler-Grenzen, feste Modellannahmen, `PRESETS`, Farben, Strategie-Beschreibungen |
| `hrb_scenario.py` | Instanzerzeugung (Aufträge, Anfahrtsmatrix), Rauschfaktoren, `make_noisy_instance` |
| `hrb_dispatch.py` | FIFO/EDD/ATC (auch störungsbewusst), Vorausplanung/ILS, lokale Suche fest UND mit variablem Startzustand (`_from`) |
| `hrb_disruption.py` | Ausfall-Draw, `simulate_rigid`, `simulate_reactive`, Rauschen-Gegenstücke, `reactive_under_noise` |
| `hrb_fleet.py` | Praktisches Minimum (Suche), Matching-Untergrenze (eigene Implementierung), CP-SAT-Cross-Check |
| `hrb_evaluation.py` | `check_feasible`/`evaluate` (Basis wie `yard_evaluation.py`), ein Tag mit allen Strategien, Sieger-Tabelle, Umschlagpunkt-Kurve, Stichprobe, Verdikt, bedingte Meldung |
| `hrb_visualization.py` | Gantt je Fahrzeug (Störfenster/Rauschmarkierung), Sieger-Heatmap, Umschlagpunkt-Kurve, Spannweite/Verteilung (alle Achsen fest) |
| `hrb_ui_panel.py` | Panel je Strategie, Mindestflotte-Panel, Vergleichstabelle |
| `hrb_pdf_export.py` | PDF-Ergebnis (`fpdf2`, Kernschrift, Sonderzeichen-Bereinigung inkl. `σ`) |
| `hrb_presets.py` | `SETTING_SPECS`, Permalink (Begrenzen und Einrasten), Presets, Seed-Knopf |
| `hrb_stories.py` | Abnahmekriterien der Presets (Quelle für Werkzeug und Tests) |
| `tools/tune_presets.py`, `tools/PRESET_SWEEP.md` | Preset-Abstimmung und ihr Bericht (AP 6) |
| `tools/mutation_check.py` | Fehler-Einbau-Test |
| `tests/` | siehe oben |

## Bewusst nicht umgesetzt (mögliche Erweiterungen)

- **Gleichzeitiger Mischbetrieb beider Störungsarten** (Ausfall UND Rauschen zugleich) - nicht gemessen, würde die Kernaussage verwässern (Plan Abschnitt 15).
- **Rauschen auf die Servicezeit**, Reparaturaufschlag nach Ausfallende, mehr als zwei Fahrzeug-Reserven.
- **Kontinuierlicher Störstärke-Regler ohne Stützpunkt-Absicherung** - nur 0/20/55 min bzw. 0/25/60 % sind gemessen, Zwischenwerte interpoliert.
- Kopplung an Tor-Slots/andere Hafen-Module, Kante Minimum−1/−2 als eigener Regler-Bereich (nur Kontext im Text).

## Verwandte Demos mit demselben mathematischen Modell

Verschiedene Themen im Portfolio teilen (fast) dasselbe Modell. Vor einer neuen Demo-Idee deshalb das
Modell vergleichen, nicht die Kulisse (Stand 2026-09-23):

- **Starrer Plan gegen reaktives Nachplanen unter Störung** ist ein wiederkehrendes Muster: `fahrzeugflotte-demo`,
  `robuste-kaiplatz-demo`, `blockzuweisung-demo` und `hofrobust-demo`. Der Twist von `hofrobust-demo`: am praktischen
  Minimum hängt der Sieger von der Störungsart ab (Ausfall: reaktiv klar besser, Fahrzeit-Rauschen: Münzwurf). Ideen wie
  robuste Touren bei unsicheren Standzeiten oder Same-Day-Aufträge im Nahverkehr (`vrp_demo`) wären das fünfte Exemplar
  und nur mit einem Hook jenseits von "reaktiv gewinnt" sinnvoll.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py population|seeds|shown`. Fehler-Einbau: `python tools/mutation_check.py [--jobs N] [--dry-run]`.

---

Gebaut mit Streamlit, Plotly, OR-Tools (CP-SAT) und fpdf2.
