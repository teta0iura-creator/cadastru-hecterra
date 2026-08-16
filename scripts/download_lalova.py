import json
import time
from pathlib import Path

import requests


# ============================================================
# CONFIGURARE
# ============================================================

WFS_URL = "https://geodata.gov.md/geoserver/cadastru_data/wfs"

TYPE_NAME = "cadastru_data:terenuri"

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "lalova.geojson"

# EPSG folosit de geometria cadastrală returnată de WFS
CRS = "EPSG:4026"

# ------------------------------------------------------------
# ZONA LALOVA
#
# Valorile sunt în EPSG:4026.
# Sunt intenționat puțin mai largi decât zona verificată
# pentru parcelele 67243040184 etc.
#
# După ce obținem limita oficială a comunei, aceste valori
# vor fi înlocuite automat cu limita reală.
# ------------------------------------------------------------

MIN_X = 242000
MAX_X = 247000

MIN_Y = 267000
MAX_Y = 274000

# Dimensiunea fiecărei bucăți.
# Mai mic = mai sigur pentru server.
CELL_SIZE = 1000

# Câte obiecte cerem maxim într-o singură solicitare.
COUNT = 1000

TIMEOUT = 120

SLEEP_BETWEEN_REQUESTS = 0.5


# ============================================================
# FUNCȚII
# ============================================================

def make_bbox(minx, miny, maxx, maxy):
    return f"{minx},{miny},{maxx},{maxy},{CRS}"


def download_cell(minx, miny, maxx, maxy):
    """
    Descarcă parcelele dintr-o singură celulă BBOX.
    """

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": CRS,
        "bbox": make_bbox(minx, miny, maxx, maxy),
        "count": COUNT,
    }

    print(
        f"  BBOX: "
        f"{minx},{miny} -> {maxx},{maxy}"
    )

    try:
        response = requests.get(
            WFS_URL,
            params=params,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as e:
        print(f"  EROARE HTTP: {e}")
        return []

    except ValueError as e:
        print(f"  EROARE JSON: {e}")
        print(response.text[:500])
        return []

    features = data.get("features", [])

    print(f"  Găsite: {len(features)} parcele")

    return features


def feature_key(feature):
    """
    Creează o cheie unică pentru eliminarea duplicatelor.
    """

    if feature.get("id"):
        return feature["id"]

    properties = feature.get("properties", {})

    cadastral = properties.get("codcadastral")

    if cadastral:
        return str(cadastral)

    return json.dumps(
        feature,
        sort_keys=True,
        ensure_ascii=False,
    )


def save_geojson(features):
    """
    Salvează toate parcelele într-un GeoJSON.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    geojson = {
        "type": "FeatureCollection",
        "name": "lalova_terenuri",
        "crs": {
            "type": "name",
            "properties": {
                "name": f"urn:ogc:def:crs:EPSG::{CRS.split(':')[1]}"
            },
        },
        "features": features,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            geojson,
            f,
            ensure_ascii=False,
        )

    print()
    print("==========================================")
    print("DESCĂRCARE FINALIZATĂ")
    print("==========================================")
    print(f"Parcele: {len(features)}")
    print(f"Fișier:  {OUTPUT_FILE}")
    print("==========================================")


# ============================================================
# PROGRAM PRINCIPAL
# ============================================================

def main():

    print()
    print("==========================================")
    print(" DESCĂRCARE CADASTRU - LALOVA")
    print("==========================================")
    print(f"WFS:       {WFS_URL}")
    print(f"Layer:     {TYPE_NAME}")
    print(f"CRS:       {CRS}")
    print(
        f"Zonă:      "
        f"{MIN_X},{MIN_Y} -> {MAX_X},{MAX_Y}"
    )
    print()

    all_features = {}

    total_cells = (
        ((MAX_X - MIN_X) // CELL_SIZE) + 1
    ) * (
        ((MAX_Y - MIN_Y) // CELL_SIZE) + 1
    )

    cell_number = 0

    for x in range(
        MIN_X,
        MAX_X,
        CELL_SIZE,
    ):

        for y in range(
            MIN_Y,
            MAX_Y,
            CELL_SIZE,
        ):

            cell_number += 1

            print(
                f"[{cell_number}/{total_cells}]"
            )

            features = download_cell(
                x,
                y,
                x + CELL_SIZE,
                y + CELL_SIZE,
            )

            for feature in features:

                key = feature_key(feature)

                all_features[key] = feature

            print(
                f"  Total unic până acum: "
                f"{len(all_features)}"
            )

            time.sleep(
                SLEEP_BETWEEN_REQUESTS
            )

    save_geojson(
        list(all_features.values())
    )


if __name__ == "__main__":
    main()
