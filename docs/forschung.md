# Forschungsgrundlage

Stand: November 2026. Recherche zu Methoden und Befunden, auf denen Erfassung,
Auswertung und Selbstexperimente der App aufbauen. Quellen wurden über
Suchergebnisse und Abstracts geprüft, nicht vollständig gelesen.
„(unsicher)“ markiert Angaben ohne verifizierte Primärquelle.

## Befunde und was die App daraus macht

| Befund / Methode | Evidenz | Quelle | Umsetzung |
|---|---|---|---|
| N-of-1 / Single-Case-Designs mit Randomisierung; Randomisierungstest braucht keine Normalverteilung | stark (Methode) | Kratochwill & Levin 2010, *Psychological Methods*, „Randomization to the Rescue“ | Experimente: Bedingung pro Tag vorab zufällig zuweisen, Auswertung per Permutationstest |
| Selbstexperimente von Laien brauchen feste Struktur | mittel | Daskalova et al. 2017, *IMWUT*, „Lessons Learned from Two Cohorts of Personal Informatics Self-Experiments“ | Hypothese, Dauer und Zielgröße vor Start festlegen; Abbruch nur mit Vermerk |
| Day Reconstruction Method als Näherung an Experience Sampling | mittel | Kahneman et al. 2004, *Science*, „A Survey Method for Characterizing Daily Life Experience“ | Nachträgliches Erfassen ist erlaubt, wird aber als rekonstruiert behandelt |
| Micro-Breaks verbessern Energie und Müdigkeit (d ≈ 0,35), Leistung kaum | mittel / schwach | Albulescu et al. 2022, *PLOS ONE* 17(8): e0272460 | Merkmale Pausen je Deep-Work-Stunde und mittlere Pausenlänge; Hinweis „Pausen heben eher Energie als Output“ |
| Attention Residue: Unerledigtes bindet Aufmerksamkeit | mittel | Leroy 2009, *OBHDP* 109: 168–181 | Merkmal Kategoriewechsel/h; Feld „abgeschlossen?“ am Block |
| Unterbrechungen: schneller, aber mehr Stress | schwach–mittel | Mark, Gudith & Klocke 2008, *CHI*, „The Cost of Interrupted Work“ | Optionales Feld „unterbrochen“ am Block |
| Dehydrierung ab 2 % Körpermasse schadet Aufmerksamkeit leicht | mittel; Alltagstrinkmenge schwach | Wittbrodt & Millard-Stafford 2018, *Med Sci Sports Exerc* | Wasser nur als Kontrollvariable, kein Leistungsversprechen |
| Koffein 6 h vor dem Schlafen verkürzt Schlaf objektiv um > 1 h | mittel (n = 12, hohe Dosis) | Drake et al. 2013, *J Clin Sleep Med* 9(11): 1195–1200 | Merkmal Uhrzeit des letzten Kaffees gegen Schlaf |
| Chronische Schlafrestriktion summiert sich, Selbstgefühl unterschätzt sie | stark | Van Dongen et al. 2003, *SLEEP*, „The cumulative cost of additional wakefulness“ | Merkmal Schlafschnitt der letzten 7 Tage statt nur Vornacht |
| Planning Fallacy: Pläne sind zu optimistisch; Außensicht (eigene Basisraten) hilft | stark / mittel | Buehler, Griffin & Ross 1994, *JPSP* 67: 366–381 | Plan-Faktor: Median Ist/Plan je Art, Hinweis beim Planen |
| Progress Principle: Fortschritt ist das wichtigste positive Tagesereignis | mittel (korrelativ) | Amabile & Kramer 2011, *The Progress Principle* | Abendfrage „Heute Fortschritt gemacht?“ mit kurzer Notiz |
| Abschalten nach Feierabend hängt mit Wohlbefinden zusammen | mittel (korrelativ) | Wendsche & Lohmann-Haislah 2017, *Frontiers in Psychology*, doi 10.3389/fpsyg.2016.02072 | Abendfrage „Wie gut abgeschaltet? 1–5“ |
| Implementation Intentions („Wenn X, dann Y“) | mittel, kleiner als früher berichtet | Gollwitzer & Sheeran 2006, *Adv. Exp. Soc. Psychol.* 38: 69–119 | Jede Experiment-Regel als Wenn-dann-Satz |
| Ultradiane 90-Minuten-Zyklen als Arbeitsregel | umstritten | (unsicher) Studien aus den 1990ern, Bestätigung fehlt | Keine Empfehlung, nur eigene Daten zeigen |
| Pomodoro 25/5 | schwach | (unsicher) nur kleine Studien | Höchstens als Experiment, nie als Empfehlung |

