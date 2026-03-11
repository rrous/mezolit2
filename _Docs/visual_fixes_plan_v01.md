# Plán: Vizuální opravy mapy — terén, biotopy, pobřeží

## Kontext

Uživatel vizuálně zkontroloval mapu a identifikoval 5 problémů, které způsobují nepřirozený vzhled:
1. Lake Flixton nectí DEM
2. Chalk downland má rovnou západní hranici
3. Pobřeží je geometrické, chybí moře a realistická přílivová zóna
4. Říční nivy místy neodpovídají terénu, velké ploché oblasti bez struktury
5. Díry a mezery v pokrytí, málo mikroregionů

Preference: vždy DEM-odvozený tvar (i když není ideální), PoC nemusí být perfektní ale uvěřitelný.
Řeky: pro celý Yorkshire ponechat OS Open Rivers (současné toky), pro oblast Star Carr rekonstruovat paleochannels z DEM + publikací.

---

## Soubory k úpravě

| Soubor | Změny |
|--------|-------|
| `pipeline/04_terrain.py` | Problémy #1–#5 (hlavní soubor — klasifikace, polygonizace, řeky) |
| `pipeline/05_kb_rules.py` | Problémy #4b, #5c (biotopy, mikroregiony, ecotony) |
| `pipeline/03_coastline.py` | Problém #3 (coastal boundary, sea polygon) |
| `kb_data/schema_examples_v04.json` | Nové typy v KB schématu |
| `_Docs/schema_examples_v04.json` | Sync se schématem |

---

## Problém #1: Lake Flixton — hybrid DEM

**Soubor:** `04_terrain.py`, funkce `add_star_carr_anchor` (řádky ~458–554)

**Aktuálně:** 30 ručních vertexů + Gaussovský šum, žádná vazba na DEM.

**Řešení:**
1. Extrahovat DEM sub-okno (~6×4 km) kolem Star Carr (54.2778°N, -0.5833°E)
2. Sweep elevačních prahů od minima nahoru (po 0.5m krocích)
3. Na každém prahu polygonizovat oblast pod prahem (`rasterio.features.shapes`)
4. Vybrat polygon obsahující/nejbližší k centru Star Carr
5. Scorovat kandidáty proti publikovaným rozměrům (~2.4×1.1 km) — Gaussovský kernel
6. Oříznout nejlepší polygon bounding elipsou (20% margin nad historickými rozměry)
7. Simplifikovat (`tolerance ~15m`) + minimální šum (σ=3m, seed=42)
8. **Žádný fallback na syntetický polygon** — uživatel preferuje vždy DEM

**Nové funkce:**
- `extract_lake_from_dem(dem_path, clon, clat)` → Shapely Polygon
- `score_lake_candidate(ew_km, ns_km, area_km2, aspect)` → float 0–1

**Validace:** PP score, aspect ratio, area — porovnat s aktuálními hodnotami (PP=0.773, aspect=3.69).

---

## Problém #2: Chalk boundary — DEM escarpment

**Soubor:** `04_terrain.py`, řádek 48 (`WOLDS_BOUNDARY_LON = -0.8`) a řádek 191

**Aktuálně:** `lon_grid > -0.8` → dokonale rovná svislá čára.

**Řešení:**
1. **Detekce chalk escarpmentu z DEM:**
   - V pásu elevace 50–300m (kde se chalk a limestone překrývají)
   - Spočítat gradient elevace ve směru V→Z (východní derivace)
   - Chalk Wolds mají výrazný **západní svah** (strmý escarpment na Z, pozvolný na V)
   - Identifikovat pixely kde: `east_gradient > threshold` (escarpment) jako hranici
2. **Alternativní přístup (jednodušší, doporučuji):**
   - Místo jedné linie použít **elevační konturu** — např. kde terén klesá pod ~80m z východu
   - Na Wolds je chalk nad escarpmentem, pod ním je limestone/clay
   - Práh: pixely s elevací 50–300m, kde průměrná elevace v okruhu ~2km na západ je výrazně nižší
