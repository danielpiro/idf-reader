# DataLoader Design Document

## Class Structure

```python
class DataLoader:
    def __init__(self):
        # Primary Cache - Frequently accessed core data
        self._zones_cache = {}        # {zone_id: ZoneData}
        self._surfaces_cache = {}     # {surface_id: SurfaceData}
        self._constructions_cache = {} # {construction_id: ConstructionData}
        self._materials_cache = {}    # {material_id: MaterialData}

        # Secondary Cache - Related data with moderate access
        self._schedules_cache = {}    # {schedule_id: ScheduleData}
        self._areas_cache = {}        # {area_id: AreaData}
        self._hvac_cache = {}        # {zone_id: HVACData}

        # Cache Status Tracking
        self._loaded_sections = set()  # Track which data sections are loaded
        self._dirty_flags = {}        # Track modified cache sections
```

## Core Interface

```python
class DataLoader:
    def load_file(self, idf_path: str) -> None:
        """Initial load of IDF file, populating primary cache."""
        pass

    def get_zone(self, zone_id: str) -> ZoneData:
        """Get zone data from cache or load if needed."""
        pass

    def get_surface(self, surface_id: str) -> SurfaceData:
        """Get surface data from cache or load if needed."""
        pass

    def get_construction(self, construction_id: str) -> ConstructionData:
        """Get construction data from cache or load if needed."""
        pass

    def get_material(self, material_id: str) -> MaterialData:
        """Get material data from cache or load if needed."""
        pass

    def get_schedule(self, schedule_id: str) -> ScheduleData:
        """Get schedule data from cache or load if needed."""
        pass
```

## Caching Strategy

### 1. Primary Cache (Immediate Load)

- Zone basic properties
- Surface definitions
- Common construction details
- Frequently used material properties

```python
def _load_primary_cache(self):
    """Load most frequently accessed data during initialization."""
    self._load_zones_basic()
    self._load_surfaces_basic()
    self._load_common_constructions()
    self._load_core_materials()
```

### 2. Secondary Cache (Lazy Load)

- Detailed schedule data
- Area relationships
- HVAC configurations
- Extended material properties

```python
def _load_secondary_cache(self, section: str):
    """Load secondary data sections on first access."""
    if section not in self._loaded_sections:
        if section == "schedules":
            self._load_schedules_data()
        elif section == "areas":
            self._load_areas_data()
        # ... other section handlers
        self._loaded_sections.add(section)
```

### 3. Cache Management

```python
def clear_cache(self, section: Optional[str] = None):
    """Clear specific or all cache sections."""
    pass

def refresh_cache(self, section: Optional[str] = None):
    """Reload specific or all cache sections from file."""
    pass

def get_cache_status(self) -> Dict[str, bool]:
    """Return loading status of all cache sections."""
    pass
```

## Data Access Patterns

### 1. Direct Access (Primary Cache)

```python
zone_data = loader.get_zone("ZONE1")
surface_data = loader.get_surface("SURFACE1")
```

### 2. Relational Access (Cached References)

```python
zone = loader.get_zone("ZONE1")
zone_surfaces = loader.get_zone_surfaces(zone.id)
construction = loader.get_construction(surface.construction_id)
```

### 3. Bulk Access (Optimized Loading)

```python
all_zones = loader.get_all_zones()
floor_surfaces = loader.get_surfaces_by_type("FLOOR")
```

## Parser Integration

```python
class BaseParser:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader

    def process_data(self):
        """Use DataLoader instead of direct file access."""
        pass
```

Example usage in MaterialsParser:

```python
class MaterialsParser(BaseParser):
    def process_construction(self, construction_id: str):
        construction = self.data_loader.get_construction(construction_id)
        materials = [
            self.data_loader.get_material(mat_id)
            for mat_id in construction.material_ids
        ]
```

## Performance Considerations

1. Memory Management

   - Configurable cache sizes
   - LRU eviction for secondary cache
   - Memory usage monitoring

2. Optimization Techniques

   - Batch loading for related data
   - Index creation for frequent queries
   - Cache prewarming for common patterns

3. Thread Safety
   - Read/write locks for cache access
   - Thread-safe cache updates
   - Concurrent access handling

Would you like me to proceed with implementing this design, or would you like to discuss any specific aspects in more detail?
