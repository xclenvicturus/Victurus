# /docs/economy_system_design.md

# Victurus Economy System Design

## Overview

The Victurus economy system creates a dynamic, immersive trading and econom## Implementation Strategy

### Phase 1: Foundation (Core Trading)
**Goal**: Basic buy/sell economy with essential commodities

#### Database Schema
- **Commodities Table**: Item definitions, categories, base properties
- **Market Inventory Table**: Station/facility stock levels and prices
- **Market Orders Table**: Buy/sell orders from facilities and players
- **Price History Table**: Historical pricing data for trend analysis

#### Core Commodities (Modular System Economy)
- **Raw Resources** (Tier 1): Iron Ore, Copper Ore, Titanium Ore, Silicon, Carbon, Hydrogen, etc.
- **Refined Resources** (Tier 2): Steel, Aluminum, Fuel, Plastics, Superconductors
- **Base Components** (Tier 3): Electronics, Mechanical Parts, Power Cells, Air Recyclers
- **Advanced Components** (Tier 4): Thruster Arrays, Reactor Cores, Armor Plating, Shield Emitters
- **Modules** (Tier 5): Refuel Module, Repair Module, Medical Module, Shield Generator Module
- **Final Products** (Tier 6): Complete Ships, Stations, Buildings with integrated modules

#### Modular System Benefits
- **Station Customization**: Add Refuel Module to any station → becomes refuel station
- **Ship Enhancement**: Install Shield Generator Module → adds defensive capability
- **Facility Expansion**: Add Production Module → enables commodity manufacturing
- **Scalable Complexity**: Start simple, add modules as needed for functionality

#### Basic Features
- Spot trading at stations
- Simple supply/demand price adjustments
- Facility consumption and production
- Basic inventory management

### Phase 2: Production Chains (Supply Chain Economy)
**Goal**: Multi-tier production with facility interdependence

#### Expanded Systems
- **Multi-input Production**: Facilities requiring multiple commodities
- **Production Scheduling**: Time-based manufacturing processes
- **Supply Contracts**: Long-term supply agreements
- **Transport Networks**: NPC cargo ships moving goods

#### Advanced Features
- Complex production trees (Tier 1 → Tier 5)
- Facility investment and ownership
- Supply chain optimization
- Regional price variations

### Phase 3: Economic Warfare (Advanced Economy)
**Goal**: Full economic manipulation and faction-level economics

#### Military Integration
- **Supply Line Attacks**: Disrupting competitor supply chains
- **Market Manipulation**: Large-scale price manipulation through strategic trading
- **Economic Intelligence**: Espionage networks for competitor information
- **Blockade Economics**: Controlling key trade routes

#### Empire Building
- **Facility Construction**: Building custom production facilities
- **Fleet Management**: Automated trading fleets
- **Faction Economics**: Managing faction-wide resource flows
- **Territorial Control**: Economic control of systems and trade routes

---

## Player Progression Paths

### The Merchant Emperor Path
1. **Small Trader**: Buy/sell at stations for profit
2. **Route Specialist**: Establish profitable trade routes
3. **Fleet Owner**: Multiple ships running automated routes
4. **Facility Owner**: Own production facilities
5. **Market Controller**: Manipulate regional economies
6. **Economic Emperor**: Control entire sector economies

### The Faction Leader Path
1. **Faction Member**: Join existing organization
2. **Supply Specialist**: Handle faction logistics and trading
3. **Economic Advisor**: Plan faction economic strategy
4. **Department Head**: Control faction economic operations
5. **Faction Leader**: Lead organization through economic/political means
6. **Galactic Power**: Control multiple factions and alliances

### The Combat Profiteer Path
1. **Mercenary**: Sell combat loot and salvage
2. **Pirate Hunter**: Eliminate pirates, sell seized cargo
3. **War Contractor**: Supply military factions with equipment
4. **Arms Dealer**: Control weapons and military equipment trade
5. **Warlord**: Use economic power to fund private armies
## Final Implementation Specifications

### 1. Market Interface Design ✅
**DECISION: Hybrid Trading System**
- **Small Scale Trading**: Direct purchase at station prices (fuel, food, medical supplies)
- **Large Scale Trading**: Market order system with bid/ask spreads for bulk commodities
- **End User Experience**: Simple flat-rate purchases for immediate needs
- **Business Operations**: Market orders, contract negotiations, bulk trading for supply chains

### 2. Transportation & Logistics ✅
**DECISION: Complete Multi-Modal Transport System**
- **Player Ships**: Direct cargo transport by player vessels
- **NPC Transport Services**: Contract shipping companies to move cargo
- **Automated Player Fleets**: Set up automated trading routes with owned ships
- **Equal Competition**: All transport options available to NPCs and players equally

