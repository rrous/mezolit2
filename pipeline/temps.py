import requests

# --- NASTAVENÍ ---
API_KEY = " 8927919d5e24067088cd8a4c47a89ab2"
# BBox Yorkshire: West, South, East, North
PARAMS = {
    "demtype": "COP30",
    "west": -3.0,
    "south": 53.0,
    "east": 1.0,
    "north": 55.0,
    "outputFormat": "GTiff",
    "API_Key": API_KEY
}

URL = "https://portal.opentopography.org"

print("Stahuji Copernicus DEM pro Yorkshire z OpenTopography...")
response = requests.get(URL, params=PARAMS, stream=True)

if response.status_code == 200:
    with open("yorkshire_dem.tif", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Hotovo! Soubor uložen jako yorkshire_dem.tif")
else:
    print(f"Chyba: {response.status_code}")
    print(response.text)