## Experiment-Vorlagen

Alle mit mindestens mittlerer Evidenz. Die Bedingung wird vorab zufällig
zugewiesen, die Auswertung erfolgt per Permutationstest.

| Vorlage | Regel (Wenn-dann) | Design | Zielgröße |
|---|---|---|---|
| Koffein-Schluss | Wenn es 14 Uhr ist, dann trinke ich keinen Kaffee mehr. | 2-Tages-Blöcke randomisiert, ca. 16 Tage | Schlaf, Zufriedenheit am Folgetag |
| Schlafkorridor | Wenn es 22:30 Uhr ist, dann gehe ich ins Bett. | randomisierte Wochenblöcke (8 Blöcke à 7 Tage, 56 Tage; längere Phasen wären besser, Kompromiss), kleinstes p ≈ 0,029 (zweiseitig, 2 von 70 Zuweisungen) | Produktivität |
| Mikropausen | Wenn ich 50 Minuten gearbeitet habe, dann mache ich 5–10 Minuten Pause. | tageweise randomisiert, 20 Tage | Zufriedenheit (Energie), dann Produktivität |
| Gebündelte Kommunikation | Wenn ich vormittags Deep Work mache, dann öffne ich keine Mails und keinen Chat. | tageweise randomisiert, 20 Tage | Wechsel/h, Produktivität |
| Abschlussnotiz | Wenn ich einen Block wechsle, dann notiere ich 2 Minuten lang Stand und nächsten Schritt. | tageweise randomisiert, 20 Tage | Produktivität |
| Wenn-dann-Start | Wenn ich morgens am Schreibtisch sitze, dann beginne ich sofort mit dem geplanten Deep-Work-Block. | tageweise randomisiert, 28 Tage | Arbeitsbeginn, Deep Work |
| Plan-Puffer | Wenn ich plane, dann multipliziere ich die Dauer mit meinem Plan-Faktor. | randomisierte Wochenblöcke (8 Blöcke à 7 Tage, 56 Tage), kleinstes p ≈ 0,029 (zweiseitig, 2 von 70 Zuweisungen) | Ist/Plan-Verhältnis |
| Abschalt-Ritual | Wenn ich Feierabend mache, dann schließe ich mit einem festen Ritual ab. | randomisierte Wochenblöcke (8 Blöcke à 7 Tage, 56 Tage), kleinstes p ≈ 0,029 (zweiseitig, 2 von 70 Zuweisungen) | Zufriedenheit, Schlaf |

## Statistik (Standardbibliothek, 14–200 Tage)

- Spearman-Korrelation mit `statistics.correlation(..., method="ranked")`,
  Konfidenzintervall per Block-Bootstrap (Blocklänge 5 Tage) wegen
  Autokorrelation. Erst ab 30 Tagen anzeigen.
- Gute gegen schwache Tage: Cliff's Delta mit Bootstrap-Intervall statt
  p-Wert. Gruppen nach Dritteln des Scores.
- Experimente: Permutationstest unter dem tatsächlichen
  Randomisierungsschema, 5 000 Durchläufe.
- Autokorrelation Lag 1 ausweisen; bei |r₁| > 0,3 effektive Stichprobe
  n · (1 − r₁) / (1 + r₁) verwenden.
- Wochentagseffekt vor dem Korrelieren entfernen (Mittel je Wochentag
  abziehen).
- Mehrfaches Testen: Benjamini-Hochberg über alle geprüften Merkmale; Treffer
  trotzdem nur als Hypothese.
- Scores sind ordinal: Rangverfahren statt t-Test.

## Was die App nicht behauptet

- Keine festen Arbeitsrhythmen (90/20, Pomodoro) als Regel.
- Kein „mehr Wasser oder Kaffee steigert den Fokus“.
- Keine Pauschalzahlen wie „40 % Verlust durch Kontextwechsel“ oder
  „23 Minuten Wiederaufnahme“.
- Keine Ursachen aus Korrelationen. Kausale Aussagen nur nach randomisiertem
  Selbstexperiment, und auch dann vorsichtig.
