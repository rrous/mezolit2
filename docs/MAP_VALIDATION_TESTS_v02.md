# Mezolit2 — Validační testy krajinného modelu
## MAP_VALIDATION_TESTS_v02.md

*Verze 0.2 | 2026-03-26*
*Status: NÁVRH — před implementací pipeline*
*Změny v0.2: 6 nových testů, opravy konzistence, ověřené datové zdroje, implementační plán.*

> Tento dokument definuje sadu testů pro ověření věrohodnosti a konzistence
> generované krajinné mapy mezolitického osídlení. Testy jsou navrženy jako
> uzly znalostní báze (KB) se stejným epistemickým systémem jako biotopy
> a archeologické nálezy. Parametry testů jsou verzovány a auditovatelné.

---

## 1. Principy

### 1.1 Test jako KB uzel

Každý test je uzel v KB se stejnou strukturou jako ostatní záznamy:
- Parametry mají vlastní `certainty` a `source`
- Změna parametru = nový záznam v `revision_history`
- `status` sleduje vědecký stav testu (VALID / HYPOTHESIS / REVISED)

### 1.2 Typy skórovacích funkcí

| Funkce | Kdy použít | Odvození |
|--------|-----------|----------|
| `BINARY` | Fyzikální zákon — pravda nebo lež | Certainty parametrů: n/a |
| `SIGMOID` | Silná empirická evidence, doložený threshold efekt | Certainty: DIRECT / INDIRECT |
| `LINEAR_DECAY` | Default — threshold je odhad bez empirické opory | Certainty: INFERENCE / SPECULATION |

**Pravidlo:** `score_function` se odvozuje z `certainty` hodnot parametrů.
Pokud se certainty zlepší novým výzkumem, funkce se přepne automaticky.

Sigmoid parametry `center` a `steepness` jsou zatím `null` — doplní se daty.

### 1.3 Universality enum

| Hodnota | Definice |
|---------|----------|
| `GLOBAL` | Platí fyzikálně všude — nezávislé na biologii ani kultuře |
| `TEMPERATE_EUROPE` | Platí pro temperátní ekosystémy Evropy (a analogické zóny světa) |
| `MESOLITHIC_EUROPE` | Doloženo z mezolitických lokalit v Evropě |
| `CZECH_BASIN` | Regionálně specifické pro Českou kotlinu |

### 1.4 Vztah testů k datovým zdrojům

`required_data` slouží pro **konfiguraci a audit**, ne pro runtime provádění testu.
Pipeline zkontroluje dostupnost dat před spuštěním testu a přeskočí testy
s chybějícími daty — výsledek je `SKIPPED`, ne `FAIL`.

### 1.5 Sdílené parametry (NOVÉ v v0.2)

Parametry používané více testy jsou definovány jednou a referencovány ID.
Změna sdíleného parametru se propaguje do všech testů, které ho používají.

| ID | Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----|----------|---------|----------|-----------|-------|
| `SP-01` | `catchment_radius_km` | 15 | km | INFERENCE | Binford 2001 — průměrný denní dosah lovecko-sběračské skupiny |

Používán v: T-ECO-03, T-ECO-10, T-ARCH-01.

### 1.6 Závislosti mezi testy (NOVÉ v v0.2)

Některé testy mají explicitní závislost — `depends_on` říká, že test
nemá smysl spouštět bez výsledku jiného testu. Pipeline respektuje
závislosti a přeskočí závislý test pokud prerequisita nebyla splněna.

---

## 2. Schema testu (referenční)

```
TEST_NODE {
  id:            string           -- unikátní identifikátor
  name:          string           -- lidsky čitelný název
  category:      PHY|ECO|ARCH|GEO
  universality:  GLOBAL|TEMPERATE_EUROPE|MESOLITHIC_EUROPE|CZECH_BASIN
  type:          BINARY|SCORING
  score_function: BINARY|SIGMOID|LINEAR_DECAY
  depends_on:    [string] | null  -- NOVÉ v v0.2: ID testů, na které závisí
  preconditions: object | null    -- NOVÉ v v0.2: podmínky pro spuštění
  
  parameters: {
    [name]: {
      value:     number | null    -- null = TODO, doplnit daty
      unit:      string
      certainty: DIRECT|INDIRECT|INFERENCE|SPECULATION
      source:    string           -- citace nebo "TODO"
      shared_param_id: string | null  -- odkaz na sdílený parametr
      revision_history: [
        { date, value, certainty, source, reason }
      ]
    }
  }
  
  required_data: [string]         -- pro konfiguraci/audit pipeline
  
  epistemics: {
    certainty: DIRECT|INDIRECT|INFERENCE|SPECULATION
    status:    VALID|HYPOTHESIS|REVISED|DISPUTED|REFUTED
    notes:     string
  }
}
```

---

## 3. Testy — kategorie PHY (Fyzikální)

*Binární testy platné globálně. Fail = chyba v datech nebo jejich zpracování.*

---

### T-PHY-01: Říční spád
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Každý říční segment musí mít výškový gradient ≥ 0 ve směru toku
(od zdroje k ústí). Tolerance ±0.5m pro chyby DEM v deltách a estuárech.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `elevation_tolerance` | 0.5 | m | DIRECT | Fyzikální zákon; tolerance pro DEM chybu GLO-30 |

**Required data:** DEM (Copernicus GLO-30 / ČÚZK DMR 5G), říční síť (DIBAVOD)

**Interpretace:** FAIL = segment kde downstream bod je výše než upstream.
Signalizuje chybu v DEM klasifikaci nebo v digitalizaci říční sítě.

**Epistemics:** certainty: DIRECT | status: VALID

---

### T-PHY-02: Mokřad v depresi
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Mokřadní biotopy (VMB kódy M*, R*, T*, V*) nesmí ležet na lokálním
výškovém maximu. Střed polygonu biotopu nesmí být výše než průměrná
elevace okolí v definovaném poloměru o více než stanovený práh.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `radius_m` | 500 | m | INFERENCE | Typická velikost mokřadního polygonu VMB |
| `elevation_excess_max` | 5 | m | INFERENCE | Konzervativní práh pro DEM šum |

**Required data:** DEM, AOPK VMB

**Interpretace:** FAIL = mokřad na topografickém hřebeni nebo plošině.
Pravděpodobná chyba mapování biotopů nebo DEM artefakt.

**Epistemics:** certainty: DIRECT | status: VALID

---