### 3. Production Timing ✅
**DECISION: Game Time Production Cycles**
- **Progression Tied**: Production cycles advance with game time, not real time
- **Meaningful Duration**: Long enough to create strategic value (days/weeks game time)
- **Vulnerability Windows**: Long production cycles create opportunities for sabotage/raids
- **Player Engagement**: No waiting for real-time processes, but strategic planning required

### 4. Economic Balancing ✅
**DECISION: AI-Driven Algorithmic Balance**
- **Automated Systems**: AI algorithms adjust supply/demand based on market conditions
- **Dynamic Response**: System responds to player actions and market disruptions
- **Self-Regulating**: Economy maintains stability through algorithmic intervention
- **Developer Oversight**: Manual adjustments for major system changes only

### 5. Starting Economy State ✅
**DECISION: Pre-Established Functioning Economy**
- **Active Systems**: Galaxy starts with established NPC trade networks
- **Immediate Gameplay**: Players can begin trading immediately without waiting
- **Realistic Foundation**: Existing infrastructure supports current populations and facilities
- **Player Integration**: Players enter and compete within existing economic framework

### 6. Advanced Economic Systems ✅
**DECISION: Full Spectrum Economic Warfare & Diplomacy**

#### Economic Espionage
- **Intelligence Networks**: Spy on competitor trade routes, production, and stockpiles
- **Information Trading**: Sell intelligence to other factions
- **Counter-Intelligence**: Protect your own operations from spying

#### Contract Trading
- **Future Delivery**: Contracts for goods to be delivered at future dates
- **Price Hedging**: Lock in prices for future transactions
- **Supply Guarantees**: Long-term supply agreements with facilities

#### Insurance Systems
- **Cargo Insurance**: Protect shipments against piracy and accidents
- **Facility Insurance**: Coverage for production facilities and infrastructure
- **Route Insurance**: Premium routes with guaranteed safe passage

#### Economic Diplomacy
- **Trade Agreements**: Faction-level preferential trading terms
- **Economic Sanctions**: Restrict trade with hostile factions
- **Resource Sharing**: Alliance resource pooling agreements
- **Economic Treaties**: Complex multi-faction economic arrangements

---

## Complete System Architecture

### Database Schema Requirements

#### Core Tables
```sql
-- Commodities and their properties
commodities (commodity_id, name, category, tier, base_value, volume, perishable)

-- Market inventory at all locations
market_inventory (location_id, commodity_id, quantity, base_price, last_updated)

-- Active market orders (buy/sell)
market_orders (order_id, location_id, commodity_id, quantity, price, order_type, expires)

-- Price history for trend analysis
price_history (location_id, commodity_id, price, quantity_sold, timestamp)

-- Production facilities and their configurations
production_facilities (facility_id, location_id, facility_type, input_commodities, output_commodities, production_rate)

-- Transportation contracts and logistics
transport_contracts (contract_id, origin, destination, commodity_id, quantity, price, status)
```

#### Advanced Tables
```sql
-- Economic intelligence and espionage
intelligence_reports (report_id, faction_id, target_faction, information_type, data, timestamp)

-- Insurance policies and claims
insurance_policies (policy_id, insured_party, coverage_type, premium, coverage_amount)

-- Trade agreements and diplomatic relations
trade_agreements (agreement_id, faction_a, faction_b, terms, status, expires)

-- Supply contracts and future delivery
supply_contracts (contract_id, buyer_id, seller_id, commodity_id, quantity, delivery_date, price)
```

### Implementation Priority

#### Phase 1: Core Economy (MVP)
1. **Basic Commodities**: Fuel, Food, Medical, Steel, Electronics
2. **Simple Trading**: Direct buy/sell at stations
3. **Production Basics**: Facilities consume inputs, produce outputs
4. **Price Dynamics**: Supply/demand affects pricing
5. **Transport**: Player ships move cargo

#### Phase 2: Market Systems
1. **Market Orders**: Bulk trading with bid/ask spreads
2. **Advanced Commodities**: Complete production tree implementation
3. **NPC Transport**: Contract shipping services
4. **Production Chains**: Multi-tier manufacturing
5. **Price History**: Trading charts and trend analysis

#### Phase 3: Economic Warfare
1. **Automated Fleets**: Player-owned trading routes
2. **Economic Intelligence**: Espionage and information trading
3. **Contract Trading**: Future delivery and supply contracts
4. **Insurance Systems**: Risk management for shipments
5. **Economic Diplomacy**: Inter-faction trade agreements

### Success Metrics

#### Economic Health Indicators
- **Price Stability**: Prices fluctuate within reasonable ranges
- **Supply Availability**: Critical commodities remain available
- **Trade Volume**: Active trading across the galaxy
- **Production Efficiency**: Facilities operate near capacity

