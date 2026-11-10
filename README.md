# Rhombenpixelung

Ein Bild wird in ein Mosaik aus Rhomben umgewandelt. Jedes Hexagon eines regelmäßigen Gitters wird in drei Rhomben zerlegt. Die Farbe einer Kachel entsteht aus den enthaltenen Bildpixeln. Optional reduziert K-Means im Lab-Farbraum die Palette; ähnliche Farben lassen sich anschließend zusammenführen.

Die Kommandozeilenversion basiert auf `Verpixelung.ipynb`. Die ursprünglichen Notebooks bleiben als Experimente erhalten. Es ist kein Notebook-Server und keine grafische Oberfläche nötig.

## Installation

Python 3.10 oder neuer. Unter Windows/PowerShell im Projektordner:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Danach entweder die Umgebung aktivieren oder in den folgenden Beispielen `python` durch `.\.venv\Scripts\python.exe` ersetzen. In der vorhandenen Arbeitsumgebung sind die benötigten Bibliotheken bereits installiert.

## Aufrufe

```powershell
# Ohne weitere Optionen: Originalabmessungen, Kantenlänge 40, PNG neben dem Original
python rhombenpixel.py resource/iris.jpg

# Zielpfad, kleinere Kacheln, maximal 24 Farben und 1600 Pixel Breite
python rhombenpixel.py resource/iris.jpg --side 20 --colors 24 --width 1600 -o export/iris_cli.png

# Exakt 1200 × 1200 Pixel, bildfüllend beschneiden, JPEG mit hoher Qualität
python rhombenpixel.py resource/iris.jpg --side 30 --width 1200 --height 1200 --fit cover --quality 95 -o export/iris_square.jpg

# Vektorausgabe; die Rhomben bleiben echte Vektorflächen
python rhombenpixel.py resource/iris.jpg --side 30 --colors 32 --format svg --output-dir export/vector

# Glättung, gedrehtes Gitter, ähnliche Palettenfarben zusammenführen
python rhombenpixel.py resource/iris.jpg --side 24 --blur 1 --angle 30 --colors 32 --merge-delta 5 -o export/iris_rotated.png

# Transparenter Hintergrund, sichtbare Kachelkonturen und Rand
python rhombenpixel.py resource/iris.jpg --margin 30 --background transparent --edge-color "#202020" --edge-width 0.3 -o export/iris_outline.png

# Schnelle Verarbeitung eines großen Bildes und verlustfreies WebP
python rhombenpixel.py resource/iris.jpg --max-input-size 1200 --side 20 --lossless -o export/iris.webp

python rhombenpixel.py --help
```

Aufruf von einem beliebigen Arbeitsverzeichnis:

```powershell
python "E:\Peter\DataScience\Rhombenpixelung\rhombenpixel.py" "C:\Bilder\mein bild.jpg" --side 20 -o "C:\Bilder\Ergebnisse\mosaik.png"
```

## Parameter

| Option | Bedeutung / Standard |
|---|---|
| `input` | Eingabebild, Pflichtargument |
| `-o`, `--output` | Vollständiger Ausgabepfad; fehlende Zielordner werden angelegt |
| `--output-dir` | Alternativ nur Zielordner; Name wird `<eingabe>_mosaic.<format>` |
| `--format` | `png`, `jpg`/`jpeg`, `webp`, `tif`/`tiff`, `bmp`, `svg`, `pdf`; sonst aus Dateiendung, standardmäßig PNG |
| `--side` | Rhombenkantenlänge in Pixeln des Arbeitsbildes; Standard 40 |
| `--blur` | Gauß-Glättung vor der Farbberechnung, Sigma in Arbeitsbildpixeln; 0 = aus |
| `--angle` | Drehung des Gitters in Grad; 0 |
| `--offset-x`, `--offset-y` | Verschiebung des Gitters in Arbeitsbildpixeln; 0 |
| `--colors` | Maximale Farbanzahl vor Zusammenführung; 0 = individuelle Kachelmittelwerte |
| `--merge-delta` | Lab-Abstand (Delta E 76), unter dem Palettenzentren zusammengeführt werden; 0 = aus, benötigt `--colors` |
| `--seed` | Zufallsstart für reproduzierbares K-Means; 42 |
| `--max-input-size` | Optionales Verkleinern der längsten Eingabekante vor der Analyse; standardmäßig unverändert |
| `--width`, `--height` | Gewünschte Ausgabeabmessungen in Pixeln; eine Angabe erhält das Seitenverhältnis |
| `--scale` | Alternative zu Breite/Höhe, z. B. 0.5 oder 2; Standard 1 |
| `--fit` | `contain` (Standard): vollständig einpassen; `cover`: bildfüllend beschneiden; `stretch`: verzerren |
| `--margin` | Rand um das Bild in Arbeitsbildpixeln vor Einpassen/Beschneiden; 0 |
| `--background` | Farbe, z. B. `white`, `"#112233"` oder `transparent`; weiß |
| `--edge-color` | Konturfarbe; standardmäßig keine Kontur |
| `--edge-width` | Konturbreite in Punkten; 0; für sichtbare Konturen Farbe und Breite angeben |
| `--dpi` | DPI-Metadaten bzw. physische Vektorseitengröße; 100 |
| `--antialias` | Raster-Supersampling 1–4; 2. Höhere Werte kosten mehr Speicher |
| `--quality` | JPEG-/WebP-Qualität 1–100; 95 |
| `--lossless` | Verlustfreies WebP |
| `--overwrite` | Vorhandene Ausgabedatei ausdrücklich ersetzen |

