"""
Thermal physics engine — Fourier's Law via R-value model.

Q = (A · ΔT) / R_total   [Watts]
"""

INSIDE_TEMP = 22.0
OUTSIDE_TEMP_CRITICAL = -40.0
HEATING_SEASON_DAYS = 213
HEATING_TARIFF_KWH = 12.5
HOURS_PER_MONTH = 730

SNIP_REQUIRED_U = {
    "walls": 0.31,
    "roof": 0.22,
    "windows": 1.30,
}

MATERIAL_PRESETS = {
    "khrushchyovka_panel": {
        "label": "Хрущёвка (панель 220мм)",
        "description": "Советская панель без утепления",
        "layers": [
            {"name": "железобетон", "r": 0.11},
            {"name": "воздушный зазор", "r": 0.18},
            {"name": "штукатурка", "r": 0.04},
        ],
        "u_values": {"walls": 1.40, "roof": 0.90, "windows": 2.60},
        "insulation_upgrade": "Пенополиуретан 100мм + тройной стеклопакет",
        "insulation_cost_per_m2": 5200,
    },
    "brezhnevka_panel": {
        "label": "Брежневка (улучшенная панель)",
        "description": "Панель 300мм с минимальной изоляцией",
        "layers": [
            {"name": "железобетон", "r": 0.15},
            {"name": "минвата 50мм", "r": 1.25},
            {"name": "штукатурка", "r": 0.04},
        ],
        "u_values": {"walls": 0.85, "roof": 0.65, "windows": 2.20},
        "insulation_upgrade": "Минвата 150мм + энергоэффективные окна",
        "insulation_cost_per_m2": 4500,
    },
    "brick_soviet": {
        "label": "Кирпич советский (2.5 кирпича)",
        "description": "Кирпичная кладка без утеплителя",
        "layers": [
            {"name": "кирпич", "r": 0.52},
            {"name": "штукатурка", "r": 0.04},
        ],
        "u_values": {"walls": 0.95, "roof": 0.70, "windows": 2.40},
        "insulation_upgrade": "Минвата 120мм + замена окон",
        "insulation_cost_per_m2": 4800,
    },
    "modern_ventilated": {
        "label": "Современный вентфасад",
        "description": "Кирпич + вентилируемый фасад (Левый берег)",
        "layers": [
            {"name": "кирпич", "r": 0.35},
            {"name": "минвата 100мм", "r": 2.50},
            {"name": "воздушный зазор", "r": 0.18},
            {"name": "композит", "r": 0.02},
        ],
        "u_values": {"walls": 0.38, "roof": 0.24, "windows": 1.50},
        "insulation_upgrade": "Дополнительная минвата 50мм + Low-E стекло",
        "insulation_cost_per_m2": 3200,
    },
    "glass_curtain": {
        "label": "Стеклянный curtain-wall",
        "description": "Высотка Левого берега, стекло + композит",
        "layers": [
            {"name": "алюминий + стекло", "r": 0.22},
            {"name": "воздушный зазор", "r": 0.18},
        ],
        "u_values": {"walls": 0.55, "roof": 0.30, "windows": 1.80},
        "insulation_upgrade": "Замена на тройной Low-E стеклопакет",
        "insulation_cost_per_m2": 8500,
    },
}


def r_total_from_preset(preset_key: str) -> float:
    preset = MATERIAL_PRESETS[preset_key]
    return sum(layer["r"] for layer in preset["layers"])


def calculate_q_watts(area_m2: float, delta_t: float, r_total: float) -> float:
    if r_total <= 0:
        return 0.0
    return (area_m2 * delta_t) / r_total


def calculate_heat_loss(building: dict, temp_out: float) -> dict:
    delta_t = INSIDE_TEMP - temp_out
    u = building["u_values"]

    wall_w = u["walls"] * building["facade_area_m2"] * delta_t
    roof_w = u["roof"] * building["roof_area_m2"] * delta_t
    window_w = u["windows"] * building["window_area_m2"] * delta_t
    total_w = wall_w + roof_w + window_w

    r_total = r_total_from_preset(building["material_preset"])

    return {
        "total_kw": round(total_w / 1000.0, 2),
        "total_watts": round(total_w, 1),
        "breakdown": {
            "walls_kw": round(wall_w / 1000.0, 2),
            "roof_kw": round(roof_w / 1000.0, 2),
            "windows_kw": round(window_w / 1000.0, 2),
        },
        "delta_t": delta_t,
        "r_total": round(r_total, 3),
    }