#### Player Engagement Metrics
- **Trading Activity**: Players actively participate in markets
- **Route Establishment**: Players develop consistent trade routes
- **Facility Investment**: Players invest in and own production
- **Economic Conflict**: Market manipulation and economic warfare occur

---

## Risk Mitigation

### Economic Collapse Prevention
- **Circuit Breakers**: Automatic intervention if prices become extreme
- **Strategic Reserves**: Government stockpiles for critical commodities
- **Emergency Production**: Backup systems for essential goods

### Exploit Prevention
- **Market Monitoring**: Detection of unusual trading patterns
- **Position Limits**: Maximum market positions to prevent monopolization
- **Faction Balance**: Prevent single faction economic dominance

### Player Experience Protection
- **Minimum Availability**: Essential commodities always available somewhere
- **Price Caps**: Maximum prices for critical survival goods
## Summary & Next Steps

### Design Philosophy Achieved
✅ **Realistic Economic Simulation**: Every item must be produced/harvested - nothing from thin air  
✅ **Equal Competition**: NPCs and players operate under identical economic rules  
✅ **Multiple Victory Paths**: Economic empire, faction leadership, or combat profiteering  
✅ **Strategic Depth**: Supply chain vulnerability, market manipulation, economic warfare  
✅ **Player Agency**: From small trader to galactic economic emperor  

### Core Systems Defined
- **5-Tier Production Tree**: Raw materials → Final products with realistic manufacturing chains
- **Hybrid Trading Interface**: Simple purchases + market orders for different scale operations
- **Complete Transport Network**: Player ships, NPC services, automated fleets
- **AI-Balanced Markets**: Algorithmic supply/demand management with strategic depth
- **Advanced Economic Tools**: Espionage, contracts, insurance, diplomacy

### Ready for Implementation
The economy system design is now **complete and comprehensive**. This document provides:
- Clear technical specifications for database design
- Detailed implementation phases with priorities
- Risk mitigation strategies for economic stability
- Multiple player progression paths for different playstyles
- Integration points with existing game systems

### Development Approach
1. **Start with Phase 1**: Core trading system with essential commodities
2. **Build Incrementally**: Add complexity in controlled phases
3. **Test Extensively**: Economic balance requires careful tuning
4. **Monitor Metrics**: Track both economic health and player engagement
5. **Iterate Based on Data**: Adjust algorithms based on actual gameplay

The foundation is solid - time to begin implementation! 🚀

---

*This design document represents the complete economic vision for Victurus. All major systems are defined and ready for development. The production tree document (`commodity_production_tree.md`) provides the detailed commodity specifications needed for implementation.* environment where players can engage in commerce, resource management, and economic strategy across the galaxy.

## Design Requirements & Vision

### 1. Economic Complexity Level ✅
**DECISION: Moderate to Complex Production Chain Economy**
- Complete production chains: mines→refineries→markets→consumers
- Regional pricing differences based on local supply/demand
- Dynamic elements driven by actual supply/demand, not artificial systems
- Everything must be produced or gathered - **NO "out of thin air" generation**

### 2. Player Agency & Ownership ✅
**DECISION: Full Economic Empire Building**
Players can:
- **Trade** commodities at existing facilities
- **Invest** in facilities to increase production/capacity  
- **Own** facilities outright and manage them
- **Manipulate** markets through large trades or economic warfare
- **Build fleets** of mining/trading ships
- **Own planets/systems** and control entire supply chains
- **Create factions** and become completely self-sufficient
- **Economic warfare** - blockade supply routes, corner markets, etc.

### 3. Market Dynamics ✅
**DECISION: Fully Dynamic Supply/Demand Pricing**
- Prices change based on actual supply and demand
- Stockouts drive up prices (fuel station without fuel pays premium)
- Supply disruption affects entire chains (destroyed fuel convoy = higher prices)
- Player actions can manipulate regional economies
- Example: Blockade warpgate → fuel shortage → price spike → regional economic impact

### 4. Trade Specialization ✅
**DECISION: Complete Trading Spectrum**
All trading types included:
- **Basic commodities** (food, metals, manufactured goods)
- **Luxury/rare goods** with higher margins but more risk
- **Illegal contraband** with high profits but legal/diplomatic risks
- **Time-sensitive cargo** (medical supplies, news data, perishables)

### 5. Economic Goals & Player Paths ✅
**DECISION: Multiple Victory Conditions**
Three primary gameplay paths:
- **Economic Domination**: Build trading empire → Buy out competitors → Control galaxy financially
- **Faction Leadership**: Join organization → Rise through ranks → Take control through missions/politics
- **Military Mercenary**: Combat focus → Sell loot → Build forces → Conquest through warfare

## Core Economic Principles

### 1. Resource Scarcity & Production Reality
- **Nothing spawns from thin air** - all goods must be produced/harvested
- **Supply chains can break** - facilities need constant resupply to function
- **Stockouts have consequences** - empty fuel depot can't refuel ships
- **Transport is vulnerable** - convoys can be attacked, disrupting supply

