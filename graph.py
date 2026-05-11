from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Callable
from enum import Enum
from collections import defaultdict
import json
from graphviz import Digraph
import networkx as nx
import matplotlib.pyplot as plt


class StateType(Enum):
    """Типы состояний"""
    INITIAL = "initial"
    FINAL = "final"
    INTERMEDIATE = "intermediate"
    ERROR = "error"


@dataclass
class Object:
    """Объект, участвующий в инструкциях"""
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    current_state_id: Optional[str] = None
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Object) else False


@dataclass
class State:
    """Состояние в графе инструкций"""
    id: str
    name: str
    description: str = ""
    state_type: StateType = StateType.INTERMEDIATE
    objects_present: Set[Object] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Action:
    """Действие, которое переводит из одного состояния в другое"""
    id: str
    name: str
    description: str = ""
    
    # Объекты, участвующие в действии
    required_objects: Set[Object] = field(default_factory=set)
    produced_objects: Set[Object] = field(default_factory=set)
    consumed_objects: Set[Object] = field(default_factory=set)
    
    # Пред- и постусловия
    preconditions: List[Callable] = field(default_factory=list)
    postconditions: List[Callable] = field(default_factory=list)
    
    # Дополнительные параметры
    execution_time: float = 1.0
    probability: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Проверка, может ли действие быть выполнено"""
        # Проверяем все предусловия
        for precondition in self.preconditions:
            if not precondition(context):
                return False
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение действия"""
        if not self.can_execute(context):
            raise ValueError(f"Action {self.name} cannot be executed")
        
        # Применяем постусловия для модификации контекста
        for postcondition in self.postconditions:
            postcondition(context)
        
        return context


