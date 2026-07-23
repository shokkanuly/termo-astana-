"""Request models for the API.

These are the payload shapes accepted by the routers. Responses are returned as plain
dicts rather than models, so there are no response schemas here.
"""

from typing import Optional

from pydantic import BaseModel


class HardwareTelemetry(BaseModel):
    """ESP32 traffic node: ultrasonic distance + flow speed + relay load."""

    node_id: str
    temp_c: float
    distance_cm: float
    flow_speed_kmh: float
    lane_blocked: bool
    power_kw: float


class TwinMetrics(BaseModel):
    traffic_speed_kmh: float
    congestion_index: float
    air_quality_co2_ppm: float
    facade_heat_loss_w_m2: float
    ambient_temp_c: float


class TwinTelemetry(BaseModel):
    timestamp: str
    district_id: str
    metrics: TwinMetrics
    ai_trigger: bool


class TelemetryPayload(BaseModel):
    city: str
    district_id: str
    metrics: TwinMetrics


class ThermoPayload(BaseModel):
    building_id: str
    name: str
    age: int
    current_loss_wm2: float
    insulation_type: str
    target_thickness_mm: int
    calculated_reduction_percent: int


class ChatRequest(BaseModel):
    message: str
    mode: str                          # 'traffic' | 'thermo'
    session_id: str = "default"
    context: dict = {}


class SmartControlRequest(BaseModel):
    district_id: str = "nurzhol_sector_A"
    mode: str = "AUTO"
    metrics: Optional[TwinMetrics] = None
    hardware: dict = {}
    manual_action: Optional[str] = None


class ESP32Payload(BaseModel):
    """ESP32 thermal node: indoor/outdoor probe pair plus window reed switch."""

    node_id: str
    t_in: float
    t_out: float
    window_open: bool
    humidity: Optional[float] = None
