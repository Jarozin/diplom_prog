from typing import Dict, List, Optional, Tuple, Any
import json

from models import Object, State, Action, StateType, HistoryStep


class InstructionGraph:
    def __init__(self, name: str = "InstructionGraph", label_manager=None):
        self.name = name
        self.states: Dict[str, State] = {}
        self.actions: Dict[str, Action] = {}
        self.objects: Dict[str, Object] = {}
        self.transitions: Dict[tuple, str] = {}
        self.current_state_id: Optional[str] = None
        self.execution_history: List[HistoryStep] = []
        self.label_manager = label_manager
    
    @classmethod
    def from_json(cls, json_file: str, label_manager=None):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        graph = cls(data.get('name', 'InstructionGraph'), label_manager)
        for obj_data in data.get('objects', []):
            obj = Object(name=obj_data['name'], obj_type=obj_data.get('type', 'object'), properties={})
            graph.add_object(obj)
        for state_data in data.get('states', []):
            state = State(
                id=state_data['id'], name=state_data['name'], description=state_data.get('description', ''),
                state_type=StateType.from_string(state_data.get('type', 'intermediate')),
                objects_state=state_data.get('objects_state', {})
            )
            graph.add_state(state)
        for action_data in data.get('actions', []):
            action = Action(
                id=action_data['id'], name=action_data['name'], description=action_data.get('description', ''),
                required_objects=set(action_data.get('required_objects', [])),
                produced_objects=set(action_data.get('produced_objects', [])),
                consumed_objects=set(action_data.get('consumed_objects', [])),
                execution_time=action_data.get('execution_time', 1.0),
                probability=action_data.get('probability', 1.0)
            )
            graph.add_action(action)
        for trans_data in data.get('transitions', []):
            graph.add_transition(trans_data['from'], trans_data['action'], trans_data['to'])
        return graph
    
    def add_state(self, state: State) -> None:
        self.states[state.id] = state
        if state.state_type == StateType.INITIAL and self.current_state_id is None:
            self.current_state_id = state.id
    
    def add_action(self, action: Action) -> None:
        self.actions[action.id] = action
    
    def add_object(self, obj: Object) -> None:
        self.objects[obj.name] = obj
    
    def add_transition(self, from_state_id: str, action_id: str, to_state_id: str) -> None:
        if from_state_id not in self.states:
            raise ValueError(f"Состояние {from_state_id} не найдено")
        if action_id not in self.actions:
            raise ValueError(f"Действие {action_id} не найдено")
        if to_state_id not in self.states:
            raise ValueError(f"Состояние {to_state_id} не найдено")
        self.transitions[(from_state_id, action_id)] = to_state_id
    
    def get_available_actions(self, state_id: Optional[str] = None) -> List[Tuple[Action, str]]:
        if state_id is None:
            state_id = self.current_state_id
        if state_id is None:
            return []
        available = []
        for (from_state, action_id), to_state in self.transitions.items():
            if from_state == state_id:
                action = self.actions.get(action_id)
                if action:
                    available.append((action, to_state))
        return available
    
    def execute_action(self, action_id: str, recommendations: Optional[List[Dict]] = None, silent: bool = False) -> bool:
        if self.current_state_id is None:
            if not silent:
                print("Нет текущего состояния")
            return False
        transition_key = (self.current_state_id, action_id)
        if transition_key not in self.transitions:
            if not silent:
                print(f"Нет перехода из {self.current_state_id} с действием {action_id}")
            return False
        action = self.actions.get(action_id)
        if not action:
            if not silent:
                print(f"Действие {action_id} не найдено")
            return False
        next_state_id = self.transitions[transition_key]
        old_state = self.current_state_id
        old_state_name = self.states[old_state].name
        self.current_state_id = next_state_id
        new_state_name = self.states[self.current_state_id].name
        history_step = HistoryStep(
            from_state=old_state, from_state_name=old_state_name,
            action_id=action_id, action_name=action.name,
            to_state=self.current_state_id, to_state_name=new_state_name,
            recommendations=recommendations or []
        )
        self.execution_history.append(history_step)
        if not silent:
            print(f"\n[ВЫПОЛНЕНО] {action.name}")
            print(f"     Из: {old_state_name}")
            print(f"     В: {new_state_name}")
        return True
    
    def get_current_objects_state(self) -> Dict[str, Dict[str, Any]]:
        if self.current_state_id and self.current_state_id in self.states:
            return self.states[self.current_state_id].objects_state
        return {}
    
    def format_objects_state(self, objects_state: Dict[str, Dict[str, Any]]) -> str:
        if not objects_state:
            return ""
        lines = []
        for obj_name, obj_props in objects_state.items():
            true_props = []
            for prop_name, prop_value in obj_props.items():
                if prop_value is True:
                    true_props.append(prop_name)
                elif prop_value is not False and prop_value is not None:
                    true_props.append(f"{prop_name}={prop_value}")
            if true_props:
                lines.append(f"      {obj_name}: {', '.join(true_props)}")
            else:
                lines.append(f"      {obj_name}: (нет активных свойств)")
        return "\n".join(lines)
    
    def show_history(self):
        print("\n[ИСТОРИЯ ВЫПОЛНЕНИЯ]")
        if not self.execution_history:
            print("   (пусто)")
            return
        for i, step in enumerate(self.execution_history, 1):
            print(f"\n   {i}. {step.from_state_name} -> [{step.action_name}] -> {step.to_state_name}")
            if step.recommendations:
                print(f"      Рекомендации:")
                for rec in step.recommendations:
                    print(f"        - {rec['text']}")
            else:
                print(f"      (рекомендации не показывались)")
    
    def print_statistics(self):
        print("\n[ТЕКУЩАЯ СТАТИСТИКА]")
        print(f"   Текущее состояние: {self.states[self.current_state_id].name if self.current_state_id else 'Нет'}")
        print(f"   Выполнено действий: {len(self.execution_history)}")
        print(f"   Доступно действий: {len(self.get_available_actions())}")
        print(f"   Всего состояний: {len(self.states)}")
        print(f"   Всего объектов: {len(self.objects)}")
        objects_state = self.get_current_objects_state()
        if objects_state:
            print(f"\n[СОСТОЯНИЕ ОБЪЕКТОВ В ТЕКУЩЕМ СОСТОЯНИИ]")
            print(self.format_objects_state(objects_state))
    
    def print_ascii_graph(self) -> None:
        print("\n" + "="*70)
        print(f"ГРАФ ИНСТРУКЦИЙ: {self.name}")
        print("="*70)
        print("\n[СОСТОЯНИЯ]")
        for state_id, state in self.states.items():
            type_marker = {
                StateType.INITIAL: "(НАЧ)", StateType.FINAL: "(КОН)",
                StateType.ERROR: "(ОШИБ)", StateType.INTERMEDIATE: "(-)"
            }.get(state.state_type, "(-)")
            current_marker = " <- ТЕКУЩЕЕ" if state_id == self.current_state_id else ""
            print(f"   {type_marker} {state.name} [{state_id}]: {state.description}{current_marker}")
            if state.objects_state:
                for obj_name, obj_props in state.objects_state.items():
                    true_props = []
                    for prop_name, prop_value in obj_props.items():
                        if prop_value is True:
                            true_props.append(prop_name)
                        elif prop_value is not False and prop_value is not None:
                            true_props.append(f"{prop_name}={prop_value}")
                    if true_props:
                        print(f"        - {obj_name}: {', '.join(true_props)}")
                    else:
                        print(f"        - {obj_name}: (нет активных свойств)")
        print("\n[ДЕЙСТВИЯ]")
        for action_id, action in self.actions.items():
            print(f"   [-] {action.name} [{action_id}]: {action.description}")
            if action.required_objects:
                print(f"        Требует: {', '.join(action.required_objects)}")
            if self.label_manager:
                labels = self.label_manager.get_labels_for_action(action)
                if labels:
                    label_names = [label.name for label in labels]
                    print(f"        Метки: {', '.join(label_names)}")
        print("\n[ПЕРЕХОДЫ]")
        for (from_state, action_id), to_state in self.transitions.items():
            action = self.actions.get(action_id)
            from_state_name = self.states[from_state].name
            to_state_name = self.states[to_state].name
            action_name = action.name if action else action_id
            print(f"   {from_state_name} -> [{action_name}] -> {to_state_name}")
        print("\n[ОБЪЕКТЫ]")
        for obj_name, obj in self.objects.items():
            obj_type = "субъект" if obj.obj_type == "subject" else "объект"
            print(f"   - {obj_name} ({obj_type})")
        print("="*70)