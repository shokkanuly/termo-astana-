"""Gemini-backed advisory endpoints, each with a rule-based local fallback."""

import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException

from app import repository as repo
from app.schemas import ChatRequest, TelemetryPayload, ThermoPayload
from app.utils import clean_json_response, run_db

logger = logging.getLogger("AstanaTwinCombinedAPI")

router = APIRouter()

# ─────────────────────────────────────────────
# SMART CONTROL LOGIC ENGINE
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# REST ENDPOINTS - TRAFFIC AI OPTIMIZATION (Gemini)
# ─────────────────────────────────────────────
@router.post("/api/analyze")
async def analyze_telemetry(payload: TelemetryPayload):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _local_traffic_fallback(payload)

    prompt = f"""You are the Chief AI Urban Logistics & Energy Efficiency Coordinator for Astana City.
Analyze this Astana Twin District Telemetry Snapshot:
- District: {payload.district_id}
- Avg Traffic Speed: {payload.metrics.traffic_speed_kmh} km/h
- Congestion Index: {payload.metrics.congestion_index}%
- Air Quality (CO2): {payload.metrics.air_quality_co2_ppm} PPM
- Facade Heat Loss: {payload.metrics.facade_heat_loss_w_m2} W/m²
- Ambient Temperature: {payload.metrics.ambient_temp_c}°C

Analyze the correlation between traffic speed/congestion (CO2 emissions) and building heat loss.
Return strictly in JSON:
{{
  "analysis": "detailed assessment in Russian",
  "recommendations": "concrete traffic light and thermal retrofit actions in Russian",
  "adjustments": [{{"roadId": "R1", "action": "GREEN_WAVE", "direction": "East-West", "duration": 15, "reason": "reason in Russian"}}],
  "efficiencyMetrics": {{"travelTimeReduction": 22, "co2Reduction": 14, "avgSpeedIncrease": 18}}
}}"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(api_url, json=body, timeout=25.0)
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail="Gemini endpoint error")
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(clean_json_response(text))
        except Exception as e:
            logger.error("Gemini traffic analysis error: %s", e)
            return _local_traffic_fallback(payload)

def _local_traffic_fallback(payload: TelemetryPayload) -> dict:
    co2   = payload.metrics.air_quality_co2_ppm
    speed = payload.metrics.traffic_speed_kmh
    loss  = payload.metrics.facade_heat_loss_w_m2

    analysis = f"[Local AI] Уровень CO₂: {co2:.0f} PPM. Средняя скорость: {speed:.1f} км/ч. Теплопотери фасада: {loss:.0f} Вт/м²."
    recs     = "Параметры в пределах нормы. Регулировка светофоров стандартная."
    adjs     = []
    eff      = {"travelTimeReduction": 5, "co2Reduction": 4, "avgSpeedIncrease": 6}

    if co2 > 700:
        analysis += f" ⚠️ Критическое скопление CO₂ на перекрёстке Node-A."
        recs      = "Активировать режим «Зелёная волна» для разгрузки перекрёстка Node-A."
        adjs      = [{"roadId": "R2", "action": "GREEN_WAVE", "direction": "East-West", "duration": 25, "reason": "CO₂ Node-A разгрузка"},
                     {"roadId": "R5", "action": "BUS_PRIORITY", "direction": "North-South", "duration": 15, "reason": "Приоритет BRT обхода"}]
        eff       = {"travelTimeReduction": 24, "co2Reduction": 18, "avgSpeedIncrease": 20}
    elif loss > 130:
        analysis += f" Высокие теплопотери ({loss:.0f} Вт/м²)."
        recs      = "Рекомендован локальный аудит изоляции фасадов."
        adjs      = [{"roadId": "R1", "action": "GREEN_WAVE", "direction": "East-West", "duration": 10, "reason": "Номинальный режим"}]
        eff       = {"travelTimeReduction": 8, "co2Reduction": 6, "avgSpeedIncrease": 7}

    return {"analysis": analysis, "recommendations": recs, "adjustments": adjs, "efficiencyMetrics": eff}

# ─────────────────────────────────────────────
# REST ENDPOINTS - THERMO AI ANALYSIS (Gemini)
# ─────────────────────────────────────────────
@router.post("/api/analyze-thermo")
async def analyze_thermo(payload: ThermoPayload):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        result = _local_thermo_fallback(payload)
    else:
        prompt = f"""You are the Senior AI Building Energy Efficiency Consultant for Astana Municipality.
