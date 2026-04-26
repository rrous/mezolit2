# Mezolit2 — Dokumentace

Tento adresář je jediný zdroj pravdy pro projektovou dokumentaci.
Starší/nahrazené dokumenty jsou v [`archiv/`](archiv/).

---

## Aktuální fokus: Polabí (M3+)

Cíl: **kvalitativně lepší data** — realistický terén, biotopy, hydrologie.
Předchozí mapy (Yorkshire, Třeboňsko) zůstávají, ale nedosahují požadované úrovně — plné děr, neodpovídající DEM, geometrické hranice.

> **Lekce z revize 2026-04:** Yorkshire má 1 586 děr v biotopech (6 % plochy), 61 děr ve vodě s protékající řekou (791 km řek). Třeboňsko lepší, ale stále má 177 děr. Žádný test v MAP_VALIDATION v0.2 to nezachytil.
>
> Reakce v v0.3:
> - Nová kategorie testů **GEOM** (T-GEOM-01 díry, T-GEOM-02 řeka vyřezává vodu, T-GEOM-03 konektivita)
> - `polabi_implementace.md §5.3` — 5 prevenčních pravidel, `§9.3` — povinná geometrická quality gate před importem
> - `AUDIT_GAPS_v01.md §12` — kvantifikace, akční položky
>
> **Polabí nesmí opakovat tyto chyby.**

| Dokument | Obsah |
|---|---|
| [polabi_implementace.md](polabi_implementace.md) | **Implementační plán Polabí** — bbox, data, preprocessing, PostGIS schéma, klasifikace, meandry, fraktální hranice, validace |

---

## Koncepční a metodická dokumentace (napříč regiony)

| Dokument | Obsah |
|---|---|
| [DESIGN_PLAN.md](DESIGN_PLAN.md) | Master design KB — node typy, vrstvy, epistemický systém, SITE_INSTANCE |
| [SCIENCE_GUIDE.md](SCIENCE_GUIDE.md) | Průvodce pro vědce/obsahové přispěvatele (terrain, biotopy, ekotony, epistemika) |
| [METHODOLOGY_GUIDE.md](METHODOLOGY_GUIDE.md) | Metodika rekonstrukce — 8-vrstvý model přežití, zadání per disciplína |
| [TECH_GUIDE.md](TECH_GUIDE.md) | Architektura, repo, prerekvizity, pipeline, deployment |
| [MAP_VALIDATION_TESTS_v02.md](MAP_VALIDATION_TESTS_v02.md) | Sada testů pro ověření věrohodnosti krajinné mapy (použitelné pro všechny regiony) |
| [AUDIT_GAPS_v01.md](AUDIT_GAPS_v01.md) | Audit mezer v datech Yorkshire (lekce pro další regiony) |

---

## Regionální design dokumenty

| Region | Status | Dokumenty |
|---|---|---|
| **Yorkshire / Star Carr** | M1+M2 hotovo, data nedostačující kvalitou | [DESIGN_PLAN.md](DESIGN_PLAN.md), [AUDIT_GAPS_v01.md](AUDIT_GAPS_v01.md) |
| **Třeboňsko** | Pipeline rozpracovaná | [GEO_DESIGN_v02.md](GEO_DESIGN_v02.md) |
| **Polabí** | Plánování (prioritní) | [polabi_implementace.md](polabi_implementace.md) |

---

## Referenční data

JSON schémata a slovníky jsou v [`../kb_data/`](../kb_data/) (kanonická verze, používá pipeline).

| Soubor | Obsah |
|---|---|
| `kb_data/schema_examples_v04.json` | Ukázky terrain_subtypes, biotopes, ecotones, site_instances |
| `kb_data/vocabulary_v02.json` | Enum definice s layer anotacemi a epistemickým rámcem |

---

## Archiv

Soubory v [`archiv/`](archiv/) jsou nahrazené nebo historické (Yorkshire M1/M2 fáze):

| Soubor | Proč archivováno |
|---|---|
| `mezoliticky_design_plan_v8.md` | Nahrazeno `DESIGN_PLAN.md` (v9) |
| `poc_design_v02.md` | Yorkshire PoC implementován; obsah pokrývá `TECH_GUIDE.md` |
| `visual_fixes_plan_v01.md` | Yorkshire M2 vizuální opravy dokončeny |
