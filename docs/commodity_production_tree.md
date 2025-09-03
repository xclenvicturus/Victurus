# /docs/commodity_production_tree.md

# Victurus Commodity Production Tree System

## Overview

This document defines the complete production tree for all commodities in Victurus, from raw materials through final products. Every item in the game must have a traceable production path from harvested/mined resources.

## Production Tree Structure

### Tier 1: Raw Resources (Harvested/Extracted)
These are extracted directly from planets, moons, asteroids, gas clouds, or other celestial bodies.

#### Mineral Resources
- **Iron Ore** (Planets, Moons, Asteroids)
- **Copper Ore** (Planets, Moons, Asteroids)
- **Aluminum Ore** (Planets, Moons)
- **Titanium Ore** (Asteroids, select Planets)
- **Rare Earth Elements** (select Planets, rare Asteroids)
- **Radioactive Ore** (specific Planets, rare Asteroids)
- **Silicon** (Planets, Moons)
- **Carbon** (Gas Clouds, Planets with atmosphere)

#### Energy & Gas Resources
- **Hydrogen** (Gas Giants, Gas Clouds)
- **Helium** (Gas Giants)
- **Methane** (Gas Giants, Ice Moons)
- **Oxygen** (Planets with atmosphere)
- **Nitrogen** (Planets with atmosphere)

#### Biological & Organic Resources
- **Water Ice** (Moons, Ice Fields, Comets)
- **Organic Compounds** (Planets with life)
- **Agricultural Products** (Inhabited Planets with AgriDomes)
- **Biomass** (Planets with ecosystems)

### Tier 2: Refined Resources (Processed Materials)
Raw resources processed into standardized materials for manufacturing.

#### Refined Metals & Alloys
- **Steel** ← Iron Ore + Carbon (at Refinery)
- **Aluminum** ← Aluminum Ore (at Refinery)
- **Copper** ← Copper Ore (at Refinery)
- **Titanium** ← Titanium Ore (at Advanced Refinery)
- **Rare Alloys** ← Rare Earth Elements + processing (at Advanced Refinery)
- **Superconductors** ← Rare Earth Elements + advanced processing (at High-Tech Facility)

#### Processed Chemicals & Fuels
- **Fuel** ← Hydrogen + processing (at Refinery)
- **Water** ← Water Ice + processing (at Processing Plant)
- **Oxygen Canisters** ← Oxygen + processing (at Processing Plant)
- **Plastics** ← Carbon + chemical processing (at Chemical Plant)
- **Advanced Polymers** ← Carbon + advanced processing (at Chemical Plant)

#### Basic Industrial Materials
- **Glass** ← Silicon + processing (at Fabricator)
- **Composite Materials** ← Carbon + advanced processing (at Advanced Fabricator)
- **Ceramics** ← Silicon + specialized processing (at Advanced Fabricator)

### Tier 3: Base Components (Standard Parts)
Refined resources assembled into standardized components used across multiple applications.

#### Electronic Components
- **Basic Electronics** ← Silicon + Copper (at Electronics Plant)
- **Advanced Circuitry** ← Basic Electronics + Rare Earth Elements (at Electronics Plant)
- **Computer Cores** ← Advanced Circuitry + specialized processing (at High-Tech Facility)
- **Data Storage Units** ← Silicon + Rare Alloys (at Electronics Plant)

#### Mechanical Components
- **Mechanical Parts** ← Steel + Aluminum (at Fabricator)
- **Precision Machinery** ← Titanium + Advanced Circuitry (at Advanced Fabricator)
- **Power Cells** ← Rare Alloys + Advanced Circuitry (at Electronics Plant)
- **Structural Framework** ← Steel + Titanium (at Fabricator)

#### Life Support Components
- **Air Recyclers** ← Steel + Basic Electronics + Plastics (at Fabricator)
- **Water Purifiers** ← Steel + Basic Electronics + filters (at Fabricator)
- **Atmosphere Processors** ← Advanced components + specialized systems (at Advanced Fabricator)

### Tier 4: Advanced Components (Specialized Systems)
Base components combined into sophisticated sub-systems for specific applications.