Analyze the following building thermal loss configuration:
- Building ID: {payload.building_id}
- Building Name: {payload.name}
- Construction Year: {payload.age}
- Current Heat Loss: {payload.current_loss_wm2} W/m²
- Installed Insulation: {payload.insulation_type}
- Simulated Upgrade Thickness: {payload.target_thickness_mm} mm
- Estimated Heat Loss Reduction: {payload.calculated_reduction_percent}%

Recommend specific building envelope retrofits for Astana's sub-zero climate (-30°C winters).
Return strictly in JSON:
{{
  "analysis": "detailed thermal loss assessment in Russian",
  "recommendations": "insulation material and installation recommendations in Russian",
  "kpi": {{"annualCo2ReductionTons": 4.8, "annualCostSavingKzt": 340000}}
}}"""

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}

        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(api_url, json=body, timeout=25.0)
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail="Gemini endpoint error")
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(clean_json_response(text))
            except Exception as e:
                logger.error("Gemini thermo analysis error: %s", e)
                result = _local_thermo_fallback(payload)

    await run_db(repo.save_thermo_log, {
        "building_id":              payload.building_id,
        "building_name":            payload.name,
        "construction_year":        payload.age,
        "base_heat_loss_wm2":       payload.current_loss_wm2,
        "insulation_type":          payload.insulation_type,
        "insulation_thickness_mm":  payload.target_thickness_mm,
        "reduction_percent":        payload.calculated_reduction_percent,
        "annual_co2_tons":          result.get("kpi", {}).get("annualCo2ReductionTons", 0),
        "annual_savings_kzt":       result.get("kpi", {}).get("annualCostSavingKzt", 0),
        "ai_analysis":              result.get("analysis", ""),
        "ai_recommendations":       result.get("recommendations", ""),
    })

    return result

def _local_thermo_fallback(payload: ThermoPayload) -> dict:
    saved   = payload.current_loss_wm2 * (payload.calculated_reduction_percent / 100.0)
    co2     = round(saved * 0.045, 1)
    savings = int(saved * 2300)
    return {
        "analysis": f"[Local AI] Аудит {payload.name} ({payload.age} г.). Теплопотери {payload.current_loss_wm2} Вт/м² — признак устаревшего теплового контура ({payload.insulation_type}).",
        "recommendations": f"Монтаж утеплителя {payload.target_thickness_mm} мм. Рекомендуются плиты базальтовой ваты (≥110 кг/м³) для климата Астаны (-30°C зима).",
        "kpi": {"annualCo2ReductionTons": co2, "annualCostSavingKzt": savings}
    }

# ─────────────────────────────────────────────
# REST ENDPOINTS - AI CHAT ADVISOR WITH HISTORY
# ─────────────────────────────────────────────
@router.post("/api/chat")
async def ai_chat(req: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY")

    await run_db(repo.save_chat_message, req.session_id, req.mode, "user", req.message, req.context)
    history_rows = await run_db(repo.fetch_chat_history, req.session_id, req.mode, 12)

    if not api_key:
        reply = _local_chat_fallback(req.message, req.mode, req.context)
    else:
        reply = await _call_gemini_chat(api_key, req.message, req.mode, req.context, history_rows)

    await run_db(repo.save_chat_message, req.session_id, req.mode, "assistant", reply, {})
    return {"reply": reply, "session_id": req.session_id, "mode": req.mode}

async def _call_gemini_chat(api_key: str, user_msg: str, mode: str, context: dict, history: list) -> str:
    if mode == "traffic":
        system = f"""Ты — AI-координатор дорожного движения системы KHA-DIVERGENT для Астаны.
Текущие данные телеметрии:
• Средняя скорость: {context.get('avgSpeed', '?')} км/ч
• Индекс заторов: {context.get('congestionRate', '?')}%
• CO₂: {context.get('co2Ppm', '?')} PPM
• Теплопотери фасадов: {context.get('facadeHeatLoss', '?')} Вт/м²
• Температура: {context.get('ambientTemp', '?')}°C
• Активные AI-регулировки: {context.get('appliedAdjustments', 'нет')}
Дорожная сеть: R1=Turan Ave, R2=Kabanbay Batyr, R3=Mangilik El, R4=Kunayev St, R5=Dostyk St, R6=Syganak St.
Отвечай кратко (2-4 предложения). Можешь рекомендовать действия: GREEN_WAVE, BUS_PRIORITY, EMERGENCY_CORRIDOR на дорогах R1-R6."""
    else:
        b = context.get("selectedBuilding") or {}
        system = f"""Ты — AI-консультант по энергоэффективности зданий для Астаны, система KHA-DIVERGENT.
