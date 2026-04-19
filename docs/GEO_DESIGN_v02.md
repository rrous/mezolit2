# Mezolit2 — Geologická vrstva Třeboňska
## GEO_DESIGN_v02.md

*Verze 0.2 | 2026-03-26*
*Status: NÁVRH — rozhodovací body R1–R5 uzavřeny, před implementací pipeline*
*Změny v0.2: Rozhodnutí R1–R5 zanesena, DMR 5G ověřen, substrate enum rozšířen, ID konvence stanovena.*

> Tento dokument popisuje jak sestavit geologickou vrstvu (KB vrstva 1)
> pro oblast Třeboňska (~30×30 km) kolem Švarcenberku.
> Navazuje na MAP_VALIDATION_TESTS_v02.md a METHODOLOGY_GUIDE_v03.md.

---

## 1. Bbox a anchor

```
SW: 48.93°N, 14.53°E
NE: 49.22°N, 14.95°E
~32 km (N-S) × 29 km (E-W)
~928 km²
```

**Anchor site:** Švarcenberk (49.148°N, 14.707°E)
- Paleolake, 450 × 700 m, sedimenty do 11 m hloubky + 3 m rašeliny
- Dřevěné artefakty datované 9130–8630 cal BCE (Šída, Pokorný, Kuneš 2007)
- Jezero existovalo od ~14 000 BCE do ~3500 BCE — v horizontu 7000 BCE mělo otevřenou hladinu
- Dnes rybník (52 ha), vybudován na přelomu 17./18. stol.

**Proč právě tento bbox:**
- Zachytí denní catchment (15 km) kolem anchoru
- Zahrnuje celou Třeboňskou rybniční soustavu (Rožmberk, Svět, Horusický)
- Zachytí řeku Lužnici (hlavní vodní koridor S–J)
- Zachytí okraj pánve (přechod kvartér → krystalinikum = geologická diverzita)

---

## 2. Co víme o geologii Třeboňska

### 2.1 Geologická stavba (z rešerše)

Třeboňská pánev je tektonicky podmíněná sníženina vyplněná sedimenty.
Podloží tvoří moldanubické krystalinikum. Hlavní geologické jednotky:

| Jednotka | Stáří | Litologie | Kde v bbox | Relevance pro model |
|----------|-------|-----------|------------|---------------------|
| **Moldanubikum** | Prekambrium–Paleozoikum | Ruly, granulity, migmatity | Okraje pánve (V, Z) | Nepropustný substrát, skalní výchozy |
| **Klikovské souvrství** | Svrchní křída (senon) | Pískovce, slepence, jílovce, prachovce | Hlavní výplň pánve, až 300 m mocnost | Propustné → ovlivňuje hydrologii |
| **Neogenní sedimenty** | Miocén | Jíly, písky, diatomity, křemenci | Západní část pánve | Střídání propustných a nepropustných |
| **Pleistocénní štěrkopísky** | Kvartér | Říční štěrky a písky | Podél Lužnice a Nežárky, 2 terasové úrovně | Propustné, vodní režim, suroviny |
| **Váté písky** | Pozdní glaciál–postglaciál | Eolické písky | Pás 34 km Majdalena → Veselí n.L. | Specifický biotop (suchý, kyselý) |
| **Rašeliny** | Holocén | Slatiny, oligotrofní rašeliny | Okolí Záblatského a Horusického ryb. | Paleoekologie, přechodový typ |
| **Jezerní sedimenty** | Pozdní glaciál–holocén | Jíly, gyttja, rašelina | Švarcenberk + 18 dalších paleolakes | **KLÍČOVÉ** — anchor pro celý model |
| **Nivní sedimenty** | Holocén | Hlíny, jemné písky | Niva Lužnice | Záplavová zóna |

### 2.2 Co je pro ~7000 BCE STEJNÉ jako dnes

- **Bedrock (moldanubikum):** Identický. Certainty: DIRECT.
- **Křídové sedimenty:** Identické. Certainty: DIRECT.
- **Neogenní sedimenty:** Identické. Certainty: DIRECT.
- **Pleistocénní terasy:** Existovaly, tvořeny během glaciálu. Certainty: DIRECT.
- **Váté písky:** Již naváté (pozdní glaciál). Certainty: INDIRECT (přesný rozsah nejistý).