### T-PHY-03: Jezero bez povodí
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Každé jezero nebo větší vodní plocha musí mít definovatelné povodí
(catchment area) — uzavřený terénní útvar, ze kterého voda přitéká.
Jezero bez povodí je topografická anomálie.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_catchment_area_km2` | 0.1 | km² | INFERENCE | Minimální hydrologicky smysluplné povodí |
| `lake_min_area_ha` | 1 | ha | INFERENCE | Threshold velikosti vodní plochy pro test |

**Required data:** DEM (flow accumulation), DIBAVOD vodní plochy

**Interpretace:** FAIL = vodní plocha bez identifikovatelného povodí.
Může signalizovat izolovanou depresi (krasový závrt — legitimní výjimka),
nebo chybu v DEM.

**Epistemics:** certainty: INDIRECT | status: VALID
*Poznámka: Krasové závrty jsou legitimní výjimka — filtrovatelné přes ČGS geologická data.*

---

### T-PHY-04: Říční síť a geologický substrát — konzistence
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Velké trvalé toky nesmí procházet vysoce propustným substrátem
(kras, chalk, čistý písek) bez povrchového toku v realitě.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `high_permeability_substrates` | ["karst", "chalk", "clean_sand"] | — | INDIRECT | Hydrogeologická literatura |

*OPRAVA v0.2: Konzistentní anglické klíče, shodné s vocabulary_v02.json konvencí.*

**Required data:** DIBAVOD říční síť, ČGS geologická mapa 1:50 000

**Interpretace:** FAIL = velký trvalý tok na krasovém substrátu bez
hydrogeologického zdůvodnění (podzemní tok).

**Epistemics:** certainty: INDIRECT | status: HYPOTHESIS
*Poznámka: Třeboňsko = pískovce, ne kras — nízké riziko false positive.*

---

### T-PHY-05: Biotopová hranice a terén — skok
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Hranice biotopu nesmí procházet středem homogenního terénního
polygonu bez terénního důvodu (sklon, hydrologie, substrát).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_terrain_change_pct` | 15 | % | SPECULATION | Expertní odhad — **PRIORITNÍ KANDIDÁT pro kalibraci** |
| `homogeneity_radius_m` | 300 | m | SPECULATION | Expertní odhad — **PRIORITNÍ KANDIDÁT pro kalibraci** |

*POZNÁMKA v0.2: Oba parametry jsou SPECULATION bez jakékoli opory.
Tento test je prvním kandidátem pro kalibraci jakmile budou reálná data.
Výsledky interpretovat velmi opatrně.*

**Required data:** DEM, AOPK VMB, ČGS geologie

**Interpretace:** FAIL = biotopová hranice bez korespondující terénní
změny v okolí. Signalizuje buď chybu mapování, nebo chybějící
terénní vrstvu (geologická hranice, která není v DEM viditelná).

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-PHY-06: Sklon vs. mokřadní biotopy (NOVÝ v v0.2)
**Universality:** GLOBAL | **Type:** BINARY | **Score function:** BINARY

Mokřadní biotopy (VMB kódy M*, R*, T*, V*) nesmí ležet na svazích
se sklonem > 5°. Vocabulary_v02 definuje slope kategorie — mokřady
vyžadují `flat` nebo `very_low` (≤ 2°). Tolerance do 5° pro DEM
artefakty a okrajové pixely.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `max_slope_degrees` | 5 | ° | DIRECT | Fyzika — voda se nezdržuje na strmém svahu |
| `slope_percentile` | 90 | % | INFERENCE | 90. percentil sklonu v polygonu (filtr okrajových pixelů) |

**Required data:** DEM (slope raster), AOPK VMB

**Interpretace:** FAIL = mokřad na strmém svahu. Buď chyba VMB mapování,
nebo DEM artefakt. Doplňuje T-PHY-02 (ten testuje elevaci, tento sklon).

**Epistemics:** certainty: DIRECT | status: VALID

---

### T-PHY-07: Elevace paleojezera vs. publikované hladiny (NOVÝ v v0.2)
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Pro známá paleojezera (Švarcenberk, Lake Flixton) musí modelovaná
elevace vodní hladiny odpovídat publikovaným paleohydrologickým datům
v rámci chyby DEM.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `flixton_level_m_aod` | 24 | m | INDIRECT | Taylor & Alison 2018 |
| `svarcenberk_level_m_asl` | null | m | — | TODO — Pokorný et al. 2010 |
| `dem_error_margin_m` | 3 | m | DIRECT | GLO-30 vertical accuracy ~2-4m |

**Required data:** DEM, publikované paleohladiny

**Interpretace:** Odchylka DEM od publikované hladiny > dem_error_margin_m
signalizuje buď špatnou identifikaci jezerní pánve v DEM, nebo potřebu
korekce. Toto je nejsilnější anchor validace — pokud DEM umístí jezero
na špatnou elevaci, vše downstream je špatně.

**Epistemics:** certainty: INDIRECT | status: VALID

---

## 4. Testy — kategorie ECO (Ekologické / Etologické)

*Testy konzistence ekologických vztahů. Mix BINARY a SCORING.*

---

### T-ECO-01: Dostupnost vody z mezolitické lokality
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY
*(→ SIGMOID pokud certainty parametrů dosáhne INDIRECT)*

*OPRAVA v0.2: Universality změněna z GLOBAL na TEMPERATE_EUROPE.
Kelly 2013 zahrnuje celosvětový vzorek včetně aridních oblastí kde
jsou vzdálenosti k vodě výrazně větší. Pro temperátní Evropu je
500m threshold specifičtější.*

Mezolitické lokality preferují polohy v blízkosti stálého vodního zdroje.
Voda = absolutní fyziologická potřeba (3 dny bez vody = smrt).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `threshold_m` | 500 | m | INFERENCE | Kelly 2013 — medián vzdálenosti k vodě, celosvětový vzorek; pro temperátní Evropu pravděpodobně konzervativní |
| `sigmoid_center_m` | null | m | — | TODO — doplnit daty |
| `sigmoid_steepness` | null | — | — | TODO — doplnit daty |

**Skóre:**
- score = 1.0 pokud vzdálenost ≤ threshold_m
- score lineárně klesá k 0.0 na 2× threshold_m
- Populační test: Mann-Whitney U porovnání nálezů vs. náhodné body (p < 0.05)

**Required data:** AMČR souřadnice lokalit, DIBAVOD trvalé toky + vodní plochy

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ECO-02: Ekotonová poloha lokality
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Mezolitické lokality preferují rozhraní biotopů (ekotony). Ekoton
= vyšší druhová diverzita, přístup k více typům zdrojů z jednoho místa.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `ecotone_buffer_m` | 200 | m | INFERENCE | Star Carr literatura — tábor přesně na rozhraní les/mokřad; Binford 2001 |
| `min_ecotone_score` | 2.0 | — | INFERENCE | Nálezy by měly být 2× častěji u ekotonů než náhodné body |
| `sigmoid_center_m` | null | m | — | TODO |
| `sigmoid_steepness` | null | — | — | TODO |