def severity_from_q(q_kw: float) -> str:
    if q_kw >= 120:
        return "CRITICAL"
    if q_kw >= 80:
        return "HIGH"
    if q_kw >= 40:
        return "MODERATE"
    return "LOW"


def severity_color(severity: str) -> str:
    return {
        "CRITICAL": "#ff2200",
        "HIGH": "#ff6600",
        "MODERATE": "#ffaa00",
        "LOW": "#00aaff",
    }.get(severity, "#666666")


def monthly_waste_kzt(building: dict, temp_out: float = -15.0) -> float:
    loss = calculate_heat_loss(building, temp_out)
    return round(loss["total_kw"] * HOURS_PER_MONTH * HEATING_TARIFF_KWH, 0)


def seasonal_cost_kzt(building: dict, temp_out: float = -15.0) -> float:
    loss = calculate_heat_loss(building, temp_out)
    return loss["total_kw"] * 24 * HEATING_SEASON_DAYS * HEATING_TARIFF_KWH


def calculate_roi(building: dict) -> dict:
    current = calculate_heat_loss(building, OUTSIDE_TEMP_CRITICAL)
    current_season = seasonal_cost_kzt(building, -15.0)
    monthly_waste = monthly_waste_kzt(building, -15.0)

    preset = MATERIAL_PRESETS[building["material_preset"]]
    upgraded = {**building, "u_values": SNIP_REQUIRED_U.copy()}
    upgraded_loss = calculate_heat_loss(upgraded, OUTSIDE_TEMP_CRITICAL)
    upgraded_season = seasonal_cost_kzt(upgraded, -15.0)

    yearly_saving = current_season - upgraded_season
    renovation_cost = (
        building["facade_area_m2"] * preset["insulation_cost_per_m2"]
        + building["window_area_m2"] * 25000
    )

    roi_years = renovation_cost / yearly_saving if yearly_saving > 0 else 99.0
    roi_months = roi_years * 12

    reduction_pct = (
        (current["total_kw"] - upgraded_loss["total_kw"]) / current["total_kw"] * 100
        if current["total_kw"] > 0
        else 0
    )

    pitch = (
        f"Это здание теряет {monthly_waste:,.0f} ₸/мес. "
        f"Инвестиция {renovation_cost:,.0f} ₸ в {preset['insulation_upgrade'].lower()} "
        f"окупится за {roi_months:.1f} мес."
    )

    return {
        "current_critical_loss_kw": current["total_kw"],
        "optimized_critical_loss_kw": upgraded_loss["total_kw"],
        "loss_reduction_percent": round(reduction_pct, 1),
        "monthly_waste_kzt": monthly_waste,
        "estimated_cost_kzt": round(renovation_cost, 0),
        "yearly_saving_kzt": round(yearly_saving, 0),
        "roi_months": round(roi_months, 1),
        "roi_years": round(roi_years, 1),
        "insulation_type": preset["insulation_upgrade"],
        "pitch": pitch,
    }


def generate_thermal_matrix(building: dict, temp_out: float, cells: int = 48) -> list:
    """Generate normalized heat-loss values [0..1] for facade thermal grid."""
    import random

    rng = random.Random(building["id"])
    base = calculate_heat_loss(building, temp_out)["total_kw"]
    u_wall = building["u_values"]["walls"]
    u_win = building["u_values"]["windows"]

    matrix = []
    for i in range(cells):
        is_window_zone = (i % 8) in (2, 5)
        u = u_win if is_window_zone else u_wall
        noise = rng.uniform(0.85, 1.15)
        cell_q = u * (INSIDE_TEMP - temp_out) * noise
        matrix.append(round(cell_q, 2))

    max_q = max(matrix) if matrix else 1
    return [round(v / max_q, 3) for v in matrix]