## Größen, Transparenz und Formate

- **Kachelgröße und Ausgabegröße sind unabhängig.** `--side` bestimmt den Detailgrad der Analyse, `--width`/`--height` die exportierte Größe. Vergrößern der Ausgabe erzeugt keine zusätzlichen Kacheln.
- Mit `--max-input-size` entsteht zuerst ein verkleinertes Arbeitsbild. Kachelgröße, Glättung, Gitterversatz und Rand beziehen sich dann auf dieses Arbeitsbild. Ohne explizite Ausgabegröße wird dessen Größe einschließlich Rand ausgegeben.
- Bei Angabe beider Abmessungen ist die Rasterausgabe exakt so groß. `contain` ergänzt bei Bedarf Hintergrundflächen, `cover` schneidet ab, `stretch` verändert auch die Rhombenproportionen. Ohne Rand und mit passendem Seitenverhältnis reicht das Mosaik bis zum Bildrand.
- Rasterformate enthalten echte Pixelabmessungen. SVG/PDF enthalten Vektorpolygone; ihre physische Seitengröße ist `Breite / DPI` × `Höhe / DPI` in Zoll. Beispiel: 1200 Pixel bei 300 DPI entsprechen 4 Zoll. `--antialias` gilt nur für Rasterformate.
- Transparente Eingabepixel werden bei den RGB-Mittelwerten mit ihrem Alpha gewichtet. Jede Kachel erhält außerdem einen mittleren Alpha-Wert. Transparenzgrenzen werden dadurch ebenfalls mosaikiert. EXIF-Bildorientierung wird vor der Verarbeitung angewendet.
- PNG, TIFF, WebP und SVG unterstützen transparente Ausgaben. JPEG und BMP werden auf eine deckende Fläche reduziert; bei `transparent` wird dafür Weiß verwendet. PDF erhält gegebenenfalls transparente Flächen, deren Anzeige vom PDF-Betrachter abhängt.
- Farbprofile werden nicht in ein verwaltetes Zielfarbprofil konvertiert; die Verarbeitung behandelt RGB-Werte als sRGB. Für farbverbindlichen Druck ein bereits nach sRGB konvertiertes Eingabebild verwenden. Animierte Eingaben liefern nur ihr erstes Bild.
- Die Palette begrenzt die **Kachelfarben**. Kantenglättung, Transparenz, Hintergrund, Konturen und verlustbehaftete Kompression können zusätzliche Pixel-Farbwerte erzeugen. Die Zusammenführung verwendet aktualisierte, nach Kachelanzahl gewichtete Zentren. K-Means gewichtet Kacheln gleich, nicht nach ihrer sichtbaren Fläche.
- Format und Dateiendung müssen zusammenpassen. Bestehende Ausgaben werden nur mit `--overwrite` ersetzt. Das Eingabebild darf auch mit dieser Option nicht als Ausgabepfad verwendet werden.

## Prüfung

```powershell
python -m unittest -v
```

Die Tests erzeugen ihre Eingaben selbst: Ausgabeformate und -abmessungen, Vektorpolygone, Transparenz, Gitterabdeckung bei Drehung, Seitenverhältnisse, reproduzierbare Farbpaletten und Schutz vor unbeabsichtigtem Überschreiben. Keine privaten Bilder nötig.

Für ein öffentliches Repository zunächst Code, README, Anforderungen und Tests auswählen. Die vorhandenen Ordner `resource` und `export` enthalten die ursprüngliche Bildsammlung und sollten nicht ungeprüft mit veröffentlicht werden. Eine Lizenz für Code und freigegebene Beispielbilder ist vor Veröffentlichung noch festzulegen.
