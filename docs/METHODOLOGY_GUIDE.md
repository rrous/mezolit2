# Mezolit2 — Metodický průvodce pro vědce
## Jak budovat model přežití mezolitických skupin v Yorkshire (~6200 BCE)

*Verze 0.2 | 2026-03-15*

> Tento dokument NEŘÍKÁ „vyplňte data". Říká „jakou metodu použít, aby data měla vědeckou hodnotu."
> Viz také: `AUDIT_GAPS_v01.md` — audit mezer v současných datech.

---

## Obsah

1. [Cíl projektu — proč to děláme](#1-cíl-projektu)
2. [Model přežití — 8 vrstev závislostí](#2-model-přežití)
3. [Nový směr: dovednosti → krajina → dovednosti (yo-yo)](#3-nový-směr)
4. [Co víme — Star Carr jako kotva](#4-co-víme)
5. [Co nevíme a potřebujeme](#5-co-nevíme)
6. [Metodické zadání per disciplína](#6-metodické-zadání)
   - [6.1 Geolog](#61-geolog)
   - [6.2 Hydrolog](#62-hydrolog)
   - [6.3 Ekolog / Botanik](#63-ekolog--botanik)
   - [6.4 Zoolog](#64-zoolog)
   - [6.5 Archeolog / Etnograf](#65-archeolog--etnograf)
   - [6.6 Matematik / Modelář](#66-matematik--modelář)
7. [Epistemický systém — jak pracujeme s nejistotou](#7-epistemický-systém)
8. [Současný stav — co je hotové a kde jsou díry](#8-současný-stav)
9. [Datový přehled KB (reference)](#9-datový-přehled-kb)
10. [Lessons learned — co nefungovalo](#10-lessons-learned)

---

## 1. Cíl projektu

### Co stavíme

Strukturovanou znalostní bázi (knowledge base), která umožní odpovědět na otázku:

> **Jaké byly šance na přežití mezolitické lovecko-sběračské skupiny na daném místě, v dané sezóně, s danou technologií?**

Nejde o přesnou odpověď. Jde o **model**, který:
- Zachycuje známé i neznámé proměnné
- Explicitně říká, co je doložené a co je spekulace
- Umožňuje simulovat „co by se stalo, kdyby…"
- Je rozšiřitelný novými daty bez překopání architektury

### Co NESTAVÍME

- Encyklopedii mezolitu (popis → ne model)
- Přesnou mapu 6200 BCE (rekonstrukce → ne kartografie)
- Hru (zábava → ne věda)

### Výzkumná otázka (z [DESIGN_PLAN.md](DESIGN_PLAN.md))

> Jaké byly klíčové faktory — ekologické, technologické a sociální — které určovaly přežití a prosperitu člověka v mezolitické severní Evropě (~9500–6000 BCE)?

### Proč Yorkshire, proč 6200 BCE

- **Star Carr / Lake Flixton** — nejlépe dokumentovaná mezolitická lokalita v Británii. 20+ archeologických sites v jednom lakescape. ADS archiv s GIS daty.
- **~6200 BCE** — moment oddělení Británie od kontinentu (Doggerland). Dramatická ekologická změna.
- **Yorkshire** — geologicky diverzní: pobřeží, nížiny, řeky, vápencové plošiny, Penniny. Všechny klíčové biotopy na jednom místě.

---

## 2. Model přežití — 8 vrstev závislostí

Přežití skupiny je výsledek kaskády závislostí ([DESIGN_PLAN.md](DESIGN_PLAN.md), sekce 5):

```
Vrstva 1: TERÉN + KLIMA                         ← IMPLEMENTOVÁNO
    │  Jaké jsou fyzické podmínky?
    │  (geologie, nadm. výška, sklon, hydrologie, klima)
    ▼
Vrstva 2: CAN_HOST PRAVIDLA                      ← IMPLEMENTOVÁNO
    │  Jak terén určuje, které biotopy tu mohou existovat?
    │  (grafový model: terrain_subtype → biotop přes CAN_HOST hrany)
    ▼
Vrstva 3: BIOTOPY + EKOTONY                      ← IMPLEMENTOVÁNO
    │  Jaké ekologické komunity existují a kde?
    │  (les, mokřad, jezero, pobřeží... a přechodové zóny)
    ▼
Vrstva 4: POPULACE ORGANISMŮ                     ← NEEXISTUJE
    │  Co a v jakém množství žije v krajině?
    │  (jelen per km², líska per ha, ryby per km řeky...)
    ▼
Vrstva 5: PRIMÁRNÍ ZDROJE                        ← NEEXISTUJE
    │  Co je dostupné k lovu a sběru?
    │  (lovitelná zvěř, jedlé rostliny, ryby...)
    ▼
Vrstva 6: UCHOVANÉ ZDROJE                        ← NEEXISTUJE
    │  Co skupina uchovala pro období nedostatku?
    │  (sušené maso, uzené ryby, ořechy...)
    ▼
Vrstva 7: DOSTUPNÉ ZDROJE                        ← NEEXISTUJE
    │  Co skupina reálně získá po odečtu kompetice?
    │  (vlci, medvědi, jiné skupiny, ztráty při lovu...)
    ▼
Vrstva 8: PŘEŽITÍ SKUPINY                        ← NEEXISTUJE
    │  Pokrývá kombinace zdrojů potřeby?
    │  (kalorie, proteiny, tuky, voda, přístřeší, teplo)
    │
    └── TECHNOLOGIE (průřezová vrstva)            ← NEEXISTUJE
        Jak nástroje a techniky mění konverze na vrstvách 5-7?
        (luk vs. oštěp, uzení vs. sušení, čluny vs. brodění...)
```

### Současný shortcut

Místo vrstev 4-7 máme na biotopu přímo `kcal/km²/rok` — jedno číslo, které přeskakuje celý řetězec. Toto číslo nemá metodické odvození (viz AUDIT §2). Potřebujeme buď:
- **Rozdělit** shortcut na vrstvy 4-7 (ideální, ale náročné)
- **Nebo** explicitně popsat konverzní řetězec NPP → human kcal s citacemi per krok

---

## 3. Nový směr: dovednosti → krajina → dovednosti (yo-yo)

### Změna perspektivy

Dosavadní přístup šel zdola nahoru: terén → biotop → zdroje → přežití. Nový přístup začíná **od lidí** a jejich dovedností — a iterativně zpřesňuje znalostní bázi:

```
ITERACE 1: Co lidé uměli a potřebovali?
    │
    │  Klíčové dovednosti a znalosti skupiny v dané lokaci
    │  (Ale pozor: dovednost je relevantní jen pokud na ní záviselo přežití)
    │
    │  Příklad: Rybolov je klíčová dovednost JEN POKUD v lokaci byly
    │  dostatečné rybí zdroje a skupina na nich závisela.
    │  Parohové masky ze Star Carr → lovecká technika na jelena → jelen
    │  musel být klíčový zdroj → les/mokřad ekoton musel být dostupný.
    │
    ▼
ITERACE 2: Co muselo v krajině být, aby dovednosti fungovaly?
    │
    │  Předpoklady pro uplatnění dovedností
    │  → implikované vlastnosti krajiny
    │
    │  Příklad: Lov jelena vyžaduje les s dostatečnou populací.
    │  Populace jelena vyžaduje dostatek pastvy (palouky, okraje lesa).
    │  Palouky vyžadují terénní podmínky (slope, substrate, disturbance).
    │  → ZPŘESNĚNÍ terrain + biotop dat
    │
    ▼
ITERACE 3: Co nového nám krajina říká o dovednostech?
    │
    │  Zpřesněná krajina → nové otázky o dovednostech
    │
    │  Příklad: Horský hřeben odděluje bohaté jarní a letní oblasti.
    │  → Skupina MUSELA umět přecházet hřeben (→ nízká trafficability
    │  v zimě, vysoká energetická cena → potřeba uchovaných zdrojů
    │  na cestu → technologie uchovávání je klíčová dovednost)
    │
    ▼
ITERACE N: Konvergence
    Opakujeme, dokud se model stabilizuje — nové iterace
    nepřinášejí zásadní změny v pochopení.
```

### Proč yo-yo a ne bottom-up

Bottom-up přístup (terén → biotop → zdroje → přežití) vedl k:
- **Fabricated hodnotám** — vyplnili jsme „kcal/km²/rok" bez metody, protože jsme chtěli dostat číslo na konci řetězce
- **Irelevantním detailům** — detailně jsme modelovali terrain, ale bez znalosti, co z toho je PODSTATNÉ pro přežití
- **Chybějícímu kontextu** — biotop bez znalosti dovedností je jen mapa; dovednost bez krajiny je jen seznam

Yo-yo přístup zajistí, že **zpřesňujeme jen to, na čem záleží** — dovednosti říkají, které vlastnosti krajiny jsou kritické, a krajina říká, které dovednosti byly nutné.

### Praktický příklad: Star Carr

**Iterace 1 — dovednosti:**
- Lov jelena (90% fauny) → dovednost: zálesáctví, lovecké techniky (masky?)
- Práce s dřevem (platforma) → dovednost: tesařství s kamennými nástroji
- Práce s parohem → dovednost: zpracování tvrdých materiálů
- Sezónní migrace (jaro/léto) → dovednost: navigace, plánování
- Flintové mikrolity (22 000+) → dovednost: kamenná industrie

**Iterace 2 — co muselo v krajině být:**
- Les s hustou populací jelena → bt_003 (boreální les) s dostatečnými palouky (bt_009)
- Jezero s přístupem → bt_001 + platforma → ekoton les/mokřad (ec_001) MUSÍ existovat
- Zdroj flintu → tst_005 (chalk downland) musí být v dosahu (Yorkshire Wolds, ~30 km)
- Zimní lokace → kam skupina odcházela na podzim/zimu? (NEZNÁMO — klíčová otázka)

**Iterace 3 — co krajina říká zpět:**
- Yorkshire Wolds (30 km) = zdroj flintu, ale suchá krajina (bt_006, nízká produktivita)
- → Flintové expedice vyžadovaly buď uchovávané zásoby na cestu, nebo lovecké příležitosti cestou
- → Říční koridory (bt_007) jako lovecké + transportní trasy
- → NOVÁ OTÁZKA: Byly říční koridory „dálnice" mezolitického Yorkshire?

---

## 4. Co víme — Star Carr jako kotva

### Přímé doklady (DIRECT)

| Znalost | Zdroj | Co z toho vyplývá |
|---------|-------|-------------------|
| Primární tábor na rozhraní les/mokřad u jezera | Clark 1954; Milner 2018 | Toto konkrétní místo bylo využíváno |
| Osídlení jaro/léto (ne celoročně) | Legge & Rowley-Conwy 1988 | Sezónní mobilita skupin |
| 90% jelení fauna | Clark 1954 | Jelen = primární kořist NA TOMTO MÍSTĚ |
| 22 000+ mikrolitů | Milner 2018 | Intenzivní výroba nástrojů z flintu |
| Dřevěná platforma u jezera | Mellars & Dark 1998 | Technologie práce s vodním prostředím |
| 33+ parohových masek | Clark 1954 | Rituální/lovecké praktiky |
| Domácí pes | Milner 2018 | Vliv na lovecké strategie |

### Nepřímé doklady (INDIRECT)

| Znalost | Zdroj | Certainty |
|---------|-------|-----------|
| Lake Flixton tvar (~5.52 km², 234 vertexů) | ADS, Palmer 2015 | INDIRECT |
| Hladina jezera ~24m aOD | Taylor & Alison 2018 | INDIRECT |
| Boreální les (bříza-líska-borovice) | Simmons 1996 (pyly) | INDIRECT |
| Mořská hladina -25m | Shennan 2018 | INDIRECT |

### Co Star Carr NEŘÍKÁ

Star Carr je **kotva**, ne **šablona**:

- **Star Carr je výjimečný** — jeden z největších mezolitických nalezišť v Evropě. Není „typický tábor".
- **20 sites = jeden cluster** — všechny ADS lokality jsou kolem jednoho jezera. Nevíme, jak vypadaly tábory jinde.
- **Časový posun** — Star Carr: 9335-8525 cal BCE, snapshot: ~6200 BCE. Rozdíl ~2000 let. Toto je **vědomé designové rozhodnutí** — terrain se nemění, biotopy se měnily graduálně. Je to SPECULATION, ale přijatá, protože alternativa (žádná kotva) by byla horší. Epistemický systém to zachycuje korektně.
- **90% jelen ≠ 90% všude** — faunal assemblage reflektuje TENTO biotop. Na pobřeží by dominovaly ryby a mlži.

### Yorkshire — krajinné zóny

```
North Sea (pobřeží při -25m)
    ├── Holderness coast (přílivové estuáry, tst_008)
    ├── Yorkshire Wolds (křída, flint, tst_005 → bt_006)
    ├── Vale of Pickering ← LAKE FLIXTON (tst_001 → bt_001)
    │       └── Star Carr (primary_camp), Flixton Island (island_site)
    ├── North York Moors (vápencová plošina, tst_003 → bt_003)
    ├── Vale of York (říční niva, tst_002 → bt_002)
    │       └── Řeky: Ouse, Derwent, Wharfe
    ├── Yorkshire Dales (vápenec, tst_003)
    └── Pennines (vrchovinná rašeliniště, tst_006 → bt_004)
```

---

## 5. Co nevíme a potřebujeme

### 5.1 Jak odvodit produktivitu biotopu

**Problém:** Máme 11 biotopů, každý s `kcal/km²/rok`. Všechna čísla nemají oporu v citovaných zdrojích (viz AUDIT §2). Např. bt_003 (boreální les) = 350 000 kcal, zdroj „odhad z Rackham 1986" — Rackham toto číslo neobsahuje.

**Co chybí:** Konverzní řetězec:
```
NPP (čistá primární produktivita, g/m²/rok)     ← ekologická literatura
    ↓
Edible fraction (jaká část je lidsky jedlá?)      ← botanik + zoolog
    ↓
Harvesting efficiency (kolik lovci-sběrači získají?) ← etnografické analogie
    ↓
Human-exploitable kcal/km²/rok                    ← s confidence intervalem
```

### 5.2 Jak nastavit sezónní modifikátory

**Problém:** ~44 sezónních modifikátorů bez citace. Např. bt_009 (glade), podzim = 1.8 (nejvyšší v celé KB) — zcela bez podkladu.

**Co chybí:** Per biotop × sezóna: které resource druhy, kolik, odkud to víme.

### 5.3 Jak vypadala krajina mimo Star Carr

**Problém:** Terrain klasifikace z DEM 30m, chalk/limestone boundary na -0.8° longitude (geo-hack, ne geologie), oblasti bez terénního typu.

**Co chybí:** BGS 625K geologická data, jistota řek dle substrátu, věrohodné (ne hranaté) hranice polygonů.

### 5.4 Dovednosti a technologie

**Problém:** Vrstvy 4-8 + Technologie neexistují vůbec. V yo-yo přístupu jsou dovednosti PRVNÍM krokem.

**Co chybí:** Katalog dovedností mezolitické skupiny → implikované nároky na krajinu → zpětná vazba do KB.

### 5.5 Nejistota jako vlastnost systému

**Problém:** I s perfektními daty existují miliony drobných nepoznatelných vlivů (kde stojí jelen, jestli potok zamrzl, jestli líska urodila...), jejichž agregát určuje makro výsledek — přežití. Viz AUDIT §8.

---

## 6. Metodické zadání per disciplína

### 6.1 Geolog

**Kontext:** Terrain klasifikace (10 subtypů) je z DEM 30m. Nerozlišuje vápenec od pískovce, chalk boundary je hack na -0.8° longitude.

**G1: BGS integrace**
- Vstup: BGS Geology 625K (volně dostupná)
- Výstup: Mapování BGS lithology → tst_001-008
- Metoda: Které BGS kategorie odpovídají kterému terrain_subtype? Kde potřebujeme nové kategorie?

**G2: Validace DEM klasifikace**
- Vstup: Existující terrain polygony + BGS data
- Výstup: Confusion matrix — kde se DEM a BGS shodují / neshodují

**G3: Substrate atributy**
- Vstup: BGS lithology + soil maps
- Výstup: Per terrain polygon: substrate, permeability, bearing capacity z geologických dat

### 6.2 Hydrolog

**Kontext:** Říční síť je moderní OS Open Rivers — proxy za 6200 BCE.

**H1: Jistota polohy řek**
- Metoda: f(šířka_toku, tvrdost_substrátu, sklon_údolí) → certainty score
- Příklad: Derwent v limestone údolí → VYSOKÁ jistota; malý tok v rašelině → MINIMÁLNÍ

**H2: Paleořeky z DEM**
- Flow accumulation z DEM vs. moderní řeky → odchylka = míra nejistoty

**H3: Lake Flixton hydrologie**
- Watershed delineation, přítoky, odtok. Validace proti sedimentárním datům.

**H4: Sezónní hydrologie**
- Kdy záplavy, kdy sucho, kdy zamrzá. Moderní data → paleoklima korekce.

### 6.3 Ekolog / Botanik

**Kontext:** 11 biotopů definováno, ale kvantitativní parametry (produktivita, sezónní modifikátory) nemají metodické odvození.

**E1: Net Primary Productivity per biotop**
- Rešerše peer-reviewed studií pro analogické ekosystémy
- **Kritické:** Odlišit NPP (fotosyntéza) od human-exploitable kcal!
- Příklad špatně: „bt_002 Wetland = 1 200 000 kcal" s odkazem na Mitsch & Gosselink, kteří měří plant NPP, ne lidské kalorie
- Příklad správně: „NPP boreálního lesa = 400-600 g/m²/rok (Gower et al. 2001, Tab. 3)"

**E2: Konverzní řetězec NPP → human kcal**
- Per biotop: jaké edible species, jaká hustota, jaký edible yield, jaká harvesting efficiency
- **Toto je KLÍČOVÝ deliverable** — nahrazuje současné fabricated hodnoty

**E3: Sezónní dostupnost zdrojů**
- Per biotop × sezóna: fenologická data per species
- Příklad: bt_003 les, podzim: líska (Corylus) fruiting září-říjen. Kolik kg/ha?

**E4: Edge effect — empirický základ**
- Species richness na rozhraních vs. interiér
- Alternativa: přiznat jako CALIBRATION parameter, definovat range (1.0-2.0)
- Současné hodnoty (1.15-1.6) jsou fabricated — Forman & Godron 1986 diskutují koncept, ne konkrétní multiplikátory

**E5: Vegetační rekonstrukce**
- Pylové profily z Yorkshire → validace přiřazení biotop → terrain

### 6.4 Zoolog

**Kontext:** Vrstva 4 (populace organismů) neexistuje. Star Carr říká CO tam bylo, ne KOLIK.

**Z1: Populační hustoty klíčové zvěře**
- Jelen lesní (90% Star Carr fauny), srnec, prase, pratur (vyhynulý — analogie), bobr (ecosystem engineer)
- Per druh × biotop: jedinci/km² z moderních analogií (Skandinávie, Skotsko)

**Z2: Sezónní chování a zranitelnost**
- Říje jelena (podzim) = méně opatrný, spawning ryb (jaro) = koncentrace v řekách

**Z3: Predátoři jako kompetice**
- Vlk (hlavní kompetitor o jelena), medvěd (rybí tahy, mršiny)
- Kolik z „dostupné zvěře" sežerou predátoři?

### 6.5 Archeolog / Etnograf

**Kontext:** Star Carr je kotva. Nový yo-yo přístup začíná od dovedností.

**A1: Katalog dovedností mezolitické skupiny**
- Ze Star Carr assemblage: lov jelena, práce s dřevem, kamenná industrie (flint), zpracování parohu, sezónní plánování
- Z etnografických analogií: rybolov, sběr, uchovávání, navigace, obchod?
- **Per dovednost:** jaké předpoklady v krajině? (yo-yo iterace 2)

**A2: Settlement pattern modely**
- Prediktivní kritéria — kde očekávat osídlení?
- Site catchment analysis, optimal foraging theory
- **Pozor na cirkulární validaci** — nelze kalibrovat a validovat na stejných datech

**A3: Etnografické analogie**
- Moderní lovecko-sběračské skupiny v boreálním/temperátním klimatu
- Sámové (Skandinávie), Nuxalk (BC, Kanada), Ainu (Hokkaido)
- Per analogie: velikost skupiny, territory, sezónní pohyb, caloric budget

**A4: Technologické konverzní koeficienty**
- Luk vs. oštěp → success rate; uzení vs. sušení → účinnost; čluny → territory
- Zdroj: experimentální archeologie + etnografie

**A5: Kalorické potřeby skupiny**
- kcal/den per osoba × velikost skupiny (15-30 lidí) × sezóna
- Složení: muži, ženy, děti, starci → různé potřeby

### 6.6 Matematik / Modelář

**Kontext:** KB je plná nejistot — ne proto, že jsme líní, ale proto, že nejistota je inherentní vlastnost systému. Miliony drobných nepoznatelných vlivů (kde stojí jelen, jestli potok zamrzl, jestli líska urodila...) se agregují do makro výsledku — přežití nebo nepřežití.

Analogie ze statistické fyziky: nesledujeme jednu molekulu, ale miliarda drobných interakcí dá emergentní vlastnost (teplotu, tlak, fázový přechod). Zde: miliarda drobných ekologických nejistot → emergentní „přežitelnost".

**M1: Propagace nejistot**
- Řetězec terrain → biotop → productivita → seasonal → edge_effect → kcal → přežití
- Které parametry mají největší vliv? Existuje dominantní zdroj nejistoty?

**M2: Stabilita a křehkost**
- Kde je přežití robustní (Star Carr typ — přežije se skoro vždy)?
- Kde je křehké (okraj upland v zimě — malá změna = kolaps)?
- Existují prahové hodnoty (fázové přechody)?

**M3: Charakter distribuce**
- Monte Carlo s variabilními parametry → normální rozdělení? těžké chvosty? bimodální?

**M4: Jistota polohy řek**
- f(šířka, substrate, sklon) → certainty score per říční segment
- Validace: flow accumulation z DEM vs. moderní řeky

**M5: Generování věrohodných hranic**
- Hranaté polygony z DEM → přírodně vypadající hranice
- Různá geologie = různá nepravidelnost (říční niva hladká, skalnaté pobřeží fraktální)

**M6: Testy věrohodnosti**
- Flow accumulation predikuje řeky → odchylka od reality
- Simulace šíření lesa → odpovídá pylovým profilům?
- Biotop se nemění uprostřed homogenního terénu → konzistence hranic
- Settlement prediction → korelace s nalezišti (pozor na cirkulární validaci)

**M7: Informační obsah dat**
- Která vrstva má největší informační hodnotu pro predikci přežití?
- Kdybychom mohli zlepšit jen jednu vrstvu, která?

---

## 7. Epistemický systém — jak pracujeme s nejistotou

### Každý záznam nese metadata

```json
{
  "certainty": "DIRECT | INDIRECT | INFERENCE | SPECULATION",
  "source": "autor, rok, strana/tabulka",
  "status": "VALID | REVISED | DISPUTED | REFUTED | HYPOTHESIS",
  "revision_note": "proč se změnilo"
}
```

### Úrovně jistoty

| Úroveň | Definice | Příklad | Požadavek na zdroj |
|---------|----------|---------|-------------------|
| **DIRECT** | Přímý archeologický / geologický nález | Star Carr excavation | Autor, rok, strana |
| **INDIRECT** | Proxy evidence — pyl, fauna, izotopy | Pylový profil → vegetace | Autor, rok, metoda |
| **INFERENCE** | Odvozeno z modelu, analogie, řetězce | NPP z moderní Skandinávie | **Celý inferenční řetězec** |
| **SPECULATION** | Expertní hypotéza, žádná přímá opora | „Záměrné vypalování lesa" | Přiznání, že jde o spekulaci |

### Klíčové pravidlo: INFERENCE vyžaduje řetězec

**Špatně:**
```json
{ "value": 350000, "certainty": "INFERENCE", "source": "odhad z Rackham 1986" }
```

**Správně:**
```json
{
  "value": 350000,
  "certainty": "INFERENCE",
  "source": "NPP boreálního lesa 400-600 g/m²/rok (Gower et al. 2001, Tab. 3) × edible fraction 2-5% (Kelly 2013, p. 67) × harvesting efficiency 30-50% (Binford 2001, p. 234)",
  "confidence_interval": [240000, 1500000]
}
```

### Stav záznamů

| Stav | Popis | Příklad |
|------|-------|---------|
| **VALID** | Aktuálně přijatý | Star Carr = jarní/letní sídliště |
| **REVISED** | Nahrazen novějším | (odkaz na nástupce) |
| **DISPUTED** | Vědecká debata | Záměrné vypalování krajiny |
| **REFUTED** | Odmítnutý | Star Carr jako celoroční sídliště (Clark 1954 → REFUTED Legge 1988) |
| **HYPOTHESIS** | Pracovní hypotéza | Event biotopy (bt_010, bt_011) |

---

## 8. Současný stav — co je hotové a kde jsou díry

### Hotové (Milestone 1)

| Komponenta | Stav | Detail |
|------------|------|--------|
| DEM terrain klasifikace | Funguje | 10 subtypů (tst_001-008 + 2 stuby), DEM 30m |
| Lake Flixton z ADS | Hotové | 234 vertexů, 5.52 km², INDIRECT |
| 20 archeologických sites | Hotové | ADS postglacial_2013, DIRECT |
| Říční síť | Funguje | OS Open Rivers, moderní proxy |
| Pobřeží | Funguje | GEBCO -25m kontura (hranaté) |
| 11 biotopů + CAN_HOST | Definováno | Kvantitativní parametry nepodložené |
| 6 ekotonů | Definováno | edge_effect_factor nepodložený |
| Pipeline (Python) | Funkční | 8 skriptů, reprodukovatelný |
| Frontend (Leaflet) | Funkční | Barvy, certainty, sezóna, panel |
| DB (Supabase PostGIS) | Funkční | 8 tabulek, GIST indexy |

### Díry (z AUDIT_GAPS_v01)

| Problém | Dopad | AUDIT § |
|---------|-------|---------|
| Produktivita fabricated (11 hodnot) | Celý survival model stojí na vymyšlených číslech | §2 |
| Edge effects fabricated (6 hodnot) | Ekotony — klíčový koncept — bez empirického základu | §3 |
| Sezónní modifikátory fabricated (~44 hodnot) | Sezónní dynamika je spekulativní | §4 |
| Terrain coverage gaps | Oblasti 100-150m bez tst klasifikace | §5 |
| Chalk/limestone hack (-0.8° longitude) | Geologická hranice na zeměpisné délce | §5 |
| Hranaté hranice polygonů | Vizuálně neuvěřitelné | §9 |
| Vrstvy 4-8 + Technologie | Celý survival framework neexistuje | §7 |

---

## 9. Datový přehled KB (reference)

### 9.1 Terrain subtypes (10 typů)

| ID | Název | Hydrologie | Elevation | Substrate | Příklad v Yorkshire |
|----|-------|------------|-----------|-----------|---------------------|
| tst_001 | Ledovcová jezerní pánev | permanent_standing_water | 0-100m | organic_lacustrine | Lake Flixton |
| tst_002 | Říční niva | seasonal_flooding | 0-150m | alluvial | Vale of York |
| tst_003 | Vápencová plošina | well_drained | 150-500m | limestone_sandstone | North York Moors |
| tst_004 | Fenlandová pánev | high_water_table | 0-50m | peat | Humberhead |
| tst_005 | Křídová plošina (Wolds) | well_drained | 50-300m | chalk_rendzina | Yorkshire Wolds |
| tst_006 | Vrchovinná rašeliniště | waterlogged_summit | 300-720m | blanket_peat | Pennines |
| tst_007 | Skalnaté pobřeží | well_drained | 0-30m | granite_slate | Flamborough Head |
| tst_008 | Přílivový estuár | tidal_inundation | -5-10m | tidal_mud_sand | Humber estuary |
| tst_009 | Velká stálá řeka | permanent_flow | — | river_gravel | Ouse (STUB) |
| tst_010 | Malý sezónní tok | seasonal_flow | — | mixed | (STUB) |

### 9.2 Biotopy (11 typů)

| ID | Název | Terrain | Produktivita* | Trafficability | Season peak |
|----|-------|---------|---------------|----------------|-------------|
| bt_001 | Mělké jezero | tst_001 | HIGH (800k)* | LOW (×2.0) | Jaro (ryby) |
| bt_002 | Mokřad / slatiniště | tst_002, tst_004 | VERY_HIGH (1.2M)* | LOW (×2.0) | Jaro (rákos, ptáci) |
| bt_003 | Boreální les (bříza-líska-borovice) | tst_003 | MEDIUM (350k)* | MEDIUM_HIGH (×1.1) | Podzim (ořechy, říje) |
| bt_004 | Otevřená vrchovina | tst_006 | LOW (150k)* | HIGH (×1.0) | Léto (pastva) |
| bt_005 | Pobřežní slanisko | tst_008 | HIGH (700k)* | LOW_TO_MEDIUM (×1.5) | Jaro/Podzim (ryby) |
| bt_006 | Křídový skrub | tst_005 | LOW_TO_MED (200k)* | HIGH (×1.0) | Léto (flint, jelen) |
| bt_007 | Říční lužní les | tst_002 | HIGH (750k)* | MEDIUM (×1.3) | Jaro (tah ryb) |
| bt_008 | Přílivová zóna | tst_007, tst_008 | MED_TO_HIGH (500k)* | MEDIUM (×1.3) | Léto (mlži) |
| bt_009 | Lesní palouk (micro) | tst_003, tst_005 | MED_TO_HIGH (550k)* | HIGH (×1.0) | Podzim (líska) |
| bt_010 | Post-fire grassland (event) | — | MED_TO_HIGH (450k)* | HIGH (×1.0) | Jaro (exploze bylin) |
| bt_011 | Drought wetland (event) | — | MEDIUM (300k)* | MEDIUM (×1.4) | Léto (koncentr. ryby) |

**\* Všechny hodnoty kcal/km²/rok jsou FABRICATED** — nemají metodické odvození. Citované zdroje je neobsahují. Viz AUDIT §2 a zadání E1/E2 výše.

### 9.3 Ekotony (6 typů)

| ID | Hranice | Edge factor* | Human relevance | Příklad |
|----|---------|-------------|-----------------|---------|
| ec_001 | Les ↔ Mokřad | 1.6* | **CRITICAL** | Star Carr — tábor přesně na tomto ekotonu |
| ec_002 | Mokřad ↔ Jezero | 1.4* | HIGH | Pobřeží Lake Flixton |
| ec_003 | Les ↔ Otevřená krajina | 1.3* | MEDIUM | Horní hranice lesa |
| ec_004 | Řeka ↔ Les | 1.45* | HIGH | Říční koridory jako lovecké trasy |
| ec_005 | Pobřeží ↔ Mokřad | 1.5* | HIGH | Estuáry s přílivem |
| ec_006 | Les ↔ Palouk | 1.5* | HIGH | Okraje pasek v lese |

**\* Všechny edge_effect hodnoty jsou FABRICATED** — Forman & Godron 1986 diskutují koncept edge effectu, ne konkrétní multiplikátory pro Mesolithic Yorkshire.

### 9.4 Architektura — grafový model

```
TERRAIN_SUBTYPE  ──CAN_HOST──►  BIOTOPE  ──adjacency──►  ECOTONE
    (geologie,                   (ekologie,               (přechodová
    immutable)                   can_host hrany)            zóna)
         │
         ▼
   TERRAIN_FEATURE
   (geometrie — polygon)
         │
         ▼
   SITE_INSTANCE
   (archeologická kotva)
```

Biotop „ví", kde může existovat. CAN_HOST hrany na biotopu říkají: na kterých terrain subtypech, s jakým triggerem (baseline/event), s jakou kvalitou (quality_modifier 0.0-1.0).

Klient traversuje graf: terrain_subtype → najdi biotopy s odpovídajícím can_host → vyber dominantní (trigger=baseline, nejvyšší quality_modifier).

---

## 10. Lessons learned — co nefungovalo

### L1: Citace ≠ doklad
Uvedení „Rackham 1986" u čísla 350 000 kcal neznamená, že Rackham toto číslo poskytl. Zdroj musí být verifikovatelný.

### L2: Primární produktivita ≠ co může člověk sníst
Mitsch & Gosselink měří fotosyntézu. Pro člověka je dostupný jen zlomek. Konverzní řetězec NPP → human kcal je netriviální.

### L3: Star Carr je kotva, ne šablona
Výjimečné naleziště = výjimečný referenční bod. Ale není „typický tábor".

### L4: DEM ≠ geologie
30m DEM rozliší výšku a sklon. Nerozliší vápenec od pískovce. Pro to potřebujeme BGS data.

### L5: Jedno číslo ≠ model
Produktivita v kcal přeskakuje 4 vrstvy. Číslo bez rozkladu nemá vědeckou hodnotu.

### L6: Nejistota je vlastnost, ne chyba
KB bude VŽDY plná nejistot. Cíl: kvantifikovat, porozumět propagaci, vědět kde je systém křehký.

### L7: PoC musí být transparentní
„Uvěřitelný pro vědce" = explicitní o tom, co víme a co nevíme. Hallucinated čísla s falešnými citacemi jsou HORŠÍ než upřímné „TODO".

### L8: Bottom-up nestačí
Terén → biotop → zdroje nefungoval bez znalosti, CO je podstatné pro přežití. Nový yo-yo přístup (dovednosti → krajina → dovednosti) řeší tento problém.

### L9: Epistemický systém je správný — ale nebyl dodržován
INFERENCE vyžaduje explicitní inferenční řetězec, ne jen odkaz na knihu.

### L10: Temporal gap je vědomá spekulace
Star Carr 9300-8500 BCE → snapshot 6200 BCE = přijaté designové rozhodnutí. Epistemický systém to zachycuje korektně.

---

*Tento dokument je živý — aktualizuje se s přibývajícími odpověďmi na metodické otázky.*
*Viz také: `AUDIT_GAPS_v01.md` (audit mezer), `TECH_GUIDE.md` (technický průvodce).*
*Zdrojová KB data: `kb_data/schema_examples_v04.json`, `kb_data/vocabulary_v02.json`*