### 2.3 Co je pro ~7000 BCE JINÉ než dnes

| Prvek | Dnes | ~7000 BCE | Certainty | Zdroj |
|-------|------|-----------|-----------|-------|
| **Rybníky** | 10 000+ ha rybníků | NEEXISTOVALY (15.–18. stol.) | DIRECT | Historické prameny |
| **Paleojezera** | Neexistují (zazemněna) | Otevřená hladina (min. Švarcenberk) | INDIRECT | Pokorný et al. 2010; Hošek et al. 2013 |
| **Rašeliniště** | Rozsáhlá (tisíce ha) | Menší / mladší — začínají se tvořit | INDIRECT | Pylové profily |
| **Říční síť** | Regulovaná + kanály (Zlatá stoka) | Přirozené meandry, vyšší dynamika | INFERENCE | Geomorfologická analogie |
| **Odlesnění** | >50% zemědělská půda | ~0% — kompletní lesní pokryv | INDIRECT | Pylové profily (vrstva 3, ne zde) |

### 2.4 Klíčový poznatek: žádný flint

**Třeboňská pánev NEMÁ zdroje flintu ani kvalitního rohovce.**

Substrát je převážně pískovcový/jílovcový. Nejbližší zdroje štípatelné
suroviny jsou desítky km daleko (Šída & Prostředník 2014 pro Český ráj;
pro jižní Čechy je situace ještě horší). To je zásadní constraint
pro model — viz T-ARCH-02 (surovinový dosah).

Lokální alternativy: křemenné valouny z říčních štěrkopísků (kvalita?),
kvarcit. Potřeba ověření u geologa.

---

## 3. Datové zdroje a transformace

### 3.1 Vstupní data

| Zdroj | Co obsahuje | Formát | Transformace na ~7000 BCE |
|-------|------------|--------|---------------------------|
| **ČGS geologická mapa 1:50 000** | Lithologie, stratigrafie, tektonika | WMS/WFS | Žádná — bedrock je identický |
| **ČGS kvartérní mapa** | Kvartérní pokryv (typ, mocnost) | WMS/WFS | Minimální — odstranit antropogenní navážky |
| **DEM (GLO-30 nebo DMR 5G)** | Elevace, sklon | GeoTIFF | Žádná — terén se za 9000 let nezměnil* |
| **DIBAVOD** | Říční síť, vodní plochy, povodí | SHP | Odstranit kanály (Zlatá stoka aj.), ponechat přirozené toky |
| **Hošek et al. 2013/2016** | Polohy 19 paleolakes v pánvi | Publikace (mapy) | Digitalizace z publikací |
| **Pokorný et al. 2010** | Švarcenberk — stratigrafie, pyly | Publikace | Elevace hladiny, rozměry pánve |

\* Výjimka: říční eroze a sedimentace v nivě Lužnice mohly změnit lokální topografii o jednotky metrů.

### 3.2 Mapování ČGS → KB terrain_subtypes

Toto je KLÍČOVÁ tabulka dokumentu. Mapuje reálné geologické kategorie
z ČGS mapy na KB terrain_subtype uzly.

**Princip:** Nekopírujeme Yorkshire terrain_subtypes (tst_001–010).
Vytváříme NOVÉ terrain_subtypes specifické pro Třeboňsko, protože
geologie je zásadně odlišná. Sdílené je schema (struktura uzlu),
ne obsah. **ID konvence: prefix `cz_`** (rozhodnutí R5).

