from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Callable
from enum import Enum
from collections import defaultdict
import json
import networkx as nx
import matplotlib.pyplot as plt


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
            cls.INITIAL: "Начальное",
            cls.FINAL: "Конечное",
            cls.INTERMEDIATE: "Промежуточное",
            cls.ERROR: "Ошибка"
        }
        return mapping.get(self, "Неизвестно")


@dataclass
class Object:
    name: str
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


@dataclass
class Action:
    id: str
    name: str
    description: str = ""
    
    required_objects: Set[str] = field(default_factory=set)
    produced_objects: Set[str] = field(default_factory=set)
    consumed_objects: Set[str] = field(default_factory=set)
    preconditions: List[Dict] = field(default_factory=list)
    postconditions: List[Dict] = field(default_factory=list)
    execution_time: float = 1.0
    probability: float = 1.0
    
    _precondition_funcs: List[Callable] = field(default_factory=list, repr=False)
    _postcondition_funcs: List[Callable] = field(default_factory=list, repr=False)
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        for precondition in self._precondition_funcs:
            if not precondition(context):
                return False
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.can_execute(context):
            raise ValueError(f"Действие {self.name} не может быть выполнено")
        
        for postcondition in self._postcondition_funcs:
            postcondition(context)
        
        return context


class InstructionGraph:
    def __init__(self, name: str = "InstructionGraph"):
        self.name = name
        self.states: Dict[str, State] = {}
        self.actions: Dict[str, Action] = {}
        self.objects: Dict[str, Object] = {}
        self.transitions: Dict[tuple, str] = {}
        self.current_state_id: Optional[str] = None
        self.execution_history: List[tuple] = []
        
    @classmethod
    def from_json(cls, json_file: str):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        graph = cls(data.get('name', 'InstructionGraph'))
        
        for obj_data in data.get('objects', []):
            obj = Object(
                name=obj_data['name'],
                properties={}
            )
            graph.add_object(obj)
        
        for state_data in data.get('states', []):
            state = State(
                id=state_data['id'],
                name=state_data['name'],
                description=state_data.get('description', ''),
                state_type=StateType.from_string(state_data.get('type', 'intermediate')),
                objects_state=state_data.get('objects_state', {})
            )
            graph.add_state(state)
        
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
            action._precondition_funcs = cls._compile_conditions(action.preconditions, graph)
            action._postcondition_funcs = cls._compile_conditions(action.postconditions, graph)
            graph.add_action(action)
        
        for trans_data in data.get('transitions', []):
            graph.add_transition(
                trans_data['from'],
                trans_data['action'],
                trans_data['to']
            )
        
        return graph
    
    @staticmethod
    def _compile_conditions(conditions: List[Dict], graph: 'InstructionGraph') -> List[Callable]:
        compiled = []
        
        for cond in conditions:
            cond_type = cond.get('type')
            
            if cond_type == 'object_property':
                obj_name = cond['object']
                prop_name = cond['property']
                operator = cond['operator']
                value = cond['value']
                
                def make_check(obj_name, prop_name, operator, value):
                    def check(context):
                        current_state_id = context['current_state']
                        current_state = graph.states.get(current_state_id)
                        if not current_state:
                            return False
                        
                        obj_state = current_state.objects_state.get(obj_name, {})
                        prop_value = obj_state.get(prop_name)
                        
                        if prop_value is None:
                            return False
                        
                        if operator == '>':
                            return prop_value > value
                        elif operator == '<':
                            return prop_value < value
                        elif operator == '==':
                            return prop_value == value
                        elif operator == '!=':
                            return prop_value != value
                        elif operator == '>=':
                            return prop_value >= value
                        elif operator == '<=':
                            return prop_value <= value
                        return False
                    return check
                
                compiled.append(make_check(obj_name, prop_name, operator, value))
            
            elif cond_type == 'set_property':
                obj_name = cond['object']
                prop_name = cond['property']
                value = cond['value']
                
                def make_setter(obj_name, prop_name, value):
                    def setter(context):
                        if 'next_state_id' in context:
                            next_state = graph.states.get(context['next_state_id'])
                            if next_state:
                                if obj_name not in next_state.objects_state:
                                    next_state.objects_state[obj_name] = {}
                                next_state.objects_state[obj_name][prop_name] = value
                    return setter
                
                compiled.append(make_setter(obj_name, prop_name, value))
            
            elif cond_type == 'modify_property':
                obj_name = cond['object']
                prop_name = cond['property']
                operation = cond['operation']
                value = cond['value']
                
                def make_modifier(obj_name, prop_name, operation, value):
                    def modifier(context):
                        if 'next_state_id' in context:
                            next_state = graph.states.get(context['next_state_id'])
                            if next_state:
                                if obj_name not in next_state.objects_state:
                                    next_state.objects_state[obj_name] = {}
                                current = next_state.objects_state[obj_name].get(prop_name, 0)
                                if operation == 'add':
                                    next_state.objects_state[obj_name][prop_name] = current + value
                                elif operation == 'subtract':
                                    next_state.objects_state[obj_name][prop_name] = current - value
                                elif operation == 'multiply':
                                    next_state.objects_state[obj_name][prop_name] = current * value
                                elif operation == 'divide':
                                    next_state.objects_state[obj_name][prop_name] = current / value
                    return modifier
                
                compiled.append(make_modifier(obj_name, prop_name, operation, value))
            
            elif cond_type == 'print':
                message_template = cond.get('message', '')
                
                def make_printer(message_template):
                    def printer(context):
                        message = message_template
                        current_state_id = context['current_state']
                        current_state = graph.states.get(current_state_id)
                        if current_state:
                            for obj_name, obj_props in current_state.objects_state.items():
                                for prop_name, prop_value in obj_props.items():
                                    placeholder = f"{{{obj_name}.{prop_name}}}"
                                    if placeholder in message:
                                        message = message.replace(placeholder, str(prop_value))
                        print(f"      {message}")
                    return printer
                
                compiled.append(make_printer(message_template))
        
        return compiled
    
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
    
    def get_available_actions(self, state_id: Optional[str] = None) -> List[tuple]:
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
            
            return True
            
        except Exception as e:
            if not silent:
                print(f"[ОШИБКА] При выполнении {action.name}: {e}")
            return False
    
    def _get_context(self, next_state_id: Optional[str] = None) -> Dict[str, Any]:
        context = {
            'current_state': self.current_state_id,
            'next_state_id': next_state_id,
            'objects': self.objects.copy(),
            'execution_history': self.execution_history.copy()
        }
        return context
    
    def _update_context(self, context: Dict[str, Any], next_state_id: str) -> None:
        if 'objects' in context:
            self.objects.update(context['objects'])
    
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
    
    def step_by_step_mode(self):
        print("\n" + "="*70)
        print("ИНТЕРАКТИВНЫЙ ПОШАГОВЫЙ РЕЖИМ")
        print("="*70)
        
        if self.current_state_id is None:
            print("[ОШИБКА] Нет начального состояния!")
            return
        
        steps = 0
        max_steps = 100
        
        while steps < max_steps:
            current_state = self.states[self.current_state_id]
            print("\n" + "-"*70)
            print(f"[ТЕКУЩЕЕ СОСТОЯНИЕ] {current_state.name}")
            print(f"   Описание: {current_state.description}")
            print(f"   Тип: {current_state.state_type.to_rus()}")
            
            if current_state.objects_state:
                print("\n   Состояние объектов:")
                formatted = self.format_objects_state(current_state.objects_state)
                print(formatted)
            
            if current_state.state_type in [StateType.FINAL, StateType.ERROR]:
                print(f"\n{'[ДОСТИГНУТО КОНЕЧНОЕ СОСТОЯНИЕ]' if current_state.state_type == StateType.FINAL else '[ДОСТИГНУТО СОСТОЯНИЕ ОШИБКИ]'}")
                break
            
            available_actions = self.get_available_actions()
            
            if not available_actions:
                print("\n[ПРЕДУПРЕЖДЕНИЕ] Нет доступных действий из текущего состояния!")
                break
            
            print(f"\n[ДОСТУПНЫЕ ДЕЙСТВИЯ] ({len(available_actions)}):")
            print("   +----+--------------------------------------------------+-----------------------+")
            print("   | №  | Действие                                         | Следующее состояние   |")
            print("   +----+--------------------------------------------------+-----------------------+")
            
            for idx, (action, next_state_id) in enumerate(available_actions, 1):
                next_state = self.states[next_state_id]
                action_name = action.name[:48] + "..." if len(action.name) > 48 else action.name
                print(f"   | {idx:2} | {action_name:<48} | {next_state.name:<21} |")
            
            print("   +----+--------------------------------------------------+-----------------------+")
            print("   | 0  | Выход                                            | -                     |")
            print("   | q  | Показать историю                                 | -                     |")
            print("   | s  | Показать статистику                              | -                     |")
            print("   | v  | Визуализировать граф                             | -                     |")
            print("   +----+--------------------------------------------------+-----------------------+")
            
            choice = input("\nВаш выбор: ").strip().lower()
            
            if choice == '0':
                print("\nВыход из пошагового режима.")
                break
            elif choice == 'q':
                self.show_history()
                continue
            elif choice == 's':
                self.print_statistics()
                continue
            elif choice == 'v':
                self.visualize("step_visualization")
                continue
            
            try:
                idx = int(choice)
                if 1 <= idx <= len(available_actions):
                    action, next_state_id = available_actions[idx - 1]
                    
                    print(f"\nВыполнить действие: {action.name}?")
                    confirm = input("   Подтвердить (y/n): ").strip().lower()
                    
                    if confirm == 'y':
                        print(f"\nВыполняется: {action.name}...")
                        success = self.execute_action(action.id)
                        if success:
                            steps += 1
                    else:
                        print("   Действие отменено.")
                else:
                    print("[ОШИБКА] Неверный номер действия!")
            except ValueError:
                print("[ОШИБКА] Неверная команда!")
        
        if steps >= max_steps:
            print(f"\n[ПРЕДУПРЕЖДЕНИЕ] Достигнуто максимальное количество шагов ({max_steps})!")
        
        print("\n" + "="*70)
        print(f"Пошаговый режим завершен. Выполнено шагов: {steps}")
        print("="*70)
    
    def show_history(self):
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
    
    def visualize(self, filename: str = "instruction_graph") -> None:
        try:
            G = nx.DiGraph()
            
            # Цвета для разных типов узлов
            state_color = '#AED6F1'      # светлый синий
            action_color = '#ABEBC6'     # светлый зеленый
            object_color = '#F9E79F'     # светлый желтый
            initial_color = '#F5B7B1'    # светлый красный
            final_color = '#D5D8DC'      # серый
            
            # Добавляем узлы состояний
            for state_id, state in self.states.items():
                if state.state_type == StateType.INITIAL:
                    color = initial_color
                elif state.state_type == StateType.FINAL:
                    color = final_color
                else:
                    color = state_color
                
                # Формируем подпись с состоянием объектов (только True значения)
                obj_lines = []
                for obj_name, obj_props in state.objects_state.items():
                    true_props = []
                    for prop_name, prop_value in obj_props.items():
                        if prop_value is True:
                            true_props.append(prop_name)
                        elif prop_value is not False and prop_value is not None:
                            true_props.append(f"{prop_name}={prop_value}")
                    if true_props:
                        obj_lines.append(f"{obj_name}: {', '.join(true_props)}")
                
                obj_text = "\n".join(obj_lines[:3])
                if obj_text and len(obj_text) > 50:
                    obj_text = obj_text[:47] + "..."
                label = f"{state.name}\n{state.description[:20]}" + (f"\n{obj_text}" if obj_text else "")
                
                G.add_node(f"state_{state_id}", 
                        label=label,
                        type='state',
                        color=color)
            
            # Добавляем узлы действий
            for action_id, action in self.actions.items():
                G.add_node(f"action_{action_id}",
                        label=f"{action.name[:30]}",
                        type='action',
                        color=action_color)
            
            # Добавляем узлы объектов (только имена)
            for obj_name in self.objects.keys():
                G.add_node(f"object_{obj_name}",
                        label=obj_name,
                        type='object',
                        color=object_color)
            
            # Добавляем ребра: состояние -> действие и действие -> состояние
            for (from_state, action_id), to_state in self.transitions.items():
                action = self.actions.get(action_id)
                if action:
                    G.add_edge(f"state_{from_state}", f"action_{action_id}")
                    G.add_edge(f"action_{action_id}", f"state_{to_state}")
            
            # Добавляем связи объектов с действиями (required) - пунктирные стрелки
            for action_id, action in self.actions.items():
                for obj_name in action.required_objects:
                    G.add_edge(f"object_{obj_name}", f"action_{action_id}", style='dashed')
            
            # Настройка отображения
            plt.figure(figsize=(16, 12))
            
            # Позиционирование узлов
            pos = {}
            state_count = 0
            action_count = 0
            object_count = 0
            
            # Располагаем состояния слева, действия в центре, объекты справа
            for node, data in G.nodes(data=True):
                node_type = data.get('type', 'state')
                if node_type == 'state':
                    pos[node] = (-3, state_count * 1.5 - 4)
                    state_count += 1
                elif node_type == 'action':
                    pos[node] = (0, action_count * 1.5 - 4)
                    action_count += 1
                else:
                    pos[node] = (3, object_count * 1.5 - 4)
                    object_count += 1
            
            # Рисуем узлы по типам
            for node_type, color in [('state', state_color), ('action', action_color), ('object', object_color)]:
                nodes = [n for n, d in G.nodes(data=True) if d.get('type') == node_type]
                if nodes:
                    nx.draw_networkx_nodes(G, pos, nodelist=nodes,
                                        node_color=color, node_size=2500,
                                        edgecolors='black', linewidths=1,
                                        alpha=0.9)
            
            # Отдельно рисуем начальное и конечное состояния (чтобы выделить цветом)
            initial_nodes = [f"state_{sid}" for sid, s in self.states.items() if s.state_type == StateType.INITIAL]
            final_nodes = [f"state_{sid}" for sid, s in self.states.items() if s.state_type == StateType.FINAL]
            
            if initial_nodes:
                nx.draw_networkx_nodes(G, pos, nodelist=initial_nodes,
                                    node_color=initial_color, node_size=2500,
                                    edgecolors='black', linewidths=2,
                                    alpha=0.9)
            
            if final_nodes:
                nx.draw_networkx_nodes(G, pos, nodelist=final_nodes,
                                    node_color=final_color, node_size=2500,
                                    edgecolors='black', linewidths=2,
                                    alpha=0.9)
            
            # Рисуем ребра с явными стрелками
            # Разделяем обычные и пунктирные ребра
            solid_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('style') != 'dashed']
            dashed_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('style') == 'dashed']
            
            # Рисуем сплошные ребра со стрелками
            if solid_edges:
                for u, v in solid_edges:
                    # Получаем координаты узлов
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    
                    # Рисуем линию
                    plt.plot([x1, x2], [y1, y2], 'gray', linewidth=1.5, alpha=0.7, zorder=1)
                    
                    # Рисуем стрелку в конце линии
                    dx = x2 - x1
                    dy = y2 - y1
                    d = (dx**2 + dy**2)**0.5
                    if d > 0:
                        # Позиция стрелки (в 80% от начала к концу)
                        arrow_pos = 0.85
                        x_arrow = x1 + dx * arrow_pos
                        y_arrow = y1 + dy * arrow_pos
                        
                        # Нормализованное направление
                        ndx = dx / d
                        ndy = dy / d
                        
                        # Рисуем стрелку
                        arrow_length = 0.15
                        arrow_width = 0.08
                        plt.arrow(x_arrow, y_arrow, ndx * arrow_length, ndy * arrow_length,
                                head_width=arrow_width, head_length=arrow_length,
                                fc='gray', ec='gray', alpha=0.8, zorder=2)
            
            # Рисуем пунктирные ребра со стрелками
            if dashed_edges:
                for u, v in dashed_edges:
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    
                    # Рисуем пунктирную линию
                    plt.plot([x1, x2], [y1, y2], 'gray', linewidth=1.5, 
                            linestyle='--', alpha=0.6, zorder=1)
                    
                    # Рисуем стрелку в конце линии
                    dx = x2 - x1
                    dy = y2 - y1
                    d = (dx**2 + dy**2)**0.5
                    if d > 0:
                        arrow_pos = 0.85
                        x_arrow = x1 + dx * arrow_pos
                        y_arrow = y1 + dy * arrow_pos
                        
                        ndx = dx / d
                        ndy = dy / d
                        
                        arrow_length = 0.15
                        arrow_width = 0.08
                        plt.arrow(x_arrow, y_arrow, ndx * arrow_length, ndy * arrow_length,
                                head_width=arrow_width, head_length=arrow_length,
                                fc='gray', ec='gray', alpha=0.7, zorder=2)
            
            # Рисуем подписи узлов
            labels = nx.get_node_attributes(G, 'label')
            for node, (x, y) in pos.items():
                label = labels.get(node, '')
                plt.text(x, y, label, fontsize=8, fontweight='bold',
                        ha='center', va='center', zorder=3,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        # Легенда
            from matplotlib.patches import Patch
            from matplotlib.lines import Line2D
            
            legend_elements = [
                Patch(facecolor=state_color, alpha=0.8, edgecolor='black', label='Состояния (промежуточные)'),
                Patch(facecolor=action_color, alpha=0.8, edgecolor='black', label='Действия'),
                Patch(facecolor=object_color, alpha=0.8, edgecolor='black', label='Объекты'),
                Patch(facecolor=initial_color, alpha=0.8, edgecolor='black', label='Начальное состояние'),
                Patch(facecolor=final_color, alpha=0.8, edgecolor='black', label='Конечное состояние'),
                Line2D([0], [0], color='gray', linewidth=1.5, 
                    marker='>', markersize=10, markeredgewidth=1.5,
                    label='Переход (направление показано стрелкой)'),
                Line2D([0], [0], color='gray', linewidth=1.5, linestyle='--',
                    marker='>', markersize=10, markeredgewidth=1.5,
                    label='Использование объекта (пунктир со стрелкой)')
            ]
            plt.legend(handles=legend_elements, loc='upper right', fontsize=10, framealpha=0.9)
            
            plt.title(f"Граф инструкций: {self.name}\n(Состояния, действия и объекты как отдельные узлы)", 
                    fontsize=14, fontweight='bold')
            plt.axis('off')
            
            # Устанавливаем равные пропорции осей
            plt.gca().set_aspect('equal')
            
            plt.tight_layout()
            plt.savefig(f"{filename}.png", dpi=300, bbox_inches='tight')
            print(f"[ИНФО] Граф сохранен как {filename}.png")
            plt.show()
        except Exception as e:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Визуализация не удалась: {e}")
            import traceback
            traceback.print_exc()
    
    def print_ascii_graph(self) -> None:
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
        
        print("\n[ПЕРЕХОДЫ]")
        for (from_state, action_id), to_state in self.transitions.items():
            action = self.actions.get(action_id)
            from_state_name = self.states[from_state].name
            to_state_name = self.states[to_state].name
            action_name = action.name if action else action_id
            print(f"   {from_state_name} -> [{action_name}] -> {to_state_name}")
        
        print("\n[ОБЪЕКТЫ]")
        for obj_name in self.objects.keys():
            print(f"   - {obj_name}")
        
        print("="*70)


def main():
    import sys
    import os
    
    print("=" * 70)
    print("ЗАГРУЗЧИК ГРАФА ИНСТРУКЦИЙ (Сеть Петри + Диаграмма состояний)")
    print("=" * 70)
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = input("\nВведите путь к JSON файлу с инструкцией (по умолчанию: coffee_linear.json): ").strip()
        if not json_file:
            json_file = "coffee_linear.json"
    
    if not os.path.exists(json_file):
        print(f"\n[ОШИБКА] Файл {json_file} не найден!")
        print("   Создайте файл конфигурации или проверьте путь.")
        return
    
    try:
        print(f"\nЗагрузка графа из {json_file}...")
        graph = InstructionGraph.from_json(json_file)
        print("[УСПЕХ] Граф успешно загружен!")
    except Exception as e:
        print(f"[ОШИБКА] Не удалось загрузить JSON: {e}")
        return
    
    print(f"\n[ИНФОРМАЦИЯ О ГРАФЕ]")
    print(f"   Название: {graph.name}")
    print(f"   Состояний: {len(graph.states)}")
    print(f"   Действий: {len(graph.actions)}")
    print(f"   Объектов: {len(graph.objects)}")
    print(f"   Переходов: {len(graph.transitions)}")
    
    graph.print_ascii_graph()
    
    print("\n" + "="*70)
    print("ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:")
    print("="*70)
    print("   1. Интерактивный пошаговый режим (ручное управление)")
    print("   2. Показать информацию о графе")
    print("   3. Визуализировать граф (состояния, действия, объекты)")
    print("   0. Выход")
    print("="*70)
    
    choice = input("\nВаш выбор (0-3): ").strip()
    
    if choice == '1':
        print("\nЗапуск пошагового режима...")
        input("Нажмите Enter для начала...")
        graph.step_by_step_mode()
        
        print("\n[ИТОГОВАЯ СТАТИСТИКА]")
        graph.print_statistics()
        print("\n[ПОЛНАЯ ИСТОРИЯ]")
        graph.show_history()
        
    elif choice == '2':
        print("\n[ДЕТАЛЬНАЯ ИНФОРМАЦИЯ]")
        graph.print_statistics()
        
    elif choice == '3':
        print("\nВизуализация графа...")
        graph.visualize("loaded_graph")
        print("[УСПЕХ] Визуализация графа завершена!")
        
    elif choice == '0':
        print("\nДо свидания!")
        return
    
    else:
        print("\n[ОШИБКА] Неверный выбор!")
    
    result_file = json_file.replace('.json', '_result.json')
    print(f"\nСохранение результатов в {result_file}...")
    
    final_objects_state = graph.get_current_objects_state()
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'execution_history': graph.execution_history,
            'final_state_id': graph.current_state_id,
            'final_state_name': graph.states[graph.current_state_id].name if graph.current_state_id else None,
            'final_objects_state': final_objects_state
        }, f, indent=2, ensure_ascii=False)
    print("[УСПЕХ] Результаты сохранены!")
    
    print("\n" + "="*70)
    print("Программа завершена")
    print("="*70)


if __name__ == "__main__":
    main()