**Skóre:**
- Ratio: (% nálezů do ecotone_buffer_m od hranice biotopu) / (% náhodných bodů)
- score = ratio / min_ecotone_score, cap na 1.0

**Required data:** AMČR souřadnice, AOPK VMB biotopové polygony

**Epistemics:** certainty: INDIRECT | status: VALID
*Poznámka: Test je citlivý na granularitu VMB. Mikrobiotopy (<1 ha) nejsou v VMB zachyceny
(potvrzeno: AOPK uvádí že „efemérní biotopy tak může pominout").*

---

### T-ECO-03: Habitat jelena — přítomnost v catchmentu
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Pokud je na lokalitě doložena jelení fauna, musí být v denním
catchmentu dostatek habitatu jelena lesního — kombinace
lesa a otevřených ploch (ekotony les↔palouk).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj | Sdílený |
|----------|---------|----------|-----------|-------|---------|
| `catchment_radius_km` | 15 | km | INFERENCE | Binford 2001 | **SP-01** |
| `min_forest_cover_pct` | 30 | % | SPECULATION | Expertní odhad — **TODO ověřit ekologickou literaturou** (Jedrzejewska et al. 1997?) |
| `min_edge_density_m_per_km2` | null | m/km² | — | TODO — doplnit z ekologické literatury |

*POZNÁMKA v0.2: min_forest_cover_pct je SPECULATION, ne INFERENCE — opravena certainty.*

**Required data:** AMČR (lokality s jelení faunou), AOPK VMB lesní biotopy

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS
*Poznámka: VMB zachycuje dnešní biotopy. Proxy pro mezolit — INFERENCE.*

---

### T-ECO-04: Populační hustota jelena a produktivita biotopu
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Modelovaná produktivita biotopu musí být konzistentní s ekologicky
odůvodněnou minimální hustotou jelení populace nutnou pro udržitelný lov.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_deer_density_km2` | 2.0 | jedinci/km² | INFERENCE | Moderní analogie — Skandinávie, boreální les (Cederlund & Sand 1994) |
| `kcal_per_deer_year` | null | kcal | — | TODO — doplnit z faunální literatury |
| `hunting_efficiency` | null | — | — | TODO — experimentální archeologie |

**Required data:** KB biotopové produktivity, faunální literatura (vrstva 4 KB)

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS
*Poznámka: Závisí na vrstvě 4 KB (populace organismů) — zatím neexistuje.*

---

### T-ECO-05: Rybí habitat — konzistence s vodním biotopem
**Universality:** TEMPERATE_EUROPE | **Type:** BINARY | **Score function:** BINARY

Pokud je na lokalitě doložena rybí fauna (zejm. severní Čechy — Divišová
et al. 2021), musí být v blízkosti odpovídající vodní biotop (jezero,
řeka, mokřad) s dostatečnou průtočností nebo plochou.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `max_water_distance_m` | 300 | m | INFERENCE | Analogie se Star Carr — platforma u jezera |
| `min_water_area_ha` | 5 | ha | INFERENCE | Minimální plocha pro udržitelný rybolov skupiny |

**Required data:** AMČR (lokality s rybí faunou), DIBAVOD vodní plochy a toky

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ECO-06: Sezónní dostupnost ořechů — líska v dosahu
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Líska (Corylus avellana) = klíčový tukový zdroj na podzim (~60% tuku).
Pokud je na lokalitě doložen sběr ořechů (zuhelnatělé skořápky),
musí VMB obsahovat odpovídající biotopy v dosahu (lesy s lískou,
okraje lesa, ekotony).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `hazel_catchment_radius_m` | 5000 | m | INFERENCE | Pěší sběr ořechů — denní vzdálenost pro sběrnou výpravu |
| `min_hazel_habitat_pct` | 10 | % | SPECULATION | Expertní odhad — TODO ověřit botanickou literaturou |

**Required data:** AMČR (lokality s doloženou lískou), AOPK VMB (L* lesy)

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ECO-07: Kontinuita říčního koridoru
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Říční koridory fungují jako „dálnice" — propojují různé biotopy a
umožňují pohyb skupin i zvěře. Říční lužní les (bt_007 nebo VMB L2*)
by měl kontinuálně lemovat hlavní toky v modelovaném území.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `corridor_width_m` | 100 | m | INFERENCE | Ekologická literatura — minimální šířka funkčního koridoru |
| `max_gap_m` | 500 | m | INFERENCE | Maximální přerušení koridoru pro zachování funkce |
| `min_continuity_pct` | 70 | % | SPECULATION | Expertní odhad — TODO |

**Required data:** DIBAVOD říční síť, AOPK VMB lužní biotopy

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ECO-08: Přirozená zonace vegetace s nadmořskou výškou
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** SIGMOID

*OPRAVA v0.2: Score function změněna z LINEAR_DECAY na SIGMOID.
Oba klíčové parametry (lowland_max, montane_min) mají certainty INDIRECT
→ dle pravidla §1.2 se použije SIGMOID.*

Vegetační pásma musí odpovídat očekávané zonaci s nadmořskou výškou:
lužní lesy v nivách, listnaté lesy ve středních polohách, jehličnaté
a horské biotopy ve vyšších polohách.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `lowland_max_elevation_m` | 300 | m | INDIRECT | Fytogeografická literatura pro ČR |
| `montane_min_elevation_m` | 600 | m | INDIRECT | Fytogeografická literatura pro ČR |
| `tolerance_pct` | 20 | % | INFERENCE | Lokální variabilita (inverzní polohy, skalní výchozy) |
| `sigmoid_center_m` | null | m | — | TODO |
| `sigmoid_steepness` | null | — | — | TODO |

**Required data:** DEM, AOPK VMB

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ECO-09: Bobří habitat — výskyt biotopu
**Universality:** TEMPERATE_EUROPE | **Type:** BINARY | **Score function:** BINARY

Bobr (Castor fiber) = ecosystem engineer, mezoliticky doložen v ČR.
Bobří habitat vyžaduje pomalu tekoucí nebo stojaté vody s lužními
dřevinami (vrba, topol, olše) v bezprostřední blízkosti.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `max_stream_gradient_pct` | 2 | % | INDIRECT | Ekologická literatura — bobr neosidluje rychlé toky |
| `riparian_buffer_m` | 50 | m | INDIRECT | Ekologická literatura — zóna lužní vegetace |

**Required data:** DIBAVOD toky (+ spád z DEM), AOPK VMB lužní biotopy

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ECO-10: Tukový problém — sezónní kritičnost
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Na jaře/v létě (Star Carr sezóna) jsou jeleni nejlibovější — riziko
protein poisoning. Model musí mít v denním catchmentu lokality
alespoň jeden alternativní tučný zdroj (ryby, líska, bobr, los/pratur).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj | Sdílený |
|----------|---------|----------|-----------|-------|---------|
| `fat_source_catchment_km` | 15 | km | INFERENCE | Binford 2001 | **SP-01** |
| `min_fat_source_types` | 2 | počet | SPECULATION | Expertní odhad — TODO ověřit nutritivní literaturou |
| `spring_summer_only` | true | — | DIRECT | Tukový problém specifický pro jaro/léto |

**Required data:** KB aktivity (ACTIVITY_GRAPH) — závisí na vrstvě 4-5 KB

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS
*Poznámka: Závisí na ACTIVITY_GRAPH_v01 — plně implementovatelný až po doplnění vrstev 4-5.*

---

### T-ECO-11: Celoroční pokrytí zdroji — sezónní cyklus (NOVÝ v v0.2)
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Každá sezóna v ročním cyklu musí mít v denním catchmentu alespoň
jeden viabilní zdroj proteinů, tuků a sacharidů. T-ECO-10 testuje
jen jarní/letní tukový deficit — tento test kontroluje VŠECHNY sezónní
mezery. Zimní kalorický deficit je stejně smrtelný jako jarní tukový.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj | Sdílený |
|----------|---------|----------|-----------|-------|---------|
| `catchment_radius_km` | 15 | km | INFERENCE | Binford 2001 | **SP-01** |
| `required_macronutrients` | ["protein", "fat", "carbohydrate"] | — | DIRECT | Fyziologie — Cordain et al. 2000 |
| `seasons` | ["SPRING", "SUMMER", "AUTUMN", "WINTER"] | — | DIRECT | — |
| `min_sources_per_macronutrient` | 1 | počet | INFERENCE | Minimální redundance pro přežití |
| `score_per_missing_season` | 0.25 | — | SPECULATION | Lineární penalizace per sezóna bez pokrytí |

**Required data:** KB aktivity (ACTIVITY_GRAPH) + RESOURCE nutriční data (vrstva 4-5 KB)

**Interpretace:** score = 1.0 - (počet_sezón_bez_pokrytí × score_per_missing_season).
Sezóna je "bez pokrytí" pokud chybí alespoň jeden macronutrient v catchmentu.
Zimní pokrytí může záviset na podzimním skladování (ořechy) — test potřebuje
propojení na ACTIVITY_GRAPH storage model.

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS
*Poznámka: Plně implementovatelný až po ACTIVITY_GRAPH + vrstvách 4-5.*

---

### T-ECO-12: Ekoton — existence na hranicích biotopů (NOVÝ v v0.2)
**Universality:** TEMPERATE_EUROPE | **Type:** BINARY | **Score function:** BINARY

Kde dva různé VMB biotopové polygony sdílejí hranici, měl by model
obsahovat ekoton. Naopak — modelované ekotony musí odpovídat reálným
biotopovým hranicím. Žádné "ghost ecotones" v homogenním terénu.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_boundary_length_m` | 100 | m | INFERENCE | Minimální délka hranice pro funkční ekoton |
| `biotope_type_difference` | true | — | DIRECT | Ekoton vyžaduje DVA různé biotopy |

**Required data:** AOPK VMB biotopové polygony, KB ekotony

**Interpretace:** FAIL pokud:
(a) KB ekoton neodpovídá žádné reálné VMB hranici, nebo
(b) Významná VMB hranice (>100m) nemá odpovídající KB ekoton.
Testuje konzistenci mezi KB ekotonovou vrstvou a reálným biotopovým mapováním.

**Epistemics:** certainty: INDIRECT | status: VALID

---

## 5. Testy — kategorie ARCH (Archeologické vzory)

*Testy konzistence s mezolitickými sídelními vzory.*

---

### T-ARCH-01: Catchment úplnost — kritické zdroje
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

V denním catchmentu každé lokality musí být zastoupeny
všechny kritické zdroje: voda, protein, tuk, surovina pro nástroje.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj | Sdílený |
|----------|---------|----------|-----------|-------|---------|
| `catchment_radius_km` | 15 | km | INFERENCE | Binford 2001 | **SP-01** |
| `required_resource_types` | ["water", "protein", "fat", "raw_material"] | — | INFERENCE | Yo-yo analýza + fyziologické potřeby (METHODOLOGY_GUIDE_v03) |
| `score_per_missing_resource` | 0.25 | — | SPECULATION | Lineární penalizace za chybějící zdroj |

**Required data:** AMČR, DIBAVOD, AOPK VMB, ČGS suroviny

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ARCH-02: Surovinový dosah — kamenná industrie
**Universality:** CZECH_BASIN | **Type:** SCORING | **Score function:** LINEAR_DECAY

Pro každou mezolitickou lokalitu v České kotlině musí být v dosahu
alespoň jeden zdroj štípatelné suroviny (rohovec, křemen, radiolarit).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `primary_threshold_km` | 30 | km | INDIRECT | Šída & Prostředník 2014 — transport surovin z Českého ráje |
| `extended_threshold_km` | 80 | km | INFERENCE | Horní limit pro mezolitický transport (bez dokladu pro ČR) |
| `sigmoid_center_km` | null | km | — | TODO |
| `sigmoid_steepness` | null | — | — | TODO |

**Required data:** AMČR souřadnice, ČGS WFS ložiska surovin
(`https://mapy.geology.cz/arcgis/services/Suroviny/loziska_zdroje/MapServer/WFSServer`)

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ARCH-03: Výhledová poloha tábořiště
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

*OPRAVA v0.2: Přidána precondition. Test se spouští POUZE pro lokality
v otevřené krajině (VMB pokryv lesa < 50% v buffer 1km). V hustě zalesněné
mezolitické krajině je viewshed neplatný — les blokuje výhled.*

Primární tábořiště v otevřené krajině preferují polohy s dobrým výhledem
na okolí — bezpečnost, pozorování zvěře.

**Preconditions:**
```json
{
  "applicable_only_if": "forest_cover_pct_1km < 50",
  "skip_reason": "Viewshed neplatný v hustě zalesněné krajině"
}
```

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `viewshed_radius_km` | 5 | km | INFERENCE | Praktický výhled v otevřené krajině |
| `min_viewshed_ratio` | 1.5 | — | SPECULATION | TODO — ověřit na evropských mezolitických lokalitách |
| `forest_cover_threshold_pct` | 50 | % | INFERENCE | Precondition — pod 50% les viewshed má smysl |

**Required data:** DEM, AMČR souřadnice, AOPK VMB (lesní pokryv)

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ARCH-04: Nadmořská výška lokalit — distribuce
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Mezolitické lokality preferují nižší polohy (niva, jezerní pánev,
říční terasa). Distribuce nadmořských výšek nálezů by měla být
statisticky odlišná od distribuce celého modelovaného území.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `preferred_elevation_max_m` | 400 | m | INDIRECT | Agregát evropských mezolitických lokalit — většina pod 400m |
| `statistical_test` | "Mann-Whitney-U" | — | DIRECT | Standardní neparametrický test |
| `significance_threshold` | 0.05 | p-value | DIRECT | Konvenční vědecký standard |

**Required data:** DEM, AMČR souřadnice

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-ARCH-05: Sezonalita — biotop odpovídá doložené sezóně
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Pokud má lokalita doloženou sezónu (Star Carr = jaro/léto), musí
modelovaný biotop v dané sezóně poskytovat odpovídající zdroje.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_seasonal_productivity` | 0.3 | [0-1 quality] | SPECULATION | Minimální sezónní produktivita biotopů v okolí — TODO |

**Required data:** AMČR (sezónní data), KB sezónní modifikátory biotopů

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ARCH-06: Hustota lokalit vs. produktivita krajiny
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

*OPRAVA v0.2: Explicitní závislost na T-ARCH-07 (detekční bias).
Bez korekce na výzkumnou intenzitu je korelace hustota↔produktivita
nesmyslná.*

**Depends_on:** `["T-ARCH-07"]`

Hustota mezolitických lokalit v oblasti by měla korelovat s modelovanou
produktivitou krajiny — PO KOREKCI na výzkumnou intenzitu (T-ARCH-07).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `correlation_min` | 0.3 | Pearson r | SPECULATION | Minimální korelace — TODO ověřit |
| `grid_cell_km` | 10 | km | INFERENCE | Granularita analýzy |

**Required data:** AMČR hustota lokalit (korigovaná T-ARCH-07), KB produktivity biotopů

**Epistemics:** certainty: SPECULATION | status: HYPOTHESIS
*Upozornění: KB produktivita je fabricated (viz AUDIT §2). Test bude mít
nízkou hodnotu dokud nebudou reálné produktivity.*

---

### T-ARCH-07: Detekční bias — korekce výzkumné intenzity
**Universality:** CZECH_BASIN | **Type:** SCORING | **Score function:** LINEAR_DECAY

Oblasti s vyšší výzkumnou intenzitou (více provedených výzkumů v AMČR)
by měly mít proporcionálně více nálezů. Test identifikuje oblasti
kde absence nálezů je pravděpodobně artefakt nedostatku výzkumu.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `research_intensity_proxy` | "pocet_akci_amcr" | — | INFERENCE | AMČR počet akcí na grid buňku jako proxy |
| `grid_cell_km` | 10 | km | INFERENCE | Granularita analýzy |
| `min_actions_for_valid_absence` | 5 | počet | SPECULATION | Minimální počet akcí pro "důvěryhodnou absenci" — TODO |

**Required data:** AMČR (počet akcí per oblast), AMČR mezolitické lokality

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-ARCH-08: Proxy populace — paleopatologická konzistence
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Pokud model zahrnuje zdravotní vrstvu, musí být konzistentní s
proxy populacemi (Zvejnieki, Iron Gates, Skateholm).

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `freshwater_protein_min_pct` | 30 | % | INDIRECT | Drucker et al. 2016, Noyen-sur-Seine — izotopy |
| `proxy_population` | "Zvejnieki" | — | INFERENCE | Nejbližší geograficky relevantní proxy pro ČR |

**Required data:** KB vrstvy 4-5 (zatím neexistují), izotopová literatura

**Epistemics:** certainty: INDIRECT | status: HYPOTHESIS
*Poznámka: Plně implementovatelný až po doplnění vrstev 4-5 KB.*

---

### T-ARCH-09: Prostorové shlukování lokalit (NOVÝ v v0.2)
**Universality:** MESOLITHIC_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

**Depends_on:** `["T-ARCH-07"]` (korekce na výzkumnou intenzitu)

Mezolitické lokality by měly vykazovat statisticky signifikantní
shlukování (Ripley's K nebo nearest-neighbor analýza) oproti náhodné
distribuci. Shlukování kolem produktivních ekotonů a vodních zdrojů
je očekávané. Náhodná distribuce signalizuje buď datový problém,
nebo špatný krajinný model.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `statistical_test` | "Ripleys_K" | — | DIRECT | Standardní test prostorové autokorelace |
| `significance_threshold` | 0.05 | p-value | DIRECT | Konvenční standard |
| `distance_bands_m` | [500, 1000, 2000, 5000, 10000] | m | INFERENCE | Multi-scale analýza |

**Required data:** AMČR souřadnice (korigované T-ARCH-07)

**Interpretace:** Signifikantní shlukování na vzdálenosti 500-2000m →
lokality se koncentrují kolem produktivních míst (jezera, řeky, ekotony).
Absence shlukování → buď málo dat, nebo model nepředpovídá preference správně.

**Epistemics:** certainty: INDIRECT | status: HYPOTHESIS

---

## 6. Testy — kategorie GEO (Geologické / Surovinové)

---

### T-GEO-01: Geologická mapa vs. terénní klasifikace
**Universality:** GLOBAL | **Type:** SCORING | **Score function:** LINEAR_DECAY

Terrain subtypes (tst_*) musí odpovídat geologické mapě ČGS.
Confusion matrix: DEM-derived klasifikace vs. ČGS 1:50 000.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `min_agreement_pct` | 70 | % | INFERENCE | Přijatelná shoda pro 30m DEM vs. 1:50 000 geologická mapa |
| `critical_substrates` | ["chalk", "limestone", "peat"] | — | DIRECT | Substráty s nejvyšším dopadem na biotopy |

**Required data:** KB terrain polygony, ČGS WMS/WFS geologická mapa 1:50 000

**Epistemics:** certainty: INFERENCE | status: HYPOTHESIS

---

### T-GEO-02: Flint / rohovec — dostupnost v substrátu
**Universality:** CZECH_BASIN | **Type:** BINARY | **Score function:** BINARY

Pokud terrain_subtype nemá flint_availability=NONE v KB vocabuláři,
musí ČGS geologická mapa v daném místě obsahovat odpovídající
geologický útvar (křída, rohovec-bearing sedimenty).

**Parametry:**

*(test je binární — žádné skórovací parametry)*

**Required data:** KB vocabulary (flint_availability), ČGS geologická mapa,
ČGS WFS ložiska surovin

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-GEO-03: Hydrologie substrátu — konzistence s VMB
**Universality:** GLOBAL | **Type:** SCORING | **Score function:** LINEAR_DECAY

Hydrologický režim terrain_subtype (vocabulary: hydrology) musí být
konzistentní s biotopy na něm modelovanými přes CAN_HOST hrany.
Propustný substrát (chalk, limestone) nemůže hostit trvalé mokřady
bez hydrogeologického zdůvodnění.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `permeability_wetland_conflict` | ["chalk_rendzina", "limestone_thin_soil"] | — | DIRECT | Hydrogeologická literatura |
| `tolerance_pct` | 5 | % | INFERENCE | Lokální výjimky (závrtové mokřady v krasu) |

**Required data:** KB terrain subtypes, AOPK VMB, ČGS geologie

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-GEO-04: Kvartérní sedimenty v jezerních pánvích
**Universality:** TEMPERATE_EUROPE | **Type:** SCORING | **Score function:** LINEAR_DECAY

Jezerní pánve (tst_001 nebo analogie) musí ležet na kvartérních
sedimentech (glaciální, fluvioglaciální, nebo organické) dle ČGS.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `quaternary_substrates` | ["glacial_till", "organic_lacustrine", "alluvial"] | — | DIRECT | Kvartérní geologie |
| `min_coverage_pct` | 80 | % | INFERENCE | Tolerance pro hraniční polygony |

**Required data:** KB terrain polygony (tst_001), ČGS kvartérní mapa

**Epistemics:** certainty: INDIRECT | status: VALID

---

### T-GEO-05: DEM přesnost v kontrolních bodech (NOVÝ v v0.2)
**Universality:** GLOBAL | **Type:** SCORING | **Score function:** LINEAR_DECAY

Porovnání DEM elevace v známých geodetických/archeologických kontrolních
bodech proti publikovaným hodnotám. Každý jiný test předpokládá, že DEM
je správný — tento test validuje samotný základ.

**Parametry:**

| Parametr | Hodnota | Jednotka | Certainty | Zdroj |
|----------|---------|----------|-----------|-------|
| `max_deviation_m` | 3 | m | DIRECT | GLO-30 specifikace vertikální přesnosti |
| `control_points` | [] | — | — | TODO — doplnit z ČÚZK geodetických bodů + publikovaných hodnot |

**Required data:** DEM, geodetické kontrolní body (ČÚZK), publikované archeologické elevace

**Interpretace:** Průměrná odchylka > max_deviation_m signalizuje systematický
bias v DEM, který se propaguje do VŠECH dalších testů. Prioritní diagnostika.

**Epistemics:** certainty: DIRECT | status: VALID

---

## 7. Přehledová tabulka všech testů

| ID | Název | Kat. | Universality | Type | Score fn | Status | Depends on | Fáze |
|----|-------|------|-------------|------|----------|--------|------------|------|
| T-PHY-01 | Říční spád | PHY | GLOBAL | BINARY | BINARY | VALID | — | 1 |
| T-PHY-02 | Mokřad v depresi | PHY | GLOBAL | BINARY | BINARY | VALID | — | 1 |
| T-PHY-03 | Jezero bez povodí | PHY | GLOBAL | BINARY | BINARY | VALID | — | 1 |
| T-PHY-04 | Říční síť vs. substrát | PHY | GLOBAL | BINARY | BINARY | HYPOTHESIS | — | 1 |
| T-PHY-05 | Biotopová hranice vs. terén | PHY | GLOBAL | BINARY | BINARY | HYPOTHESIS | — | 1 |
| **T-PHY-06** | **Sklon vs. mokřad** | PHY | GLOBAL | BINARY | BINARY | VALID | — | **1** |
| **T-PHY-07** | **Paleojezero elevace** | PHY | TEMP_EU | SCORING | LIN_DECAY | VALID | — | **1** |
| T-ECO-01 | Dostupnost vody | ECO | TEMP_EU* | SCORING | LIN_DECAY | VALID | — | 2 |
| T-ECO-02 | Ekotonová poloha | ECO | TEMP_EU | SCORING | LIN_DECAY | VALID | — | 2 |
| T-ECO-03 | Habitat jelena | ECO | TEMP_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 2 |
| T-ECO-04 | Produktivita vs. jelen | ECO | TEMP_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 3 |
| T-ECO-05 | Rybí habitat | ECO | TEMP_EU | BINARY | BINARY | VALID | — | 2 |
| T-ECO-06 | Líska v dosahu | ECO | TEMP_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 2 |
| T-ECO-07 | Říční koridor | ECO | TEMP_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 1 |
| T-ECO-08 | Vegetační zonace | ECO | TEMP_EU | SCORING | SIGMOID* | VALID | — | 1 |
| T-ECO-09 | Bobří habitat | ECO | TEMP_EU | BINARY | BINARY | VALID | — | 1 |
| T-ECO-10 | Tukový problém | ECO | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 3 |
| **T-ECO-11** | **Celoroční pokrytí** | ECO | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | **3** |
| **T-ECO-12** | **Ekoton existence** | ECO | TEMP_EU | BINARY | BINARY | VALID | — | **1** |
| T-ARCH-01 | Catchment úplnost | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 3 |
| T-ARCH-02 | Surovinový dosah | ARCH | CZ_BASIN | SCORING | LIN_DECAY | VALID | — | 2 |
| T-ARCH-03 | Výhledová poloha | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | precond. | 2 |
| T-ARCH-04 | Nadmořská výška | ARCH | MESO_EU | SCORING | LIN_DECAY | VALID | — | 2 |
| T-ARCH-05 | Biotop vs. sezóna | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 3 |
| T-ARCH-06 | Hustota vs. produktivita | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | **T-ARCH-07** | 2 |
| T-ARCH-07 | Detekční bias | ARCH | CZ_BASIN | SCORING | LIN_DECAY | HYPOTHESIS | — | 2 |
| T-ARCH-08 | Proxy populace | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | — | 3 |
| **T-ARCH-09** | **Shlukování lokalit** | ARCH | MESO_EU | SCORING | LIN_DECAY | HYPOTHESIS | **T-ARCH-07** | **2** |
| T-GEO-01 | Geologie vs. terrain | GEO | GLOBAL | SCORING | LIN_DECAY | HYPOTHESIS | — | 1 |
| T-GEO-02 | Flint vs. geologie | GEO | CZ_BASIN | BINARY | BINARY | VALID | — | 1 |
| T-GEO-03 | Hydrologie vs. VMB | GEO | GLOBAL | SCORING | LIN_DECAY | VALID | — | 1 |
| T-GEO-04 | Kvartér v pánvích | GEO | TEMP_EU | SCORING | LIN_DECAY | VALID | — | 1 |
| **T-GEO-05** | **DEM kontrolní body** | GEO | GLOBAL | SCORING | LIN_DECAY | VALID | — | **1** |

\* Změny v0.2 označeny tučně. TEMP_EU = TEMPERATE_EUROPE, MESO_EU = MESOLITHIC_EUROPE.

**Celkem:** 33 testů | 11 BINARY | 22 SCORING | 15 VALID | 18 HYPOTHESIS
**Nové v v0.2:** T-PHY-06, T-PHY-07, T-ECO-11, T-ECO-12, T-ARCH-09, T-GEO-05

---

## 8. Závislosti mezi testy a KB vrstvami

```
KB vrstva 1-3 (terén, CAN_HOST, biotopy)  →  T-PHY-*, T-ECO-08, T-ECO-12, T-GEO-*
DIBAVOD + DEM (žádné KB vrstvy)           →  T-PHY-01, T-PHY-06, T-PHY-07, T-GEO-05
AMČR prostorová data                       →  T-ECO-01-03,05-06, T-ARCH-01-04,06-07,09
KB vrstva 4-5 (populace, primární zdroje)  →  T-ECO-04, T-ECO-10, T-ECO-11
ACTIVITY_GRAPH                             →  T-ECO-10, T-ECO-11, T-ARCH-01, T-ARCH-05

Test závislosti:
  T-ARCH-06 → T-ARCH-07  (hustota nesmyslná bez korekce na bias)
  T-ARCH-09 → T-ARCH-07  (shlukování nesmyslné bez korekce na bias)
```

---

## 9. Ověřené datové zdroje pro Českou kotlinu

### 9.1 DIBAVOD (hydrologie)
- **URL:** https://www.dibavod.cz/
- **Formát:** ESRI Shapefile (ZIP)
- **Přístup:** Volný, bez registrace
- **Obsah:** Říční síť, vodní plochy, povodí, záplavová území (1:50 000)
- **Souř. systém:** S-JTSK → nutný reprojekce do WGS84
- **Stav:** Neaktualizovaný — statická data. Pro účely projektu dostatečné.

### 9.2 AOPK VMB (biotopové mapování)
- **Download:** https://data.nature.cz/ds/21
- **Open data portál:** https://gis-aopkcr.opendata.arcgis.com/
- **WMS:** `https://gis.nature.cz/arcgis/services/Biotopy/PrirBiotopHabitat/MapServer/WMSServer`
- **Formáty:** Shapefile, KML, GeoJSON, CSV + WMS/WFS
- **Přístup:** CC BY 4.0, bez registrace
- **Obsah:** Biotopové polygony ČR, klasifikace Chytrý. Základní mapování 2001-2005, 12letý aktualizační cyklus.
- **Omezení:** Celostátní měřítko — efemérní a mikro (<1 ha) biotopy chybí. Relevantní pro T-ECO-02.

### 9.3 ČGS (geologie)
- **Portál:** https://cgs.gov.cz/en/maps-and-data
- **Web služby:** https://cgs.gov.cz/en/maps-and-data/web-services
- **Klíčové WMS/WFS:**
  - Geologická mapa 1:500 000 (INSPIRE, volná)
  - Geologická mapa 1:50 000 (kompletní pokrytí ČR)
  - Ložiska surovin WFS: `https://mapy.geology.cz/arcgis/services/Suroviny/loziska_zdroje/MapServer/WFSServer` (pro T-GEO-02)
  - Hydrogeologické mapy
  - Vrty + mocnost kvartéru
- **Přístup:** WMS/WFS volně. Bulk stažení 1:50 000 vektorů může vyžadovat dohodu (data@geology.cz). Open data v GeoJSON přes Národní katalog OD.

### 9.4 AMČR (archeologie)
- **Registrace:** https://amcr.aiscr.cz/accounts/register/ (volná, pro roli "researcher")
- **API:** OAI-PMH v2.2 na `https://api.aiscr.cz/2.2/oai`
- **Dokumentace:** https://arup-cas.github.io/aiscr-api-home/
- **GitHub:** https://github.com/ARUP-CAS
- **Digitální archiv (prohlížení):** https://digiarchiv.aiscr.cz/
- **Přístupové role:**
  - A (anonymous): publikované projekty + sites
  - B (researcher): plný přístup k záznamům, dokumentům, PIANům
  - C (archaeologist): z licencované organizace
  - D (archivist): plný přístup
- **Klíčové sety:** `archeologicky_zaznam:lokalita` (lokality), `pian` (geometrie), `heslo:obdobi` (období pro filtraci mezolitu)
- **Objem:** ~859 000 záznamů celkem
- **Licence:** CC BY-NC 4.0
- **Pozor:** Starší záznamy mají prostorovou přesnost na úrovni katastrálního území (centroid), ne GPS. Slovník `pian_presnost` indikuje kvalitu.

---

## 10. Implementační plán

### Fáze 0: Akvizice dat (prerequisita)

| Zdroj | Akce | Odhadovaný čas |
|-------|------|----------------|
| DIBAVOD | Stáhnout SHP z dibavod.cz, import do PostGIS (ogr2ogr) | 30 min |
| DEM | Copernicus GLO-30 přes OpenTopography API (existující pipeline) nebo ČÚZK DMR 5G | 1-2 hodiny |
| AOPK VMB | Stáhnout SHP z data.nature.cz/ds/21, import do PostGIS | 1 hodina |
| AMČR | Registrace na amcr.aiscr.cz (role B), harvest přes OAI-PMH | 2-4 hodiny |
| ČGS | WMS pro vizuální ověření, WFS query pro Třeboňsko bbox | 1-2 hodiny |

### Fáze 1: Testy bez AMČR (11 testů — DEM + DIBAVOD + VMB + ČGS)

Tyto testy validují terénní základ bez jakýchkoli archeologických dat.

| Test | Data | Komplexita |
|------|------|------------|
| **T-GEO-05** DEM kontrolní body | DEM + publikované hodnoty | Nízká — **spustit první** |
| T-PHY-01 Říční spád | DEM + DIBAVOD | Nízká |
| T-PHY-02 Mokřad v depresi | DEM + VMB | Nízká |
| **T-PHY-06** Sklon vs. mokřad | DEM + VMB | Nízká |
| **T-PHY-07** Paleojezero elevace | DEM + literatura | Nízká |
| T-PHY-04 Říční síť vs. substrát | DIBAVOD + ČGS | Střední |
| T-PHY-05 Biotop vs. terén | DEM + VMB + ČGS | Střední |
| T-ECO-08 Vegetační zonace | DEM + VMB | Střední |
| T-ECO-09 Bobří habitat | DIBAVOD + DEM + VMB | Střední |
| **T-ECO-12** Ekoton existence | VMB + KB ekotony | Střední |
| T-ECO-07 Říční koridor | DIBAVOD + VMB | Střední |
| T-GEO-01 Geologie vs. terrain | KB terrain + ČGS | Střední |
| T-GEO-02 Flint vs. geologie | KB vocab + ČGS WFS | Nízká |
| T-GEO-03 Hydrologie vs. VMB | KB terrain + VMB + ČGS | Střední |
| T-GEO-04 Kvartér v pánvích | KB terrain + ČGS | Střední |

### Fáze 2: Testy s AMČR (10 testů)

Po registraci a harvestu AMČR dat:

| Test | Navíc k fázi 1 |
|------|----------------|
| T-ECO-01 Voda z lokality | + AMČR sites |
| T-ECO-02 Ekotonová poloha | + AMČR sites |
| T-ECO-03 Habitat jelena | + AMČR (jelení fauna) |
| T-ECO-05 Rybí habitat | + AMČR (rybí fauna) |
| T-ECO-06 Líska v dosahu | + AMČR (líska) |
| T-ARCH-02 Surovinový dosah | + AMČR + ČGS minerály |
| T-ARCH-03 Výhledová poloha | + AMČR + DEM + VMB (precondition!) |
| T-ARCH-04 Nadmořská výška | + AMČR sites |
| T-ARCH-07 Detekční bias | + AMČR events |
| **T-ARCH-09** Shlukování | + AMČR sites (po T-ARCH-07) |
| T-ARCH-06 Hustota vs. produk. | + AMČR (po T-ARCH-07) |

### Fáze 3: Testy vyžadující KB vrstvy 4-5 nebo ACTIVITY_GRAPH (7 testů)

Aktivují se postupně jak se staví survival model:

| Test | Závisí na |
|------|-----------|
| T-ECO-04 Produktivita vs. jelen | Vrstva 4 (populace) |
| T-ECO-10 Tukový problém | ACTIVITY_GRAPH + vrstva 4-5 |
| **T-ECO-11** Celoroční pokrytí | ACTIVITY_GRAPH + RESOURCE data |
| T-ARCH-01 Catchment úplnost | ACTIVITY_GRAPH |
| T-ARCH-05 Biotop vs. sezóna | KB sezónní modifikátory |
| T-ARCH-08 Proxy populace | Vrstva 4-5 + izotopová lit. |

### Pipeline architektura (sketch)

```
TestRunner
    │
    ├── check_data_availability(test.required_data)
    │       → SKIP pokud chybí zdroj
    │
    ├── check_dependencies(test.depends_on)
    │       → SKIP pokud prerequisita nesplněna
    │
    ├── check_preconditions(test.preconditions)
    │       → SKIP s důvodem pokud nesplněna
    │
    ├── run_test(test)
    │       → {test_id, score, details, data_version, timestamp}
    │
    └── store_result(supabase)
            → KB uzel s epistemickými metadaty + snapshot parametrů

Výstupy:
    ├── JSON validation report
    ├── Leaflet overlay (PASS/FAIL/SKIP per polygon)
    └── Summary dashboard (per fáze, per kategorie)
```

Každý test = jedna Python funkce v modulu `tests/{category}/{test_id}.py`.
Sdílené parametry v `config/shared_params.json`.
Závislosti řešeny topologickým řazením (DAG).

---

## 11. TODO — parametry k doplnění

| Test | Parametr | Navrhovaný zdroj |
|------|----------|-----------------|
| T-PHY-07 | svarcenberk_level_m_asl | Pokorný et al. 2010 |
| T-ECO-01 | sigmoid_center_m, sigmoid_steepness | Etnografická studie (Kelly 2013 rozšíření) |
| T-ECO-02 | sigmoid_center_m, sigmoid_steepness | Agregát evropských mezolitických lokalit |
| T-ECO-03 | min_edge_density, min_forest_cover_pct | Ekologická literatura — jelen lesní |
| T-ECO-04 | kcal_per_deer_year, hunting_efficiency | Faunální literatura + exp. archeologie |
| T-ECO-06 | min_hazel_habitat_pct | Botanická literatura — Corylus avellana |
| T-ECO-07 | min_continuity_pct | Krajinná ekologie — koridor funkčnost |
| T-ARCH-03 | min_viewshed_ratio | Analýza evropských mezolitických lokalit |
| T-ARCH-06 | correlation_min | Statistická analýza po doplnění KB vrstev |
| T-ARCH-07 | min_actions_for_valid_absence | AMČR statistika výzkumné intenzity |
| T-GEO-05 | control_points | ČÚZK geodetické body + archeologické publikace |

---

## 12. Changelog v0.1 → v0.2

### Nové testy (6)
- T-PHY-06: Sklon vs. mokřadní biotopy — doplňuje T-PHY-02 o test sklonu
- T-PHY-07: Paleojezero elevace — anchor validace DEM přesnosti
- T-ECO-11: Celoroční pokrytí zdroji — rozšíření T-ECO-10 na všechny sezóny
- T-ECO-12: Ekoton existence na VMB hranicích — validace KB ekotonů
- T-ARCH-09: Prostorové shlukování lokalit — Ripley's K analýza
- T-GEO-05: DEM přesnost v kontrolních bodech — validace základu všech testů

### Opravy konzistence (7)
- T-ECO-01: Universality GLOBAL → TEMPERATE_EUROPE (Kelly 2013 je celosvětový, threshold specifický pro temperátní zónu)
- T-ECO-08: Score function LINEAR_DECAY → SIGMOID (oba parametry INDIRECT → pravidlo §1.2)
- T-PHY-04: Parametr language standardizován (anglické klíče, shodné s vocabulary_v02)
- T-PHY-05: Oba SPECULATION parametry explicitně označeny jako prioritní kandidáti pro kalibraci
- T-ECO-03: min_forest_cover_pct certainty opravena na SPECULATION (ne INFERENCE)
- T-ARCH-06: Explicitní depends_on: T-ARCH-07
- T-ARCH-03: Přidána precondition (forest_cover_pct < 50%)

### Strukturální vylepšení
- §1.5: Sdílené parametry (SP-01: catchment_radius_km) — prevence driftu
- §1.6: Explicitní závislosti mezi testy (depends_on)
- §9: Ověřené datové zdroje s přesnými URL (verifikace 2026-03-26)
- §10: Fázovaný implementační plán (Fáze 0-3)
- §12: Changelog

---

*Tento dokument je živý — parametry se doplňují s přibývajícími daty a vědeckou spoluprací.*
*Viz také: METHODOLOGY_GUIDE_v03.md, ACTIVITY_GRAPH_v01.md, vocabulary_v02.json*
