# IDF Building Model Relationship Map

## Element Relationships

```mermaid
graph TD
    Z[Zone] --> |has| S[Schedule:Compact]
    Z --> |contains| BS[BuildingSurface:Detailed]
    Z --> |has properties| ZP[Zone Properties]
    ZP --> FA[Floor Area]
    ZP --> V[Volume]
    ZP --> M[Multiplier]

    BS --> |made of| C[Construction]
    C --> |consists of| ML[Material Layers]
    ML --> |has| MP[Material Properties]
    MP --> CD[Conductivity]
    MP --> D[Density]
    MP --> SH[Specific Heat]
    MP --> SA[Solar Absorptance]
    MP --> T[Thickness]

    Z --> |categorized by| A[Area]
    A --> |has types| AT[Area Types]
    AT --> R[Regular Areas]
    AT --> ST[Storage Areas]

    BS --> |has type| ST[Surface Type]
    ST --> W[Wall]
    ST --> F[Floor]
    ST --> C[Ceiling]
    ST --> R[Roof]

    BS --> |has| BC[Boundary Condition]
    BC --> O[Outdoors]
    BC --> G[Ground]
    BC --> I[Internal]

    Z --> |may have| HVAC[HVAC System]
    HVAC --> |controlled by| HS[Heating Schedule]
    HVAC --> |controlled by| CS[Cooling Schedule]
```

## Key Relationships Explained

1. Zone-Level Relationships

   - A Zone is the primary container element
   - Contains physical properties (floor area, volume, multiplier)
   - Can belong to specific Areas (regular or storage)
   - May have HVAC systems with schedules

2. Surface-Level Relationships

   - Each Zone has one or more BuildingSurface:Detailed objects
   - Surface attributes:
     - Type (wall, floor, ceiling, roof)
     - Boundary condition (outdoors, ground, internal)
     - Construction definition

3. Construction-Level Relationships

   - Constructions define material layering
   - Each material layer has:
     - Physical properties (thickness, density)
     - Thermal properties (conductivity, specific heat)
     - Solar properties (absorptance)

4. Schedule Relationships
   - Zones link to Schedule:Compact objects
   - HVAC systems use schedules for operation control
   - Schedules define time-based parameters

## Data Dependencies

- Zone → Schedule (time control)
- Zone → BuildingSurface (physical composition)
- BuildingSurface → Construction (material definition)
- Construction → Material (properties)
- Zone → Area (organization)
- Zone → HVAC (climate control)

## Implications for DataLoader Design

1. Primary Cache Layer

   - Zone definitions
   - Surface definitions
   - Construction definitions
   - Material properties

2. Secondary Cache Layer

   - Schedule data
   - Area assignments
   - HVAC configurations
   - Boundary conditions

3. On-Demand Loading
   - Detailed material properties
   - Schedule details
   - Complex HVAC parameters