| ČGS kategorie | KB terrain_subtype | Hydrology (vocabulary_v02) | Substrate (vocabulary_v03*) | Slope |
|---------------|-------------------|----------------------------|---------------------------|-------|
| Moldanubické ruly/granulity | **tst_cz_001**: Krystalické podloží | well_drained | **crystalline_basement** | moderate–steep |
| Křídové pískovce (Klikovské s.) | **tst_cz_002**: Pískovcová plošina | well_drained / moderate_moisture | **cretaceous_sandstone** | flat–low |
| Křídové jílovce | **tst_cz_003**: Jílovcová deprese | high_water_table | **cretaceous_claystone** | flat |
| Neogenní jíly/diatomity | **tst_cz_004**: Neogenní jezerní sedimenty | high_water_table | **neogene_lacustrine** | flat |
| Pleistocénní štěrkopísky (terasy) | **tst_cz_005**: Říční terasa | well_drained | river_gravel | flat–very_low |
| Holocénní niva (Lužnice) | **tst_cz_006**: Říční niva | seasonal_flooding | alluvial_clay_peat | flat |
| Váté písky | **tst_cz_007**: Eolický písek | well_drained | **aeolian_sand** | flat–low |
| Rašelina (přechodový typ) | **tst_cz_008**: Rašeliniště | permanent_saturation | peat | flat |
| Jezerní sedimenty (paleolakes) | **tst_cz_009**: Jezerní pánev (zaniklá) | permanent_standing_water | organic_lacustrine_sediment | flat |
| Stálý vodní tok (Lužnice, Nežárka) | **tst_cz_010**: Velká řeka | permanent_flow | river_gravel | — |

\* **vocabulary_v03:** Rozšíření substrate enum o 4 nové univerzální hodnoty
(rozhodnutí R1). Tučně = nové hodnoty. Viz §3.3.

**Počet terrain_subtypes:** Předběžně 10. Finální počet se rozhodne
po vizuální inspekci ČGS dat (rozhodnutí R3) — pokud křídové subfacie
(pískovce vs. jílovce vs. slepence) hostí zásadně odlišné biotopy,
rozdělit tst_cz_002/003 na více typů.

### 3.3 Co je v mapování NEJISTÉ

**Problém 1: Granularita ČGS vs. KB**

ČGS mapa 1:50 000 rozlišuje desítky lithologických kategorií.
KB terrain_subtype je hrubší (10 typů). Mapování M:1 (mnoho ČGS → jeden KB)
musí být explicitní a zdokumentované.

**Problém 2: Kvartérní pokryv vs. bedrock**

ČGS geologická mapa ukazuje buď bedrock NEBO kvartérní pokryv —
záleží na mapovém listu. Pro terrain_subtype potřebujeme OBĚ vrstvy:
bedrock (co je pod tím) + pokryv (co je na povrchu). Řešení: kombinace
geologické mapy + kvartérní mapy.

**Problém 3: Substrate vocabulary — ROZŠÍŘENÍ (rozhodnutí R1)**

Vocabulary_v02 substrate enum byl navržen pro Yorkshire. Pro Třeboňsko
přidáváme 4 nové **univerzální** hodnoty (bez region tagu) do vocabulary_v03:

| Nový substrate | Definice | Kde na Třeboňsku | Existující approx. |
|---------------|----------|------------------|-------------------|
| `crystalline_basement` | Metamorfované horniny (ruly, granulity, migmatity) | Okraje pánve | `granite_slate_sandstone` (nepřesné) |
| `cretaceous_sandstone` | Svrchnokřídové kontinentální pískovce a slepence | Hlavní výplň pánve | `limestone_sandstone` (nepřesné) |
| `cretaceous_claystone` | Svrchnokřídové jílovce a prachovce | Deprese v pánvi | `glacial_till` (špatné) |
| `aeolian_sand` | Váté (eolické) písky z pozdního glaciálu | Pás Majdalena–Veselí | `marine_sand_gravel` (špatné) |
| `neogene_lacustrine` | Neogenní jezerní jíly, diatomity, křemenci | Západní část pánve | `alluvial_clay_peat` (nepřesné) |

Yorkshire hodnoty zůstávají beze změn. Nové hodnoty jsou univerzální —
mohou být použity kdekoliv v Evropě kde se vyskytují stejné lithologie.

**Problém 4: Paleolakes — kde přesně?**

Hošek et al. (2013, 2016) identifikovali 19 zaniklých jezer v pánvi.
Publikace obsahují mapy, ale ne GIS data. Potřeba:
- Digitalizace poloh z publikovaných map (manuální práce)
- Nebo kontakt na Hoška/Pokorného pro GIS vrstvy

