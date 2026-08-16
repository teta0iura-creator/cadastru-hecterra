import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw
from pyproj import Transformer
from shapely.geometry import shape, box
from shapely.ops import transform


# ============================================================
# CONFIGURARE
# ============================================================

INPUT_FILE = Path("data/lalova.geojson")
OUTPUT_DIR = Path("lalova_tiles")

MIN_ZOOM = 12
MAX_ZOOM = 18

TILE_SIZE = 256

# Grosimea liniei parcelei
LINE_WIDTH = 2

# Transparent background
BACKGROUND = (0, 0, 0, 0)

# Culoarea conturului cadastrului
LINE_COLOR = (255, 0, 0, 220)


# ============================================================
# COORDONATE
# ============================================================

# Datele WFS sunt în EPSG:4026.
# Tile-urile XYZ Web Mercator folosesc EPSG:3857.

transformer = Transformer.from_crs(
    "EPSG:4026",
    "EPSG:3857",
    always_xy=True
)


def transform_geometry(geometry):
    return transform(
        transformer.transform,
        geometry
    )


# ============================================================
# XYZ TILE CALCUL
# ============================================================

WEB_MERCATOR_HALF_WORLD = 20037508.342789244


def lonlat_to_tile(lon, lat, zoom):
    """
    Transformă lon/lat în coordonate XYZ tile.
    """

    lat = max(min(lat, 85.05112878), -85.05112878)

    n = 2 ** zoom

    x = int((lon + 180.0) / 360.0 * n)

    lat_rad = math.radians(lat)

    y = int(
        (
            1.0
            - math.asinh(math.tan(lat_rad)) / math.pi
        )
        / 2.0
        * n
    )

    return x, y


def mercator_to_tile_xy(x, y, zoom):
    """
    Transformă coordonate EPSG:3857 în pixeli XYZ.
    """

    n = 2 ** zoom

    px = (
        (x + WEB_MERCATOR_HALF_WORLD)
        / (2 * WEB_MERCATOR_HALF_WORLD)
        * n
        * TILE_SIZE
    )

    py = (
        (WEB_MERCATOR_HALF_WORLD - y)
        / (2 * WEB_MERCATOR_HALF_WORLD)
        * n
        * TILE_SIZE
    )

    return px, py


# ============================================================
# GEOMETRIE → PIXELI
# ============================================================

def draw_linestring(draw, coordinates, zoom, tile_x, tile_y):
    points = []

    for x, y in coordinates:

        px, py = mercator_to_tile_xy(
            x,
            y,
            zoom
        )

        tile_px = px - tile_x * TILE_SIZE
        tile_py = py - tile_y * TILE_SIZE

        points.append(
            (
                round(tile_px),
                round(tile_py)
            )
        )

    if len(points) >= 2:
        draw.line(
            points,
            fill=LINE_COLOR,
            width=LINE_WIDTH,
            joint="curve"
        )


def draw_polygon(draw, polygon, zoom, tile_x, tile_y):

    exterior = list(
        polygon.exterior.coords
    )

    draw_linestring(
        draw,
        exterior,
        zoom,
        tile_x,
        tile_y
    )

    for interior in polygon.interiors:

        draw_linestring(
            draw,
            list(interior.coords),
            zoom,
            tile_x,
            tile_y
        )


def draw_geometry(draw, geometry, zoom, tile_x, tile_y):

    if geometry.is_empty:
        return

    geom_type = geometry.geom_type

    if geom_type == "Polygon":

        draw_polygon(
            draw,
            geometry,
            zoom,
            tile_x,
            tile_y
        )

    elif geom_type == "MultiPolygon":

        for polygon in geometry.geoms:

            draw_polygon(
                draw,
                polygon,
                zoom,
                tile_x,
                tile_y
            )

    elif geom_type == "GeometryCollection":

        for geom in geometry.geoms:

            draw_geometry(
                draw,
                geom,
                zoom,
                tile_x,
                tile_y
            )


# ============================================================
# ÎNCĂRCARE GEOJSON
# ============================================================

print("=" * 60)
print("GENERARE TILE-URI CADASTRU LALOVA")
print("=" * 60)

print()
print(f"Fișier intrare: {INPUT_FILE}")
print()

if not INPUT_FILE.exists():

    raise FileNotFoundError(
        f"Nu există fișierul: {INPUT_FILE}"
    )


with open(
    INPUT_FILE,
    "r",
    encoding="utf-8"
) as f:

    geojson = json.load(f)


features = geojson.get(
    "features",
    []
)

print(
    f"Parcele găsite: {len(features)}"
)

if not features:

    raise RuntimeError(
        "GeoJSON-ul nu conține parcele."
    )


# ============================================================
# TRANSFORMARE ÎN EPSG:3857
# ============================================================

print()
print("Transformare EPSG:4026 → EPSG:3857...")

geometries = []

for index, feature in enumerate(features, start=1):

    geometry_data = feature.get(
        "geometry"
    )

    if not geometry_data:
        continue

    geometry = shape(
        geometry_data
    )

    if geometry.is_empty:
        continue

    try:

        geometry_3857 = transform_geometry(
            geometry
        )

        geometries.append(
            geometry_3857
        )

    except Exception as e:

        print(
            f"EROARE la parcela {index}: {e}"
        )


print(
    f"Geometrii procesate: {len(geometries)}"
)


# ============================================================
# EXTINDERE TOTALĂ
# ============================================================

