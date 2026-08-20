import os
import mapbox_vector_tile
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, MultiPolygon

INPUT_ROOT = r"Lalova_tiles"
OUTPUT_ROOT = r"Lalova_png"

TILE_SIZE = 256
EXTENT = 4096

converted = 0
errors = 0
labels = 0


def get_font(zoom):
    font_path = r"C:\Windows\Fonts\arial.ttf"

    if zoom >= 18:
        size = 9
    elif zoom >= 17:
        size = 8
    elif zoom >= 16:
        size = 7
    else:
        size = 6

    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()


def geometry_to_polygons(geometry):
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon":
        return [Polygon(ring) for ring in [coordinates[0]] if len(ring) >= 4]

    if geometry_type == "MultiPolygon":
        result = []

        for polygon in coordinates:
            if polygon and len(polygon[0]) >= 4:
                result.append(Polygon(polygon[0]))

        return result

    return []


def draw_ring(draw, ring):
    scale = TILE_SIZE / EXTENT

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

    for polygon in polygons:
        for ring in polygon:
            draw_ring(draw, ring)


def add_label(draw, geometry, text, zoom):
    global labels

    if zoom < 15:
        return

    if not text:
        return

    font = get_font(zoom)

    polygons = geometry_to_polygons(geometry)

    if not polygons:
        return

    # Alegem cel mai mare poligon
    polygon = max(polygons, key=lambda p: p.area)

    if polygon.is_empty:
        return

    # Punct garantat în interiorul poligonului
    point = polygon.representative_point()

    x = point.x * TILE_SIZE / EXTENT
    y = TILE_SIZE - (point.y * TILE_SIZE / EXTENT)

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    min_x, min_y, max_x, max_y = polygon.bounds

    polygon_width = (max_x - min_x) * TILE_SIZE / EXTENT
    polygon_height = (max_y - min_y) * TILE_SIZE / EXTENT

    # Nu punem text dacă parcela este prea mică
    if polygon_width < text_width + 6:
        return

    if polygon_height < text_height + 6:
        return

    # Evităm etichete în afara imaginii
    if x < 2 or x > TILE_SIZE - 2:
        return

    if y < 2 or y > TILE_SIZE - 2:
        return

    tx = x - text_width / 2
    ty = y - text_height / 2

    # Halo alb pentru lizibilitate
    draw.text(
        (tx, ty),
        text,
        font=font,
        fill=(0, 0, 0, 255),
        stroke_width=2,
        stroke_fill=(255, 255, 255, 230)
    )

    labels += 1


def convert_tile(input_file, output_file):
    global labels

    with open(input_file, "rb") as f:
        data = f.read()

    tile = mapbox_vector_tile.decode(data)

    image = Image.new(
        "RGBA",
        (TILE_SIZE, TILE_SIZE),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(image)

    zoom = int(os.path.relpath(
        input_file,
        INPUT_ROOT
    ).split(os.sep)[0])

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

            # Contur cadastral
            draw_geometry(draw, geometry)

            feature_count += 1

            # Cod cadastral
            properties = feature.get("properties", {})
            cod = properties.get("codcadastral")

            if cod:
                add_label(
                    draw,
                    geometry,
                    str(cod).strip(),
                    zoom
                )

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
print("   LALOVA PBF -> PNG + COD CADASTRAL")
print("==============================================")
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

            if converted % 100 == 0:
                print(
                    f"[PROGRES] {converted} tile-uri convertite..."
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
print("              FINALIZAT")
print("==============================================")
print()
print("Tile-uri convertite :", converted)
print("Erori                :", errors)
print("Etichete cadastrale  :", labels)
print()
print("PNG-urile sunt in:")
print(os.path.abspath(OUTPUT_ROOT))
print()