---

## 4. Pipeline — kroky

### Krok 1: DEM import — DMR 5G (rozhodnutí R4)

```
Vstup:  ČÚZK DMR 5G pro bbox
        ArcGIS ImageServer: https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer
        Alternativně: Export přes Geoprohlížeč ČÚZK (email + bbox + TXT formát)
Výstup: PostGIS raster (2m pixel), slope raster, hillshade
Formát: S-JTSK (EPSG:5514) → reprojekce do WGS84 (EPSG:4326)
Effort: Střední — nový pipeline (ne adaptace Yorkshire GLO-30)
```

**Parametry DMR 5G (ověřeno 2026-03-26):**
- Rozlišení: **2m pixel** (ne 5m jak dříve odhadováno)
- Vertikální přesnost: **0.18m** odkrytý terén, **0.3m** zalesněný terén
- Pro bbox ~930 km²: ~232 mil. bodů → přesamplovat na 5m pro terénní analýzy (slope, flow accumulation), ponechat 2m pro detailní vizualizaci
- Zdroj: Letecké laserové skenování 2009–2013, průběžně aktualizováno
- Přístup: Volně ke stažení, otevřená data v Národním katalogu OD

**Proč NE GLO-30:** Vertikální přesnost 0.18m vs. ~3m = řádový rozdíl.
Pro říční spád (T-PHY-01), paleolake elevaci (T-PHY-07) a slope analýzu
je to zásadní. Třeboňská pánev je plochá (sklon 1.5‰) — GLO-30 by
v řadě míst nerozlišil terénní gradienty vůbec.

### Krok 2: ČGS geologická mapa — import

```
Vstup:  ČGS WMS/WFS pro bbox (geologická mapa 1:50 000)
Výstup: PostGIS polygony s lithologickými atributy
Nástroj: ogr2ogr / rasterio pro WFS query s bbox filter
Effort: Střední — nutné zjistit přesnou strukturu WFS odpovědi
Riziko: WFS nemusí vracet vektorová data pro 1:50 000 (jen WMS raster?)
Fallback: Rasterizace WMS + klasifikace barev → polygony (méně přesné)
```

**TODO před implementací:** Otestovat ČGS WFS endpoint s bbox query.
Zjistit zda vrací vektorová data s atributy, nebo jen raster.

### Krok 3: Mapování ČGS → terrain_subtypes

```
Vstup:  ČGS polygony (krok 2) + mapovací tabulka (§3.2)
Výstup: terrain_subtype polygony v KB schema
Nástroj: Python skript — lookup table + spatial join
Effort: Střední — mapovací tabulka vyžaduje ruční ověření per ČGS kategorie
```

### Krok 4: Kvartérní pokryv overlay

```
Vstup:  ČGS kvartérní mapa + terrain polygony (krok 3)
Výstup: terrain polygony obohacené o kvartérní atributy (substrate, mocnost)
Nástroj: Spatial intersection
Effort: Střední
```

### Krok 5: DIBAVOD říční síť — import + filtr

```
Vstup:  DIBAVOD SHP (staženo z dibavod.cz)
Výstup: Říční síť v PostGIS, filtrovaná na přirozené toky
Filtr:  Odstranit umělé kanály (Zlatá stoka, Nová řeka, rybniční stoky)
Effort: Střední — identifikace umělých toků vyžaduje manuální kontrolu
        nebo atributové filtrování (DIBAVOD má atribut typ_toku?)
```

### Krok 6: Paleolakes digitalizace

```
Vstup:  Hošek et al. 2013/2016 (publikované mapy) + Pokorný et al. 2010
Výstup: Polygony paleolakes (tst_CZ_009) v PostGIS
Nástroj: Manuální digitalizace NEBO kontakt na autory pro GIS data
Effort: VYSOKÝ pokud manuálně; NÍZKÝ pokud autoři poskytnou data
```

**Doporučení:** Kontaktovat Pokorného/Hoška. Je to legitimní vědecká
spolupráce a oni mají data v GIS formátu — jen nejsou publikovaná online.

