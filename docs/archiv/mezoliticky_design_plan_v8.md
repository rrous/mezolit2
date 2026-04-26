# MEZOLITICKÝ KNOWLEDGE BASE
## Star Carr — Británie ~6200 BCE | Design Plán Projektu
*Verze 0.8 | Draft*

---

## 1. Výzkumná otázka a cíle projektu

Jaké byly klíčové faktory — ekologické, technologické a sociální — které určovaly přežití a prosperitu člověka v mezolitické severní Evropě (~9500–6000 BCE), se zvláštním zaměřením na oblast Star Carr / Lake Flixton a její extrapolaci na celou Británii?

### 1.1 Primární cíl

Vytvořit strukturovanou ontologii a knowledge base zachycující ekologické, technologické a sociální dimenze mezolitického života jako propojený znalostní graf. Knowledge base poskytuje parametrická data pro modelování přežití skupin a ekologické simulace.

### 1.2 Dílčí cíle

- Popsat terénní prvky, biotopy a ekotony jako graph uzly s CAN_HOST hranami
- Modelovat ekologické vztahy jako síť nezávisle na perspektivě člověka
- Zachytit dopady lidské činnosti na krajinu přes event triggery
- Udržovat epistemickou poctivost: každý záznam má míru jistoty, zdroj a verzi
- Poskytovat parametrická data přes API klientům (Unreal Engine, GIS, vědecké nástroje)

---

## 2. Rozsah a zaměření

### 2.1 Geografický a časový rámec

| Parametr | Hodnota |
|---|---|
| Lokalita (kotva) | Star Carr / Lake Flixton, Yorkshire, UK |
| Prostorový rozsah | Celá Británie + bývalý Doggerland |
| Snapshot | ~6200 BCE — moment oddělení Británie od pevniny |
| Mořská hladina | ~25–30 m pod současnou úrovní (Shennan et al.) |
| Klimatická fáze | Boreal / počátek Atlantiku |
| Klíčová reference | Milner et al. (2018): Star Carr — Life in Britain after the Ice Age |

---

## 3. Architektura Knowledge Base

### 3.1 Vrstvové oddělení (klíčové rozhodnutí)

```
KB VRSTVY (statická data — co stavíme):
  TERRAIN_SUBTYPE      — generický typ terénního prvku, quasi-immutable (geologický čas)
  TERRAIN_INSTANCE     — konkrétní lokalita s anchor evidence (Star Carr, Wash...)
  BIOTOPE              — definice ekologické komunity + CAN_HOST hrany na terrain
  ECOTONE              — přechod dvou biotopů, immutable

USAGE VRSTVY (klientská zodpovědnost — KB dodá parametry):
  BIOTOPE_MAP          — klient aplikuje baseline CAN_HOST hrany na terrain → snapshot 6200 BCE
  MODIFIED_MAP         — klient aplikuje event CAN_HOST hrany při eventu + duration tracking
  CURRENT_STATE        — klient filtruje přes query: {season, weather, time_of_day}
```

**Pravidlo:** KB poskytuje pouze parametry a pravidla. Mapu si klient staví a udržuje sám.

### 3.2 Immutability hierarchie

```
TERRAIN_SUBTYPE (geologický čas)
  > BIOTOPE + CAN_HOST hrany (vědecké poznání, verzováno)
    > BIOTOPE_MAP (klientský snapshot)
      > CURRENT_STATE (runtime filtr)
```

### 3.3 Grafový model — CAN_HOST hrana (klíčové rozhodnutí)

**Zrušen rule engine** — nahrazen přímými CAN_HOST hranami na BIOTOPE uzlech. Terrain je pasivní, biotop ví kde může existovat.

```
BIOTOPE.can_host[] = [
  {
    terrain_subtype: "tst_002",   // říční niva
    trigger: "baseline",          // součást snapshotu / nebo event_fire, event_drought...
    spatial_scale: "landscape",   // landscape | local | micro
    quality_modifier: 1.0,        // 0.0–1.0, vliv terrainu na kvalitu biotopu
    duration_years: null,         // null = permanentní; N = sukcese zpět za N let
    note: "říční niva — primární výskyt"
  }
]
```

**Klient traversuje graf:** pro daný `terrain_subtype` najdi biotopy kde figuruje v `can_host` → filtruj `trigger` → použij `quality_modifier`.

**quality_modifier** reflektuje jak dobře terrain podporuje biotop. Příklad: post_fire_grassland na říční nivě (bohatá půda) = 0.95, na rašelině Pennin = 0.5.

### 3.4 Query dimensions — struktura dotazu na CURRENT_STATE

Klient posílá query ve tvaru:
```json
{
  "hex_or_polygon_id": "...",
  "season": "AUTUMN",
  "weather": "RAIN",
  "time_of_day": "DAWN"   // jen pro faunu
}
```

