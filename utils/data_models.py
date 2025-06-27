"""
Data models used across the application.
Contains dataclass definitions for various domain objects.
"""
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class ZoneData:
    """Container for zone-related data"""
    id: str
    name: str
    floor_area: float
    volume: float
    multiplier: int
    area_id: Optional[str] = None

@dataclass
class SurfaceData:
    """Container for surface-related data"""
    id: str
    name: str
    surface_type: str
    construction_name: str
    boundary_condition: str
    zone_name: str

@dataclass
class ConstructionData:
    """Container for construction-related data"""
    id: str
    name: str
    material_layers: list[str]
    thickness: float

@dataclass
class ScheduleData:
    """Container for schedule-related data"""
    id: str
    name: str
    type: str
    raw_rules: List[str]
    zone_id: Optional[str] = None
    zone_type: Optional[str] = None

@dataclass
class MaterialData:
    """Container for material-related data"""
    id: str
    name: str
    conductivity: float
    density: float
    specific_heat: float
    thickness: float
    solar_absorptance: float

@dataclass
class IdealLoadsData:
    """Container for ZoneHVAC:IdealLoadsAirSystem data"""
    id: str
    name: str
    zone_name: str
    max_heating_supply_air_temperature: float
    min_cooling_supply_air_temperature: float
    max_heating_supply_air_humidity_ratio: float
    min_cooling_supply_air_humidity_ratio: float
    heating_limit: str
    cooling_limit: str
    dehumidification_control_type: str
    humidification_control_type: str
