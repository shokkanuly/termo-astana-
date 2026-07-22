import requests
import random
import time
from app.database import get_db
import app.database as db_mod

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box around Bayterek / Nurzhol Boulevard
BBOX = (51.120, 71.410, 51.135, 71.445)

STREETS = [
    "пр. Мангилик Ел",
    "ул. Достык",
    "ул. Сыганак",
    "ул. Кунаева",
    "ул. Туркестан",
    "ул. Акмешит",
    "ул. Кабанбай батыра"
]

MATERIAL_PRESETS = [
    "modern_ventilated",
    "glass_curtain",
    "brick_soviet",
    "brezhnevka_panel",
    "khrushchyovka_panel"
]

LANDMARK_FOOTPRINTS = [
    {"id": "LM_BAITEREK", "name": "Baiterek Monument", "height": 97, "coords": [[71.4300, 51.1280], [71.4310, 51.1280], [71.4310, 51.1286], [71.4300, 51.1286], [71.4300, 51.1280]], "street": "Водно-зеленый бульвар, 1"},
    {"id": "LM_KHAN_SHATYR", "name": "Khan Shatyr Plaza", "height": 150, "coords": [[71.4045, 51.1315], [71.4075, 51.1315], [71.4075, 51.1335], [71.4045, 51.1335], [71.4045, 51.1315]], "street": "пр. Туран, 37"},
    {"id": "LM_AKORDA", "name": "Ak Orda Palace", "height": 80, "coords": [[71.4445, 51.1245], [71.4475, 51.1245], [71.4475, 51.1265], [71.4445, 51.1265], [71.4445, 51.1245]], "street": "ул. Мангилик Ел, 1"},
    {"id": "LM_ABU_DHABI", "name": "Abu Dhabi Plaza Tower", "height": 311, "coords": [[71.4320, 51.1212], [71.4342, 51.1212], [71.4342, 51.1228], [71.4320, 51.1228], [71.4320, 51.1212]], "street": "ул. Сыганак, 16"},
    {"id": "bld_kmg_1", "name": "KazMunayGas Head Office", "height": 75, "coords": [[71.4150, 51.1292], [71.4190, 51.1292], [71.4190, 51.1308], [71.4150, 51.1308], [71.4150, 51.1292]], "street": "ул. Кабанбай батыра, 19"},
    {"id": "bld_emerald_1", "name": "Emerald Towers Block A", "height": 210, "coords": [[71.4230, 51.1278], [71.4252, 51.1278], [71.4252, 51.1292], [71.4230, 51.1292], [71.4230, 51.1278]], "street": "ул. Достык, 8"},
    {"id": "bld_turan_1", "name": "Turan Ave 18 Complex", "height": 48, "coords": [[71.4035, 51.1345], [71.4055, 51.1345], [71.4055, 51.1358], [71.4035, 51.1358], [71.4035, 51.1345]], "street": "пр. Туран, 18"},
    {"id": "bld_turan_2", "name": "Turan Ave 24 Towers", "height": 72, "coords": [[71.4160, 51.1375], [71.4185, 51.1375], [71.4185, 51.1390], [71.4160, 51.1390], [71.4160, 51.1375]], "street": "пр. Туран, 24"},
    {"id": "bld_kabanbay_1", "name": "Kabanbay Batyr Ave 19", "height": 55, "coords": [[71.4200, 51.1310], [71.4225, 51.1310], [71.4225, 51.1322], [71.4200, 51.1322], [71.4200, 51.1310]], "street": "пр. Кабанбай батыра, 19"},
    {"id": "bld_kabanbay_2", "name": "Kabanbay Batyr Ave 27", "height": 85, "coords": [[71.4240, 51.1250], [71.4265, 51.1250], [71.4265, 51.1264], [71.4240, 51.1264], [71.4240, 51.1250]], "street": "пр. Кабанбай батыра, 27"},
    {"id": "bld_mangilik_1", "name": "Mangilik El Ave 12", "height": 64, "coords": [[71.4330, 51.1170], [71.4358, 51.1170], [71.4358, 51.1185], [71.4330, 51.1185], [71.4330, 51.1170]], "street": "пр. Мангилик Ел, 12"},
    {"id": "bld_dostyk_1", "name": "Dostyk St 5 Plaza", "height": 40, "coords": [[71.4295, 51.1290], [71.4315, 51.1290], [71.4315, 51.1302], [71.4295, 51.1302], [71.4295, 51.1290]], "street": "ул. Достык, 5"},
    {"id": "bld_highvill_1", "name": "Highvill Block A", "height": 95, "coords": [[71.4660, 51.1235], [71.4700, 51.1235], [71.4700, 51.1260], [71.4660, 51.1260], [71.4660, 51.1235]], "street": "ул. Ахмета Байтурсынова, 1"},
    {"id": "bld_opera_1", "name": "Astana Opera Theater", "height": 40, "coords": [[71.4115, 51.1330], [71.4145, 51.1330], [71.4145, 51.1350], [71.4115, 51.1350], [71.4115, 51.1330]], "street": "ул. Кунаева, 1"}
]

