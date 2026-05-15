from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum


class StateType(Enum):
    INITIAL = "initial"
    FINAL = "final"
    INTERMEDIATE = "intermediate"
    ERROR = "error"
    
    @classmethod
    def from_string(cls, value: str):
        mapping = {
            "initial": cls.INITIAL,
            "final": cls.FINAL,
            "intermediate": cls.INTERMEDIATE,
            "error": cls.ERROR
        }
        return mapping.get(value.lower(), cls.INTERMEDIATE)
    
    def to_rus(self) -> str:
        mapping = {
            StateType.INITIAL: "Начальное",
            StateType.FINAL: "Конечное",
            StateType.INTERMEDIATE: "Промежуточное",
            StateType.ERROR: "Ошибка"
        }
        return mapping.get(self, "Неизвестно")


@dataclass
class Object:
    name: str
    obj_type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Object) else False
    
    def __str__(self):
        return self.name
    
    def get_property(self, prop_name: str):
        return self.properties.get(prop_name)
    
    def set_property(self, prop_name: str, value: Any):
        self.properties[prop_name] = value


@dataclass
class State:
    id: str
    name: str
    description: str = ""
    state_type: StateType = StateType.INTERMEDIATE
    objects_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def get_true_properties(self, obj_name: str) -> List[str]:
        if obj_name not in self.objects_state:
            return []
        props = self.objects_state[obj_name]
        true_props = []
        for prop_name, prop_value in props.items():
            if prop_value is True:
                true_props.append(prop_name)
            elif prop_value is not False and prop_value is not None:
                true_props.append(f"{prop_name}={prop_value}")
        return true_props


@dataclass
class Action:
    id: str
    name: str
    description: str = ""
    required_objects: Set[str] = field(default_factory=set)
    produced_objects: Set[str] = field(default_factory=set)
    consumed_objects: Set[str] = field(default_factory=set)
    execution_time: float = 1.0
    probability: float = 1.0


@dataclass
class Label:
    name: str
    keywords: List[str]
    recommendations: List[Dict]
    
    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        search_text = text_lower.replace('_', ' ')
        for keyword in self.keywords:
            keyword_lower = keyword.lower().replace('_', ' ')
            if keyword_lower in search_text:
                return True
        return False


@dataclass
class HistoryStep:
    from_state: str
    from_state_name: str
    action_id: str
    action_name: str
    to_state: str
    to_state_name: str
    recommendations: List[Dict]