Данные выбранного здания: {b.get('name','?')} (ID: {b.get('id','?')}), год постройки: {b.get('age','?')},
изоляция: {b.get('insulation','?')}, теплопотери: {b.get('h0','?')} Вт/м².
Климат Астаны: -30°C зима, +35°C лето. Норма теплопотерь: <80 Вт/м².
Отвечай кратко (2-4 предложения). Давай конкретные рекомендации по материалам (базальтовая вата, EPS, PIR-плиты, полиуретан)."""

    contents = []
    for row in history[-8:]:
        gemini_role = "user" if row["role"] == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": row["content"]}]})

    contents.append({"role": "user", "parts": [{"text": system + "\n\nВопрос: " + user_msg}]})

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(api_url, json={"contents": contents}, timeout=20.0)
            if r.status_code != 200:
                raise Exception(f"Gemini returned {r.status_code}")
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error("Gemini chat error: %s", e)
            return _local_chat_fallback(user_msg, mode, context)

def _local_chat_fallback(msg: str, mode: str, ctx: dict) -> str:
    m = msg.lower()
    if mode == "traffic":
        speed = ctx.get("avgSpeed", 0)
        co2   = ctx.get("co2Ppm", 0)
        cong  = ctx.get("congestionRate", 0)
        if any(k in m for k in ["congestion", "пробка", "затор", "traffic"]):
            status = "⚠️ Высокая загрузка" if cong > 50 else "✅ Нормальный поток"
            return f"{status}. Индекс заторов: {cong}%. {'Рекомендую GREEN_WAVE на R1 (Turan Ave).' if cong > 50 else 'Светофоры в стандартном режиме.'}"
        if any(k in m for k in ["co2", "air", "воздух", "выброс"]):
            return f"CO₂: {co2:.0f} PPM. {'⚠️ Превышение нормы — рекомендую разгрузку R2.' if co2 > 600 else '✅ В норме (<450 PPM).'}"
        if any(k in m for k in ["speed", "скорость", "быстро"]):
            return f"Средняя скорость по 6 коридорам: {speed:.1f} км/ч. {'Трафик замедлен.' if speed < 35 else 'Трафик в норме.'}"
        return f"Статус: скорость {speed:.1f} км/ч, заторы {cong}%, CO₂ {co2:.0f} PPM. Добавьте Gemini API ключ в .env для детального анализа."
    else:
        b = ctx.get("selectedBuilding") or {}
        if not b:
            return "Пожалуйста, выберите здание на карте для получения теплового анализа."
        h0 = b.get('h0', 0)
        if any(k in m for k in ["insulation", "изоляция", "утеплитель", "материал"]):
            return f"Для {b.get('name','здания')} ({h0} Вт/м²): рекомендую базальтовую вату 120-150 мм для климата Астаны. Текущая: {b.get('insulation','неизвестно')}."
        if any(k in m for k in ["cost", "стоимость", "экономия", "savings", "окупаемость"]):
            savings = round(h0 * 0.4 * 2300)
            return f"Расчётная экономия для {b.get('name','здания')}: ~{savings:,} KZT/год с утеплением 150 мм. Окупаемость ~4-6 лет."
        if any(k in m for k in ["rating", "класс", "energy", "энергия"]):
            rating = "A" if h0 < 55 else "B" if h0 < 90 else "C" if h0 < 130 else "D" if h0 < 185 else "E"
            return f"{b.get('name','Здание')} — энергокласс {rating} ({h0} Вт/м²). Целевой стандарт СНИП РК: <80 Вт/м²."
        return f"{b.get('name','Здание')} ({b.get('id','?')}): теплопотери {h0} Вт/м², год {b.get('age','?')}, изоляция: {b.get('insulation','?')}. Добавьте Gemini API ключ в .env для полного анализа."
