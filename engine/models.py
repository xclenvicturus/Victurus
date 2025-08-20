from dataclasses import dataclass
from typing import Optional

@dataclass
class Faction:
    id: int
    name: str
    description: str

@dataclass
class System:
    id: int
    name: str

@dataclass
class Planet:
    id: int
    name: str
    system_id: int

@dataclass
class Station:
    id: int
    name: str
    planet_id: int
    faction_id: int

@dataclass
class Item:
    id: int
    name: str
    base_price: int
    type: str
    description: str

@dataclass
class Ship:
    id: int
    name: str
    hull: int
    damage: int
    cargo_capacity: int
    base_price: int
    fuel_capacity: int
    jump_range: float
    efficiency: float
    shields: int = 0
    energy_capacity: int = 0

@dataclass
class NPC:
    id: int
    name: str
    station_id: int
    faction_id: int
    role: str
    dialog: str

@dataclass
class Quest:
    id: int
    title: str
    description: str
    giver_npc_id: int
    target_station_id: int
    reward_credits: int

@dataclass
class StartStation:
    id: int
    label: str
    has_hangar: int