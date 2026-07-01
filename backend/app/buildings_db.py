from app.thermal_engine import MATERIAL_PRESETS

ASTANA_DISTRICTS = [
    "Есиль",
    "Сарыарка",
    "Алматы",
    "Байконыр",
    "Сарайшык",
]


def _b(id_, address, district, year, preset, facade, roof, windows, mx, my, sector=""):
    return {
        "id": id_,
        "address": address,
        "district": district,
        "sector": sector,
        "year_built": year,
        "wall_material": MATERIAL_PRESETS[preset]["label"],
        "material_preset": preset,
        "facade_area_m2": facade,
        "roof_area_m2": roof,
        "window_area_m2": windows,
        "u_values": MATERIAL_PRESETS[preset]["u_values"].copy(),
        "map_x": mx,
        "map_y": my,
    }


_RAW = [
    # Сарыарка
    ("bld_sary_01", "ул. Сейфуллина, 24", "Сарыарка", 1974, "khrushchyovka_panel", 1800, 800, 350, 548, 145, "sary_seifullin"),
    ("bld_sary_02", "ул. Сейфуллина, 56", "Сарыарка", 1971, "khrushchyovka_panel", 1650, 720, 320, 565, 160, "sary_seifullin"),
    ("bld_sary_03", "ул. Кенесары, 42", "Сарыарка", 1981, "brezhnevka_panel", 2200, 950, 420, 675, 125, "sary_kenesary"),
    ("bld_sary_04", "ул. Кенесары, 78", "Сарыарка", 1983, "brezhnevka_panel", 2000, 880, 390, 690, 140, "sary_kenesary"),
    ("bld_sary_05", "ул. Бейбитшилик, 18", "Сарыарка", 1968, "khrushchyovka_panel", 1500, 650, 280, 530, 175, "sary_seifullin"),
    ("bld_sary_06", "ул. Желтоксан, 12", "Сарыарка", 1979, "brezhnevka_panel", 1900, 820, 370, 715, 75, "sary_zheltoksan"),
    ("bld_sary_07", "ул. Жанкожа батыра, 5", "Сарыарка", 1975, "khrushchyovka_panel", 1700, 740, 330, 600, 95, "sary_vokzal"),
    ("bld_sary_08", "пр. Жибек Жолы, 33", "Сарыарка", 1986, "brick_soviet", 2100, 900, 410, 640, 110, "sary_vokzal"),
    # Алматы
    ("bld_alm_01", "ул. Абая, 52", "Алматы", 1978, "brick_soviet", 2400, 1100, 480, 575, 305, "alm_abay"),
    ("bld_alm_02", "ул. Абая, 18", "Алматы", 1982, "brezhnevka_panel", 1950, 850, 370, 595, 320, "alm_abay"),
    ("bld_alm_03", "пр. Республики, 15", "Алматы", 1985, "brezhnevka_panel", 1900, 820, 360, 645, 265, "alm_respublika"),
    ("bld_alm_04", "ул. Бараева, 8", "Алматы", 1976, "khrushchyovka_panel", 1600, 700, 300, 660, 290, "alm_respublika"),
    ("bld_alm_05", "ул. Сатпаева, 30", "Алматы", 1990, "brick_soviet", 2200, 950, 430, 695, 345, "alm_satpaev"),
    ("bld_alm_06", "ул. Брусиловского, 14", "Алматы", 1980, "brezhnevka_panel", 1850, 800, 350, 620, 335, "alm_baiterek"),
    ("bld_alm_07", "ул. Панфилова, 6", "Алматы", 1973, "khrushchyovka_panel", 1550, 680, 290, 490, 310, "alm_baiterek"),
    # Есиль
    ("bld_esil_01", "пр. Мангилик Ел, 19", "Есиль", 2012, "modern_ventilated", 4500, 1500, 1200, 175, 215, "esil_mangilik"),
    ("bld_esil_02", "пр. Мангилик Ел, 55", "Есиль", 2016, "modern_ventilated", 5200, 1800, 1400, 195, 200, "esil_mangilik"),
    ("bld_esil_03", "ул. Достык, 5", "Есиль", 2018, "glass_curtain", 6200, 2100, 2800, 155, 250, "esil_nurzhol"),
    ("bld_esil_04", "ул. Достык, 18", "Есиль", 2020, "glass_curtain", 5800, 1950, 2600, 170, 265, "esil_nurzhol"),
    ("bld_esil_05", "ул. Кабанбай батыра, 53", "Есиль", 2015, "modern_ventilated", 3800, 1300, 950, 240, 310, "esil_turkistan"),
    ("bld_esil_06", "ул. Туркестан, 8", "Есиль", 2014, "modern_ventilated", 3500, 1200, 880, 255, 340, "esil_turkistan"),
    ("bld_esil_07", "ул. Сығанақ, 15", "Есиль", 2011, "modern_ventilated", 3200, 1100, 800, 85, 195, "esil_syganak"),
    ("bld_esil_08", "EXPO бульвар, 1", "Есиль", 2017, "glass_curtain", 7500, 2500, 3200, 110, 400, "esil_expo"),
    ("bld_esil_09", "ул. Мәскеу, 12", "Есиль", 2013, "modern_ventilated", 4000, 1400, 1000, 200, 180, "esil_mangilik"),
    # Байконыр
    ("bld_bay_01", "ул. Айнаколь, 33", "Байконыр", 1972, "khrushchyovka_panel", 1600, 700, 310, 515, 415, "bay_aynakol"),
    ("bld_bay_02", "ул. Айнаколь, 67", "Байконыр", 1970, "khrushchyovka_panel", 1500, 660, 290, 530, 430, "bay_aynakol"),
    ("bld_bay_03", "ул. Жансугурова, 8", "Байконыр", 1989, "brick_soviet", 2100, 900, 400, 595, 455, "bay_zhansugurov"),
    ("bld_bay_04", "ул. Жансугурова, 45", "Байконыр", 1987, "brezhnevka_panel", 1950, 840, 380, 610, 470, "bay_zhansugurov"),
    ("bld_bay_05", "ул. Ш. Уалиханова, 12", "Байконыр", 1977, "khrushchyovka_panel", 1650, 710, 310, 655, 445, "bay_mkr7"),
    ("bld_bay_06", "мкр. 7, д. 14", "Байконыр", 1984, "brezhnevka_panel", 1800, 780, 340, 670, 425, "bay_mkr7"),
    ("bld_bay_07", "мкр. 12, д. 8", "Байконыр", 1976, "khrushchyovka_panel", 1580, 690, 300, 545, 495, "bay_mkr12"),
    # Сарайшык
    ("bld_sar_01", "ул. Туран, 55", "Сарайшык", 2010, "modern_ventilated", 3200, 1100, 780, 575, 575, "sar_turan"),
    ("bld_sar_02", "ул. Туран, 28", "Сарайшык", 2012, "modern_ventilated", 3500, 1200, 850, 590, 590, "sar_turan"),
    ("bld_sar_03", "ул. Керей-Жанибек, 12", "Сарайшык", 1976, "khrushchyovka_panel", 1700, 750, 330, 645, 615, "sar_kerey"),
    ("bld_sar_04", "ул. Керей-Жанибек, 44", "Сарайшык", 1978, "brezhnevka_panel", 1850, 800, 360, 660, 630, "sar_kerey"),
    ("bld_sar_05", "ул. Е-753, 5", "Сарайшык", 2015, "modern_ventilated", 2800, 980, 700, 700, 600, "sar_inj"),
    ("bld_sar_06", "ул. Инжу, 10", "Сарайшык", 2008, "modern_ventilated", 2600, 900, 650, 495, 645, "sar_inj"),
    ("bld_sar_07", "пр. Кабанбай батыра, 120", "Сарайшык", 2019, "glass_curtain", 4800, 1600, 1100, 720, 655, "sar_airport"),
]

BUILDINGS_DB = {
    row[0]: _b(*row) for row in _RAW
}