### Krok 7: Validační testy (MAP_VALIDATION_TESTS_v02, Fáze 1)

Po krocích 1-6 spustit:
- T-GEO-05: DEM kontrolní body
- T-PHY-01: Říční spád (s DIBAVOD)
- T-PHY-06: Sklon vs. mokřad (jakmile bude VMB — vrstva 3)
- T-GEO-01: Geologie vs. terrain klasifikace
- T-GEO-03: Hydrologie vs. VMB

---

## 5. Rozhodnutí (uzavřeno 2026-03-26)

| # | Otázka | Rozhodnutí | Důsledek |
|---|--------|-----------|----------|
| **R1** | Rozšířit substrate enum? | **Ano, univerzálně** (bez region tagu) | 5 nových substrate hodnot ve vocabulary_v03 (§3.3) |
| **R2** | Jak řešit rybníky? | **Vymazat, nahradit paleokrajinou** | Pipeline musí transformovat rybníky na tst_cz_006/008/009 dle kontextu |
| **R3** | Kolik terrain_subtypes? | **Rozhodne se po inspekci ČGS dat** | Předběžně 10, finální počet po kroku 2 pipeline |
| **R4** | DEM zdroj? | **DMR 5G** (2m pixel, 0.18m přesnost) | Nový pipeline krok 1 (ne adaptace Yorkshire) |
| **R5** | ID konvence? | **Prefix `cz_`**: `tst_cz_001`, `bt_cz_001` | Konzistentní na všech typech uzlů, oba regiony ve stejné DB |

### R2 detail — strategie odstraňování rybníků

Každý rybník v bbox se nahradí paleokrajinou dle kontextu:

| Rybník | Rozloha | Náhrada ~7000 BCE | Certainty | Zdroj |
|--------|---------|-------------------|-----------|-------|
| Švarcenberk | 52 ha | **tst_cz_009** (paleolake — otevřená hladina) | INDIRECT | Pokorný et al. 2010 |
| Rožmberk | 489 ha | **tst_cz_006** (niva) nebo tst_cz_009 (paleolake?) | SPECULATION | Hošek et al. — je v seznamu 19 jezer? |
| Horusický | 416 ha | tst_cz_006/008 | SPECULATION | Kontextová inference z okolní geologie |
| Svět | 200 ha | tst_cz_006 | SPECULATION | Kontextová inference |
| Ostatní | různé | Per rybník na základě ČGS kvartérní mapy | SPECULATION | — |

**Kritické:** Pro Švarcenberk máme INDIRECT evidenci (sedimenty, pyly, datace).
Pro ostatní rybníky je to SPECULATION — musí být explicitně označeno v KB.
Hošek et al. identifikovali 19 paleolakes — potřebujeme jejich seznam
a polohy, aby rozhodnutí per rybník mělo oporu.

---

## 6. Otevřené otázky pro geology (před implementací)

### Q-GEO-01: Struktura ČGS WFS

Vrací ČGS WFS pro geologickou mapu 1:50 000 vektorová data s atributy
(lithologie, stratigrafie) pro bbox query? Nebo jen WMS raster?
→ **Nutné otestovat před pipeline implementací.**

### Q-GEO-02: Dostupnost paleolake GIS dat

Mají Hošek/Pokorný GIS polygony zaniklých jezer? Jsou ochotní sdílet?
→ **Kontaktovat autory.**

### Q-GEO-03: Lokální suroviny

Existují na Třeboňsku lokální zdroje štípatelné suroviny (křemenné
valouny z teras? kvarcit z moldanubika?)? Nebo vše importováno?
→ **Otázka pro geologa nebo Šídu.**

### Q-GEO-04: DIBAVOD atributy umělých toků

Má DIBAVOD atribut rozlišující přirozené vs. umělé toky?
→ **Ověřit ze stažených dat.**

### Q-GEO-05: DMR 5G dostupnost — ✅ VYŘEŠENO

DMR 5G je volně ke stažení jako otevřená data. Přístup přes:
- Geoprohlížeč ČÚZK (manuální export s bbox)
- ArcGIS ImageServer REST API: `https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer`
- Pixel 2m, přesnost 0.18m, formáty SHP/DGN/DXF/TXT, S-JTSK (EPSG:5514)
- Pro bbox ~930 km²: ~232M bodů (přesamplovat na 5m pro analýzy)

