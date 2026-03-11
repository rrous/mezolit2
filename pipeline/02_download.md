# Stažení geodat pro Mezolit2 PoC

Všechna data stáhnout do `data/raw/`.

## 1. Copernicus DEM GLO-30 (30m DEM)

**Co:** Digitální model terénu, 30m rozlišení, globální pokrytí.

**Postup:**
1. Registrace na https://dataspace.copernicus.eu/ (zdarma)
2. Vyhledat "Copernicus DEM GLO-30"
3. Stáhnout tiles pokrývající Yorkshire bbox:
   - West: -3.0°, East: 1.0°, South: 53.0°, North: 55.0°
   - (bbox je mírně větší než Yorkshire pro overlap)
4. Potřebné tiles (přibližně):
   - `Copernicus_DSM_COG_10_N53_00_W003_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N53_00_W002_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N53_00_W001_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N53_00_E000_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N54_00_W003_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N54_00_W002_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N54_00_W001_00_DEM.tif`
   - `Copernicus_DSM_COG_10_N54_00_E000_00_DEM.tif`
5. Uložit do `data/raw/dem/`

**Alternativa:** OpenTopography (https://opentopography.org) — stejná data, jednodušší stažení.

**Velikost:** ~200-400 MB celkem
**Licence:** Copernicus, attribution required

## 2. GEBCO 2023 (batometrie)

**Co:** Batometrická mřížka, 15 arc-second (~450m), celosvětová.

**Postup:**
1. Navigovat na https://www.gebco.net/data_and_products/gridded_bathymetry_data/
2. Zvolit "GEBCO_2023 Sub-ice Topo/Bathy"
3. Použít grid download tool — vybrat oblast:
   - West: -5.0°, East: 3.0°, South: 52.0°, North: 56.0°
   - (větší bbox pro celé východní pobřeží Anglie + Severní moře)
4. Stáhnout jako NetCDF nebo GeoTIFF
5. Uložit do `data/raw/gebco/`

**Velikost:** ~50-100 MB
**Licence:** Free, attribution required

## 3. OS Open Rivers

**Co:** Hydrografická síť Anglie a Walesu — říční toky jako liniové prvky.

**Postup:**
1. Navigovat na https://osdatahub.os.uk/downloads/open/OpenRivers
2. Stáhnout GeoPackage formát (celá Anglie)
3. Uložit do `data/raw/rivers/`

**Velikost:** ~50 MB
**Licence:** OGL (Open Government Licence) — free, attribution required
**CRS:** EPSG:27700 (British National Grid) — pipeline reprojektuje na EPSG:4326

## 4. ADS Postglacial 2013 (Lake Flixton + Sites)

**Co:** GIS data pro Lake Flixton a 20 archeologických lokalit z archivu Star Carr.

**Zdroj:** University of York (2018), Star Carr and Lake Flixton archives.
- DOI: [10.5284/1041580](https://doi.org/10.5284/1041580)
- Mapa: https://archaeologydataservice.ac.uk/archives/view/postglacial_2013/map.cfm
- Reference: Palmer et al. (2015); Taylor & Alison (2018); Milner et al. (2018)

**Postup:**
```bash
python 02b_download_ads.py
```
Skript automaticky stáhne 2 GML soubory do `data/raw/ads/`:
- `lake2_wgs84.gml` — polygon Lake Flixton (autorský obrys jezera)
- `sites_wgs84.gml` — 20 lokalit s polygonovou geometrií (Star Carr, Flixton Island, Seamer Carr atd.)

**Velikost:** ~100 KB celkem
**CRS:** WGS84 (EPSG:4326) — bez reprojekce
**Licence:** ADS open access, attribution required

## Verifikace

Po stažení ověřit:
```bash
ls data/raw/dem/*.tif       # DEM tiles
ls data/raw/gebco/*         # GEBCO grid
ls data/raw/rivers/*.gpkg   # OS Open Rivers
ls data/raw/ads/*.gml       # ADS Lake Flixton + sites
```

## Poznámky

- DEM tiles mohou mít různý naming convention dle zdroje
- GEBCO data mohou být v NetCDF (.nc) — pipeline zpracuje obojí
- OS Open Rivers jsou v British National Grid (EPSG:27700) — reprojekce je součástí pipeline