def fetch_osm_buildings():
    return generate_fallback_buildings()

def generate_fallback_buildings(count=30):
    """Generates realistic building footprints around Nurzhol Boulevard for offline safety."""
    print("Generating fallback building polygons...")
    elements = []
    
    # 1. Add precise landmark building footprints
    for idx, lm in enumerate(LANDMARK_FOOTPRINTS):
        geometry = [{"lat": pt[1], "lon": pt[0]} for pt in lm["coords"]]
        elements.append({
            "type": "way",
            "id": 2000000 + idx,
            "geometry": geometry,
            "tags": {
                "building": "commercial",
                "height": str(lm["height"]),
                "addr:street": lm["street"],
                "addr:housenumber": "1"
            }
        })

    # 2. Add surrounding central district residential/office blocks
    lat_center, lon_center = 51.1283, 71.4305
    random.seed(42)
    
    for i in range(count):
        lat = lat_center + random.uniform(-0.006, 0.006)
        lon = lon_center + random.uniform(-0.012, 0.012)
        
        w_lat = random.uniform(0.0004, 0.0008)
        w_lon = random.uniform(0.0006, 0.0012)
        
        geometry = [
            {"lat": lat - w_lat, "lon": lon - w_lon},
            {"lat": lat + w_lat, "lon": lon - w_lon},
            {"lat": lat + w_lat, "lon": lon + w_lon},
            {"lat": lat - w_lat, "lon": lon + w_lon},
            {"lat": lat - w_lat, "lon": lon - w_lon}
        ]
        
        levels = random.choice([7, 12, 16, 22, 28])
        elements.append({
            "type": "way",
            "id": 1000000 + i,
            "geometry": geometry,
            "tags": {
                "building": "residential" if i % 2 == 0 else "apartments",
                "building:levels": str(levels),
                "addr:street": random.choice(STREETS),
                "addr:housenumber": str(random.randint(1, 99)),
            }
        })
    return elements

def get_element_geometry(el):
    if el.get("type") == "way":
        return el.get("geometry", [])
    elif el.get("type") == "relation":
        outer_points = []
        for member in el.get("members", []):
            if member.get("role") == "outer" and member.get("geometry"):
                outer_points.extend(member["geometry"])
        return outer_points
    return []

def get_polygon_stats(geom_points, height):
    kx = 111320.0 * 0.6276
    ky = 111320.0
    
    pts = []
    for p in geom_points:
        pts.append((p['lon'] * kx, p['lat'] * ky))
        
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    roof_area = abs(area) / 2.0
    
    perimeter = 0.0
    for i in range(n - 1):
        dx = pts[i+1][0] - pts[i][0]
        dy = pts[i+1][1] - pts[i][1]
        perimeter += (dx*dx + dy*dy)**0.5
        
    facade_area = perimeter * height
    window_area = facade_area * 0.22
    return roof_area, facade_area, window_area

def ingest_data():
    import json
    elements = fetch_osm_buildings()
    if not elements:
        print("No elements to ingest.")
        return

    with get_db() as conn:
        if db_mod.DB_BACKEND == "sqlite":
            cur = conn.cursor()
            print("Clearing SQLite buildings table...")
            cur.execute("DELETE FROM buildings;")
            inserted_count = 0
            for el in elements:
                geom_points = get_element_geometry(el)
                if not geom_points or len(geom_points) < 3:
                    continue
                if geom_points[0] != geom_points[-1]:
                    geom_points.append(geom_points[0])
                
                osm_id = str(el.get("id"))
                b_id = f"bld_{osm_id}"
                tags = el.get("tags", {})
                
                height = 15.0
                if "height" in tags:
                    try:
                        height = float(tags["height"])
                    except ValueError:
                        pass
                elif "building:levels" in tags:
                    try:
                        height = float(tags["building:levels"]) * 3.2
                    except ValueError:
                        pass
                else:
                    height = float(random.choice([12, 18, 25, 30, 48, 60]))

                preset = random.choices(
                    MATERIAL_PRESETS,
                    weights=[0.40, 0.20, 0.20, 0.10, 0.10],
                    k=1
                )[0]
                
                street = tags.get("addr:street")
                house = tags.get("addr:housenumber")
                address = f"{street}, {house}" if street and house else f"{random.choice(STREETS)}, {random.randint(1, 100)}"
                district = "Есиль"
                
                roof_area, facade_area, window_area = get_polygon_stats(geom_points, height)
                geom_json_str = json.dumps({
                    "type": "Polygon",
                    "coordinates": [[ [pt['lon'], pt['lat']] for pt in geom_points ]]
                })
                
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO buildings (id, osm_id, height, material, address, district, facade_area_m2, roof_area_m2, window_area_m2, geom_geojson)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (b_id, osm_id, height, preset, address, district, facade_area, roof_area, window_area, geom_json_str))
                    inserted_count += 1
                except Exception as e:
                    print(f"Error inserting SQLite building {b_id}: {e}")
                    continue
            print(f"Inserted {inserted_count} buildings into SQLite.")

if __name__ == "__main__":
    ingest_data()