print()
print("Calcul extindere...")

minx = min(
    geometry.bounds[0]
    for geometry in geometries
)

miny = min(
    geometry.bounds[1]
    for geometry in geometries
)

maxx = max(
    geometry.bounds[2]
    for geometry in geometries
)

maxy = max(
    geometry.bounds[3]
    for geometry in geometries
)

print()
print(
    f"X: {minx:.2f} → {maxx:.2f}"
)

print(
    f"Y: {miny:.2f} → {maxy:.2f}"
)


# ============================================================
# GENERARE TILE-URI
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


for zoom in range(
    MIN_ZOOM,
    MAX_ZOOM + 1
):

    print()
    print(
        "=" * 60
    )

    print(
        f"ZOOM {zoom}"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Calculăm tile-urile care acoperă extinderea
    # --------------------------------------------------------

    min_lon_tile = (
        minx + WEB_MERCATOR_HALF_WORLD
    ) / (
        2 * WEB_MERCATOR_HALF_WORLD
    )

    max_lon_tile = (
        maxx + WEB_MERCATOR_HALF_WORLD
    ) / (
        2 * WEB_MERCATOR_HALF_WORLD
    )

    min_lat_tile = (
        WEB_MERCATOR_HALF_WORLD - maxy
    ) / (
        2 * WEB_MERCATOR_HALF_WORLD
    )

    max_lat_tile = (
        WEB_MERCATOR_HALF_WORLD - miny
    ) / (
        2 * WEB_MERCATOR_HALF_WORLD
    )

    n = 2 ** zoom

    min_x = max(
        0,
        int(min_lon_tile * n)
    )

    max_x = min(
        n - 1,
        int(max_lon_tile * n)
    )

    min_y = max(
        0,
        int(min_lat_tile * n)
    )

    max_y = min(
        n - 1,
        int(max_lat_tile * n)
    )

    total_tiles = (
        (max_x - min_x + 1)
        *
        (max_y - min_y + 1)
    )

    print(
        f"Tile-uri estimate: {total_tiles}"
    )

    generated = 0

    # --------------------------------------------------------
    # Pentru fiecare tile
    # --------------------------------------------------------

    for tile_x in range(
        min_x,
        max_x + 1
    ):

        for tile_y in range(
            min_y,
            max_y + 1
        ):

            # ------------------------------------------------
            # Extinderea tile-ului în EPSG:3857
            # ------------------------------------------------

            world_px_left = (
                tile_x * TILE_SIZE
            )

            world_px_right = (
                (tile_x + 1) * TILE_SIZE
            )

            world_py_top = (
                tile_y * TILE_SIZE
            )

            world_py_bottom = (
                (tile_y + 1) * TILE_SIZE
            )

            world_size = (
                2
                * WEB_MERCATOR_HALF_WORLD
            )

            x_left = (
                world_px_left
                /
                (n * TILE_SIZE)
                *
                world_size
                -
                WEB_MERCATOR_HALF_WORLD
            )

            x_right = (
                world_px_right
                /
                (n * TILE_SIZE)
                *
                world_size
                -
                WEB_MERCATOR_HALF_WORLD
            )

            y_top = (
                WEB_MERCATOR_HALF_WORLD
                -
                world_py_top
                /
                (n * TILE_SIZE)
                *
                world_size
            )

            y_bottom = (
                WEB_MERCATOR_HALF_WORLD
                -
                world_py_bottom
                /
                (n * TILE_SIZE)
                *
                world_size
            )

            tile_bbox = box(
                x_left,
                y_bottom,
                x_right,
                y_top
            )

            # ------------------------------------------------
            # Verificăm dacă există parcele în tile
            # ------------------------------------------------

            relevant_geometries = []

            for geometry in geometries:

                if geometry.intersects(
                    tile_bbox
                ):

                    relevant_geometries.append(
                        geometry
                    )

            if not relevant_geometries:

                continue

            # ------------------------------------------------
            # Imagine transparentă
            # ------------------------------------------------

            image = Image.new(
                "RGBA",
                (
                    TILE_SIZE,
                    TILE_SIZE
                ),
                BACKGROUND
            )

            draw = ImageDraw.Draw(
                image
            )

            # ------------------------------------------------
            # Desenăm parcelele
            # ------------------------------------------------

            for geometry in relevant_geometries:

                draw_geometry(
                    draw,
                    geometry,
                    zoom,
                    tile_x,
                    tile_y
                )

            # ------------------------------------------------
            # Salvare
            # ------------------------------------------------

            tile_dir = (
                OUTPUT_DIR
                / str(zoom)
                / str(tile_x)
            )

            tile_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            tile_file = (
                tile_dir
                / f"{tile_y}.png"
            )

            image.save(
                tile_file,
                "PNG",
                optimize=True
            )

            generated += 1

    print(
        f"Tile-uri generate: {generated}"
    )


# ============================================================
# FINAL
# ============================================================

print()
print("=" * 60)
print("GENERARE FINALIZATĂ")
print("=" * 60)

print()
print(
    f"Director: {OUTPUT_DIR}"
)

print()
print(
    "Structura este compatibilă cu XYZ:"
)

print(
    "lalova_tiles/{z}/{x}/{y}.png"
)

print()
print(
    "Poți folosi această adresă în Hecterra:"
)

print(
    "https://teta0iura-creator.github.io/"
    "cadastru-hecterra/"
    "lalova_tiles/{z}/{x}/{y}.png"
)

print()