### 2. Facility Dependency
- **Fuel Depots** need fuel deliveries to operate
- **Repair Bays** need spare parts and materials
- **Refineries** need raw materials to produce goods
- **Markets** need goods to sell
- **All facilities** consume resources and need resupply

### 3. Economic Warfare Potential
- **Supply route interdiction** - blockade key routes to starve regions
- **Market manipulation** - corner markets through large purchases
- **Facility sabotage** - destroy key production to create shortages
- **Economic espionage** - gather intelligence on competitor operations

## Technical Implementation Details

### 1. Commodity System ✅
**DECISION: Expandable Tier-Based Production Tree**
- **Production Tree**: Raw Materials → Primary Processing → Secondary Processing → Complex Assembly → Final Products
- **Commodity Categories**: See detailed production tree in `commodity_production_tree.md`
- **Expandable Design**: New commodities added as systems are developed
- **Multi-Input Production**: Facilities can require multiple inputs (e.g., Electronics = Silicon + Copper)

### 2. Supply Chain Architecture ✅
**DECISION: Realistic Multi-Tier Production Chains**
- **Tier 1**: Raw materials (mined/harvested directly from celestial bodies)
- **Tier 2**: Primary processing (ore → refined metals, hydrogen → fuel)
- **Tier 3**: Secondary processing (components assembly)
- **Tier 4**: Complex assembly (ship parts, facility modules)
- **Tier 5**: Final products (complete ships, facilities, consumer goods)

### 3. NPC Economic Behavior ✅
**DECISION: Equal Competition Model**
- **No Advantages**: NPCs follow same economic rules as players
- **Resource Dependency**: All NPC stations/ships/planets require resources to operate
- **Competitive Trading**: NPCs seek best prices and highest profits
- **Market Participation**: NPCs compete directly with players for resources and contracts
- **Consumption Reality**: All entities consume fuel, food, medical supplies, etc.

### 4. Facility Operations ✅
**DECISION: Realistic Inventory & Capacity Management**

#### Storage & Capacity
- **Storage Limits**: All facilities have maximum stockpile capacity
- **Overhead Costs**: Excessive inventory affects operational costs and pricing
- **Emergency Reserves**: Facilities maintain minimum stock levels to avoid production halts
- **Automatic Ordering**: Facilities place market orders when reserves get low

#### Information Transparency
- **Public Information**: Prices, production output volumes, general availability
- **Private Information**: Input stock levels, internal inventory, specific supply needs
- **Market Orders**: Buy/sell orders visible on commodity exchanges
- **Intelligence Value**: Hidden information available through espionage networks

### 5. Economic Intelligence & Information Systems ✅
**DECISION: Tiered Information Access**

#### Publicly Available
- **Current Prices**: Always visible at trading locations
- **Price History**: Historical price charts for trend analysis
- **Supply Indicators**: General availability (Low/Medium/High) based on market orders
- **Production Data**: Output volumes and facility capacity utilization

#### Faction/Organization Access
- **Transport Routes**: Known trade routes only visible to faction members
- **Supply Contracts**: Internal faction supply agreements
- **Strategic Resources**: Faction resource stockpile information

#### Intelligence Networks Required
- **Competitor Routes**: Other factions' trade routes and schedules
- **Supply Vulnerabilities**: Critical supply dependencies of competitors
- **Market Manipulation**: Planned large trades or economic warfare
- **Production Secrets**: Advanced facility configurations and efficiencies

### 6. Market Mechanics ✅
**DECISION: Dynamic Supply/Demand Exchange System**

#### Price Dynamics
- **Supply/Demand Driven**: Prices fluctuate based on actual availability and need
- **Stockout Premiums**: Empty facilities pay premium prices for critical supplies
- **Market Manipulation**: Large trades can temporarily affect regional prices
- **Transport Costs**: Distance and route safety affect final prices

#### Trading Interface
- **Spot Markets**: Immediate buy/sell at current prices
- **Contract Markets**: Future delivery contracts at negotiated prices
- **Bulk Trading**: Volume discounts for large transactions
- **Emergency Orders**: Premium pricing for urgent supply needs

---

## Integration with Existing Systems

### Service Facility Integration
- **Service Dependencies**: Service facilities consume resources to operate
  - Fuel Depots need fuel to sell
  - Repair Bays need spare parts and materials
  - Medical facilities need medical supplies
- **Service Quality**: Resource availability affects service pricing and availability

### Travel System Integration
- **Transport Routes**: Established shipping lanes between systems
- **Cargo Ships**: NPC and player vessels moving commodities
- **Route Security**: Piracy and conflicts affect transport costs
- **Supply Disruption**: Attacks on convoys create regional shortages
