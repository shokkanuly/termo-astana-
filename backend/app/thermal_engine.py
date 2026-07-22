import random
from app.database import get_db

# Thermal Resistance Coefficients (R-value in m²·°C/W) based on SNiP building codes
MATERIAL_R_MAPPING = {
    "brick_soviet": 1.2,
    "glass_curtain": 3.5,
    "modern_ventilated": 3.5,
    "brezhnevka_panel": 0.8,
    "khrushchyovka_panel": 0.8,
    "panel": 0.8
}

def calculate_baseline_heat_loss(facade_area: float, material: str, t_out: float) -> float:
    """
    Calculates theoretical Baseline Heat Loss in Watts.
    Formula: Loss = (Facade_Area / R_value) * (T_in - T_out)
    """
    r_value = MATERIAL_R_MAPPING.get(material, 1.0)
    t_in = 21.0
    loss_w = (facade_area / r_value) * (t_in - t_out)
    return max(loss_w, 0.0)

def load_simulation_buildings():
    """
    Loads up to 100 representative buildings from the database to stream telemetry for,
    ensuring we do not overwhelm the React frontend state machine.
    """
    from app.database import DB_BACKEND
    import json
    
    buildings = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if DB_BACKEND == "sqlite":
                cur.execute("""
                    SELECT id, osm_id, material, address, district, facade_area_m2, geom_geojson
                    FROM buildings
                    ORDER BY id ASC
                    LIMIT 100;
                """)
                rows = cur.fetchall()
                for row in rows:
                    b_id, osm_id, material, address, district, facade_area, geom_json_str = row
                    lon, lat = 71.4305, 51.1283
                    if geom_json_str:
                        try:
                            geom = json.loads(geom_json_str)
                            coords = geom["coordinates"][0]
                            lons = [c[0] for c in coords]
                            lats = [c[1] for c in coords]
                            lon = sum(lons) / len(lons)
                            lat = sum(lats) / len(lats)
                        except Exception:
                            pass
                    buildings.append({
                        "building_id": b_id,
                        "node_id": f"NODE-{osm_id}",
                        "material": material,
                        "address": address,
                        "district": district,
                        "facade_area": float(facade_area) if facade_area else 1200.0,
                        "lon": lon,
                        "lat": lat
                    })
            else:
                cur.execute("""
                    SELECT id, osm_id, material, address, district, facade_area_m2, 
                           COALESCE(ST_X(ST_Centroid(geom)), 71.4305), 
                           COALESCE(ST_Y(ST_Centroid(geom)), 51.1283)
                    FROM buildings
                    ORDER BY id ASC
                    LIMIT 100;
                """)
                rows = cur.fetchall()
                for row in rows:
                    b_id, osm_id, material, address, district, facade_area, lon, lat = row
                    buildings.append({
                        "building_id": b_id,
                        "node_id": f"NODE-{osm_id}",
                        "material": material,
                        "address": address,
                        "district": district,
                        "facade_area": float(facade_area) if facade_area else 1200.0,
                        "lon": float(lon),
                        "lat": float(lat)
                    })
    except Exception as e:
        print(f"Thermal Engine: Error loading buildings from DB: {e}")
    
    # Fallback if DB is empty during initialization
    if not buildings:
        buildings.append({
            "building_id": "bld_fallback_01",
            "node_id": "NODE-FALLBACK",
            "material": "brick_soviet",
            "address": "ул. Достык, 1",
            "district": "Есиль",
            "facade_area": 1500.0,
            "lon": 71.4305,
            "lat": 51.1283
        })
    return buildings