---

## 7. Výstupy fáze 1 (geologie)

Po dokončení pipeline (kroky 1-7):

1. **PostGIS tabulka `terrain_subtype_cz`** — polygony s KB atributy
2. **PostGIS tabulka `river_network_cz`** — filtrovaná říční síť
3. **PostGIS tabulka `paleolakes_cz`** — rekonstruované vodní plochy ~7000 BCE
4. **Leaflet mapa** — geologická vrstva s terrain_subtypes, řekami, paleolakes
5. **Validační report** — výsledky Fáze 1 testů z MAP_VALIDATION_TESTS_v02
6. **Gap report** — co chybí pro vrstvu 2 (HYDRO_DESIGN)

---

## 8. Vztah k dalším vrstvám

```
GEO_DESIGN (tento dokument)
    │
    │  terrain_subtypes + říční síť + paleolakes
    │  = fyzický základ krajiny
    ▼
HYDRO_DESIGN (další dokument)
    │
    │  Rekonstrukce hydrologického režimu ~7000 BCE
    │  Rybníky ODSTRANĚNY (R2) → paleolakes, niva, rašelina
    │  Sezónní záplavy, zamrzání, artézské prameny (Švarcenberk!)
    ▼
BIO_DESIGN (nejsložitější)
    │
    │  VMB → mezolitická vegetace
    │  Terrain + hydrology → CAN_HOST → biotopy
    │  Pylové profily jako validace
    ▼
KB vrstva 1-3 kompletní pro Třeboňsko
```

---

## Reference

- Hošek, J. et al. 2013. Newly discovered Late Glacial lakes, Třeboň Basin.
- Hošek, J. et al. 2016. (pokračování výzkumu paleolakes)
- Pokorný, P. et al. 2010. Palaeoenvironmental research of Schwarzenberg Lake. *Památky archeologické* 101.
- Šída, P., Pokorný, P. & Kuneš, P. 2007. Dřevěné artefakty raně holocenního stáří z litorálu zaniklého jezera Švarcenberk.
- Šída, P. & Prostředník, J. 2014. The Mesolithic of the Bohemian Paradise.
- EnviWeb: Geologie a geomorfologie Třeboně a okolí (enviweb.cz/92019)
- AOPK ČR: Charakteristika oblasti Třeboňsko (trebonsko.aopk.gov.cz)

---

*Tento dokument je živý — aktualizuje se po ověření datových zdrojů (§6).*
*Další kroky: HYDRO_DESIGN_v01.md, BIO_DESIGN_v01.md*

---

## 9. Changelog v0.1 → v0.2

### Rozhodnutí zanesena
- R1: Substrate enum rozšířen univerzálně (+5 hodnot → vocabulary_v03)
- R2: Rybníky se mažou a nahrazují paleokrajinou (strategie A)
- R3: Počet terrain_subtypes se rozhodne po inspekci ČGS dat
- R4: DEM = DMR 5G (2m pixel, 0.18m přesnost, volně dostupný)
- R5: ID konvence = prefix `cz_` konzistentně

### Ověřeno
- Q-GEO-05: DMR 5G dostupnost → VYŘEŠENO (otevřená data, ImageServer API)

### Aktualizováno
- §3.2: Mapovací tabulka — nové substrate hodnoty, `cz_` prefix
- §3.3: Substrate gap → rozšíření (5 nových univerzálních hodnot)
- §4 Krok 1: Pipeline přepsán na DMR 5G (místo GLO-30)
- §5: Rozhodovací body → tabulka rozhodnutí + R2 detail

### Stále otevřeno
- Q-GEO-01: ČGS WFS struktura → testovat v Claude Code
- Q-GEO-02: Paleolake GIS data → kontaktovat Hoška/Pokorného
- Q-GEO-03: Lokální suroviny → otázka pro geologa
- Q-GEO-04: DIBAVOD atributy umělých toků → ověřit ze stažených dat

