from pydantic import BaseModel
from typing import Dict, List, Optional


class BuildingSummary(BaseModel):
    id: str
    address: str
    district: str
    year_built: int
    material: str
    material_preset: str
    critical_loss_kw: float
    monthly_waste_kzt: float
    severity: str
    priority_rank: int


class HeatBreakdown(BaseModel):
    walls_kw: float
    roof_kw: float
    windows_kw: float


class HeatLossResult(BaseModel):
    total_kw: float
    total_watts: float
    breakdown: HeatBreakdown
    delta_t: float
    r_total: float


class RenovationMetrics(BaseModel):
    current_critical_loss_kw: float
    optimized_critical_loss_kw: float
    loss_reduction_percent: float
    monthly_waste_kzt: float
    estimated_cost_kzt: float
    yearly_saving_kzt: float
    roi_months: float
    roi_years: float
    insulation_type: str
    pitch: str


class ChartData(BaseModel):
    years: List[str]
    without_renovation_accumulated_kzt: List[float]
    with_renovation_accumulated_kzt: List[float]


class AnalysisResponse(BaseModel):
    building_info: dict
    metrics: RenovationMetrics
    chart_data: ChartData
    thermal_matrix: List[float]


class DistrictSummary(BaseModel):
    district: str
    building_count: int
    total_monthly_waste_kzt: float
    avg_critical_loss_kw: float
    priority_score: float
    top_building_address: str


class SensorReading(BaseModel):
    node_id: str
    district: str
    address: str
    temp_facade_c: float
    temp_ambient_c: float
    humidity_pct: float
    heat_loss_w: float
    severity: str
    is_hardware: bool
    timestamp: float


class NodeStatus(BaseModel):
    node_id: str
    district: str
    address: str
    temp_facade_c: float
    heat_loss_w: float
    severity: str
    is_hardware: bool
    last_seen: float
    map_x: Optional[float] = None
    map_y: Optional[float] = None


class MapBuilding(BaseModel):
    id: str
    address: str
    district: str
    sector: str
    map_x: float
    map_y: float
    critical_loss_kw: float
    monthly_waste_kzt: float
    severity: str


class MapDistrict(BaseModel):
    district: str
    label: str
    subtitle: str
    bank: str
    path: str
    label_x: float
    label_y: float
    sectors: list
    total_monthly_waste_kzt: float
    building_count: int
    heat_intensity: float


class CityMapResponse(BaseModel):
    width: int
    height: int
    river_path: str
    roads: List[str]
    landmarks: list
    districts: List[MapDistrict]
    buildings: List[MapBuilding]