3. **Ponechat -0.8° jako soft limit** — chalk se nerozšíří dál na západ než -1.0° (geologický fakt)

**Implementace (doporučený přístup #2):**
- V `classify_terrain()` nahradit `lon_grid > WOLDS_BOUNDARY_LON` za:
  ```
  is_chalk_zone = (elevation >= 50) & (elevation < 300) & (lon_grid > -1.0)
  # Pro každý pixel v chalk_zone: zkontrolovat, zda elevace na západ klesá strmě
  west_neighbor_elev = np.roll(elevation, -ESCARPMENT_WINDOW, axis=1)
  escarpment_drop = elevation - west_neighbor_elev
  is_wolds = is_chalk_zone & (escarpment_drop < ESCARPMENT_THRESHOLD)
  # Chalk = pixely na Wolds (na vršku/východním svahu escarpmentu)
  ```
- `ESCARPMENT_WINDOW` = ~30 pixelů (~1km při 30m DEM)
- `ESCARPMENT_THRESHOLD` = záporný drop znamená svah dolů na západ

**Výsledek:** Nepravidelná západní hranice chalk, která sleduje skutečný escarpment.

---

## Problém #3: Pobřeží — realistická hranice + moře

**Soubory:** `03_coastline.py`, `04_terrain.py`, `05_kb_rules.py`

### 3a) Použít GEBCO konturu jako skutečnou hranici (ne bbox ořez)

**Aktuálně:** `04_terrain.py` ořezává terén na YORKSHIRE_BBOX obdélník.

**Řešení:**
1. V `04_terrain.py` načíst `coastline_6200bce.geojson` (výstup z 03)
2. Po polygonizaci terénů oříznout každý polygon coastline polygonem místo bbox
3. Terén existuje jen na souši (uvnitř coastline)

### 3b) Moře jako terén

**Aktuálně:** Vše pod -3m = unclassified (0), na mapě nic.

**Řešení:**
- Přidat nový terénní subtyp **tst_009: Open sea** (nebo použít existující tst_009 z KB, který je definován jako "permanent large river" — ověřit schéma)
- Alternativa: Nepoužívat terénní subtyp, ale přidat sea polygon jako samostatný feature s vlastnostmi
- Moře = oblast mimo coastline polygon, v rámci zobrazované mapy
- Biotop: žádný (moře nemá suchozemský biotop) nebo nový bt_012 "open sea"

### 3c) Širší přílivová/bahnitá zóna

**Aktuálně:** tst_008 (tidal) = elevace -3 až 3m, slope < 1° → velmi úzký pás.

**Řešení:**
1. Rozšířit elevační rozsah: -5 až 5m (nebo -8 až 5m pro realistický bahnitý pás)
2. Případně: buffer coastline linie o ~500m na obě strany → intersekce s nízkou elevací
3. Inspirace z aktuálního pobřeží (Humber estuary, Holderness coast) — široké mudflats

### 3d) Coastal ecotone

**Aktuálně:** ec_005 (Pobřeží/Mokřad, bt_005 ↔ bt_002) existuje, ale chybí přechod souš ↔ moře.

**Řešení:**
- Přidat ecotone **ec_007: Pobřeží / Moře** (bt_008 intertidal ↔ sea)
- Nebo rozšířit tidal zónu tak, aby fungovala jako přechodová zóna sama o sobě
- V `05_kb_rules.py`: přidat generaci ec_007 z hranice tidal polygonů s coastline

---

## Problém #4: Říční nivy — lepší přizpůsobení terénu

**Soubor:** `04_terrain.py`, funkce `reclassify_river_corridors` (řádky 270–354)

**Aktuálně:** Konstantní 400m buffer, reklasifikace kde elevace < 200m.

### 4a) Variabilní šířka koridoru

**Řešení — DEM-adaptivní buffer:**
1. Pro každý river segment: vzorkovat elevaci v příčném profilu (kolmo na tok)
2. Najít bod kde elevace stoupne o >5m nad úroveň řeky → to je hrana nivy
3. Buffer = min(nalezená_šířka, 800m), min 100m
4. Zachovat `RIVER_FLOODPLAIN_MAX_ELEV = 200` jako hard cap

**Implementace:**
- Segmentovat řeky po ~500m úsecích
- Pro každý úsek: spočítat průměrnou elevaci na ose řeky z DEM
- Rozšiřovat buffer po pixelech do stran, dokud `elev_pixel - elev_river > 5m`
- Výsledné buffery sloučit → plynulá niva s proměnnou šířkou

### 4b) Star Carr — paleochannel rekonstrukce

**Aktuálně:** OS Open Rivers ukazují současné toky. Pro Star Carr oblast chceme rekonstruovat ~6200 BCE.

**Řešení — DEM flow accumulation:**
1. Definovat Star Carr sub-oblast (~10×8 km kolem 54.2778°N, -0.5833°E)
2. Z DEM spočítat **flow accumulation** (kam by tekla voda):
   - Fill sinks v DEM (`scipy.ndimage` nebo jednoduchý iterativní fill)
   - Spočítat flow direction (D8 algoritmus — 8 sousedních pixelů)
   - Akumulovat flow → pixely s hodnotou > threshold = vodní tok
3. Výsledné linie nahradí OS Open Rivers v Star Carr oblasti
4. Mimo Star Carr: ponechat OS Open Rivers beze změny

**Poznámka:** Flow accumulation z DEM ukazuje, kam by voda **přirozeně** tekla podle terénu — to je dobrá aproximace paleochannels, protože terénní deprese se za 8000 let výrazně nezměnily (na rozdíl od samotných koryt).

**Potřebné knihovny:** numpy (stačí, flow accumulation je čistě array operace)

### 4c) Vnitřní struktura velkých niv

Velké ploché oblasti (Vale of York) jsou jedna monotónní niva → nudné.

**Řešení v rámci 05_kb_rules.py:**
- Ve velkých floodplain polygonech (> 50 ha) generovat **biotopové zóny** podle vzdálenosti od řeky:
  - 0–100m od řeky → bt_007 (riparian/lužní les)
  - 100–400m → bt_002 (wetland/mokřad)
  - 400m+ → bt_003 (forest) s bt_009 glades
- Implementace: buffer řek 100m → intersekce s floodplain → bt_007 polygon
- Zbytek floodplain zůstává bt_002, ale s přidanými mikro-features

---

## Problém #5: Díry, mezery, pokrytí

### 5a) Eliminace unclassified pixelů na souši

**Soubor:** `04_terrain.py`

**Aktuálně:** Pixely, které neprojdou žádnou klasifikační podmínkou, zůstanou 0.

**Řešení:**
1. Po klasifikaci: najít pixely kde `classified == 0` AND `elevation >= SEA_LEVEL` AND pixel je uvnitř coastline
2. Přiřadit nejbližší terénní typ (nearest-neighbor z okolních klasifikovaných pixelů)
3. Nebo přiřadit default typ podle elevace (generická pravidla)

### 5b) Eliminace mezer mezi polygony

**Soubor:** `04_terrain.py`, funkce `polygonize_terrain`

**Aktuálně:** Simplifikace polygonů může vytvořit gapy.

**Řešení:**
- Po simplifikaci: snap polygony k sobě (`shapely.ops.snap` nebo `ST_SnapToGrid`)
- Nebo: simplifikovat sdílené hranice konzistentně (topologická simplifikace)
- Jednodušší: po simplifikaci vyplnit gapy — najít neklasifikované oblasti a přiřadit je sousednímu polygonu

### 5c) Více mikroregionů a biotopových typů

**Soubory:** `05_kb_rules.py`, `kb_data/schema_examples_v04.json`

**Nové mikroregiony k přidání:**
1. **bt_007 (Riparian forest)** — reálně přiřadit podél řek (nejen teoreticky)
   - V zóně 0–100m od řeky v rámci floodplain → bt_007 místo bt_002
2. **bt_006 (Chalk scrub)** — reálně přiřadit na strmých svazích chalk escarpmentu
   - Kde tst_005 AND slope > 8° → bt_006 místo bt_003
3. **bt_008 (Intertidal)** — rozšířit pokrytí (viz #3c)
4. **Více glade features** — zvýšit MAX_GLADE_FEATURES z 200 nebo odstranit cap
5. **Variace glade typů:**
   - Mokré palouky (v blízkosti vodních toků)
   - Suché palouky (na chalk/limestone)
   - Skalní výchozy (micro bt na strmých svazích)

**Nové ecotony:**
- ec_007: Pobřeží/Moře (souš ↔ sea) — viz #3d
- Případně ec_008: Chalk scrub / Forest (bt_006 ↔ bt_003) na escarpmentu

---

## Pořadí implementace

Problémy jsou provázané. Doporučuji iterativní postup — po každém kroku spustit pipeline a vizuálně zkontrolovat:

### Krok 0: Dokumentace
- Uložit tento plán jako `_Docs/visual_fixes_plan_v01.md` — trvalý záznam oprav

### Krok 1: Terénní klasifikace (`04_terrain.py`)
Všechny změny na rastru PŘED polygonizací:
- **#2** Chalk boundary — nahradit hardcoded -0.8° za DEM escarpment detekci
- **#4a** River corridors — variabilní buffer podle DEM údolí
- **#4b** Star Carr paleochannels — flow accumulation v sub-oblasti
- **#5a** Gap filling — vyplnit unclassified pixely na souši
- **#1** Lake Flixton — hybrid DEM kontury

### Krok 2: Pobřeží (`03_coastline.py` + `04_terrain.py`)
- **#3a** Coastline jako clip boundary (ne bbox)
- **#3b** Sea polygon (oblast mimo coastline)
- **#3c** Širší tidal zóna (rozšířit elevační rozsah)

### Krok 3: Polygonizace (`04_terrain.py`)
- **#5b** Gap filling po simplifikaci — snap/vyplnit mezery

### Krok 4: Biotopy a ecotony (`05_kb_rules.py`)
- **#4c** Vnitřní struktura niv (bt_007 riparian podél řek)
- **#5c** Nové biotopové přiřazení (bt_006 chalk scrub, bt_008 intertidal)
- **#5c** Více glade features — zvýšit/odstranit cap 200
- **#3d** Nové ecotony (ec_007 coastal, případně ec_008 chalk/forest)

### Krok 5: KB schéma
- Sync `kb_data/schema_examples_v04.json` a `_Docs/schema_examples_v04.json`

---

## Verifikace

Po každém kroku:
1. **Spustit pipeline:** `python 03_coastline.py` → `python 04_terrain.py` → `python 05_kb_rules.py`
2. **Vizuální kontrola na mapě** (uživatel) — hlavní kritérium úspěchu
3. **verify_db.py** — kontrola integrity dat

**Cílové metriky:**
- Lake Flixton: DEM-odvozený tvar, PP score 0.3–0.8, area ~1.5–3 km2
- Chalk boundary: nepravidelná linie sledující escarpment
- Pokrytí souše: 100% (žádné díry/mezery na souši)
- Moře: přítomno jako sea polygon
- Tidal zóna: šířka ≥ 500m v estuárních oblastech
- Biotopové typy reálně přítomné: ≥ 8 z 9 baseline (včetně bt_006, bt_007, bt_008)
- Ecotone typy: ≥ 7 (včetně nového coastal)
- Star Carr paleochannels: viditelně odlišné od OS Open Rivers
- Říční nivy: proměnná šířka, vnitřní struktura (riparian forest podél toků)