class InstructionGraph:
    """
    Гибридный граф инструкций, объединяющий сети Петри и диаграммы состояний
    """
    
    def __init__(self, name: str = "InstructionGraph"):
        self.name = name
        self.states: Dict[str, State] = {}
        self.actions: Dict[str, Action] = {}
        self.objects: Dict[str, Object] = {}
        
        # Транзиции: (from_state_id, action_id) -> to_state_id
        self.transitions: Dict[tuple, str] = {}
        
        # Текущее состояние выполнения
        self.current_state_id: Optional[str] = None
        self.execution_history: List[tuple] = []
        
        # Токены для параллельного выполнения (как в сетях Петри)
        self.tokens: Dict[str, int] = defaultdict(int)  # state_id -> количество токенов
        
    def add_state(self, state: State) -> None:
        """Добавление состояния"""
        self.states[state.id] = state
        if state.state_type == StateType.INITIAL:
            self.current_state_id = state.id
            self.tokens[state.id] = 1
    
    def add_action(self, action: Action) -> None:
        """Добавление действия"""
        self.actions[action.id] = action
    
    def add_object(self, obj: Object) -> None:
        """Добавление объекта"""
        self.objects[obj.name] = obj
    
    def add_transition(self, from_state_id: str, action_id: str, to_state_id: str) -> None:
        """Добавление перехода между состояниями через действие"""
        if from_state_id not in self.states:
            raise ValueError(f"State {from_state_id} not found")
        if action_id not in self.actions:
            raise ValueError(f"Action {action_id} not found")
        if to_state_id not in self.states:
            raise ValueError(f"State {to_state_id} not found")
        
        self.transitions[(from_state_id, action_id)] = to_state_id
    
    def get_available_actions(self, state_id: Optional[str] = None) -> List[Action]:
        """Получение доступных действий из заданного состояния"""
        if state_id is None:
            state_id = self.current_state_id
        
        if state_id is None:
            return []
        
        available_actions = []
        for (from_state, action_id), to_state in self.transitions.items():
            if from_state == state_id:
                action = self.actions.get(action_id)
                if action and action.can_execute(self._get_context()):
                    available_actions.append(action)
        
        return available_actions
    
    def execute_action(self, action_id: str, object_mapping: Optional[Dict[str, Object]] = None) -> bool:
        """
        Выполнение действия с возможной подстановкой объектов
        """
        if self.current_state_id is None:
            print("No current state set")
            return False
        
        # Проверяем существование перехода
        transition_key = (self.current_state_id, action_id)
        if transition_key not in self.transitions:
            print(f"No transition from {self.current_state_id} with action {action_id}")
            return False
        
        action = self.actions.get(action_id)
        if not action:
            print(f"Action {action_id} not found")
            return False
        
        # Создаем контекст выполнения
        context = self._get_context(object_mapping)
        
        # Выполняем действие
        try:
            new_context = action.execute(context)
            self._update_context(new_context)
            
            # Переходим в новое состояние
            old_state = self.current_state_id
            self.current_state_id = self.transitions[transition_key]
            
            # Обновляем токены (как в сетях Петри)
            self.tokens[old_state] -= 1
            self.tokens[self.current_state_id] += 1
            
            # Записываем в историю
            self.execution_history.append((old_state, action_id, self.current_state_id))
            
            print(f"✅ Executed: {action.name}")
            print(f"   From: {self.states[old_state].name}")
            print(f"   To: {self.states[self.current_state_id].name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to execute {action.name}: {e}")
            return False
    
    def _get_context(self, object_mapping: Optional[Dict[str, Object]] = None) -> Dict[str, Any]:
        """Формирование контекста выполнения"""
        context = {
            'current_state': self.current_state_id,
            'objects': object_mapping or self.objects.copy(),
            'tokens': dict(self.tokens),
            'execution_history': self.execution_history.copy()
        }
        return context
    
    def _update_context(self, context: Dict[str, Any]) -> None:
        """Обновление контекста после выполнения действия"""
        if 'objects' in context:
            self.objects.update(context['objects'])
        if 'tokens' in context:
            self.tokens.update(context['tokens'])
    
    def get_possible_paths(self, max_depth: int = 10) -> List[List[str]]:
        """
        Получение всех возможных путей выполнения (DFS)
        """
        paths = []
        
        def dfs(current_state_id: str, path: List[str], depth: int):
            if depth > max_depth:
                return
            
            available = self.get_available_actions(current_state_id)
            if not available:
                paths.append(path.copy())
                return
            
            for action in available:
                next_state = self.transitions.get((current_state_id, action.id))
                if next_state:
                    path.append(action.id)
                    dfs(next_state, path, depth + 1)
                    path.pop()
        
        if self.current_state_id:
            dfs(self.current_state_id, [], 0)
        
        return paths
    
    def visualize(self, filename: str = "instruction_graph") -> None:
        """
        Визуализация графа с помощью Graphviz
        """
        dot = Digraph(comment=self.name)
        dot.attr(rankdir='TB', size='8,5')
        
        # Добавляем состояния
        for state_id, state in self.states.items():
            color = {
                StateType.INITIAL: 'green',
                StateType.FINAL: 'red',
                StateType.INTERMEDIATE: 'lightblue',
                StateType.ERROR: 'orange'
            }.get(state.state_type, 'white')
            
            shape = 'doublecircle' if state.state_type == StateType.FINAL else 'circle'
            
            dot.node(state_id, f"{state.name}\n{state.description[:30]}", 
                    shape=shape, style='filled', fillcolor=color)
        
        # Добавляем переходы
        for (from_state, action_id), to_state in self.transitions.items():
            action = self.actions.get(action_id)
            label = action.name if action else action_id
            dot.edge(from_state, to_state, label=label, fontsize='10')
        
        # Сохраняем граф
        dot.render(filename, view=True, format='png')
        print(f"📊 Graph saved as {filename}.png")
    
    def to_json(self) -> str:
        """Экспорт графа в JSON"""
        data = {
            'name': self.name,
            'states': {
                sid: {
                    'name': s.name,
                    'description': s.description,
                    'type': s.state_type.value,
                    'objects': [obj.name for obj in s.objects_present]
                }
                for sid, s in self.states.items()
            },
            'actions': {
                aid: {
                    'name': a.name,
                    'description': a.description,
                    'required_objects': [obj.name for obj in a.required_objects],
                    'produced_objects': [obj.name for obj in a.produced_objects]
                }
                for aid, a in self.actions.items()
            },
            'transitions': [
                {'from': f, 'action': a, 'to': t}
                for (f, a), t in self.transitions.items()
            ]
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика графа"""
        return {
            'total_states': len(self.states),
            'total_actions': len(self.actions),
            'total_transitions': len(self.transitions),
            'total_objects': len(self.objects),
            'initial_state': self.current_state_id,
            'final_states': [sid for sid, s in self.states.items() 
                           if s.state_type == StateType.FINAL],
            'max_outdegree': max((len([t for t in self.transitions if t[0] == sid]) 
                                 for sid in self.states), default=0),
            'tokens_distribution': dict(self.tokens)
        }


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

def create_coffee_machine_graph() -> InstructionGraph:
    """
    Создание графа для кофемашины как пример инструкций
    """
    graph = InstructionGraph("CoffeeMachine")
    
    # Создаем объекты
    water = Object("water", properties={"amount": 500, "temperature": 20})
    coffee_beans = Object("coffee_beans", properties={"amount": 200})
    cup = Object("cup", properties={"clean": True})
    coffee = Object("coffee", properties={"ready": False})
    
    for obj in [water, coffee_beans, cup, coffee]:
        graph.add_object(obj)
    
    # Создаем состояния
    idle = State("s1", "Idle", "Машина ожидает", StateType.INITIAL)
    heating = State("s2", "Heating", "Нагрев воды")
    grinding = State("s3", "Grinding", "Измельчение зерен")
    brewing = State("s4", "Brewing", "Приготовление кофе")
    ready = State("s5", "Ready", "Кофе готов", StateType.FINAL)
    error = State("s6", "Error", "Ошибка", StateType.ERROR)
    
    for state in [idle, heating, grinding, brewing, ready, error]:
        graph.add_state(state)
    
    # Создаем действия с условиями
    def check_water(context):
        water_obj = context['objects'].get('water')
        return water_obj and water_obj.properties.get('amount', 0) > 100
    
    def heat_water(context):
        water_obj = context['objects'].get('water')
        if water_obj:
            water_obj.properties['temperature'] = 95
        return True
    
    def check_beans(context):
        beans = context['objects'].get('coffee_beans')
        return beans and beans.properties.get('amount', 0) > 10
    
    def grind_beans(context):
        beans = context['objects'].get('coffee_beans')
        if beans:
            beans.properties['amount'] -= 10
        return True
    
    def check_cup(context):
        cup_obj = context['objects'].get('cup')
        return cup_obj and cup_obj.properties.get('clean', False)
    
    def make_coffee(context):
        coffee_obj = context['objects'].get('coffee')
        if coffee_obj:
            coffee_obj.properties['ready'] = True
        return True
    
    # Добавляем действия
    heat_action = Action("act1", "Heat Water", "Нагрев воды до 95°C")
    heat_action.preconditions.append(check_water)
    heat_action.postconditions.append(heat_water)
    
    grind_action = Action("act2", "Grind Beans", "Измельчение кофейных зерен")
    grind_action.preconditions.append(check_beans)
    grind_action.postconditions.append(grind_beans)
    
    brew_action = Action("act3", "Brew Coffee", "Приготовление кофе")
    brew_action.preconditions.append(check_cup)
    brew_action.postconditions.append(make_coffee)
    brew_action.required_objects = {water, coffee_beans, cup}
    brew_action.produced_objects = {coffee}
    
    error_action = Action("err", "Error", "Ошибка приготовления")
    
    for action in [heat_action, grind_action, brew_action, error_action]:
        graph.add_action(action)
    
    # Добавляем переходы
    graph.add_transition("s1", "act1", "s2")  # Idle -> Heating
    graph.add_transition("s1", "act2", "s3")  # Idle -> Grinding
    graph.add_transition("s2", "act3", "s4")  # Heating -> Brewing
    graph.add_transition("s3", "act3", "s4")  # Grinding -> Brewing
    graph.add_transition("s4", "act3", "s5")  # Brewing -> Ready
    graph.add_transition("s1", "err", "s6")   # Idle -> Error
    
    return graph


def main():
    """Демонстрация работы графа инструкций"""
    
    print("=" * 60)
    print("📊 ГРАФ ИНСТРУКЦИЙ (Сеть Петри + Диаграмма состояний)")
    print("=" * 60)
    
    # Создаем граф для кофемашины
    coffee_graph = create_coffee_machine_graph()
    
    # Выводим статистику
    print("\n📈 Статистика графа:")
    stats = coffee_graph.get_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Визуализируем граф
    print("\n🎨 Визуализация графа...")
    coffee_graph.visualize("coffee_machine_graph")
    
    # Выводим все возможные пути
    print("\n🔀 Возможные пути выполнения:")
    paths = coffee_graph.get_possible_paths(max_depth=5)
    for i, path in enumerate(paths, 1):
        action_names = [coffee_graph.actions[aid].name for aid in path if aid in coffee_graph.actions]
        print(f"   Путь {i}: {' → '.join(action_names) if action_names else 'Завершен'}")
    
    # Демонстрация выполнения
    print("\n🚀 Выполнение инструкций:")
    print("-" * 40)
    
    # Последовательное выполнение
    actions_sequence = ["act1", "act3", "act3"]
    
    for action_id in actions_sequence:
        print(f"\n▶️ Попытка выполнения: {coffee_graph.actions[action_id].name}")
        success = coffee_graph.execute_action(action_id)
        
        if not success:
            print("   ⚠️ Действие не может быть выполнено!")
            break
    
    # Экспорт в JSON
    print("\n💾 Экспорт графа в JSON:")
    json_data = coffee_graph.to_json()
    print(json_data[:500] + "..." if len(json_data) > 500 else json_data)
    
    # Сохраняем в файл
    with open("instruction_graph.json", "w", encoding="utf-8") as f:
        f.write(json_data)
    print("\n✅ Граф сохранен в instruction_graph.json")
    
    # Дополнительная информация о токенах (сеть Петри)
    print("\n🎯 Токены (маркеры сети Петри):")
    for state_id, count in coffee_graph.tokens.items():
        state_name = coffee_graph.states[state_id].name
        print(f"   {state_name}: {count} токенов")
    
    print("\n" + "=" * 60)
    print("✨ Программа завершена")
    print("=" * 60)


if __name__ == "__main__":
    main()