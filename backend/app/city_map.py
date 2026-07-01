"""
Astana city map geometry — schematic but geographically faithful layout.

Coordinate system: 1000 × 700 (viewBox).
  West = Left Bank (Есиль)  |  East = Right Bank
  Ishim (Ишим) river runs N→S through x ≈ 395
"""

MAP_WIDTH = 1000
MAP_HEIGHT = 700

RIVER_PATH = (
    "M 395,0 C 375,80 415,160 385,240 "
    "C 370,320 410,400 390,480 "
    "C 375,560 405,640 395,700"
)

DISTRICT_GEOMETRY = {
    "Есиль": {
        "label": "ЕСИЛЬ",
        "subtitle": "Левый берег · EXPO · Нуржол",
        "bank": "left",
        "path": (
            "M 0,0 L 360,0 L 375,60 L 365,140 L 355,220 "
            "L 340,320 L 330,420 L 320,520 L 0,520 Z"
        ),
        "label_pos": {"x": 140, "y": 260},
        "sectors": [
            {"id": "esil_nurzhol", "name": "Нуржол", "cx": 200, "cy": 120},
            {"id": "esil_mangilik", "name": "Мангилик Ел", "cx": 180, "cy": 220},
            {"id": "esil_expo", "name": "EXPO", "cx": 120, "cy": 380},
            {"id": "esil_turkistan", "name": "Туркестан", "cx": 250, "cy": 320},
            {"id": "esil_syganak", "name": "Сығанақ", "cx": 90, "cy": 200},
        ],
    },
    "Сарыарка": {
        "label": "САРЫАРКА",
        "subtitle": "Правый берег · Старый центр · Вокзал",
        "bank": "right",
        "path": (
            "M 410,0 L 780,0 L 820,80 L 790,160 "
            "L 760,220 L 410,200 Z"
        ),
        "label_pos": {"x": 580, "y": 90},
        "sectors": [
            {"id": "sary_vokzal", "name": "Привокзальный", "cx": 620, "cy": 80},
            {"id": "sary_seifullin", "name": "Сейфуллина", "cx": 550, "cy": 140},
            {"id": "sary_kenesary", "name": "Кенесары", "cx": 680, "cy": 120},
            {"id": "sary_zheltoksan", "name": "Желтоксан", "cx": 720, "cy": 60},
        ],
    },
    "Алматы": {
        "label": "АЛМАТЫ",
        "subtitle": "Правый берег · Исторический центр",
        "bank": "right",
        "path": (
            "M 410,200 L 760,220 L 740,300 L 720,380 "
            "L 450,360 L 410,280 Z"
        ),
        "label_pos": {"x": 560, "y": 290},
        "sectors": [
            {"id": "alm_baiterek", "name": "Байтерек", "cx": 480, "cy": 280},
            {"id": "alm_abay", "name": "Абая", "cx": 580, "cy": 300},
            {"id": "alm_respublika", "name": "Республики", "cx": 650, "cy": 260},
            {"id": "alm_satpaev", "name": "Сатпаева", "cx": 700, "cy": 340},
        ],
    },
    "Байконыр": {
        "label": "БАЙКОНЫР",
        "subtitle": "Юго-запад · Микрорайоны 1–12",
        "bank": "right",
        "path": (
            "M 450,360 L 720,380 L 690,480 L 650,540 "
            "L 480,520 L 450,440 Z"
        ),
        "label_pos": {"x": 560, "y": 450},
        "sectors": [
            {"id": "bay_aynakol", "name": "Айнаколь", "cx": 520, "cy": 420},
            {"id": "bay_zhansugurov", "name": "Жансугурова", "cx": 600, "cy": 460},
            {"id": "bay_mkr7", "name": "МКР-7", "cx": 660, "cy": 430},
            {"id": "bay_mkr12", "name": "МКР-12", "cx": 550, "cy": 500},
        ],
    },
    "Сарайшык": {
        "label": "САРАЙШЫК",
        "subtitle": "Юго-восток · Аэропорт · Туран",
        "bank": "right",
        "path": (
            "M 480,520 L 650,540 L 720,600 L 780,700 "
            "L 420,700 L 450,580 Z"
        ),
        "label_pos": {"x": 600, "y": 610},
        "sectors": [
            {"id": "sar_turan", "name": "Туран", "cx": 580, "cy": 580},
            {"id": "sar_kerey", "name": "Керей-Жанибек", "cx": 650, "cy": 620},
            {"id": "sar_airport", "name": "Аэропорт", "cx": 720, "cy": 660},
            {"id": "sar_inj", "name": "Инжу", "cx": 500, "cy": 640},
        ],
    },
}

LANDMARKS = [
    {"id": "baiterek", "name": "Байтерек", "x": 475, "y": 295, "icon": "◆"},
    {"id": "khan_shatyr", "name": "Хан Шатыр", "x": 195, "y": 175, "icon": "▲"},
    {"id": "expo", "name": "EXPO 2017", "x": 115, "y": 395, "icon": "■"},
    {"id": "vokzal", "name": "ЖД Вокзал", "x": 635, "y": 95, "icon": "⊞"},
    {"id": "akorda", "name": "Акорда", "x": 455, "y": 310, "icon": "●"},
    {"id": "aeroexpress", "name": "Аэроэкспресс", "x": 530, "y": 250, "icon": "◎"},
    {"id": "airport", "name": "Аэропорт NQZ", "x": 735, "y": 675, "icon": "✈"},
    {"id": "nur_mosque", "name": "Мечеть Нур-Астана", "x": 220, "y": 280, "icon": "☪"},
    {"id": "palace_peace", "name": "Дворец Мира", "x": 160, "y": 310, "icon": "◇"},
]

ROADS = [
    "M 0,260 L 360,260",          # Мангилик Ел (left bank)
    "M 140,0 L 140,520",          # Кабанбай батыра
    "M 410,140 L 820,140",        # Сейфуллина
    "M 450,300 L 760,300",        # Абая
    "M 480,450 L 700,450",        # Жансугурова
    "M 520,580 L 750,580",        # Туран
]

DISTRICT_NODE_ANCHORS = {
    "Есиль": (180, 250),
    "Сарыарка": (600, 130),
    "Алматы": (560, 300),
    "Байконыр": (570, 450),
    "Сарайшык": (600, 620),
}