KB vrátí slice relevantních dat — biotop s aplikovanými `seasonal_modifiers`, fauna s aplikovanými `weather_modifiers` (budoucí vrstvy). Všechny modifikátory musí být konzistentně strukturované napříč node typy.

### 3.5 Enumerace (vocabulary)

Enums slouží primárně **vědeckému popisu a zobrazování** — nejsou nutné pro runtime fungování modelu v1. Model v1 funguje na graph traversal a `quality_modifier`.

Funkčně důležité enums (model je potřebuje):
- `season` — přímý vstup query
- `trigger` — baseline vs. event
- `trafficability` + `energy_multiplier` — kalorické modelování pohybu
- `productivity_class` — kalorický odhad
- `flint_availability` — neobnovitelná surovina terrain

Vědecký popis / zobrazování:
- `slope`, `hydrology`, `substrate` — popis terrain_subtype
- `human_relevance`, `certainty`, `status` — vědecká integrita

Plná dokumentace v souboru `vocabulary_v02.json`.

---

## 4. Datový model — Node typy

### 4.1 TERRAIN_SUBTYPE

Generický typ terénního prvku — existuje globálně. Anglická data jsou anchor evidence konkrétních instancí.

Klíčové atributy:
- `key_attributes` — hydrology, slope, substrate, elevation (vědecký popis)
- `nonrenewable_resources` — flint, kámen (funkčně důležité pro simulaci)
- `anchor_instances` — seznam konkrétních lokalit s přímým dokladem

### 4.2 BIOTOPE

Definice ekologické komunity. Obsahuje CAN_HOST hrany (vazba na terrain) a query dimensions (seasonal_modifiers, budoucí weather_modifiers).

Klíčové atributy:
- `can_host[]` — hrany s terrain_subtype, trigger, quality_modifier, duration_years
- `productivity_class` + `primary_productivity_kcal_km2_year`
- `trafficability` + `energy_multiplier`
- `seasonal_modifiers` — tabulka {season → productivity_modifier, note}

### 4.3 ECOTONE

Přechod dvou biotopů. Hrana grafu s `edge_effect_factor` > 1.0.

Dynamické ekotony (event biotop sousedí s jiným biotopem) jsou klientská zodpovědnost.

### 4.4 Budoucí node typy (vrstvy 4–9)

Podle antropologického rámce přežití (viz sekce 5):

| Node typ | Vrstva |
|---|---|
| ANIMAL | 4 — Populace organizmů |
| PLANT | 4 — Populace organizmů |
| INSECT_PRODUCT | 5 — Primární zdroje |
| TOOL, MATERIAL, TECHNIQUE | průřezová — Technologie |
| SHELTER | 7 — Dostupné zdroje |
| THREAT | více vrstev |
| HUMAN_GROUP | 8 — Přežití skupiny |

### 4.5 Epistemická vrstva (povinná u každého uzlu a hrany)

```json
"epistemics": {
  "certainty": "DIRECT | INDIRECT | INFERENCE | SPECULATION",
  "source": "autor, rok, strana",
  "status": "VALID | REVISED | DISPUTED | REFUTED | HYPOTHESIS",
  "superseded_by": null,
  "revision_note": null
}
```

---

## 5. Antropologický rámec přežití

Rámec definuje PROČ a CO zkoumáme. Všechny datové třídy a relace jsou odvozeny z hierarchického modelu závislostí.

| Vrstva | Klíčová otázka | Kritická závislost |
|---|---|---|
| 1. Terén + Klima | Jaké jsou fyzické podmínky? | Základ pro vše |
| 2. CAN_HOST pravidla | Jak terrain určuje biotop? | Vrstva 1 |
| 3. Biotopy + Ekotony | Jaké biotopy existují a kde? | Vrstva 2 |
| 4. Populace org. | Co a v jakém množství žije v krajině? | Vrstva 3 |
| 5. Primární zdroje | Co je dostupné k lovu a sběru? | Vrstva 4 |
| 6. Uchované zdroje | Co skupina uchovala pro zimu? | Vrstva 5 + Technologie |
| 7. Dostupné zdroje | Co skupina reálně získá? | Vrstva 6 + kompetice |
| 8. Přežití skupiny | Pokrývá kombinace zdrojů potřeby? | Vrstva 7 + velikost skupiny |
| T. Technologie (průřez) | Jak mění konverze na vrstvách 5–7? | Závisí na vrstvách 3–5 |

---

## 6. Epistemická poctivost a verzování

### 6.1 Míry jistoty

