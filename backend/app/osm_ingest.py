import requests
import random
import time
from app.database import get_db

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box around Bayterek / Nurzhol Boulevard
# min_lat, min_lon, max_lat, max_lon
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

def fetch_osm_buildings():
    query = f"""
    [out:json][timeout:30];
    (
      way["building"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
      relation["building"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
    );
    out geom;
    """
    try:
        print(f"Querying Overpass API for Astana buildings in bounds: {BBOX}...")
        response = requests.post(OVERPASS_URL, data={"data": query}, timeout=15)
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", [])
        print(f"Overpass API returned {len(elements)} elements.")
        if len(elements) > 5:
            return elements
    except Exception as e:
        print(f"Failed to fetch from Overpass API: {e}. Using fallback local coordinates generator.")
    return generate_fallback_buildings()

def generate_fallback_buildings(count=40):
    """Generates realistic building footprints around Nurzhol Boulevard for offline safety."""
    print("Generating fallback building polygons...")
    elements = []
    # Anchor point: Bayterek (51.1283, 71.4305)
    lat_center, lon_center = 51.1283, 71.4305
    random.seed(42)  # Stable generator
    
    for i in range(count):
        lat = lat_center + random.uniform(-0.007, 0.007)
        lon = lon_center + random.uniform(-0.015, 0.015)
        
        # Create a small rectangular polygon footprint
        w_lat = random.uniform(0.0003, 0.0007)
        w_lon = random.uniform(0.0005, 0.0011)
        
        geometry = [
            {"lat": lat - w_lat, "lon": lon - w_lon},
            {"lat": lat + w_lat, "lon": lon - w_lon},
            {"lat": lat + w_lat, "lon": lon + w_lon},
            {"lat": lat - w_lat, "lon": lon + w_lon},
            {"lat": lat - w_lat, "lon": lon - w_lon} # Close polygon
        ]
        
        levels = random.choice([5, 9, 12, 16, 22])
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

def ingest_data():
    elements = fetch_osm_buildings()
    if not elements:
        print("No elements to ingest.")
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            # Clear existing data if any (or update)
            cur.execute("TRUNCATE TABLE buildings CASCADE;")
            
            inserted_count = 0
            for el in elements:
                geom_points = el.get("geometry", [])
                if not geom_points or len(geom_points) < 3:
                    continue
                
                # Make sure the polygon is closed
                if geom_points[0] != geom_points[-1]:
                    geom_points.append(geom_points[0])
                
                # Build WKT Polygon: POLYGON((lon lat, lon lat, ...))
                wkt_coords = ", ".join([f"{pt['lon']} {pt['lat']}" for pt in geom_points])
                wkt = f"POLYGON(({wkt_coords}))"
                
                osm_id = str(el.get("id"))
                b_id = f"bld_{osm_id}"
                
                tags = el.get("tags", {})
                
                # Height calculation
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

                # Material Preset
                preset = random.choices(
                    MATERIAL_PRESETS,
                    weights=[0.40, 0.20, 0.20, 0.10, 0.10], # Prefer modern on Esil
                    k=1
                )[0]
                
                # Address
                street = tags.get("addr:street")
                house = tags.get("addr:housenumber")
                if street and house:
                    address = f"{street}, {house}"
                else:
                    address = f"{random.choice(STREETS)}, {random.randint(1, 100)}"
                
                district = "Есиль"
                
                # Insert building with PostGIS ST_GeomFromText using SRID 4326
                try:
                    cur.execute("""
                        INSERT INTO buildings (id, osm_id, height, material, address, district, geom)
                        VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                        ON CONFLICT (id) DO NOTHING;
                    """, (b_id, osm_id, height, preset, address, district, wkt))
                    inserted_count += 1
                except Exception as e:
                    print(f"Error inserting building {b_id}: {e}")
                    conn.rollback()
                    continue
            
            print(f"Inserted {inserted_count} building footprint polygons. Calculating physical areas via PostGIS geography...")
            
            # PostGIS geographical area and length computation (uses meters)
            cur.execute("""
                UPDATE buildings SET
                    roof_area_m2 = ST_Area(geom::geography),
                    facade_area_m2 = ST_Perimeter(geom::geography) * height,
                    window_area_m2 = ST_Perimeter(geom::geography) * height * 0.22;
            """)
            
    print("OSM building ingestion completed successfully.")

if __name__ == "__main__":
    ingest_data()
