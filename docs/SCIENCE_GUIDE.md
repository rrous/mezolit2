# Mezolit2 — Science & Content Guide
### Knowledge Base for Mesolithic Yorkshire (~6200 BCE)

> **CZ:** Průvodce pro vědce a tvůrce obsahu — geology, hydrology, ecology, archaeology.
> **EN:** Guide for scientists and content contributors — geologists, hydrologists, ecologists, archaeologists.

---

## Table of Contents / Obsah

1. [What is Mezolit2 KB?](#1-what-is-mezolit2-kb)
2. [Research Context / Výzkumný kontext](#2-research-context)
3. [Data Architecture / Datová architektura](#3-data-architecture)
4. [Terrain Subtypes (10 types)](#4-terrain-subtypes)
5. [Biotopes (11 types)](#5-biotopes)
6. [Ecotones (6 boundaries)](#6-ecotones)
7. [Epistemic System / Epistemika](#7-epistemic-system)
8. [Vocabulary Reference / Slovník](#8-vocabulary-reference)
9. [How to Contribute / Jak přispět](#9-how-to-contribute)
10. [Data Sources & Literature](#10-data-sources--literature)
11. [Known Limitations / Omezení](#11-known-limitations)

---

## 1. What is Mezolit2 KB?

**EN:** Mezolit2 is a geospatial knowledge base reconstructing the landscape of Yorkshire (~6200 BCE) at the transition from the Boreal to the early Atlantic climatic period. It encodes scientific knowledge about terrain, ecology, and archaeological sites as a structured graph — enabling researchers to query "what biotope could a hunter-gatherer group exploit here, in which season, with what certainty?".

**CZ:** Mezolit2 je geoprostorová znalostní databáze rekonstruující krajinu Yorkshire (~6200 BCE) na přechodu z boreálního do raného atlantického klimatického období. Vědecké poznatky o terénu, ekologii a archeologických lokalitách jsou uloženy jako strukturovaný graf — výzkumníci mohou dotazovat „jaký biotop mohl využít lovecko-sběračský tábor na tomto místě, v jakém ročním období a s jakou mírou jistoty?".

**Scope / Rozsah:**
- **Geography:** Yorkshire, England (bbox: 53.5°–54.7°N, -2.5°–0.1°E)
- **Time:** ~6200 BCE (calibrated ¹⁴C; Mesolithic, Boreal climatic period)
- **Sea level:** -25 m relative to present day (Shennan et al. 2018)
- **Archaeological anchor:** Star Carr (54.214°N, -0.403°W) — ADS postglacial_2013

---

## 2. Research Context

### Climate & Environment (~6200 BCE) / Klima a prostředí

| Parameter | Value | Source |
|-----------|-------|--------|
| Climate period | Boreal (pre-Atlantic) | Walker et al. 2012 |
| Temperature | ~1–2°C warmer than present (summer) | Davis et al. 2003 |
| Sea level offset | −25 m (land bridge Doggerland still partial) | Shennan et al. 2018 |
| Vegetation | Boreal birch-hazel-pine forest (dominant) | Simmons 1996; Rackham 1986 |
| Star Carr date range | ~9300–8500 BP (cal.) | Conneller et al. 2012 |

### Lake Flixton / Jezero Flixton

Lake Flixton was a shallow lake (max depth ~2–4 m) occupying the Vale of Pickering basin.
**CZ:** Lake Flixton bylo mělké jezero (max hloubka ~2–4 m) v kotlině Vale of Pickering.

| Attribute | Value |
|-----------|-------|
| Area | ~5.52 km² |
| Extent | 4.88 × 2.69 km |
| Water level | ~24 m aOD (Taylor & Alison 2018); DEM fallback 24.8 m EGM2008 |
| Polygon source | ADS postglacial_2013 (Palmer et al. 2015) — 234 vertices |
| Geometry | GML → WGS84 in `data/raw/ads/lake2_wgs84.gml` |

### Yorkshire Landscape Zones / Krajinné zóny Yorkshire

```
North Sea (submerged at -25m)
    │
    ├── Holderness coast (tidal estuaries, bt_008)
    │
    ├── Yorkshire Wolds (chalk downland, tst_005 → bt_006)
    │
    ├── Vale of Pickering ← LAKE FLIXTON (tst_001 → bt_001)
    │       └── Star Carr (primary_camp), Flixton Island (island_site)
    │
    ├── North York Moors (limestone plateau, tst_003 → bt_003)
    │
    ├── Vale of York (river floodplain, tst_002 → bt_002)
    │       └── Rivers: Ouse, Derwent, Wharfe
    │
    ├── Yorkshire Dales (limestone, tst_003)
    │
    └── Pennines (upland peat, tst_006 → bt_004)
```

---

## 3. Data Architecture

### Three-Layer Graph / Třívrstvý graf

The KB is organized as a directed graph with three immutable reference layers:

```
TERRAIN_SUBTYPE  ──CAN_HOST──►  BIOTOPE  ──occupies──►  ECOTONE
    (geology,                    (ecology,               (boundary
    immutable)                   scientific)              zone)
         │                           │
         ▼                           ▼
   TERRAIN_FEATURE              BIOTOPE_MAP
   (geometry polygon)           (spatial snapshot)
         │
         ▼
   SITE_INSTANCE
   (archaeological anchor)
```

**CZ — Princip CAN_HOST:**
Biotop "ví", kde může existovat. Každý záznam biotopu obsahuje pole `can_host[]` — seznam vazeb na terénní subtypy, kde daný biotop může přežít. Klient prochází: terrain_subtype → najdi všechny biotopy s odpovídajícím can_host → vyber dominantní (nejvyšší quality_modifier, trigger = "baseline").

### Immutability Hierarchy / Hierarchie neměnnosti

| Layer | Timescale | Can change? |
|-------|-----------|-------------|
| TERRAIN_SUBTYPE | Geological (10⁶ years) | No — only correction |
| BIOTOPE + CAN_HOST | Scientific knowledge | Yes — with source + revision_note |
| TERRAIN_FEATURE (geometry) | Geomorphological | No — correction only |
| BIOTOPE_MAP | Client snapshot | Recalculated from KB |
| CURRENT_STATE | Runtime (season, event) | Dynamic |

---

## 4. Terrain Subtypes

**CZ:** Terénní subtypy jsou geologicky podmíněné kategorie — reprezentují základní fyziogeografický charakter území. Jsou neměnné na škále milionů let.

### Complete Reference Table / Kompletní přehled

| ID | Name (EN) | Název (CZ) | Hydrology | Elevation | Substrate | Yorkshire location |
|----|-----------|------------|-----------|-----------|-----------|-------------------|
| **tst_001** | Glacial lake basin | Ledovcová jezerní pánev | permanent_standing_water | 0–100 m | organic_lacustrine | Vale of Pickering (Lake Flixton) |
| **tst_002** | River floodplain | Říční niva | seasonal_flooding | 0–150 m | alluvial_silts | Vale of York, river valleys |
| **tst_003** | Limestone/sandstone plateau | Vápencová/pískovcová plošina | well_drained | 150–500 m | limestone_sandstone | North York Moors, Dales |
| **tst_004** | Fenland basin | Rašelinná pánev / Fen | waterlogged_permanent | 0–50 m | peat | Humberhead Levels (SW) |
| **tst_005** | Chalk downland | Křídová plošina (Wolds) | well_drained | 50–300 m | chalk_flint | Yorkshire Wolds (east of -0.8°E) |
| **tst_006** | Upland peat basin | Vrchovinná rašeliniště | seasonally_waterlogged | 300–720 m | blanket_peat | Pennines, high moorland |
| **tst_007** | Rocky coast / sea cliff | Skalnaté pobřeží | tidal_inundation | 0–30 m | bedrock | Filey, Flamborough Head |
| **tst_008** | Tidal estuary / mudflat | Přílivový estuár | tidal_inundation | −5–10 m | tidal_sediment | Humber estuary, Hull |
| **tst_009** | Large permanent river | Velká stálá řeka | permanent_flowing_water | 0–100 m | alluvial | Ouse, Derwent (line feature) |
| **tst_010** | Small seasonal stream | Malý sezónní potok | seasonal_flowing_water | 0–400 m | mixed | Upland streams (line feature) |

> **Note:** tst_009 and tst_010 are **linear features** (rivers), not polygon terrain. They feed into tst_002 (floodplain buffer).

### Key Attributes per Type / Klíčové atributy

Each terrain subtype has these attributes in `kb_data/schema_examples_v04.json`:
- `hydrology` — water regime (see Vocabulary §8)
- `slope` — typical gradient
- `substrate` — geological parent material
- `elevation_min_m` / `elevation_max_m` — typical range
- `flint_availability` — non-renewable resource for toolmaking
- `trafficability` — ease of movement (energy cost for humans)
- `nonrenewable_resources[]` — flint, stone, clay, etc.
- `anchor_instances[]` — known named examples (e.g. "Lake Flixton")

---

## 5. Biotopes

**CZ:** Biotopy jsou ekologické společenstvo organismů. V databázi reprezentují dominantní vegetační a faunistický typ pro danou část krajiny v boreálním období. Neobsahují geometrii — jsou přiřazeny k terénním polygonům přes CAN_HOST pravidla.

### Productivity Scale / Stupnice produktivity

```
VERY_HIGH  >1 000 000 kcal/km²/year  (estuary, lake with fish runs)
HIGH         500 000–1 000 000        (wetland, riparian, coastal)
MEDIUM       200 000–500 000          (boreal forest, floodplain)
LOW        < 200 000                  (open upland, chalk scrub)
```

### Complete Biotope Reference / Kompletní přehled biotopů

| ID | Name | Terrain (tst) | Productivity | Trafficability | Human relevance | Season peak |
|----|------|---------------|-------------|----------------|-----------------|-------------|
| **bt_001** | Boreal shallow lake | tst_001 | HIGH (600 000) | LOW (×2.0) | CRITICAL | Spring (fish), Autumn (wildfowl) |
| **bt_002** | Fen wetland / Boreální mokřad | tst_002, tst_004 | HIGH (650 000) | VERY_LOW (×3.0) | HIGH | Spring/Summer (reeds, waterfowl) |
| **bt_003** | Boreal birch-hazel-pine forest | tst_003, tst_006 | MEDIUM (350 000) | MEDIUM (×1.5) | HIGH | Autumn (nuts, berry), Spring (game) |
| **bt_004** | Open upland / Otevřená krajina | tst_006 | LOW (150 000) | HIGH (×1.0) | LOW | Summer (grazing auroch, elk) |
| **bt_005** | Coastal saltmarsh/estuary | tst_007, tst_008 | HIGH (700 000) | LOW (×2.0) | HIGH | Spring/Autumn (fish, shellfish) |
| **bt_006** | Chalk scrub / grassland | tst_005 | LOW–MED (200 000) | HIGH (×1.0) | MEDIUM | Summer/Autumn (flint, deer) |
| **bt_007** | Riparian gallery forest | tst_002, tst_009 | HIGH (750 000) | MEDIUM (×1.5) | HIGH | Spring (fish runs), Autumn (nuts) |
| **bt_008** | Intertidal coastal | tst_008 | MED–HIGH (500 000) | LOW (×2.0) | MEDIUM | Summer (shellfish) |
| **bt_009** | Forest glade (micro) | tst_003, tst_006 | MED–HIGH (550 000) | HIGH (×1.0) | MEDIUM | Spring (new growth), Summer |
| **bt_010** | Post-fire grassland (event) | tst_003, tst_006 | MED–HIGH (450 000) | HIGH (×1.0) | MEDIUM | Summer (game attracted to regrowth) |
| **bt_011** | Drought-stressed wetland (event) | tst_002, tst_004 | MEDIUM (300 000) | MEDIUM (×1.5) | MEDIUM | Summer (fish concentrated) |

> **bt_010 and bt_011** are **event biotopes** — triggered by fire or drought (`trigger: "fire"` / `trigger: "drought"` in CAN_HOST). They do not appear in baseline maps.

### Seasonal Modifiers / Sezónní modifikátory

Each biotope has season multipliers (applied to base productivity):

| Biotope | Spring | Summer | Autumn | Winter |
|---------|--------|--------|--------|--------|
| bt_001 (Lake) | 1.4 | 1.0 | 1.3 | 0.4 |
| bt_002 (Wetland) | 1.4 | 1.2 | 1.1 | 0.5 |
| bt_003 (Forest) | 1.1 | 1.0 | 1.4 | 0.6 |
| bt_005 (Coastal) | 1.3 | 1.0 | 1.3 | 0.7 |
| bt_007 (Riparian) | 1.4 | 1.1 | 1.3 | 0.5 |

**CZ — Interpretace:** Hodnota > 1.0 = nadprůměrná dostupnost zdrojů v daném ročním období. Hodnota < 0.7 = výrazně snížená dostupnost (zamrzlé jezero, suché potoky).

---

## 6. Ecotones

**EN:** Ecotones are transition zones between two adjacent biotopes. They typically have **higher productivity than either parent biotope** (edge effect) because they concentrate resources from both sides. For Mesolithic hunter-gatherers, ecotones were prime hunting and gathering locations.

**CZ:** Ekotony jsou přechodové zóny mezi dvěma sousedními biotopy. Mají obvykle **vyšší produktivitu než oba rodičovské biotopy** (edge effect). Pro mezolitické lovce-sběrače byly ekotony klíčovými místy pro lov a sběr.

### Ecotone Reference / Přehled ekotonů

| ID | Boundary | Edge factor | Human relevance | Seasonal peaks |
|----|----------|-------------|-----------------|----------------|
| **ec_001** | Forest ↔ Wetland | 1.4 | **CRITICAL** | Spring (fish), Autumn (nuts + wildfowl) |
| **ec_002** | Wetland ↔ Lake | 1.3 | HIGH | Spring (fish runs), Winter (ice access) |
| **ec_003** | Forest ↔ Open upland | 1.2 | MEDIUM | Summer (auroch, deer), Autumn (berries) |
| **ec_004** | River ↔ Forest | 1.35 | HIGH | Spring (fish, beaver), Winter (ambush) |
| **ec_005** | Coast ↔ Wetland | 1.45 | HIGH | Spring/Autumn (fish, shellfish, wildfowl) |
| **ec_006** | Forest ↔ Glade | 1.15 | MEDIUM | Spring (herbs, deer), Summer |

> **ec_001 (Forest/Wetland)** at Star Carr is the most important ecotone — it is where the primary camp was located. Human hunters could exploit both forest game and lake/wetland resources within walking distance.

### Edge Effect Formula / Vzorec edge effect

```
effective_productivity = base_productivity × edge_effect_factor × season_modifier
```

Example (ec_001 at Star Carr, Spring):
```
forest (bt_003): 350 000 kcal × 1.1 (spring) = 385 000
wetland (bt_002): 650 000 × 1.4 (spring) = 910 000
ecotone bonus: max(385 000, 910 000) × 1.4 = 1 274 000 kcal/km²/year
```

---

## 7. Epistemic System

**EN:** Every node and edge in the KB carries explicit epistemic metadata. This is not optional — it is the scientific backbone of the system.

**CZ:** Každý uzel a hrana v KB nese explicitní epistemická metadata. Toto není volitelné — jde o vědeckou páteř systému.

### Certainty Levels / Úrovně jistoty

| Value | Meaning (EN) | Meaning (CZ) | Visual rendering |
|-------|-------------|--------------|-----------------|
| **DIRECT** | Direct archaeological/sediment evidence | Přímý archeologický/sedimentární doklad | Solid border, 90% opacity |
| **INDIRECT** | Proxy evidence (pollen, phytoliths, isotopes) | Proxy doklad (pyl, fytolyty, izotopy) | Dashed border, 75% |
| **INFERENCE** | Derived from models or analogues | Odvozeno z modelu nebo analogie | Dotted border, 60% |
| **SPECULATION** | Expert hypothesis, no data | Expertní hypotéza, bez dat | No border, 45% |

### Status Values / Hodnoty statusu

| Value | Meaning |
|-------|---------|
| **VALID** | Current best knowledge |
| **REVISED** | Updated — see revision_note |
| **DISPUTED** | Active scholarly debate |
| **REFUTED** | Disproven — retained for traceability |
| **HYPOTHESIS** | Proposed, not yet tested |

### Required Fields for Every Record / Povinná pole

```json
{
  "certainty": "INDIRECT",
  "source": "Simmons 1996 — Island Britain",
  "status": "VALID",
  "revision_note": null
}
```

### Certainty in Practice / Příklady v praxi

| Claim | Certainty | Why |
|-------|-----------|-----|
| Lake Flixton polygon shape | INDIRECT | ADS GML from pollen core / sediment data (Palmer 2015) |
| Boreal forest as dominant biome | INDIRECT | Pollen cores (Simmons 1996) |
| Productivity values (kcal/km²) | INFERENCE | Extrapolated from modern analogues (Rackham 1986) |
| Star Carr as primary camp | DIRECT | Excavation evidence (Clark 1954; Conneller 2012) |
| Sea level at -25 m | INDIRECT | Isostatic models + GEBCO (Shennan et al. 2018) |

---

## 8. Vocabulary Reference

**CZ:** Všechny hodnoty enumů jsou definovány v `kb_data/vocabulary_v02.json`. Níže jsou klíčové kategorie.

### 8.1 slope

| Value | Range (°) | Example |
|-------|-----------|---------|
| flat | 0–2 | Lake basin, fen |
| very_low | 2–5 | Floodplain |
| low | 5–10 | Chalk plateau |
| low_to_moderate | 2–15 | Chalk downland (compound) |
| moderate | 10–20 | Limestone plateau |
| steep | 20–35 | Escarpment |
| very_steep | >35 | Sea cliff |
| low_to_steep | 2–35 | Upland peat basin (compound) |

### 8.2 hydrology

| Value | Description |
|-------|-------------|
| permanent_standing_water | Lake/pond — permanent |
| seasonal_flooding | Floodplain — winter/spring inundation |
| waterlogged_permanent | Fen — year-round waterlogged |
| well_drained | Chalk/limestone — no surface water |
| seasonally_waterlogged | Upland peat — summer dry, winter wet |
| permanent_flowing_water | River (large) |
| seasonal_flowing_water | Stream (small, may dry) |
| tidal_inundation | Estuarine/coastal |

### 8.3 substrate

| Value | Description | Terrain |
|-------|-------------|---------|
| organic_lacustrine | Lake sediment (peat, silts) | tst_001 |
| alluvial_silts | River deposit | tst_002 |
| limestone_sandstone | Hard rock plateau | tst_003 |
| peat | Upland blanket peat | tst_004, tst_006 |
| chalk_flint | Chalk with flint nodules | tst_005 |
| tidal_sediment | Estuarine mud/sand | tst_008 |

### 8.4 productivity_class

| Value | Range (kcal/km²/year) | Ecological context |
|-------|----------------------|-------------------|
| VERY_HIGH | >1 000 000 | Estuarine fish runs, rich wetlands |
| HIGH | 500 000–1 000 000 | Riparian, coastal, lake edge |
| MEDIUM | 200 000–500 000 | Boreal forest, wetland interior |
| MEDIUM_TO_HIGH | 350 000–700 000 | Compound class |
| LOW_TO_MEDIUM | 100 000–350 000 | Chalk scrub, degraded fen |
| LOW | <200 000 | Open upland, dry heath |

### 8.5 trafficability

| Value | Energy multiplier | Meaning |
|-------|------------------|---------|
| HIGH | ×1.0 | Easy movement (open ground, chalk) |
| MEDIUM | ×1.5 | Forest with undergrowth |
| LOW | ×2.0 | Dense wetland reed, shallow lake |
| VERY_LOW | ×3.0 | Deep bog, open water crossing |

> **CZ:** Energy multiplier říká, kolikrát více energie stojí pohyb přes daný biotop oproti otevřenému terénu (HIGH = ×1.0 = referenční). Používá se v simulacích mobility skupin.

### 8.6 human_relevance

| Value | Meaning |
|-------|---------|
| CRITICAL | Ecotone always associated with camps/activity (ec_001) |
| HIGH | Major resource zone, seasonal camps expected |
| MEDIUM | Used but secondary |
| LOW | Rarely exploited (open upland in winter) |

### 8.7 permanence (rivers)

| Value | Meaning |
|-------|---------|
| permanent | Flows year-round |
| seasonal | Dries in summer |
| ephemeral | Short-lived after rain |
| reconstructed | Geomorphologically inferred, course uncertain |

### 8.8 season

`SPRING` | `SUMMER` | `AUTUMN` | `WINTER` | `YEAR_ROUND`

---

## 9. How to Contribute

### 9.1 Adding a new Biotope / Přidání nového biotopu

Edit `kb_data/schema_examples_v04.json` — add a new record to `biotopes.records[]`:

```json
{
  "id": "bt_012",
  "name": "Bog woodland (alder/willow carr)",
  "description": "Wet woodland on waterlogged soils...",
  "attributes": {
    "productivity_class": "MEDIUM",
    "primary_productivity_kcal_km2_year": 300000,
    "trafficability": "VERY_LOW",
    "energy_multiplier": 3.0
  },
  "can_host": [
    {
      "terrain_subtype": "tst_002",
      "trigger": "baseline",
      "spatial_scale": "local",
      "quality_modifier": 0.8,
      "certainty": "INFERENCE",
      "source": "Rackham 1986 — History of the Countryside"
    }
  ],
  "seasonal_modifiers": {
    "SPRING": { "modifier": 1.3, "note": "Willow catkins, first insects" },
    "SUMMER": { "modifier": 1.1, "note": "Dense canopy, alder fruiting" },
    "AUTUMN": { "modifier": 1.2, "note": "Alder seeds, waterfowl" },
    "WINTER": { "modifier": 0.6, "note": "Waterlogged, difficult movement" }
  },
  "epistemics": {
    "certainty": "INFERENCE",
    "source": "Rackham 1986; Huntley & Birks 1983",
    "status": "VALID"
  }
}
```

**Rules / Pravidla:**
- `id` must be unique (`bt_NNN` format)
- `certainty` must be one of: DIRECT, INDIRECT, INFERENCE, SPECULATION
- `source` must be a real published reference
- `productivity_class` must match vocabulary values
- `can_host[].trigger` = "baseline" for normal conditions; "fire"/"drought"/"beaver" for events

### 9.2 Adding/Correcting a Terrain Subtype

Edit `kb_data/schema_examples_v04.json` → `terrain_subtypes.records[]`.
**Never delete** — use `"status": "REVISED"` + `"revision_note"` instead.

### 9.3 Adding an Ecotone

Edit `kb_data/schema_examples_v04.json` → `ecotones.records[]`:
- Both `biotope_a_id` and `biotope_b_id` must exist in biotopes
- `edge_effect_factor` — literature-based (1.1–1.5 typical)
- `human_relevance` — must be one of vocabulary values

### 9.4 Correcting Productivity Values

If you have better kcal/km²/year data:
1. Update the value in `schema_examples_v04.json`
2. Change `certainty` to reflect the new evidence quality
3. Add/update `source` with full citation
4. Add `revision_note` explaining the change

### 9.5 What requires re-running the pipeline?

| Change | Action required |
|--------|----------------|
| KB data only (JSON) | Run `01_seed_kb_data.py` only |
| New biotope → terrain mapping | Run `01_seed_kb_data.py` + `05_kb_rules.py` + `06_import_supabase.py` |
| New terrain subtype | Full pipeline (01–06) |
| Geometry change | Run `04_terrain.py` + `06_import_supabase.py` |

---

## 10. Data Sources & Literature

### Geospatial Data / Geoprostorová data

| Dataset | Source | Version | License | Used for |
|---------|--------|---------|---------|---------|
| Copernicus DEM GLO-30 | ESA / OpenTopography | 2021 | CC-BY-4.0 | Terrain classification |
| GEBCO 2023 | GEBCO / BODC | 2023 | CC-BY-4.0 | Coastline at -25 m |
| OS Open Rivers | Ordnance Survey | 2023 | OGL v3 | River network |
| ADS postglacial_2013 | ADS (doi:10.5284/1041580) | 2015 | CC-BY-4.0 | Lake Flixton, 20 sites |

### Key Publications / Klíčové publikace

**Palaeoenvironment / Paleoklima:**
- Shennan, I. et al. (2018). *Sea-level changes and the evolution of coastal environments.* British Geological Survey.
- Davis, B.A.S. et al. (2003). The temperature of Europe during the Holocene. *Quaternary Science Reviews* 22.
- Walker, M. et al. (2012). Formal subdivision of the Holocene. *Journal of Quaternary Science* 27.

**Vegetation & Ecology / Vegetace:**
- Rackham, O. (1986). *The History of the Countryside.* Dent, London.
- Simmons, I.G. (1996). *The Environmental Impact of Later Mesolithic Cultures.* Edinburgh.
- Vera, F.W.M. (2000). *Grazing Ecology and Forest History.* CABI.

**Star Carr & Lake Flixton / Lokalita:**
- Clark, J.G.D. (1954). *Excavations at Star Carr.* Cambridge.
- Conneller, C. et al. (2012). Substantial settlement in the European Early Mesolithic. *Cambridge Archaeological Journal* 22.
- Milner, N. et al. (2018). *Star Carr Volume 2: Studies in Technology, Subsistence and Environment.* White Rose.
- Palmer, A. et al. (2015). ADS Dataset: Postglacial landscape, Vale of Pickering. doi:10.5284/1041580
- Taylor, B. & Alison, R. (2018). Lake Flixton water level reconstruction. *Quaternary Science Reviews.*

**Mesolithic Subsistence / Obživa:**
- Huntley, B. & Birks, H.J.B. (1983). *An Atlas of Past and Present Pollen Maps for Europe.* Cambridge.
- Allen, J.R.L. & Pye, K. (1992). *Saltmarshes: Morphodynamics, Conservation.* Cambridge.

---

## 11. Known Limitations

**EN — What is an approximation:**

| Aspect | Limitation | Certainty level |
|--------|-----------|-----------------|
| Terrain polygon boundaries | Derived from 30 m DEM — not geological survey | INFERENCE |
| tst_003 vs tst_005 distinction | Approximated by longitude (-0.8°) — no BGS geology used | INFERENCE |
| River courses | Modern OS rivers used as proxy — actual ~6200 BCE courses uncertain | INDIRECT |
| Productivity values (kcal) | Extrapolated from modern analogues in similar biomes | INFERENCE |
| Lake Flixton shape | ADS sediment-based polygon (234 vertices) — most reliable available | INDIRECT |
| Ecotone positions | Auto-generated from polygon boundaries — not field-mapped | INFERENCE |
| Forest glade density | Smart-hole algorithm (0.5–5 ha) from DEM — not archaeobotanical | INFERENCE |

**CZ — Kde je PoC zjednodušení:**
- Terrain polygony vznikly z DEM klasifikace elevace a sklonu — **ne geologickým průzkumem**. Označeny jako INFERENCE.
- Říční síť je moderní OS Open Rivers — proxy pro mezolitický průběh. Označena jako INDIRECT.
- Produktivita v kcal je odvozena z moderních analogií v podobných biomech. Označena jako INFERENCE.
- Toto je **PoC (Proof of Concept)** — výsledky jsou prezentovatelné vědecké komunitě jako hypotézy, ne jako ověřená fakta.