| Úroveň | Definice | Příklad ze Star Carr |
|---|---|---|
| DIRECT | Přímý archeologický nález | Parohy jelena — 90 % fauny |
| INDIRECT | Pyly, etnografie, faunal assemblage | Sezónnost z dentice jelena |
| INFERENCE | Logický závěr z kontextu | Rozšíření biotopu mimo Yorkshire |
| SPECULATION | Hypotéza bez přímé opory | Záměrné vypalování krajiny |

### 6.2 Stav záznamů

Zastaralé informace se nemazí — archivují se se stavem.

| Stav | Popis |
|---|---|
| VALID | Aktuálně přijatý poznatek |
| REVISED | Nahrazen novějším — odkaz na nástupce uložen |
| DISPUTED | Vědecká debata stále otevřená |
| REFUTED | Odmítnutý — důvod a reference uloženy |
| HYPOTHESIS | Pracovní hypotéza, dosud nepotvrzená |

*Příklad revize: Star Carr jako celoroční sídliště [REFUTED] → sezónní podzim/zima [VALID, DIRECT, Milner 2018].*

---

## 7. Prototyp — Mapa Anglie (Fáze 0)

### 7.1 Cíl prototypu

Vizualizovat všechny terrain_subtypes, biotopy a ekotony nad skutečnou geografií Anglie ~6200 BCE. Ověřit konzistenci KB a datového modelu před implementací vyšších vrstev.

### 7.2 Scope

- Zobrazit polygony/linie terénních prvků nad rekonstruovanou Anglií ~6200 BCE
- Každý prvek klikatelný / hoverable → zobrazí název, popis, klíčové atributy
- Barevné kódování dle node typu (terrain / biotope / ecotone)
- Filtr dle sezóny → změní productivity_modifier a vizuální styl

**Mimo scope prototypu:** fauna, flora, simulace skupiny, kalorické modelování.

### 7.3 Geografická data

Rekonstrukce pobřeží Británie ~6200 BCE:
- **GEBCO** — batometrie severního moře; mořské dno -25 až -30 m = rekonstruované pobřeží
- **Shennan et al. (2018)** — izostatická korekce pro Británii ~6200 BCE
- **OS Terrain 50** — digitální model terénu (5 m nebo 50 m rozlišení). PoC používá Copernicus DEM GLO-30 (volně dostupný, 30m rozlišení)
- **BGS Geology** — geologické podklady pro substrate atributy. PoC fáze 0 nepoužívá BGS — terrain_subtype rozlišení je založeno na elevaci a slope z DEM. BGS je plánován pro v2
- **OS Open Rivers** — hydrografická síť

### 7.4 GIS přístup

Přírodní objekty jsou **vektory** (polygony a linie), ne hexagony. Inspirace: Windy.com — vektorová data renderovaná dynamicky přes interaktivní mapu.

Doporučený stack:
- **Leaflet.js** nebo **MapLibre GL** — frontend interaktivní mapa
- **GeoJSON** — formát vektorových dat
- **Python/GDAL pipeline** — převod OS/BGS dat na GeoJSON vrstvy s KB atributy

### 7.5 Mapové vrstvy

| Vrstva | Typ | Zdroj dat |
|---|---|---|
| Rekonstruované pobřeží | polygon | GEBCO + Shennan 2018 |
| Terrain subtypes | polygon | BGS Geology + OS Terrain → placement |
| Biotopy (baseline) | polygon | CAN_HOST traversal nad terrainem |
| Ekotony | linie / polygon | hranice sousedních biotopů |
| Řeky | linie | OS Open Rivers + permanence atribut |

### 7.6 Frontend chování

- **Hover** → tooltip: název, biotop/terrain typ, productivity_class, certainty
- **Klik** → panel: plný popis, všechny atributy, epistemics, can_host hrany
- **Sezónní filtr** → přebarví polygony dle `seasonal_modifiers.productivity_modifier`
- **Certainty filtr** → zobrazí/skryje záznamy dle epistemické jistoty

---

## 8. API Design

### 8.1 Filozofie

API je parametrická knowledge base, nikoliv simulační engine. Klient dostává statická data pro vlastní dynamické modelování.

| Scope | Obsah | Verze |
|---|---|---|
| KB endpointy | Entity, relace, parametry, nutrition | v1 — nyní |
| Geografické endpointy | GeoJSON terrain, biotopové polygony | v2 — prototyp |
| Simulační endpointy | Klient pošle kontext, API vrátí výsledek | v3 — budoucí |

### 8.2 Klíčové endpointy v1

