# Mezolit2 — Audit mezer (Fáze 0)
## Systematická analýza: co je podložené, co extrapolované, co vymyšlené

*Verze 0.2 | 2026-03-13*

---

## Obsah

1. [Přehled — tříbarevná mapa důvěryhodnosti](#1-přehled)
2. [Produktivita biotopů — hallucinated values](#2-produktivita-biotopů)
3. [Edge effect faktory — nepodložené](#3-edge-effect-faktory)
4. [Sezónní modifikátory — bez zdroje](#4-sezónní-modifikátory)
5. [Terrain klasifikace — coverage gaps](#5-terrain-klasifikace)
6. [Star Carr extrapolace — co víme vs. co předstíráme](#6-star-carr-extrapolace)
7. [Survival framework — nedotažený cíl](#7-survival-framework)
8. [Propagace nejistot — epistemologický rámec pro matematiky](#8-propagace-nejistot)
9. [Vizuální věrohodnost — geometrie hranic a řek](#9-vizuální-věrohodnost)
10. [Lessons learned](#10-lessons-learned)
11. [Co potřebujeme od vědců](#11-co-potřebujeme-od-vědců)

---

## 1. Přehled

### Tříbarevná mapa důvěryhodnosti

| Barva | Význam | Počet položek |
|-------|--------|---------------|
| **ZELENÁ** — podložené | Přímý nebo nepřímý doklad, citace odpovídá obsahu | ~15 |
| **ORANŽOVÁ** — extrapolované | Logický závěr, ale chybí explicitní metodologie | ~20 |
| **ČERVENÁ** — hallucinated | Hodnota nemá oporu ve zdroji, který cituje | ~25 |

### Zelené (podložené)
- Star Carr jako primární tábor — DIRECT (Clark 1954, Milner 2018)
- Lake Flixton polygon — INDIRECT (ADS, Palmer 2015, 234 vertexů)
- Lake Flixton hladina ~24m aOD — INDIRECT (Taylor & Alison 2018)
- 20 archeologických lokalit — DIRECT (ADS postglacial_2013)
- Boreální les jako dominantní vegetace — INDIRECT (pylové profily, Simmons 1996)
- Mořská hladina -25m — INDIRECT (Shennan 2018, izostatické modely)
- Star Carr sezónnost jaro/léto — DIRECT (dentice jelena, Legge & Rowley-Conwy 1988)
- Faunal assemblage 90% jelen — DIRECT (Clark 1954)
- Dřevěná platforma u jezera — DIRECT (Mellars & Dark 1998)
- Pobřeží z GEBCO batometrie — INDIRECT (algoritmická rekonstrukce)
- CAN_HOST grafový model — architektonické rozhodnutí (OK)
- Epistemický systém — architektonické rozhodnutí (OK)
- Terénní subtypy 1-8 jako kategorie — vědecky standardní klasifikace

### Oranžové (extrapolované bez explicitní metody)
- Terrain polygony z DEM (30m rozlišení → hrubá klasifikace)
- Chalk/limestone boundary na -0.8° longitude (proxy za BGS geologii)
- Říční síť = moderní OS Rivers (proxy za 6200 BCE hydrologií)
- Floodplain buffer 150-800m (adaptivní, ale bez geomorfologického podkladu)
- River corridors kolem Star Carr (flow accumulation z DEM)
- Smart holes → glades (0.5-5 ha z DEM šumu → bt_009)
- Riparian zóny 100m buffer (geometrické pravidlo bez ekologického podkladu)
- Syntetické ekotony (ec_002, ec_004, ec_005, ec_006 z geometrie polygonů)
- Terrain subtypy tst_009, tst_010 (STUB — řeky nemají geometrii terénů)

### Červené (hallucinated / nepodložené)
- **VŠECH 11 hodnot produktivity kcal/km²/rok** (viz sekce 2)
- **VŠECH 6 edge_effect_factor hodnot** (viz sekce 3)
- **VŠECH ~44 sezónních modifikátorů** (viz sekce 4)
- **Energy multiplier hodnoty** (1.0, 1.1, 1.3, 1.5, 2.0, 3.0)
- **Quality_modifier hodnoty** na CAN_HOST hranách (0.3–1.0)
- Canopy cover 60-85% pro boreální les
- Visibility 15-50m v lese
- Typical glade area 100-5000 m²
- Riparian forest width 20-200m

---

## 2. Produktivita biotopů — hallucinated values

### Problém

Každý biotop má `primary_productivity_kcal_km2_year` — číslo prezentované jako vědecky odvozené. **Žádné z těchto čísel nemá oporu v citovaném zdroji.**

### Detail po biotopu

| Biotop | Hodnota | Citovaný zdroj | Co zdroj SKUTEČNĚ obsahuje | Verdikt |
|--------|---------|----------------|----------------------------|---------|
| bt_001 Lake | 800 000 | Mitsch & Gosselink 2000 | Primární produktivitu ROSTLIN v g/m²/rok pro mokřady. Ne lidsky využitelné kcal. | **HALLUCINATED** |
| bt_002 Wetland | 1 200 000 | Mitsch & Gosselink 2000 | Totéž — plant biomass, ne human-exploitable calories | **HALLUCINATED** |
| bt_003 Forest | 350 000 | "odhad z Rackham 1986" | Rackham je HISTORICKÁ kniha o anglickém venkově. Neposkytuje kcal/km²/rok. | **HALLUCINATED** |
| bt_004 Upland | 150 000 | "odhad z Simmons 1996" | Simmons pojednává o dopadu mezolitických kultur na prostředí, ne o kalorickém výnosu | **HALLUCINATED** |
| bt_005 Coastal | 700 000 | "odhad z Allen & Pye 1992" | Kniha o morfodynamice slansik, ne o kalorickém výnosu | **HALLUCINATED** |
| bt_006 Chalk scrub | 200 000 | **"odhad"** | Doslova jen "odhad" bez jakéhokoli zdroje! | **FABRICATED** |
| bt_007 Riparian | 750 000 | "odhad z Rackham 1986" | Stejný problém jako bt_003 | **HALLUCINATED** |
| bt_008 Intertidal | 500 000 | "odhad z Balaam 1987" | Kniha o skalnatém pobřeží, ne kcal data | **HALLUCINATED** |
| bt_009 Glade | 550 000 | "odhad z Vera 2000" | Vera pojednává o pastvě a historii lesa, ne o kcal | **HALLUCINATED** |
| bt_010 Post-fire | 450 000 | **"odhad — event biotop"** | Žádný zdroj | **FABRICATED** |
| bt_011 Drought wetland | 300 000 | **"odhad — event biotop"** | Žádný zdroj | **FABRICATED** |

### Kořen problému

Chybí **metodologie pro konverzi ekologických dat na human-exploitable kcal**. Citované zdroje mluví o:
- **Primární produktivitě rostlin** (g biomasy/m²/rok) — to je fotosyntéza, ne lidská potrava
- **Faunální assemblage** — druhy nalezené, ne jejich kalotrický výnos
- **Ekologii biotopů** — popisy, ne kvantifikace výnosu

Co by bylo potřeba:
1. **Net primary productivity (NPP)** z ekologické literatury → g/m²/rok per biotop
2. **Konverzní řetězec**: NPP → edible biomass → human-exploitable fraction → kcal
3. **Explicitní předpoklady**: jaký % biomasy je lidsky dostupný (sběr, lov)
4. **Ethnographic analogies**: data z moderních lovecko-sběračských skupin v podobných biomech

Relevantní zdroje, které existují ale nebyly použity:
- Kelly (2013) "Lifeways of Hunter-Gatherers" — tabulky carrying capacity
- Binford (2001) "Constructing Frames of Reference" — ET (Effective Temperature) → NPP → carrying capacity
- Winterhalder & Smith (2000) "Analyzing Adaptive Strategies" — optimal foraging theory
- Stephens & Krebs (1986) "Foraging Theory" — je v bibliografii ale nebyl použit!

---

## 3. Edge effect faktory — nepodložené

### Problém

Ekotony mají `edge_effect_factor` (1.15–1.6) prezentované s citací Forman & Godron 1986. Forman & Godron diskutují **koncept** edge effectu, ale neposkytují konkrétní multiplikativní faktory pro Mesolithic Yorkshire.

| Ekoton | Faktor | Citace | Realita |
|--------|--------|--------|---------|
| ec_001 Les/Mokřad | 1.6 | Forman & Godron 1986 | Koncept — ne číslo | **FABRICATED** |
| ec_002 Mokřad/Jezero | 1.4 | Mitsch & Gosselink 2000 | Totéž | **FABRICATED** |
| ec_003 Les/Open | 1.3 | Forman & Godron 1986 | Totéž | **FABRICATED** |
| ec_004 Řeka/Les | 1.45 | Forman & Godron 1986 | Totéž | **FABRICATED** |
| ec_005 Pobřeží/Mokřad | 1.5 | Allen & Pye 1992 | Totéž | **FABRICATED** |
| ec_006 Les/Glade | 1.5 | "INFERENCE — analogie" | Přiznáno jako analogie | **HONEST FABRICATION** |

### Co by bylo potřeba
- Empirická data o species richness na rozhraních biotopů
- Metodika pro konverzi biodiversity → human-exploitable resources
- Nebo: přiznat, že edge_effect_factor je modelový parametr k ladění, ne empirický fakt

---

## 4. Sezónní modifikátory — bez zdroje

### Problém

Každý biotop má 4 sezónní modifikátory (SPRING, SUMMER, AUTUMN, WINTER). **Žádný z nich nemá citaci.**

Příklad bt_003 (Boreální les):
```
SPRING: 0.8  — bez zdroje
SUMMER: 1.0  — bez zdroje
AUTUMN: 1.5  — "ořechy lísky; říje jelena"
WINTER: 0.6  — bez zdroje
```

Podzim 1.5 = 50% zvýšení produktivity kvůli ořechům lísky — to dává intuitivní smysl, ale:
- Kolik kcal produkuje líska na km²? (Vera 2000 diskutuje, ale neposkytuje čísla)
- Jak velký je podíl lískových ořechů na celkové food base?
- Říje jelena zvyšuje jejich zranitelnost — ale o kolik?

### Všech 44 modifikátorů je INFERENCE/SPECULATION bez metody

| Biotop | Nejproblematičtější modifikátor | Proč |
|--------|---------------------------------|------|
| bt_001 Lake | Winter 0.4 | Ledový kryt — ale rybolov přes led je doložený v severských kulturách |
| bt_002 Wetland | Spring 1.4 | Kolik přesně kcal přidá hnízdiště ptáků? |
| bt_003 Forest | Autumn 1.5 | Ořechy lísky — ale kolik? |
| bt_009 Glade | Autumn 1.8 | Nejvyšší modifikátor v celé KB — totálně bez podkladu |

---

## 5. Terrain klasifikace — coverage gaps

### Problém: Oblasti bez terénního typu

DEM klasifikace v `04_terrain.py` používá priority systém, ale některé oblasti mohou "propadnout" všemi pravidly:

1. **Nadmořská výška 100-150m** — příliš vysoko na floodplain (<50m bez řeky), příliš nízko na limestone (>150m). Pokud nejsou u řeky → žádný tst
2. **Střední svahy** (5-15°) v nízké nadmořské výšce — nesplňují kritéria pro žádný tst
3. **Oblasti mezi Wolds a Pennines** — Vale of York, ale ne v přímém dosahu řeky

### Problém: Crude classification

| Pravidlo | Problém |
|----------|---------|
| Chalk = východ od -0.8° | Geologie nesleduje zeměpisnou délku. Yorkshire Wolds mají specifický tvar. |
| Limestone = 150-500m | Penniné vápence vs. North York Moors — různé geologie, stejná klasifikace |
| Fenland = <15m, flat | Příliš jednoduché — skutečná fenland závisí na hydrologii |
| Floodplain = <50m, <2° slope | Velké plochy nížin mohou být klasifikovány jako floodplain bez řeky |
| Coastal = kombinace DEM + coastline clip | Rekonstruované pobřeží -25m je samo o sobě INFERENCE |

### Problém: Chybějící geologická data

Pipeline nepoužívá **BGS Geology 625K** (British Geological Survey) — volně dostupná data, která by:
- Rozlišila chalk, limestone, sandstone, clay, glacial till
- Eliminovala potřebu longitude-based proxy
- Přidala substrate informace přímo z geologických map

---

## 6. Star Carr extrapolace

### Co Star Carr skutečně říká

| Znalost | Certainty | Co z toho vyplývá |
|---------|-----------|-------------------|
| Primární tábor na rozhraní les/mokřad u jezera | DIRECT | Toto konkrétní místo bylo využíváno |
| Osídlení jaro/léto | DIRECT | Sezónní mobilita skupin |
| 90% jelen v faunal assemblage | DIRECT | Jelen byl primární kořist NA TOMTO MÍSTĚ |
| Dřevěná platforma | DIRECT | Technologie práce s jezerem |
| 22 000+ mikrolitů | DIRECT | Intenzivní výroba nástrojů |
| Parohové masky (33+) | DIRECT | Rituální/lovecké praktiky |

### Co z toho NELZE odvodit (ale odvodili jsme)

| Extrapolace | Problém |
|-------------|---------|
| "Star Carr = typický mezolitický tábor" | Star Carr je VÝJIMEČNÝ — jeden z největších mezolitických nalezišť v Evropě |
| "Les/mokřad ekoton je CRITICAL všude" | Platí pro Lake Flixton area, ale ne nutně pro zbytek Yorkshire |
| "Produktivita mokřadů = 1 200 000 kcal" | Odrazuje se od Star Carr úspěchu, ne od měření |
| "Settlement patterns se opakují" | 20 ADS sites je cluster kolem jednoho jezera — ne reprezentativní vzorek |
| "6200 BCE podmínky = 9300-8500 BCE podmínky" | 1000+ let rozdíl! design_plan to přiznává ale KB s tím pracuje jako by to bylo validní |

### Temporální posun — vědomé rozhodnutí

Star Carr: **9335–8525 cal BCE** (radiokarbonová data)
Snapshot KB: **~6200 BCE**

Rozdíl: ~2000-3000 let. V tomto období se les měnil (více lísky, méně břízy), Lake Flixton se zmenšoval, klima se oteplovalo.

**Toto je vědomé designové rozhodnutí** (viz [DESIGN_PLAN.md](DESIGN_PLAN.md), SITE_INSTANCE schéma: `snapshot_6200_bce_status: "post-occupation"`). Star Carr slouží jako epistemická kotva — nejlépe dokumentovaná mezolitická lokalita v Británii. Extrapolace na 6200 BCE je SPECULATION, ale přijatá jako základ PoC, protože:
- Terrain (geologie) se za 2000 let nemění
- Biotopy se měnily graduálně, ne skokově
- Alternativa (žádná kotva) by znamenala čistou spekulaci bez referenčního bodu

Epistemický systém to zachycuje korektně — `revision_note` dokumentuje temporální posun.

---

## 7. Survival framework — nedotažený cíl

### 8-vrstvý model z DESIGN_PLAN.md

```
1. Terén + Klima          ← IMPLEMENTOVÁNO (M1)
2. CAN_HOST pravidla      ← IMPLEMENTOVÁNO (M1)
3. Biotopy + Ekotony      ← IMPLEMENTOVÁNO (M1)
   ─────────────────────── KONEC IMPLEMENTACE ───
4. Populace organismů     ← NEEXISTUJE
5. Primární zdroje        ← NEEXISTUJE
6. Uchované zdroje        ← NEEXISTUJE
7. Dostupné zdroje        ← NEEXISTUJE
8. Přežití skupiny        ← NEEXISTUJE
T. Technologie (průřez)   ← NEEXISTUJE
```

### Problém

Produktivita v kcal/km²/rok na úrovni biotopu je SHORTCUT — přeskakuje vrstvy 4-7.

Správný postup by měl být:
1. **Vrstva 3** (biotop) → definuje JAKÉ organismy tu žijí
2. **Vrstva 4** (populace) → kolik jedinců per km² (carrying capacity biotopu)
3. **Vrstva 5** (primární zdroje) → kolik je dostupné k lovu/sběru (s ohledem na technologii)
4. **Vrstva 6** (uchované zdroje) → co se dá uchovat (sušení, uzení)
5. **Vrstva 7** (dostupné zdroje) → po odečtu kompetice (vlci, medvědi, jiné skupiny)
6. **Vrstva 8** (přežití) → pokrývá to potřeby skupiny?

Místo toho jsme vzali "biotop → magické číslo kcal" a přeskočili celý řetězec.

### Důsledek

Dokumentace pro vědce nemůže říkat "přispějte produktivitu v kcal" — musí popsat CELÝ metodologický řetězec a říct: "potřebujeme vaši expertízu na TOMTO kroku řetězce."

---

## 8. Propagace nejistot — epistemologický rámec pro matematiky

### Podstata problému

KB je plná nejistot — ne proto, že jsme líní, ale proto, že **nejistota je inherentní vlastnost systému**. Otázka není "jak najít přesné číslo", ale "jak s principiální nepoznatelností pracovat".

### Analogie se statistickou fyzikou

Ve statistické fyzice nesledujeme jednu molekulu. Miliarda drobných, nepoznatelných interakcí (polohy, rychlosti částic) dá emergentní vlastnost — teplotu, tlak, fázový přechod. Jednotlivé částice jsou nepodstatné; statistický agregát určuje chování systému.

V mezolitické krajině existuje analogický problém. "Částice" jsou drobné, neviditelné vlivy — je jich obrovské množství a žádný z nich není individuálně poznatelný:

- Kde přesně stojí jelen v tento okamžik
- Jestli lískový keř urodil tady nebo o 200m dál
- Jestli potok zamrzl dnes nebo až zítra
- Kde přesně prochází hranice mokřadu a lesa v tomto roce
- Kolik bobřích hrází existuje na tomto úseku řeky
- Jestli vlčí smečka je na severu nebo na jihu údolí
- Jaká je aktuální hladina jezera po posledních deštích
- Kudy přesně vede zvěřní stezka k napajedlu

Žádná z těchto věcí není poznatelná — ale jejich **agregát** se projevuje v makro světě a nakonec určuje, jestli skupina přežije zimu.

### Co z toho plyne pro KB

Naše KB operuje na makro úrovni (biotop, terrain, sezóna). Každá hodnota v KB je implicitní agregát mikroskopických nejistot. Problém: nikde nedefinujeme:

1. **Jak se nejistoty propagují skrz vrstvy** — malá chyba v terrain klasifikaci → jaký dopad na biotop → jaký dopad na resource → jaký dopad na přežití?
2. **Které nejistoty jsou dominantní** — změní se výsledek (přežití/nepřežití) víc, když posunu hranici lesa o 500m, nebo když změním produktivitu mokřadu o 20%?
3. **Kdy je systém stabilní vs. křehký** — existují místa/sezóny kde je přežití robustní (malé změny parametrů nic nemění) vs. křehké (malá změna = kolaps)?
4. **Jaký je charakter distribuce** — jsou výsledky normálně rozdělené, nebo mají těžké chvosty (většinou OK, občas katastrofa)?

### Otázky pro matematiky (formulace problematiky, ne řešení)

**O1: Sensitivity analysis**
Máme řetězec: terrain → biotop → productivita → seasonal_modifier → edge_effect → human-exploitable kcal. Každý krok obsahuje nejistotu. Které parametry mají největší vliv na koncový výsledek? Existuje dominantní zdroj nejistoty, nebo se akumulují rovnoměrně?

**O2: Stabilita a křehkost**
Existují oblasti krajiny, kde je "přežitelnost" robustní (les + mokřad + jezero = Star Carr typ — přežije se skoro vždy) vs. kde je křehká (okraj open upland v zimě — malá změna počasí = smrt)? Jak to kvantifikovat?

**O3: Emergentní vlastnosti**
Pokud spustíme model s milionem náhodných mikrostavů (pozice zvěře, výnosy rostlin, počasí...), jaké makro vlastnosti "vypadnou"? Existují fázové přechody — prahové hodnoty, pod kterými populace kolabuje?

**O4: Informační obsah dat**
Kolik informace o přežití je obsaženo v terrain mapě vs. v biotop klasifikaci vs. v sezónních modifikátorech? Jinak řečeno: kdybychom mohli zlepšit přesnost jen jedné vrstvy, která by to měla být?

**O5: Validace na známých datech**
Pokud model predikuje "tady je vhodné pro osídlení", koreluje to s distribucí známých archeologických nalezišť? A pokud ano — je to validace modelu, nebo jsme model nevědomky kalibrovali na ta samá data?

### Poznámka

Toto není sekce s řešeními. Je to formulace problematiky, která by měla vzniknout jako zadání pro matematiky/modeláře. Název "statistická archeologie" je pracovní — jde o aplikaci metod práce s nejistotou na archeologický model.

---

## 9. Vizuální věrohodnost — geometrie hranic a řek

### Problém: hranaté hranice

Pobřeží a terrain polygony vznikají z DEM rasterových dat → polygonizace → simplifikace. Výsledek je geometricky správný, ale vizuálně neuvěřitelný — hranice jsou hranaté, ne přírodní.

Memory.md explicitně říká: *"Polygony musí vypadat přirozeně, ne geometricky."*

Aktuální stav:
- `ST_SimplifyPreserveTopology` s tolerancí ~20m odstraňuje detail, ale nezavádí přírodní nepravidelnost
- Pobřeží z GEBCO -25m kontury je zvlášť hranaté (nízké rozlišení batometrie)
- Terrain polygony na rovině (fenland, floodplain) mají rovné hrany odpovídající DEM pixelům

### Problém: jistota řek dle velikosti a terénu

Všechny řeky mají implicitně stejnou jistotu polohy, ale reálně:

| Řeka | Substrate | Chování za 8000 let | Jistota polohy |
|------|-----------|---------------------|----------------|
| Velká v tvrdém údolí (Derwent v limestone) | Pevný | Minimální posun — údolí fixuje | VYSOKÁ |
| Velká v nížině (Ouse) | Alluvial | Meandruje, ale zůstává v údolí | STŘEDNÍ |
| Střední v měkkém terénu | Clay/silt | Výrazné meandry, avulze | NÍZKÁ |
| Malý potok na křídě | Chalk | Krasové jevy, podzemní toky | VELMI NÍZKÁ |
| Malý tok v rašelině | Peat | Může zcela zaniknout | MINIMÁLNÍ |

Jistota by měla být f(šířka_toku, tvrdost_substrátu, sklon_údolí) — to je úloha pro hydrologa + matematika.

### Testy věrohodnosti generovaných dat

Potřebujeme způsoby, jak ověřit, že generovaná krajina "dává smysl" — ne že je přesná (to ověřit nelze), ale že neporušuje známé zákonitosti:

**Test 1: Řeky z DEM**
Flow accumulation z DEM by měla predikovat přibližné trasy moderních řek. Odchylka predikce vs. realita = míra nejistoty pro paleořeky.

**Test 2: Šíření lesa dle terénu**
Les se z refugií šíří rychlostí závislou na slope, substrate, hydrology. Simulace šíření by po N iteracích měla odpovídat pylovým profilům z datovaných vrtů (kde existují).

**Test 3: Settlement prediction**
Pokud model produkuje mapu habitability, měla by korelovat s distribucí známých nalezišť. Ale pozor na cirkulární validaci (viz O5 výše).

**Test 4: Konzistence hranic**
Hranice biotopů by měly korelovat s terrain změnami — biotop se nemění uprostřed homogenního terénu. Tam kde se mění bez geomorfologického důvodu = podezřelé.

---

## 10. Lessons learned

### L1: Citace nejsou doklad
Uvedení "Rackham 1986" u čísla 350 000 kcal NEZNAMENÁ, že Rackham toto číslo poskytl. Zdroj musí být verifikovatelný — strana, tabulka, výpočet.

### L2: Primární produktivita ≠ human-exploitable calories
Mitsch & Gosselink měří fotosyntézu rostlin. Pro člověka je dostupný jen zlomek — lístky, ořechy, kořeny + zvířata žijící v biotopu. Konverzní řetězec chybí.

### L3: Star Carr je kotva, ne šablona
Star Carr je referenční bod pro validaci, ale nelze z něj extrapolovat na celé Yorkshire. Je to jako říct "Praha je typické české město" — je to kotva, ne reprezentativní vzorek.

### L4: DEM ≠ geologie
30m DEM umí rozlišit nadmořskou výšku a sklon. Neumí rozlišit vápenec od pískovce. Pro to potřebujeme BGS data.

### L5: Longitude není geology
-0.8° jako boundary chalk/limestone je hack. Funguje "většinou" pro Yorkshire Wolds, ale je to geo-hack, ne věda.

### L6: Moderní řeky ≠ mezolitické řeky
OS Open Rivers mapuje současný stav. Za 8000 let se koryty posunula, meandrovala, některé zanikly. Přesto je to nejlepší dostupný proxy.

### L7: Chybějící vrstvy nelze nahradit jedním číslem
Produktivita v kcal na úrovni biotopu přeskakuje 4 vrstvy survival frameworku. Číslo bez rozkladu nemá vědeckou hodnotu.

### L8: PoC ≠ věda
PoC musí být "uvěřitelný pro vědce" — to neznamená přesný, ale znamená transparentní. Hallucinated čísla s falešnými citacemi jsou HORŠÍ než upřímné "TODO — potřebujeme metodiku."

### L9: Epistemický systém funguje — ale není dodržován
Máme DIRECT/INDIRECT/INFERENCE/SPECULATION — skvělý nástroj. Ale hodnoty označené INFERENCE by měly mít explicitní inferenční řetězec, ne jen odkaz na nepříslušný zdroj.

### L10: Temporal gap je vědomá spekulace
Star Carr 9300-8500 BCE → snapshot 6200 BCE = 2000+ let. Toto je vědomé designové rozhodnutí — Star Carr je nejlepší dostupná kotva. Epistemický systém to zachycuje korektně (SPECULATION + revision_note).

---

## 11. Co potřebujeme od vědců

### Ne: "Vyplňte toto pole v JSON"

### Ano: "Navrhněte metodu pro..."

| Disciplína | Klíčová otázka | Výstup, který potřebujeme |
|------------|----------------|---------------------------|
| **Ekolog** | Jak odvodit NPP (Net Primary Productivity) pro boreální biotopy 6200 BCE? | Konverzní tabulka: biotop → NPP g/m²/rok s citací |
| **Ekolog** | Jak převést NPP → human-exploitable kcal? | Konverzní řetězec s předpoklady a citacemi |
| **Ekolog** | Jaký je empirický základ pro edge effect factors? | Species richness data z moderních analogických ekosystémů |
| **Zoolog** | Jaké populační hustoty měla klíčová zvěř (jelen, prase, tur, bobr)? | Hustota per km² per biotop s citací (vrstva 4) |
| **Botanik** | Jaký byl skutečný výnos lískových ořechů v boreálním lese? | kg/km²/rok s citací (vstup pro vrstvu 5) |
| **Hydrolog** | Jak rekonstruovat říční síť 6200 BCE z moderních dat + DEM? | Metodika: jaké parametry z DEM predikují paleokoryto |
| **Geolog** | Jak využít BGS 625K data pro terrain klasifikaci? | Mapování BGS kategorií → tst_001-008 |
| **Archeolog** | Jak extrapolovat ze Star Carr na zbytek Yorkshire? | Settlement pattern modely, site prediction criteria |
| **Etnograf/Archeolog** | Jaké ethnographic analogies platí pro severský mezolitický klima? | Tabulka moderních HG skupin v podobných podmínkách |
| **Matematik/Modelář** | Jak se nejistoty propagují skrz vrstvy KB? | Sensitivity analysis: které parametry dominují výsledku (viz sekce 8) |
| **Matematik/Modelář** | Kde je systém stabilní vs. křehký? | Identifikace oblastí/sezón s robustním vs. křehkým přežitím |
| **Matematik/Modelář** | Jak kvantifikovat jistotu polohy řek? | f(šířka, substrate, sklon) → certainty score (viz sekce 9) |
| **Matematik/Modelář** | Jak generovat věrohodné přírodní hranice? | Metoda pro nehranaté polygony respektující geologický kontext |
| **Matematik/Modelář** | Jak validovat generovaná data? | Testy věrohodnosti — flow accumulation, šíření lesa, settlement prediction |

---

## Příloha A: Hodnoty, které potřebují metodické odvození

### A.1 Produktivita — potřebný řetězec

```
Pro každý biotop (bt_001-bt_011):

KROK 1 (Ekolog): NPP z literatury
  → g biomasy/m²/rok per biotop
  → Zdroj: peer-reviewed ekologické studie
  → Citace: autor, rok, tabulka/strana

KROK 2 (Botanik/Zoolog): Trofická konverze
  → Jaké organismy žijí v biotopu?
  → Kolik % biomasy je lidsky dostupné?
  → Rostliny: edible parts / total plant mass
  → Zvířata: animal density × body mass × edible fraction

KROK 3 (Etnograf): Harvesting efficiency
  → Kolik % dostupných zdrojů lovci-sběrači reálně získají?
  → Vychází z ethnographic analogies (Kelly 2013, Binford 2001)

KROK 4 (Matematik): Konverze na kcal
  → Výsledná hodnota + confidence interval
  → Certainty level: INFERENCE (pokud řetězec je explicitní)
  → vs. SPECULATION (pokud chybí krok)
```

### A.2 Sezónní modifikátory — potřebný přístup

```
Pro každý biotop × sezónu:

1. Identifikuj klíčové resource druhy per sezóna
2. Kvantifikuj sezónní dostupnost (flowering, fruiting, rutting, migration)
3. Odvoď modifikátor jako poměr: sezónní/průměrná dostupnost
4. Dokumentuj zdroj per druh per sezóna
```

### A.3 Edge effects — potřebný přístup

```
1. Literární rešerše: species richness na rozhraních vs. interiér biotopu
2. Konverze biodiversity → food diversity → human exploitation potential
3. Alternativa: přiznat jako CALIBRATION parameter
   → definovat range (1.0-2.0)
   → ladit empiricky pomocí archaeological evidence
```

---

## Příloha B: Porovnání SCIENCE_GUIDE vs. realita

| Tvrzení v SCIENCE_GUIDE (docs/) | Realita |
|----------------------------------|---------|
| bt_002 Wetland productivity "VERY_HIGH (1 200 000)" | Fabricated — Mitsch & Gosselink měří plant NPP, ne human kcal |
| bt_003 Forest "MEDIUM (350 000)" | Fabricated — Rackham 1986 toto číslo neobsahuje |
| bt_006 Chalk scrub "LOW-MED (200 000)" | Fabricated — zdroj je "odhad" bez citace |
| ec_001 edge_effect 1.4 (v SCIENCE_GUIDE) vs 1.6 (v KB JSON) | NEKONZISTENCE — SCIENCE_GUIDE říká 1.4, schema JSON říká 1.6 |
| ec_006 edge_effect 1.15 (v SCIENCE_GUIDE) vs 1.5 (v KB JSON) | NEKONZISTENCE — SCIENCE_GUIDE říká 1.15, schema JSON říká 1.5 |
| Seasonal modifiers presented as facts | Žádný nemá citaci |
| "Productivity values: Extrapolated from modern analogues" | Které analogie? Žádný odkaz na konkrétní analog |

### Nekonzistence edge_effect hodnot

| Ekoton | schema_examples_v04.json | SCIENCE_GUIDE.md | Rozdíl |
|--------|--------------------------|-------------------|--------|
| ec_001 | 1.6 | 1.4 | **-0.2** |
| ec_002 | 1.4 | 1.3 | **-0.1** |
| ec_003 | 1.3 | 1.2 | **-0.1** |
| ec_004 | 1.45 | 1.35 | **-0.1** |
| ec_005 | 1.5 | 1.45 | **-0.05** |
| ec_006 | 1.5 | 1.15 | **-0.35** |

SCIENCE_GUIDE systematicky uvádí NIŽŠÍ hodnoty než zdrojový JSON. Sonnet pravděpodobně "korigoval" hodnoty bez dokumentace.

---

## 12. Geometrická revize Yorkshire + Třeboňsko (2026-04-19)

**Kontext:** Před startem Polabí pipeline provedena strukturální analýza GeoJSON výstupů. Uživatel vizuálně označil mapy za „nereálné, plné děr, potoky vykrajují jezera". Analýza potvrdila a kvantifikovala problém.

### 12.1 Yorkshire — katastrofický stav

| Ukazatel | Yorkshire | Komentář |
|---|---|---|
| terrain_features: polygon parts | 636 | — |
| terrain+biotopes: polygon parts | **2 673** | mnoho multipolygon s drobky |
| **Počet děr (interior rings)** | **1 586** | 2,4 díry/feature |
| Díry < 0,01 ha (artefakty) | 24 | — |
| Díry 0,01–0,5 ha (malé) | 92 | — |
| Díry 0,5–5 ha (glades, OK) | 392 | — |
| **Díry ≥ 5 ha (problém)** | **1 078** | **většina** |
| Díry ≥ 100 ha (kritické) | desítky | — |
| **Max velikost díry** | **185,46 km²** (18 546 ha) | jedna gigantická díra v lese |
| **Celková plocha děr** | **1 919 km²** (~8 %) | — |
| **Díry ve vodních biotopech** | **1 050** | — |
| **Z toho s řekou uvnitř** | **61 děr / 791 km řek** | = „potoky vykrajují jezera" |

**Top biotopy podle počtu děr (Yorkshire):**
- Mokřad/slatiniště boreální: 1 047 děr / 68 876 ha
- Říční lužní les: 378 děr / 52 646 ha
- Boreální les (bříza-líska): 54 děr / **68 592 ha** (jedna mega-díra)

### 12.2 Třeboňsko — lepší, ale nedokončené

| Ukazatel | Třeboňsko |
|---|---|
| Polygon parts | 4 587 |
| Počet děr | **177** |
| Díry ≥ 5 ha | 39 |
| Díry ≥ 100 ha | 1 |
| Max velikost | 155 ha |
| Díry ve vodě s řekou | 1 (57 m řeky) |
| Celková plocha děr | 8,5 km² (~1 %) |

### 12.3 Proč to validační testy nezachytily

- **T-PHY-08** (řeka vs. vodní plocha): v0.2 explicitně skipoval DEM-rekonstruované řeky s komentářem *„they are intentionally in paleolakes"*. To maskovalo **61 případů** v Yorkshire. Bug opraven v v0.3.
- **Test na díry neexistoval** — pipeline nikdy nepočítala počet/velikost interior rings.
- **Test na řeku protékající dírou v jezeře neexistoval.**
- **Yorkshire neměl runner** — `run_validation_tests_cz.py` byl pouze CZ-specifický.

### 12.4 Co přidáno do MAP_VALIDATION_TESTS v0.3

- **T-GEOM-01**: Díry v biotopech (práh 5 % plochy, 300 děr/1 000 km², max velikost)
- **T-GEOM-02**: Řeky vyřezávající vodu (0-tolerance)
- **T-GEOM-03**: Konektivita biotopů (izolované < 1 ha patches)
- **T-PHY-08 upraven**: testuje VŠECHNY zdroje řek, ne jen DIBAVOD
- **T-SUPP-01 dodokumentován** (již byl v runneru)

### 12.5 Co přidáno do polabi_implementace.md

- **§5.3 Prevence děr a překryvů** — 5 pravidel: full coverage, river-union-not-cut, ST_SnapToGrid, overlap check, glade reclassification
- **§9.3 Geometrické quality gates** — pipeline nesmí importovat do Supabase, pokud GEOM/PHY testy neprojdou
- **§9.4 Referenční metriky** — cíl pro Polabí: < 1 % plochy v dírách, 0 řek vyřezávajících vodu, max díra < 1 km²

### 12.6 Zbytek pro Polabí — akční položky

1. Zobecnit `run_validation_tests_cz.py` → `run_validation_tests.py --region {york|cz|polabi}`
2. Implementovat T-GEOM-01/02/03 ve Python runneru (shapely interior_rings + intersects)
3. Přidat geometric gate do pipeline `06_import_supabase.py` (odmítnout import při FAIL)
4. Retroaktivně projít Yorkshire + Třeboňsko a spočítat GEOM skóre → baseline pro srovnání

---

*Tento audit slouží jako základ pro Fázi 1 — nový metodický průvodce pro vědce.*
