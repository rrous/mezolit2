# Mezolit2 — Metodický průvodce pro vědce
## Jak budovat model přežití mezolitických skupin v Yorkshire (~6200 BCE)

*Verze 0.1 | 2026-03-13*

> Tento dokument NEŘÍKÁ „vyplňte data". Říká „jakou metodu použít, aby data měla vědeckou hodnotu."
> Viz také: `AUDIT_GAPS_v01.md` — audit mezer v současných datech.

---

## Obsah

1. [Cíl projektu — proč to děláme](#1-cíl-projektu)
2. [Model přežití — 8 vrstev závislostí](#2-model-přežití)
3. [Co víme — Star Carr jako kotva](#3-co-víme)
4. [Co nevíme a potřebujeme](#4-co-nevíme)
5. [Metodické zadání per disciplína](#5-metodické-zadání)
   - [5.1 Geolog](#51-geolog)
   - [5.2 Hydrolog](#52-hydrolog)
   - [5.3 Ekolog / Botanik](#53-ekolog--botanik)
   - [5.4 Zoolog](#54-zoolog)
   - [5.5 Archeolog / Etnograf](#55-archeolog--etnograf)
   - [5.6 Matematik / Modelář](#56-matematik--modelář)
6. [Epistemický systém — jak pracujeme s nejistotou](#6-epistemický-systém)
7. [Současný stav — co je hotové a kde jsou díry](#7-současný-stav)
8. [Lessons learned — co nefungovalo](#8-lessons-learned)

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

### Proč Yorkshire, proč 6200 BCE

- **Star Carr / Lake Flixton** — nejlépe dokumentovaná mezolitická lokalita v Británii. 20+ archeologických sites v jednom lakescape. ADS archiv s GIS daty.
- **~6200 BCE** — moment oddělení Británie od kontinentu (Doggerland). Dramatická ekologická změna. Snapshot před koncem „starého světa".
- **Yorkshire** — geologicky diverzní oblast: od pobřeží přes nížiny, řeky, vápencové plošiny až po Penniny. Všechny klíčové biotopy na jednom místě.

---

## 2. Model přežití — 8 vrstev závislostí

Cíl projektu vychází z antropologického rámce (design_plan_v9, sekce 5). Přežití skupiny je výsledek kaskády závislostí:

```
Vrstva 1: TERÉN + KLIMA
    │  Jaké jsou fyzické podmínky?
    │  (geologie, nadm. výška, sklon, hydrologie, klima)
    ▼
Vrstva 2: CAN_HOST PRAVIDLA
    │  Jak terén určuje, které biotopy tu mohou existovat?
    │  (grafový model: terrain_subtype → biotop přes CAN_HOST hrany)
    ▼
Vrstva 3: BIOTOPY + EKOTONY
    │  Jaké ekologické komunity existují a kde?
    │  (les, mokřad, jezero, pobřeží... a přechodové zóny mezi nimi)
    ▼
Vrstva 4: POPULACE ORGANISMŮ                    ← NEEXISTUJE
    │  Co a v jakém množství žije v krajině?
    │  (jelen per km², líska per ha, ryby per km řeky...)
    ▼
Vrstva 5: PRIMÁRNÍ ZDROJE                       ← NEEXISTUJE
    │  Co je dostupné k lovu a sběru?
    │  (lovitelná zvěř, jedlé rostliny, ryby...)
    ▼
Vrstva 6: UCHOVANÉ ZDROJE                       ← NEEXISTUJE
    │  Co skupina uchovala pro období nedostatku?
    │  (sušené maso, uzené ryby, ořechy...)
    ▼
Vrstva 7: DOSTUPNÉ ZDROJE                       ← NEEXISTUJE
    │  Co skupina reálně získá po odečtu kompetice?
    │  (vlci, medvědi, jiné skupiny, ztráty při lovu...)
    ▼
Vrstva 8: PŘEŽITÍ SKUPINY                       ← NEEXISTUJE
    │  Pokrývá kombinace zdrojů potřeby?
    │  (kalorie, proteiny, tuky, voda, přístřeší, teplo)
    │
    └── TECHNOLOGIE (průřezová vrstva)
        Jak nástroje a techniky mění konverzi na vrstvách 5-7?
        (luk vs. oštěp, uzení vs. sušení, čluny vs. brodění...)
```

### Současný stav

**Implementováno:** Vrstvy 1-3 (terén, CAN_HOST, biotopy + ekotony)
**Shortcut:** Místo vrstev 4-7 máme na biotopu přímo `kcal/km²/rok` — jedno číslo, které přeskakuje 4 vrstvy. Toto číslo nemá metodické odvození (viz AUDIT §2).
**Neexistuje:** Vrstvy 4-8 + Technologie

### Co to znamená pro vědce

Nepotřebujeme, abyste vyplnili „kcal/km²/rok" do tabulky. Potřebujeme, abyste navrhli **metodu**, jak se od biotopu dostat k přežití skupiny — krok po kroku, s explicitními předpoklady a citacemi.

---

## 3. Co víme — Star Carr jako kotva

### Přímé doklady (DIRECT)

| Znalost | Zdroj | Co z toho vyplývá |
|---------|-------|-------------------|
| Primární tábor na rozhraní les/mokřad u jezera | Clark 1954; Milner 2018 | Toto konkrétní místo bylo využíváno |
| Osídlení jaro/léto (ne celoročně) | Legge & Rowley-Conwy 1988 | Sezónní mobilita — skupina se přesouvala |
| 90% jelení fauna | Clark 1954 | Jelen = primární kořist NA TOMTO MÍSTĚ |
| 22 000+ mikrolitů | Milner 2018 | Intenzivní výroba nástrojů z flintu |
| Dřevěná platforma u jezera | Mellars & Dark 1998 | Technologie práce s vodním prostředím |
| 33+ parohových masek | Clark 1954 | Rituální/lovecké praktiky |
| Domácí pes (doložen ~9000 BCE) | Milner 2018 | Vliv na lovecké strategie |

### Nepřímé doklady (INDIRECT)

| Znalost | Zdroj | Certainty |
|---------|-------|-----------|
| Lake Flixton tvar a rozloha (~5.52 km²) | ADS, Palmer 2015 (sedimenty/pyl) | INDIRECT |
| Hladina jezera ~24m aOD | Taylor & Alison 2018 | INDIRECT |
| Boreální les (bříza-líska-borovice) jako dominantní vegetace | Simmons 1996 (pylové profily) | INDIRECT |
| Mořská hladina -25m | Shennan 2018 (izostatické modely) | INDIRECT |

### Co Star Carr NEŘÍKÁ

Star Carr je **kotva**, ne **šablona**. Nesmíme z ní extrapolovat víc, než je oprávněné:

- **Star Carr je výjimečný** — jeden z největších mezolitických nalezišť v Evropě. Není „typický tábor".
- **20 sites = jeden cluster** — všechny ADS lokality jsou kolem jednoho jezera. Nevíme, jak vypadaly tábory jinde v Yorkshire.
- **Časový posun** — Star Carr: 9335-8525 cal BCE, náš snapshot: ~6200 BCE. Rozdíl ~2000 let. Toto je **vědomé designové rozhodnutí** — terrain (geologie) se nemění, biotopy se měnily graduálně. Ale je to SPECULATION, přijatá proto, že alternativa (žádná kotva) by byla horší.
- **90% jelen ≠ 90% všude** — faunal assemblage reflektuje TENTO biotop (les/mokřad ekoton). Na pobřeží by dominovaly ryby a mlži, na upland pastvina pratura.

---

## 4. Co nevíme a potřebujeme

### 4.1 Jak odvodit produktivitu biotopu

**Problém:** Máme 11 biotopů, každý má `kcal/km²/rok`. Všechna čísla jsou fabricated — citované zdroje je neobsahují (viz AUDIT §2).

**Co chybí:** Konverzní řetězec:
```
NPP (čistá primární produktivita rostlin, g/m²/rok)
    → z ekologické literatury per biotop
    ↓
Edible fraction (jaká část biomasy je lidsky jedlá?)
    → rostliny: ořechy, kořeny, plody, výhonky
    → zvířata: biomasa per km² × edible fraction
    ↓
Harvesting efficiency (kolik z dostupného lovci-sběrači reálně získají?)
    → z etnografických analogií (Kelly 2013, Binford 2001)
    ↓
Human-exploitable kcal/km²/rok
    → s confidence intervalem a certainty level
```

### 4.2 Jak nastavit sezónní modifikátory

**Problém:** Každý biotop má 4 sezónní multiplikátory (jaro, léto, podzim, zima). Žádný nemá citaci.

**Co chybí:** Per biotop × sezóna:
- Které resource druhy jsou dostupné v které sezóně?
- Kolik přibude/ubude oproti průměru? (flowering, fruiting, rutting, migration, ice cover...)
- Odkud to víme? (moderní fenologie, pylové profily, ethnografie)

### 4.3 Jak vypadala krajina mimo Star Carr

**Problém:** Terrain klasifikace je z DEM — nadmořská výška + sklon. Nepoužíváme geologická data (BGS). Chalk/limestone boundary je na -0.8° longitude — geo-hack, ne geologie.

**Co chybí:**
- BGS 625K geologická mapa → přesné rozlišení substrate
- Říční síť 6200 BCE (moderní OS Rivers je proxy)
- Jistota polohy řek dle velikosti a substrátu
- Oblasti, které propadnou klasifikací (100-150m výška, mimo řeku)

### 4.4 Vrstvy 4-8 (populace → přežití)

**Problém:** Celý survival framework existuje jen jako schéma. Žádná data, žádná metodika.

**Co chybí per vrstva:**

| Vrstva | Klíčová otázka | Kdo by měl odpovědět |
|--------|---------------|----------------------|
| 4 — Populace | Kolik jelenů / km² v boreálním lese? Kolik ryb / km řeky? | Zoolog |
| 5 — Primární zdroje | Kolik kg masa / jelena? Kolik kcal / kg lískových ořechů? | Botanik + Zoolog |
| 6 — Uchované zdroje | Jaká je konverzní účinnost sušení / uzení? Jak dlouho vydrží? | Etnograf |
| 7 — Dostupné zdroje | Jaká je success rate lovu? Kolik ztrácíme predátorům? | Archeolog + Etnograf |
| 8 — Přežití | Jaké jsou kalorické potřeby skupiny 15-30 lidí per sezónu? | Fyzický antropolog |

### 4.5 Nejistota jako vlastnost systému

**Problém:** Nejde jen o „chybějící data". I kdybychom měli perfektní data, systém obsahuje principiální nejistotu — miliony drobných nepoznatelných vlivů (kde přesně stojí jelen, jestli potok zamrzl, jestli líska urodila...), jejichž agregát se projevuje v makro výsledku — přežití nebo nepřežití skupiny.

**Co chybí:** Rámec pro práci s touto nejistotou — viz sekce 5.6.

---

## 5. Metodické zadání per disciplína

### 5.1 Geolog

**Kontext:** Terrain klasifikace (10 subtypů: tst_001–tst_008 + 2 stuby pro řeky) je z DEM 30m. Funguje pro hrubé rozlišení, ale:
- Nerozlišuje vápenec od pískovce (obojí = tst_003)
- Chalk boundary na longitude -0.8° je hack
- Některé oblasti propadnou klasifikací

**Zadání G1: BGS integrace**
- Vstup: BGS Geology 625K (volně dostupná)
- Výstup: Mapování BGS lithology → tst_001-008
- Metoda: Jaké BGS kategorie odpovídají kterému terrain_subtype? Kde je mapování 1:1 a kde potřebujeme nové tst kategorie?
- Výsledek: Tabulka + certainty per mapování

**Zadání G2: Validace DEM klasifikace**
- Vstup: Existující terrain polygony + BGS data
- Výstup: Kde se DEM klasifikace a BGS shodují / neshodují
- Metoda: Overlay analýza — kolik % polygonů je správně klasifikovaných?
- Výsledek: Confusion matrix + doporučení

**Zadání G3: Substrate atributy**
- Vstup: BGS lithology + soil maps
- Výstup: Per terrain polygon: substrate, permeability, bearing capacity
- Metoda: Z BGS dat, ne z DEM inference
- Certainty: INDIRECT (BGS = moderní geologické mapování, ale substrát se za 8000 let výrazně neměnil)

### 5.2 Hydrolog

**Kontext:** Říční síť je moderní OS Open Rivers. Řeky 6200 BCE měly jiný průběh — ale jaký?

**Zadání H1: Jistota polohy řek**
- Vstup: OS Rivers + DEM + BGS substrate
- Výstup: Per řeka / segment: certainty score pozice
- Metoda: f(šířka_toku, tvrdost_substrátu, sklon_údolí, typ_nivy)
  - Velká řeka v tvrdém údolí → vysoká jistota
  - Malý tok v rašelině → minimální jistota
- Výsledek: Tabulka / funkce → certainty per segment

**Zadání H2: Paleořeky z DEM**
- Vstup: DEM 30m
- Výstup: Predikované říční trasy z flow accumulation
- Metoda: Porovnat predikci s moderní sítí → odchylka = míra nejistoty
- Výsledek: „River prediction confidence" per oblast

**Zadání H3: Lake Flixton hydrologie**
- Vstup: ADS data, DEM, Taylor & Alison 2018
- Výstup: Hydrological catchment jezera, přítoky, odtok
- Metoda: Watershed delineation z DEM + validace proti sedimentárním datům
- Certainty: INDIRECT (sedimenty existují, ale watershed je modelovaný)

**Zadání H4: Sezónní hydrologie**
- Vstup: Moderní srážkové + průtokové data pro Yorkshire
- Výstup: Sezónní pattern — kdy jsou záplavy, kdy sucho, kdy zamrzá
- Metoda: Moderní → paleoklima korekce (Boreal = mírně teplejší léta, studenější zimy)
- Certainty: INFERENCE

### 5.3 Ekolog / Botanik

**Kontext:** Biotopy (11 typů) jsou definovány, ale jejich kvantitativní parametry (produktivita, sezónní modifikátory) nemají metodické odvození.

**Zadání E1: Net Primary Productivity per biotop**
- Vstup: Ekologická literatura pro boreální / temperátní biomy
- Výstup: NPP v g/m²/rok per biotop (bt_001-bt_011)
- Metoda: Rešerše peer-reviewed studií pro analogické ekosystémy
  - Boreální les (bt_003): skandinávské studie NPP bříza-borovice
  - Mokřad (bt_002): Mitsch & Gosselink — ale pozor, oni měří plant NPP, ne human-exploitable kcal!
  - Jezero (bt_001): limnologické studie mělkých eutrofních jezer
- Certainty: INFERENCE (moderní analogie → 6200 BCE extrapolace)
- **Kritické:** Odlišit NPP (fotosyntéza) od human-exploitable kcal. To jsou dvě zásadně odlišné veličiny.

**Zadání E2: Konverzní řetězec NPP → human kcal**
- Vstup: NPP per biotop + species composition
- Výstup: Human-exploitable kcal/km²/rok s rozpadem na zdroje
- Metoda:
  1. Per biotop: jaké edible species? (ořechy, kořeny, plody, zvěř, ryby)
  2. Per species: jaká hustota? jaký edible yield?
  3. Per zdroj: jaká harvesting efficiency? (Kelly 2013, Binford 2001)
  4. Sumace → kcal/km²/rok s confidence intervalem
- **Toto je KLÍČOVÝ deliverable** — nahrazuje současné fabricated hodnoty

**Zadání E3: Sezónní dostupnost zdrojů**
- Vstup: Fenologická data per species per biotop
- Výstup: Sezónní modifikátory s citací per species
- Metoda: Per biotop × sezóna: které druhy jsou dostupné, v jakém množství?
  - Příklad bt_003 (les), podzim: líska (Corylus) — fruiting září-říjen. Kolik kg/ha? (existující data z moderních lesů)
  - Příklad bt_001 (jezero), jaro: spawning ryb. Které druhy? Kolik? (limnologická data)
- Certainty: INFERENCE (moderní fenologie → boreální klima korekce)

**Zadání E4: Edge effect — empirický základ**
- Vstup: Ekologická literatura o ecotone biodiversity
- Výstup: Species richness na rozhraních vs. interiér biotopu
- Metoda: Rešerše studies o edge effects v temperátních / boreálních ekosystémech
- **Alternativa:** Přiznat edge_effect_factor jako CALIBRATION parameter (ne empirický fakt), definovat range (1.0–2.0), ladit proti archeologickým datům
- Certainty: INFERENCE nebo SPECULATION (záleží na kvalitě analogií)

**Zadání E5: Vegetační rekonstrukce**
- Vstup: Pylové profily z Yorkshire (kde existují), paleobotanická data
- Výstup: Validace / korekce přiřazení biotop → terrain
- Metoda: Pylový profil říká „tady bylo X% bříza, Y% líska" → odpovídá to bt_003?
- Certainty: INDIRECT (pyl je přímý doklad vegetace, ale prostorové rozlišení je nízké)

### 5.4 Zoolog

**Kontext:** Vrstva 4 (populace organismů) neexistuje. Star Carr faunal assemblage říká CO tam bylo, ale ne KOLIK.

**Zadání Z1: Populační hustoty klíčové zvěře**
- Vstup: Zoologická literatura pro boreální / temperátní ekosystémy
- Výstup: Per druh × biotop: hustota (jedinci/km²)
- Klíčové druhy:
  - Jelen lesní (Cervus elaphus) — 90% Star Carr fauny
  - Srnec (Capreolus capreolus)
  - Prase divoké (Sus scrofa)
  - Pratur (Bos primigenius) — dnes vyhynulý, analogie nutná
  - Bobr (Castor fiber) — ecosystem engineer, ovlivňuje hydrologii
  - Los (Alces alces) — přítomnost v Británii 6200 BCE nejistá
- Metoda: Moderní populační hustoty v analogických biotopech (Skandinávie, Skotsko) × korekce na absenci moderních predátorů / management
- Certainty: INFERENCE

**Zadání Z2: Sezónní chování a zranitelnost**
- Vstup: Etologická data per druh
- Výstup: Per druh × sezóna: kde se zdržuje, jak je zranitelný
- Metoda:
  - Jelen — říje (podzim) = méně opatrný, shromáždění = snazší lov
  - Ryby — tah (jaro) = koncentrace v řekách
  - Ptáci — hnízdiště (jaro) = vejce a mláďata dostupné
- Certainty: INDIRECT (moderní etologie, ale chování se mění s podmínkami)

**Zadání Z3: Predátoři jako kompetice**
- Vstup: Zoologická literatura
- Výstup: Jaká je predační ztráta? Kolik z „dostupné zvěře" sežerou vlci, medvědi, orli?
- Klíčoví predátoři:
  - Vlk (Canis lupus) — hlavní kompetitor o jelena
  - Medvěd hnědý (Ursus arctos) — rybí tahy, mršiny, ořechy
  - Orel, jestřáb — malá zvěř, zajíci
- Certainty: SPECULATION (populační data pro 6200 BCE neexistují)

### 5.5 Archeolog / Etnograf

**Kontext:** Star Carr je skvělá kotva, ale potřebujeme metody pro extrapolaci na zbytek Yorkshire.

**Zadání A1: Settlement pattern modely**
- Vstup: Star Carr + další britské mezolitické sites
- Výstup: Prediktivní kritéria — kde očekávat osídlení?
- Metoda: Site catchment analysis, gravity models, optimal foraging theory
  - Které krajinné rysy korelují s osídlením? (ekoton, voda, flint, výhled...)
  - Validace: predikuje model známá naleziště?
- Certainty: INFERENCE
- **Pozor na cirkulární validaci:** pokud model kalibrujeme na známá naleziště a pak ověříme na stejných datech, nic jsme nevalidovali

**Zadání A2: Etnografické analogie**
- Vstup: Kelly 2013, Binford 2001, etnografická databáze
- Výstup: Tabulka moderních lovecko-sběračských skupin v podobných podmínkách
- Metoda: Hledat skupiny v:
  - Boreálním / temperátním klimatu
  - S přístupem k jezerům / řekám
  - Se sezónní mobilitou
  - Příklady: Sámové (Skandinávie), Nuxalk (BC, Kanada), Ainu (Hokkaido)
- Výstup per analogie: velikost skupiny, territory size, sezónní pohyb, caloric budget
- Certainty: INFERENCE (analogie z jiného kontinentu / doby)

**Zadání A3: Technologické konverzní koeficienty**
- Vstup: Experimentální archeologie, etnografie
- Výstup: Efektivita per technologie
- Příklady:
  - Luk vs. oštěp → success rate lovu (kolik pokusů / úlovek)
  - Uzení vs. sušení → konverzní účinnost (kolik kcal se zachová)
  - Čluny → kolik zvětšují dostupný territory
  - Flintové nástroje → kolik času stojí výroba vs. kolik zlepšují harvesting
- Certainty: INDIRECT (experimentální archeologie) nebo INFERENCE (etnografie)

**Zadání A4: Kalorické potřeby skupiny**
- Vstup: Fyzická antropologie, etnografie
- Výstup: kcal/den per osoba × velikost skupiny × sezóna
- Metoda:
  - Bazální metabolismus + aktivita (lov, sběr, přesuny, stavba)
  - Sezónní variace: zima = vyšší potřeba (teplo), léto = vyšší aktivita
  - Složení skupiny: muži, ženy, děti, starci → různé potřeby
- Certainty: INDIRECT (fyziologie je konstantní, ale aktivita je INFERENCE)

### 5.6 Matematik / Modelář

**Kontext:** KB je plná nejistot. Nejistota není bug — je to inherentní vlastnost systému. Miliony drobných nepoznatelných vlivů (kde přesně stojí jelen, jestli potok zamrzl, jestli líska urodila...) se agregují do makro výsledku: přežití nebo nepřežití skupiny.

Analogie ze statistické fyziky: nesledujeme jednu molekulu, ale miliarda drobných interakcí dá emergentní vlastnost (teplotu, tlak, fázový přechod). Tady: miliarda drobných ekologických nejistot dá emergentní vlastnost — míru přežitelnosti.

**Zadání M1: Propagace nejistot**
- Vstup: Řetězec terrain → biotop → productivita → seasonal → edge_effect → kcal → přežití
- Výstup: Jak se nejistota na vstupu propaguje na výstup?
- Otázky:
  - Malá chyba v terrain klasifikaci → jaký dopad na přežití?
  - Které parametry mají největší vliv? (sensitivity analysis)
  - Akumulují se nejistoty rovnoměrně, nebo dominuje jeden zdroj?

**Zadání M2: Stabilita a křehkost**
- Vstup: Model přežití (až bude existovat)
- Výstup: Mapa stability — kde je přežití robustní vs. křehké
- Otázky:
  - Star Carr typ (les + mokřad + jezero) = přežije se skoro vždy?
  - Okraj open upland v zimě = malá změna → kolaps?
  - Existují prahové hodnoty (fázové přechody)?

**Zadání M3: Charakter distribuce výsledků**
- Vstup: Monte Carlo simulace s variabilními parametry
- Výstup: Distribuce výsledků přežití
- Otázky:
  - Jsou výsledky normálně rozdělené? (většinou OK, někdy špatně)
  - Nebo mají těžké chvosty? (většinou OK, občas katastrofa)
  - Existují bimodální výsledky? (přežije / nepřežije, nic mezi)

**Zadání M4: Jistota polohy řek**
- Vstup: OS Rivers + DEM + substrate data
- Výstup: Certainty score per říční segment
- Metoda: f(šířka_toku, tvrdost_substrátu, sklon_údolí) → certainty
- Validace: flow accumulation z DEM vs. moderní řeky → odchylka = míra nejistoty

**Zadání M5: Generování věrohodných hranic**
- Vstup: Hranaté polygony z DEM polygonizace
- Výstup: Přírodně vypadající hranice
- Metoda: Respektovat geologický kontext — jinou nepravidelnost má říční niva (hladká, meandrující) a jinou skalnaté pobřeží (členité, fraktální)
- Constraint: Polygony musí vypadat přirozeně, ne geometricky

**Zadání M6: Testy věrohodnosti**
- Vstup: Generovaná krajina
- Výstup: Skóre „dává to smysl?"
- Metody:
  - Flow accumulation z DEM predikuje řeky → odchylka od reality
  - Simulace šíření lesa z refugií → odpovídá pylovým profilům?
  - Biotop se nemění uprostřed homogenního terénu → konzistence hranic
  - Settlement prediction → koreluje s distribucí nalezišť? (pozor na cirkulární validaci)

**Zadání M7: Informační obsah dat**
- Vstup: Celá KB
- Výstup: Které vrstvy dat mají největší informační hodnotu pro predikci přežití?
- Otázka: Kdybychom mohli zlepšit přesnost jen jedné vrstvy, která by to měla být?
- Metoda: Information-theoretic analýza nebo feature importance z ML modelu

---

## 6. Epistemický systém — jak pracujeme s nejistotou

### Každý záznam nese metadata

```json
{
  "certainty": "DIRECT | INDIRECT | INFERENCE | SPECULATION",
  "source": "autor, rok, strana/tabulka",
  "status": "VALID | REVISED | DISPUTED | REFUTED | HYPOTHESIS",
  "revision_note": "proč se změnilo"
}
```

### Co jednotlivé úrovně znamenají

| Úroveň | Definice | Příklad | Požadavek na zdroj |
|---------|----------|---------|-------------------|
| **DIRECT** | Přímý archeologický / geologický nález | Star Carr excavation, BGS vrty | Autor, rok, strana |
| **INDIRECT** | Proxy evidence — pyl, fauna, izotopy, sedimenty | Pylový profil → vegetace | Autor, rok, metoda |
| **INFERENCE** | Odvozeno z modelu, analogie, logického řetězce | NPP z moderní Skandinávie → 6200 BCE | **Celý inferenční řetězec** s citacemi per krok |
| **SPECULATION** | Expertní hypotéza, žádná přímá opora | „Záměrné vypalování lesa" | Explicitní přiznání, že jde o spekulaci |

### Klíčové pravidlo: INFERENCE vyžaduje řetězec

Nestačí napsat `"certainty": "INFERENCE", "source": "Rackham 1986"`. Musí být explicitní:

**Špatně:**
```json
{
  "value": 350000,
  "certainty": "INFERENCE",
  "source": "odhad z Rackham 1986"
}
```

**Správně:**
```json
{
  "value": 350000,
  "certainty": "INFERENCE",
  "source": "NPP boreálního lesa 400-600 g/m²/rok (Gower et al. 2001, Tab. 3) × edible fraction 2-5% (Kelly 2013, p. 67) × harvesting efficiency 30-50% (Binford 2001, p. 234) = 240-1500 kcal/m²/rok → 240k-1.5M kcal/km²/rok, midpoint 350k",
  "confidence_interval": [240000, 1500000]
}
```

### Nejistota v hodnotách — ne jen v klasifikaci

Současný systém zachycuje nejistotu v **klasifikaci** (DIRECT/INDIRECT/...), ale ne v **hodnotách**. Hodnota 350 000 kcal/km²/rok vypadá přesně — ale mohla by být klidně 100 000 nebo 1 000 000.

Pro matematický model potřebujeme:
- **Range** (min/max) nebo **confidence interval** per hodnota
- **Distribuce** — je to normální rozdělení? log-normální? uniform?
- **Korelace** — jsou nejistoty nezávislé, nebo spolu korelují?

---

## 7. Současný stav — co je hotové a kde jsou díry

### Hotové (Milestone 1)

| Komponenta | Stav | Poznámka |
|------------|------|----------|
| DEM terrain klasifikace (10 tst) | Funguje | Hrubé, ale konzistentní |
| Lake Flixton z ADS | Hotové | 234 vertexů, INDIRECT |
| 20 archeologických sites | Hotové | ADS, DIRECT |
| Říční síť z OS Rivers | Funguje | Moderní proxy, INDIRECT |
| Pobřeží z GEBCO -25m | Funguje | Hranaté, nízké rozlišení |
| 11 biotopů + CAN_HOST | Definováno | Kvantitativní parametry nepodložené |
| 6 ekotonů | Definováno | edge_effect_factor nepodložený |
| Pipeline (Python, 8 skriptů) | Funkční | Reprodukovatelný, testovatelný |
| Frontend (Leaflet mapa) | Funkční | Barvy, certainty, sezóna, panel |
| DB (Supabase PostGIS) | Funkční | 8 tabulek, GIST indexy |

### Díry v Milestone 1

| Problém | Detail | Viz AUDIT § |
|---------|--------|-------------|
| Produktivita fabricated | Všech 11 hodnot kcal/km²/rok nemá zdroj | §2 |
| Edge effects fabricated | Všech 6 faktorů nemá empirický základ | §3 |
| Sezónní modifikátory fabricated | ~44 hodnot bez citace | §4 |
| Terrain coverage gaps | Oblasti 100-150m mimo řeku propadnou | §5 |
| Hranaté polygony | Hranice neodpovídají přírodní nepravidelnosti | §9 |
| Chalk/limestone hack | -0.8° longitude místo BGS geologie | §5 |
| Energy multipliers fabricated | 1.0-3.0 bez zdroje | §2 |
| Quality modifiers fabricated | 0.3-1.0 na CAN_HOST hranách bez zdroje | §2 |

### Neexistující vrstvy

| Vrstva | Status | Předpoklad pro |
|--------|--------|----------------|
| 4 — Populace organismů | Nic | Vrstvu 5 |
| 5 — Primární zdroje | Nic | Vrstvu 6 |
| 6 — Uchované zdroje | Nic | Vrstvu 7 |
| 7 — Dostupné zdroje | Nic | Vrstvu 8 |
| 8 — Přežití skupiny | Nic | Cíl projektu |
| T — Technologie | Nic | Vrstvy 5-7 |

---

## 8. Lessons learned — co nefungovalo

### L1: Citace ≠ doklad
Uvedení „Rackham 1986" u čísla 350 000 kcal neznamená, že Rackham toto číslo poskytl. Zdroj musí být verifikovatelný — strana, tabulka, výpočet. Jinak je to halucinace s akademickým nátěrem.

### L2: Primární produktivita ≠ co může člověk sníst
Mitsch & Gosselink měří fotosyntézu. Pro člověka je dostupný jen zlomek — ořechy, kořeny, zvířata žijící v biotopu. Konverzní řetězec NPP → human kcal je netriviální a musí být explicitní.

### L3: Star Carr je kotva, ne šablona
Výjimečné naleziště = výjimečný referenční bod. Ale není „typický tábor" a nelze z něj extrapolovat na celé Yorkshire.

### L4: DEM ≠ geologie
30m DEM rozliší výšku a sklon. Nerozliší vápenec od pískovce. Pro to potřebujeme BGS data.

### L5: Jedno číslo ≠ model
Produktivita v kcal/km²/rok na úrovni biotopu přeskakuje 4 vrstvy survival frameworku. Číslo bez rozkladu nemá vědeckou hodnotu — potřebujeme celý řetězec.

### L6: Nejistota je vlastnost, ne chyba
KB bude VŽDY plná nejistot. Cíl není nejistotu odstranit — cíl je kvantifikovat ji, porozumět jak se propaguje, a vědět kde je systém stabilní a kde křehký.

### L7: PoC musí být transparentní
„Uvěřitelný pro vědce" neznamená přesný. Znamená: explicitní o tom, co víme, co nevíme, a jak jsme dospěli k tomu, co tvrdíme.

### L8: Epistemický systém je správný — ale nebyl dodržován
DIRECT/INDIRECT/INFERENCE/SPECULATION je skvělý nástroj. Ale INFERENCE vyžaduje explicitní inferenční řetězec, ne jen odkaz na knihu, která tu informaci neobsahuje.

---

*Tento dokument je živý — aktualizuje se s přibývajícími odpověďmi na metodické otázky.*
*Viz také: `SCIENCE_GUIDE.md` (datový slovník), `TECH_GUIDE.md` (technický průvodce), `AUDIT_GAPS_v01.md` (audit mezer).*