| Endpoint | Popis |
|---|---|
| `GET /entity/{id}` | Detail entity + relace + epistemický kontext |
| `GET /biotope/{id}/can_host` | CAN_HOST hrany biotopu s quality_modifiers |
| `GET /terrain/{subtype}/biotopes` | Biotopy možné na daném terrain_subtype |
| `GET /entity/{id}/ecological_params` | Productivity, seasonal_modifiers, energy_multiplier |
| `GET /biotope/{type}/ecotones` | Ekotony sousedící s biotopem + edge_effect |
| `GET /search?q={query}` | Full-text hledání napříč KB |
| `GET /entities?status={status}` | Filtr dle epistemického stavu |

### 8.3 Technický stack

- **Python (FastAPI)** — REST server
- **SQLite + SpatiaLite** — persistentní úložiště s prostorovými dotazy (offline/agent verze, fáze 5+)
- **Supabase PostGIS** — PoC fáze 0 používá hostovaný PostGIS (viz poc_design_v02.md)
- **NetworkX** — runtime grafová reprezentace pro relační dotazy (fáze 5+)
- **GeoJSON** — formát pro v2 prostorová data (Leaflet, QGIS, Unreal GeoReferencing)
- **Deploy:** lokálně nebo Railway/Fly.io

---

## 9. Postup realizace

| Fáze | Název | Obsah | Stav |
|---|---|---|---|
| 0 | **Prototyp mapy** | GeoJSON vrstvy terrain + biotopy + ekotony; Leaflet frontend | **NEXT** |
| 1 | Ontologie | Finalizace schématu dle v04 + vocabulary v02 | ✓ draft |
| 2 | Seed data — biotopy | Popisy biotopů, CAN_HOST hrany, ekotony | ✓ draft |
| 3 | Seed data — fauna & flora | Klíčové druhy + ekologické vztahy + distribuce | todo |
| 4 | Seed data — technologie | Nástroje, techniky, konverzní koeficienty | todo |
| 5 | Implementace agenta | Python + SQLite/SpatiaLite + NetworkX + tool use loop | todo |
| 6 | API v1 | FastAPI server, KB endpointy | todo |
| 7 | API v2 | GeoJSON vrstvy, geografické endpointy | todo |
| 8 | Webové UI | Frontend + deploy | todo |
| 9 | Iterativní plnění KB | Výzkum, konverzace s agentem, rozšiřování | průběžně |

---

## 10. Soubory projektu

| Soubor | Obsah | Verze |
|---|---|---|
| `mezoliticky_design_plan_v8.md` | Tento dokument | 0.8 |
| `schema_examples_v04.json` | Ukázkové záznamy terrain, biotopy, ekotony | 0.4 |
| `vocabulary_v02.json` | Definice všech enumerací s layer anotacemi | 0.2 |

---

## 11. Klíčové zdroje

### 11.1 Archeologické
- Milner, N. et al. (2018): Star Carr: Life in Britain after the Ice Age. CBA. **[HLAVNÍ REFERENCE]**
- Conneller, C. & Warren, G. (eds.) (2006): Mesolithic Britain and Ireland. Tempus.
- Mithen, S. (1994): The Mesolithic Age. In: Cunliffe (ed.) Oxford Illustrated Prehistory.

### 11.2 Metodologické frameworky
- Kelly, R.L. (2013): The Lifeways of Hunter-Gatherers. Cambridge UP.
- Stephens, D.W. & Krebs, J.R. (1986): Foraging Theory. Princeton UP.
- Forman, R.T.T. & Godron, M. (1986): Landscape Ecology. Wiley. **[edge effect]**
- Mitsch, W.J. & Gosselink, J.G. (2000): Wetlands. Wiley. **[produktivita mokřadů]**
- Vera, F.W.M. (2000): Grazing Ecology and Forest History. CABI. **[palouk/disturbance]**

### 11.3 Paleogeografické a paleoekologické
- Shennan, I. et al. (2018): British Isles Sea Level Changes. Geological Society.
- Weninger, B. et al. (2008): The catastrophic final flooding of Doggerland. Documenta Praehistorica.
- Gaffney, V. et al. (2007): Europe's Lost World: The Rediscovery of Doggerland. CBA.
- GEBCO: https://www.gebco.net

---

## 12. Otevřené otázky

- **Řeky jako terrain:** velké řeky quasi-immutable, malé toky dynamické — finalizovat modelování (STUB v04)
- **Weather modifiers na biotopech:** zmrzlé jezero, suché mokřad — parametrizovat jako weather_modifiers konzistentně s faunou
- **GIS pipeline:** jak převést OS/BGS data na KB GeoJSON — potřeba samostatného pipeline designu
- **Záměrný management krajiny (fire ecology):** přímé doklady v Británii?
- **Domestikace psa:** ranné doklady v severní Evropě, vliv na lovecké strategie
- **Dopad Storegga tsunami:** demografický dopad na mezolitické komunity

---

*Dokument průběžně aktualizován. Překonané sekce označeny a archivovány (viz sekce 6.2).*
