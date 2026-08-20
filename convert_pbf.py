import os
import mapbox_vector_tile
from PIL import Image, ImageDraw

INPUT_ROOT = r"Lalova_tiles"
OUTPUT_ROOT = r"Lalova_png"

TILE_SIZE = 256
EXTENT = 4096

converted = 0
skipped = 0
errors = 0


def draw_geometry(draw, geometry):
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if not coordinates:
        return

    if geometry_type == "Polygon":
        polygons = [coordinates]

    elif geometry_type == "MultiPolygon":
        polygons = coordinates

    else:
        return

    scale = TILE_SIZE / EXTENT

    for polygon in polygons:
        for ring in polygon:

            points = []

            for x, y in ring:
                px = x * scale
                py = TILE_SIZE - (y * scale)
                points.append((px, py))

            if len(points) >= 2:
                draw.line(
                    points,
                    fill=(255, 0, 0, 255),
                    width=1
                )


def convert_tile(input_file, output_file):

    with open(input_file, "rb") as f:
        data = f.read()

    tile = mapbox_vector_tile.decode(data)

    image = Image.new(
        "RGBA",
        (TILE_SIZE, TILE_SIZE),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(image)

    feature_count = 0

    for layer in tile.values():

        for feature in layer.get("features", []):

            geometry = feature.get("geometry")

            if not geometry:
                continue

            if geometry.get("type") not in (
                "Polygon",
                "MultiPolygon"
            ):
                continue

            draw_geometry(draw, geometry)
            feature_count += 1

    os.makedirs(
        os.path.dirname(output_file),
        exist_ok=True
    )

    image.save(
        output_file,
        "PNG"
    )

    return feature_count


print()
print("==============================================")
print("   LALOVA PBF -> PNG")
print("==============================================")
print()
print("Sursa :", INPUT_ROOT)
print("Iesire:", OUTPUT_ROOT)
print()

for root, dirs, files in os.walk(INPUT_ROOT):

    for filename in files:

        if not filename.lower().endswith(".pbf"):
            continue

        input_file = os.path.join(root, filename)

        relative_path = os.path.relpath(
            input_file,
            INPUT_ROOT
        )

        output_file = os.path.join(
            OUTPUT_ROOT,
            os.path.splitext(relative_path)[0] + ".png"
        )

        try:

            features = convert_tile(
                input_file,
                output_file
            )

            converted += 1

            print(
                f"[OK] {relative_path} -> "
                f"{os.path.relpath(output_file, OUTPUT_ROOT)} "
                f"({features} obiecte)"
            )

        except Exception as e:

            errors += 1

            print()
            print("[EROARE]")
            print(input_file)
            print(e)
            print()


print()
print("==============================================")
print("            FINALIZAT")
print("==============================================")
print()
print("Convertite :", converted)
print("Erori       :", errors)
print()
print("PNG-urile sunt in:")
print(os.path.abspath(OUTPUT_ROOT))
print()