#### Propulsion Systems
- **Thruster Arrays** ← Precision Machinery + Power Cells + fuel systems (at Shipyard)
- **Jump Drive Cores** ← Superconductors + Computer Cores + exotic materials (at Advanced Shipyard)
- **Maneuvering Systems** ← Mechanical Parts + Advanced Circuitry (at Shipyard)

#### Power & Energy Systems
- **Reactor Cores** ← Radioactive Ore + Superconductors + containment systems (at Advanced Fabricator)
- **Power Distribution Networks** ← Advanced Circuitry + Superconductors (at Electronics Plant)
- **Energy Storage Systems** ← Power Cells + Advanced Polymers (at Advanced Fabricator)

#### Defensive Systems
- **Armor Plating** ← Titanium + Composite Materials + advanced processing (at Shipyard)
- **Shield Emitters** ← Superconductors + Advanced Circuitry + exotic field generators (at Advanced Shipyard)
- **Point Defense Arrays** ← Precision Machinery + targeting systems + power systems (at Military Shipyard)

#### Communication & Navigation
- **Navigation Arrays** ← Computer Cores + Advanced Circuitry + sensor systems (at High-Tech Facility)
- **Communications Systems** ← Advanced Circuitry + Rare Alloys + signal processing (at Electronics Plant)
- **Sensor Suites** ← Advanced components + specialized detection systems (at High-Tech Facility)

### Tier 5: Modules (Functional Systems)
Complete functional units that can be installed on ships, stations, habitats, or facilities to provide specific capabilities.

#### Station Operation Modules
- **Refuel Module** ← Fuel storage + pumping systems + safety systems (at Industrial Shipyard)
  - *Function*: Enables any station to provide refueling services
- **Repair Module** ← Mechanical repair systems + spare parts fabrication + diagnostic systems (at Industrial Shipyard)
  - *Function*: Enables any station to provide ship repair services
- **Medical Module** ← Medical equipment + life support + pharmaceutical systems (at Medical Facility)
  - *Function*: Enables any station to provide medical services
- **Trading Module** ← Cargo handling + market systems + security systems (at Commercial Fabricator)
  - *Function*: Enables any station to operate as a trading hub

#### Ship Enhancement Modules
- **Shield Generator Module** ← Shield Emitters + Power Distribution + control systems (at Advanced Shipyard)
  - *Function*: Provides energy shielding capability to ships
- **Weapon System Module** ← Weapon platforms + targeting + power coupling (at Military Shipyard)
  - *Function*: Adds combat capability to ships
- **Cargo Expansion Module** ← Structural Framework + cargo handling + storage systems (at Industrial Shipyard)
  - *Function*: Increases ship cargo capacity
- **Mining Module** ← Mining equipment + ore processing + storage systems (at Industrial Shipyard)
  - *Function*: Enables ships to extract raw resources

#### Facility Enhancement Modules
- **Production Module** ← Manufacturing equipment + automation + quality control (at Industrial Fabricator)
  - *Function*: Enables facilities to produce specific commodity types
- **Research Module** ← Laboratory equipment + analysis systems + data processing (at Research Facility)
  - *Function*: Enables facilities to conduct research and development
- **Defense Module** ← Point Defense Arrays + early warning + coordination systems (at Military Shipyard)
  - *Function*: Provides defensive capabilities to facilities

#### Habitat Support Modules
- **Life Support Module** ← Atmosphere Processors + Water Purifiers + waste management (at Habitat Fabricator)
  - *Function*: Enables stations to support larger populations
- **Recreation Module** ← Entertainment systems + social spaces + amenities (at Commercial Fabricator)
  - *Function*: Improves habitat quality and population happiness
- **Agricultural Module** ← Growing systems + environmental control + food processing (at Agricultural Facility)
  - *Function*: Enables stations to produce food and organic materials

### Tier 6: Final Products (Complete Constructions)
Fully assembled end-user products combining multiple modules and systems.

#### Complete Ships
- **Civilian Ships** ← Ship hull + Basic modules + standard systems (at Shipyard)
  - *Base Modules*: Life Support, Navigation, Basic Propulsion
- **Military Ships** ← Military hull + Combat modules + advanced systems (at Military Shipyard)
  - *Base Modules*: Shield Generator, Weapon System, Advanced Navigation, Armor
