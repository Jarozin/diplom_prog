"""Основной класс графа инструкций"""

from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import json

from models import Object, State, Action, StateType
from conditions import compile_conditions
from labels import LabelManager


class InstructionGraph:
    """Гибридный граф инструкций (Сеть Петри + Диаграмма состояний)"""
    
    def __init__(self, name: str = "InstructionGraph", label_manager: Optional[LabelManager] = None):
        self.name = name
        self.states: Dict[str, State] = {}
        self.actions: Dict[str, Action] = {}
        self.objects: Dict[str, Object] = {}
        self.transitions: Dict[tuple, str] = {}
        self.current_state_id: Optional[str] = None
        self.execution_history: List[tuple] = []
        self.label_manager = label_manager or LabelManager()
        
    @classmethod
    def from_json(cls, json_file: str, label_manager: Optional[LabelManager] = None):
        """Загрузка графа из JSON файла"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        graph = cls(data.get('name', 'InstructionGraph'), label_manager)
        
        # Загружаем объекты
        for obj_data in data.get('objects', []):
            obj = Object(
                name=obj_data['name'],
                obj_type=obj_data.get('type', 'object'),
                properties={}
            )
            graph.add_object(obj)
        
        # Загружаем состояния
        for state_data in data.get('states', []):
            state = State(
                id=state_data['id'],
                name=state_data['name'],
                description=state_data.get('description', ''),
                state_type=StateType.from_string(state_data.get('type', 'intermediate')),
                objects_state=state_data.get('objects_state', {})
            )
            graph.add_state(state)
        
        # Загружаем действия (сначала без функций)
        actions_data = []
        for action_data in data.get('actions', []):
            action = Action(
                id=action_data['id'],
                name=action_data['name'],
                description=action_data.get('description', ''),
                required_objects=set(action_data.get('required_objects', [])),
                produced_objects=set(action_data.get('produced_objects', [])),
                consumed_objects=set(action_data.get('consumed_objects', [])),
                preconditions=action_data.get('preconditions', []),
                postconditions=action_data.get('postconditions', []),
                execution_time=action_data.get('execution_time', 1.0),
                probability=action_data.get('probability', 1.0)
            )
            actions_data.append((action, action_data))
        
        # Компилируем условия и добавляем действия
        for action, action_data in actions_data:
            action._precondition_funcs = compile_conditions(action.preconditions, graph)
            action._postcondition_funcs = compile_conditions(action.postconditions, graph)
            graph.add_action(action)
        
        # Загружаем переходы
        for trans_data in data.get('transitions', []):
            graph.add_transition(
                trans_data['from'],
                trans_data['action'],
                trans_data['to']
            )
        
        return graph
    
    def add_state(self, state: State) -> None:
        """Добавление состояния"""
        self.states[state.id] = state
        if state.state_type == StateType.INITIAL and self.current_state_id is None:
            self.current_state_id = state.id
    
    def add_action(self, action: Action) -> None:
        """Добавление действия"""
        self.actions[action.id] = action
    
    def add_object(self, obj: Object) -> None:
        """Добавление объекта"""
        self.objects[obj.name] = obj
    
    def add_transition(self, from_state_id: str, action_id: str, to_state_id: str) -> None:
        """Добавление перехода"""
        if from_state_id not in self.states:
            raise ValueError(f"Состояние {from_state_id} не найдено")
        if action_id not in self.actions:
            raise ValueError(f"Действие {action_id} не найдено")
        if to_state_id not in self.states:
            raise ValueError(f"Состояние {to_state_id} не найдено")
        
        self.transitions[(from_state_id, action_id)] = to_state_id
    
    def get_available_actions(self, state_id: Optional[str] = None) -> List[Tuple[Action, str]]:
        """Возвращает список доступных (action, next_state) из состояния"""
        if state_id is None:
            state_id = self.current_state_id
        
        if state_id is None:
            return []
        
        available = []
        for (from_state, action_id), to_state in self.transitions.items():
            if from_state == state_id:
                action = self.actions.get(action_id)
                if action and action.can_execute(self._get_context()):
                    available.append((action, to_state))
        
        return available
    
    def execute_action(self, action_id: str, silent: bool = False) -> bool:
        """Выполнение действия"""
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
        context = self._get_context(next_state_id)
        
        try:
            new_context = action.execute(context)
            self._update_context(new_context, next_state_id)
            
            old_state = self.current_state_id
            self.current_state_id = next_state_id
            
            self.execution_history.append((old_state, action_id, self.current_state_id))
            
            if not silent:
                print(f"\n[ВЫПОЛНЕНО] {action.name}")
                print(f"     Из: {self.states[old_state].name}")
                print(f"     В: {self.states[self.current_state_id].name}")
                
                if action.consumed_objects:
                    print(f"     Потреблено: {', '.join(action.consumed_objects)}")
                if action.produced_objects:
                    print(f"     Создано: {', '.join(action.produced_objects)}")
                
                # Показываем рекомендации для выполненного действия
                if self.label_manager:
                    self.label_manager.display_recommendations_for_action(action)
            
            return True
            
        except Exception as e:
            if not silent:
                print(f"[ОШИБКА] При выполнении {action.name}: {e}")
            return False
    
    def _get_context(self, next_state_id: Optional[str] = None) -> Dict[str, Any]:
        """Формирование контекста выполнения"""
        context = {
            'current_state': self.current_state_id,
            'next_state_id': next_state_id,
            'objects': self.objects.copy(),
            'execution_history': self.execution_history.copy()
        }
        return context
    
    def _update_context(self, context: Dict[str, Any], next_state_id: str) -> None:
        """Обновление контекста после выполнения"""
        if 'objects' in context:
            self.objects.update(context['objects'])
    
    def get_current_objects_state(self) -> Dict[str, Dict[str, Any]]:
        """Получить состояние объектов в текущем состоянии графа"""
        if self.current_state_id and self.current_state_id in self.states:
            return self.states[self.current_state_id].objects_state
        return {}
    
    def format_objects_state(self, objects_state: Dict[str, Dict[str, Any]]) -> str:
        """Форматирует состояние объектов для вывода"""
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
        """Показывает историю выполнения"""
        print("\n[ИСТОРИЯ ВЫПОЛНЕНИЯ]")
        if not self.execution_history:
            print("   (пусто)")
            return
        
        for i, (from_state, action_id, to_state) in enumerate(self.execution_history, 1):
            from_name = self.states[from_state].name if from_state in self.states else from_state
            to_name = self.states[to_state].name if to_state in self.states else to_state
            action_name = self.actions[action_id].name if action_id in self.actions else action_id
            print(f"   {i}. {from_name} -> [{action_name}] -> {to_name}")
    
    def print_statistics(self):
        """Показывает статистику"""
        print("\n[ТЕКУЩАЯ СТАТИСТИКА]")
        print(f"   Текущее состояние: {self.states[self.current_state_id].name if self.current_state_id else 'Нет'}")
        print(f"   Выполнено действий: {len(self.execution_history)}")
        print(f"   Доступно действий: {len(self.get_available_actions())}")
        print(f"   Всего состояний: {len(self.states)}")
        print(f"   Всего объектов: {len(self.objects)}")
        
        objects_state = self.get_current_objects_state()
        if objects_state:
            print(f"\n[СОСТОЯНИЕ ОБЪЕКТОВ В ТЕКУЩЕМ СОСТОЯНИИ]")
            formatted = self.format_objects_state(objects_state)
            print(formatted)
    
    def print_ascii_graph(self) -> None:
        """Вывод графа в текстовом виде"""
        print("\n" + "="*70)
        print(f"ГРАФ ИНСТРУКЦИЙ: {self.name}")
        print("="*70)
        
        print("\n[СОСТОЯНИЯ]")
        for state_id, state in self.states.items():
            type_marker = {
                StateType.INITIAL: "(НАЧ)",
                StateType.FINAL: "(КОН)",
                StateType.ERROR: "(ОШИБ)",
                StateType.INTERMEDIATE: "(-)"
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
            
            # Показываем метки для действия - передаем объект action
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