- **Industrial Ships** ← Industrial hull + Specialized modules + work systems (at Industrial Shipyard)
  - *Base Modules*: Mining Module, Cargo Expansion, Repair Module
- **Research Ships** ← Research hull + Science modules + analysis systems (at Research Shipyard)
  - *Base Modules*: Research Module, Advanced Sensors, Data Processing

#### Complete Stations
- **Trading Station** ← Station hull + Trading Module + support systems (at Construction Yard)
  - *Core Function*: Commodity trading and market operations
- **Refueling Station** ← Station hull + Refuel Module + fuel storage (at Construction Yard)
  - *Core Function*: Ship refueling and fuel distribution
- **Repair Station** ← Station hull + Repair Module + parts storage (at Construction Yard)
  - *Core Function*: Ship maintenance and repair services
- **Research Station** ← Station hull + Research Module + laboratory systems (at Construction Yard)
  - *Core Function*: Scientific research and development

#### Complete Buildings & Facilities
- **Mining Facility** ← Structure + Mining Module + processing systems (at Construction Yard)
  - *Core Function*: Raw resource extraction and initial processing
- **Manufacturing Facility** ← Structure + Production Module + specific equipment (at Construction Yard)
  - *Core Function*: Commodity production and assembly
- **Habitat Complex** ← Structure + Life Support Module + residential systems (at Construction Yard)
  - *Core Function*: Population housing and support
- **Defense Installation** ← Structure + Defense Module + weapon systems (at Construction Yard)
  - *Core Function*: System or facility protection

## Illegal/Contraband Production

### Illegal Commodities
- **Weapons** (in systems where banned) ← Standard weapon production
- **Drugs** ← Organic Compounds + Chemical processing (at Hidden Labs)
- **Stolen Goods** ← Various legitimate products (acquired through piracy)
- **Restricted Technology** ← Advanced components (in systems where regulated)

## Production Facility Requirements

### Facility Types Needed
- **Mining Operations** (extract Tier 1 raw materials)
- **Refineries** (Tier 1 → Tier 2 processing)
- **Chemical Plants** (specialized chemical processing)
- **Electronics Plants** (electronic component manufacturing)
- **Fabricators** (general manufacturing and assembly)
- **Advanced Fabricators** (high-tech component manufacturing)
- **Shipyards** (ship assembly)
- **Construction Yards** (facility construction)

### Production Dependencies
Each facility type requires:
- **Power** (from Reactor Cores or external power)
- **Raw Materials** (appropriate tier inputs)
- **Labor** (population or automated systems)
- **Maintenance** (replacement parts and consumables)

## Economic Flow Examples

### Example 1: Fuel Production Chain
1. **Hydrogen** harvested from Gas Giant
2. **Fuel** refined at Refinery (Hydrogen + processing)
3. **Fuel** sold to Fuel Depots
4. **Ships** purchase fuel for travel
5. **Fuel Depots** need constant resupply

### Example 2: Ship Construction Chain
1. **Iron Ore, Copper Ore, Silicon** mined from asteroids
2. **Steel, Copper, Electronics** processed at Refineries/Plants
3. **Hull Plating, Engine Blocks** manufactured at Fabricators
4. **Complete Ship** assembled at Shipyard
5. **Ship** sold to player/NPC

### Example 3: Medical Supplies Chain
1. **Organic Compounds** harvested from planet
2. **Plastics** produced from Carbon at Chemical Plant
3. **Electronics** manufactured from Silicon + Copper
4. **Medical Supplies** assembled at Medical Facility
5. **Medical Supplies** distributed to stations/planets for consumption

## Expansion Strategy

As new systems are added to the game, the production tree can be expanded by:
1. Adding new raw materials for new technologies
2. Creating new processing tiers for advanced products
3. Adding specialized facilities for unique production chains
4. Introducing regional variations in production methods

## Implementation Notes

### Phase 1 Implementation
Start with essential chains:
- Basic fuel production (Hydrogen → Fuel)
- Simple ship components (Steel, Electronics)
- Essential life support (Food, Water, Medical Supplies)

### Future Expansion
- Advanced military equipment
- Luxury goods and services
- Specialized industrial equipment
- Research and development products

---

*This document will be updated as new systems and features are added to the game.*
