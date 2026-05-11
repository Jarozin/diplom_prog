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


@dataclass
class Object:
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    current_state_id: Optional[str] = None
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Object) else False
    
    def __str__(self):
        props = ", ".join(f"{k}={v}" for k, v in self.properties.items())
        return f"{self.name}({props})" if props else self.name
    
    def get_property(self, prop_name: str):
        if '.' in prop_name:
            parts = prop_name.split('.')
            value = self.properties
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
            return value
        return self.properties.get(prop_name)


@dataclass
class State:
    id: str
    name: str
    description: str = ""
    state_type: StateType = StateType.INTERMEDIATE
    objects_present: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
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
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    _precondition_funcs: List[Callable] = field(default_factory=list, repr=False)
    _postcondition_funcs: List[Callable] = field(default_factory=list, repr=False)
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        for precondition in self._precondition_funcs:
            if not precondition(context):
                return False
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.can_execute(context):
            raise ValueError(f"Action {self.name} cannot be executed")
        
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
        self.tokens: Dict[str, int] = defaultdict(int)
        
    @classmethod
    def from_json(cls, json_file: str):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        graph = cls(data.get('name', 'InstructionGraph'))
        
        for obj_data in data.get('objects', []):
            obj = Object(
                name=obj_data['name'],
                properties=obj_data.get('properties', {})
            )
            graph.add_object(obj)
        
        for state_data in data.get('states', []):
            state = State(
                id=state_data['id'],
                name=state_data['name'],
                description=state_data.get('description', ''),
                state_type=StateType.from_string(state_data.get('type', 'intermediate')),
                objects_present=set(state_data.get('objects_present', []))
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
                        obj = context['objects'].get(obj_name)
                        if not obj:
                            return False
                        prop_value = obj.get_property(prop_name)
                        
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
                        obj = context['objects'].get(obj_name)
                        if obj:
                            obj.properties[prop_name] = value
                    return setter
                
                compiled.append(make_setter(obj_name, prop_name, value))
            
            elif cond_type == 'modify_property':
                obj_name = cond['object']
                prop_name = cond['property']
                operation = cond['operation']
                value = cond['value']
                
                def make_modifier(obj_name, prop_name, operation, value):
                    def modifier(context):
                        obj = context['objects'].get(obj_name)
                        if obj:
                            current = obj.properties.get(prop_name, 0)
                            if operation == 'add':
                                obj.properties[prop_name] = current + value
                            elif operation == 'subtract':
                                obj.properties[prop_name] = current - value
                            elif operation == 'multiply':
                                obj.properties[prop_name] = current * value
                            elif operation == 'divide':
                                obj.properties[prop_name] = current / value
                    return modifier
                
                compiled.append(make_modifier(obj_name, prop_name, operation, value))
            
            elif cond_type == 'print':
                message_template = cond.get('message', '')
                
                def make_printer(message_template):
                    def printer(context):
                        message = message_template
                        for obj_name, obj in context['objects'].items():
                            for prop_name, prop_value in obj.properties.items():
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
            self.tokens[state.id] = 1
    
    def add_action(self, action: Action) -> None:
        self.actions[action.id] = action
    
    def add_object(self, obj: Object) -> None:
        self.objects[obj.name] = obj
    
    def add_transition(self, from_state_id: str, action_id: str, to_state_id: str) -> None:
        if from_state_id not in self.states:
            raise ValueError(f"State {from_state_id} not found")
        if action_id not in self.actions:
            raise ValueError(f"Action {action_id} not found")
        if to_state_id not in self.states:
            raise ValueError(f"State {to_state_id} not found")
        
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
    
    def execute_action(self, action_id: str, object_mapping: Optional[Dict[str, Object]] = None, silent: bool = False) -> bool:
        if self.current_state_id is None:
            if not silent:
                print("No current state set")
            return False
        
        transition_key = (self.current_state_id, action_id)
        if transition_key not in self.transitions:
            if not silent:
                print(f"No transition from {self.current_state_id} with action {action_id}")
            return False
        
        action = self.actions.get(action_id)
        if not action:
            if not silent:
                print(f"Action {action_id} not found")
            return False
        
        context = self._get_context(object_mapping)
        
        try:
            new_context = action.execute(context)
            self._update_context(new_context)
            
            old_state = self.current_state_id
            self.current_state_id = self.transitions[transition_key]
            
            self.tokens[old_state] -= 1
            self.tokens[self.current_state_id] += 1
            
            if self.current_state_id in self.states:
                current_state = self.states[self.current_state_id]
                for obj_name in current_state.objects_present:
                    if obj_name in self.objects:
                        self.objects[obj_name].current_state_id = self.current_state_id
            
            self.execution_history.append((old_state, action_id, self.current_state_id))
            
            if not silent:
                print(f"\n[OK] Executed: {action.name}")
                print(f"     From: {self.states[old_state].name}")
                print(f"     To: {self.states[self.current_state_id].name}")
                
                if action.consumed_objects:
                    print(f"     Consumed: {', '.join(action.consumed_objects)}")
                if action.produced_objects:
                    print(f"     Produced: {', '.join(action.produced_objects)}")
            
            return True
            
        except Exception as e:
            if not silent:
                print(f"[ERROR] Failed to execute {action.name}: {e}")
            return False
    
    def _get_context(self, object_mapping: Optional[Dict[str, Object]] = None) -> Dict[str, Any]:
        context = {
            'current_state': self.current_state_id,
            'objects': object_mapping or self.objects.copy(),
            'tokens': dict(self.tokens),
            'execution_history': self.execution_history.copy()
        }
        return context
    
    def _update_context(self, context: Dict[str, Any]) -> None:
        if 'objects' in context:
            self.objects.update(context['objects'])
        if 'tokens' in context:
            self.tokens.update(context['tokens'])
    
    def step_by_step_mode(self):
        print("\n" + "="*70)
        print("INTERACTIVE STEP-BY-STEP MODE")
        print("="*70)
        
        if self.current_state_id is None:
            print("[ERROR] No initial state!")
            return
        
        steps = 0
        max_steps = 100
        
        while steps < max_steps:
            current_state = self.states[self.current_state_id]
            print("\n" + "-"*70)
            print(f"[CURRENT STATE] {current_state.name}")
            print(f"   Description: {current_state.description}")
            
            state_types = {
                StateType.INITIAL: "Initial",
                StateType.FINAL: "Final",
                StateType.ERROR: "Error",
                StateType.INTERMEDIATE: "Intermediate"
            }
            print(f"   Type: {state_types.get(current_state.state_type, 'Unknown')}")
            
            if current_state.state_type in [StateType.FINAL, StateType.ERROR]:
                print(f"\n{'[FINAL STATE REACHED]' if current_state.state_type == StateType.FINAL else '[ERROR STATE REACHED]'}")
                break
            
            available_actions = self.get_available_actions()
            
            if not available_actions:
                print("\n[WARNING] No available actions from current state!")
                break
            
            print(f"\n[AVAILABLE ACTIONS] ({len(available_actions)}):")
            print("   +----+------------------------------------------+-----------------------+")
            print("   | No | Action                                   | Next State            |")
            print("   +----+------------------------------------------+-----------------------+")
            
            for idx, (action, next_state_id) in enumerate(available_actions, 1):
                next_state = self.states[next_state_id]
                action_name = action.name[:40] + "..." if len(action.name) > 40 else action.name
                print(f"   | {idx:2} | {action_name:<40} | {next_state.name:<21} |")
            
            print("   +----+------------------------------------------+-----------------------+")
            print("   | 0  | Exit                                     | -                     |")
            print("   | q  | Show history                             | -                     |")
            print("   | s  | Show statistics                          | -                     |")
            print("   | v  | Visualize graph                          | -                     |")
            print("   +----+------------------------------------------+-----------------------+")
            
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == '0':
                print("\nExiting step-by-step mode.")
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
                    
                    print(f"\nExecute action: {action.name}?")
                    confirm = input("   Confirm (y/n): ").strip().lower()
                    
                    if confirm == 'y':
                        print(f"\nExecuting: {action.name}...")
                        success = self.execute_action(action.id)
                        if success:
                            steps += 1
                    else:
                        print("   Action cancelled.")
                else:
                    print("[ERROR] Invalid action number!")
            except ValueError:
                print("[ERROR] Invalid command!")
        
        if steps >= max_steps:
            print(f"\n[WARNING] Maximum steps reached ({max_steps})!")
        
        print("\n" + "="*70)
        print(f"Step-by-step mode finished. Steps executed: {steps}")
        print("="*70)
    
    def show_history(self):
        print("\n[EXECUTION HISTORY]")
        if not self.execution_history:
            print("   (empty)")
            return
        
        for i, (from_state, action_id, to_state) in enumerate(self.execution_history, 1):
            from_name = self.states[from_state].name if from_state in self.states else from_state
            to_name = self.states[to_state].name if to_state in self.states else to_state
            action_name = self.actions[action_id].name if action_id in self.actions else action_id
            print(f"   {i}. {from_name} -> [{action_name}] -> {to_name}")
    
    def print_statistics(self):
        print("\n[CURRENT STATISTICS]")
        print(f"   Current state: {self.states[self.current_state_id].name if self.current_state_id else 'None'}")
        print(f"   Actions executed: {len(self.execution_history)}")
        print(f"   Available actions: {len(self.get_available_actions())}")
        print(f"   Total states: {len(self.states)}")
        print(f"   Total objects: {len(self.objects)}")
        
        print(f"\n[OBJECTS STATE]")
        for obj in self.objects.values():
            print(f"   {obj}")
    
    def visualize(self, filename: str = "instruction_graph") -> None:
        try:
            G = nx.MultiDiGraph()
            
            # Node colors for different types
            state_color = 'lightblue'
            action_color = 'lightgreen'
            object_color = 'lightyellow'
            initial_color = 'lightcoral'
            final_color = 'lightgray'
            
            # Add state nodes
            for state_id, state in self.states.items():
                if state.state_type == StateType.INITIAL:
                    color = initial_color
                    shape = 's'
                elif state.state_type == StateType.FINAL:
                    color = final_color
                    shape = 's'
                else:
                    color = state_color
                    shape = 's'
                
                G.add_node(f"state_{state_id}", 
                          label=f"{state.name}\n{state.description[:20]}",
                          type='state',
                          color=color,
                          shape=shape)
            
            # Add action nodes
            for action_id, action in self.actions.items():
                G.add_node(f"action_{action_id}",
                          label=f"{action.name[:30]}",
                          type='action',
                          color=action_color,
                          shape='diamond')
            
            # Add object nodes
            for obj_name, obj in self.objects.items():
                props = []
                for k, v in obj.properties.items():
                    props.append(f"{k}={v}")
                props_str = '\n'.join(props[:3])
                label = f"{obj_name}\n{props_str}" if props_str else obj_name
                G.add_node(f"object_{obj_name}",
                          label=label,
                          type='object',
                          color=object_color,
                          shape='ellipse')
            
            # Add edges: state -> action -> state
            for (from_state, action_id), to_state in self.transitions.items():
                action = self.actions.get(action_id)
                if action:
                    G.add_edge(f"state_{from_state}", f"action_{action_id}", label="trigger")
                    G.add_edge(f"action_{action_id}", f"state_{to_state}", label="result")
            
            # Add object participation edges
            for action_id, action in self.actions.items():
                for obj_name in action.required_objects:
                    G.add_edge(f"object_{obj_name}", f"action_{action_id}", 
                              label="required", style='dashed')
                for obj_name in action.consumed_objects:
                    G.add_edge(f"object_{obj_name}", f"action_{action_id}", 
                              label="consumed", style='dotted', color='red')
                for obj_name in action.produced_objects:
                    G.add_edge(f"action_{action_id}", f"object_{obj_name}", 
                              label="produced", style='dotted', color='green')
            
            # Setup plot
            plt.figure(figsize=(16, 12))
            
            # Layout
            pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)
            
            # Separate layout by node type for better visualization
            pos_adjusted = {}
            state_count = 0
            action_count = 0
            object_count = 0
            
            for node, data in G.nodes(data=True):
                node_type = data.get('type', 'state')
                if node_type == 'state':
                    pos_adjusted[node] = (-2, state_count * 2 - 5)
                    state_count += 1
                elif node_type == 'action':
                    pos_adjusted[node] = (0, action_count * 2 - 5)
                    action_count += 1
                else:
                    pos_adjusted[node] = (2, object_count * 2 - 5)
                    object_count += 1
            
            # Draw nodes by type
            for node_type, color, shape in [
                ('state', 'lightblue', 's'),
                ('action', 'lightgreen', 'D'),
                ('object', 'lightyellow', 'o')
            ]:
                nodes = [n for n, d in G.nodes(data=True) if d.get('type') == node_type]
                if nodes:
                    nx.draw_networkx_nodes(G, pos_adjusted, nodelist=nodes,
                                         node_color=color, node_size=2000,
                                         node_shape=shape, alpha=0.8)
            
            # Draw edges
            edge_colors = []
            for u, v, data in G.edges(data=True):
                label = data.get('label', '')
                if label == 'trigger':
                    edge_colors.append('blue')
                elif label == 'result':
                    edge_colors.append('green')
                elif label == 'required':
                    edge_colors.append('gray')
                else:
                    edge_colors.append('black')
            
            nx.draw_networkx_edges(G, pos_adjusted, edge_color=edge_colors,
                                 arrows=True, arrowsize=15, arrowstyle='->',
                                 connectionstyle='arc3,rad=0.1', alpha=0.6)
            
            # Draw labels
            labels = nx.get_node_attributes(G, 'label')
            nx.draw_networkx_labels(G, pos_adjusted, labels, font_size=8, font_weight='bold')
            
            # Draw edge labels
            edge_labels = {(u, v): d['label'] for u, v, d in G.edges(data=True) if d.get('label')}
            nx.draw_networkx_edge_labels(G, pos_adjusted, edge_labels, font_size=7)
            
            # Legend
            from matplotlib.patches import Patch, FancyBboxPatch
            legend_elements = [
                Patch(facecolor='lightblue', alpha=0.8, label='States'),
                Patch(facecolor='lightgreen', alpha=0.8, label='Actions'),
                Patch(facecolor='lightyellow', alpha=0.8, label='Objects'),
                Patch(facecolor='lightcoral', alpha=0.8, label='Initial State'),
                Patch(facecolor='lightgray', alpha=0.8, label='Final State')
            ]
            plt.legend(handles=legend_elements, loc='upper right', fontsize=10)
            
            plt.title(f"Instruction Graph: {self.name}\n(States, Actions, and Objects as separate nodes)", 
                     fontsize=14, fontweight='bold')
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(f"{filename}.png", dpi=300, bbox_inches='tight')
            print(f"[INFO] Graph saved as {filename}.png")
            plt.show()
        except Exception as e:
            print(f"[WARNING] Visualization failed: {e}")
    
    def print_ascii_graph(self) -> None:
        print("\n" + "="*70)
        print(f"INSTRUCTION GRAPH: {self.name}")
        print("="*70)
        
        print("\n[STATES]")
        for state_id, state in self.states.items():
            type_marker = {
                StateType.INITIAL: "(S)",
                StateType.FINAL: "(F)",
                StateType.ERROR: "(E)",
                StateType.INTERMEDIATE: "(-)"
            }.get(state.state_type, "(-)")
            current_marker = " <- CURRENT" if state_id == self.current_state_id else ""
            print(f"   {type_marker} {state.name} [{state_id}]: {state.description}{current_marker}")
        
        print("\n[ACTIONS]")
        for action_id, action in self.actions.items():
            print(f"   [-] {action.name} [{action_id}]: {action.description}")
        
        print("\n[TRANSITIONS]")
        for (from_state, action_id), to_state in self.transitions.items():
            action = self.actions.get(action_id)
            from_state_name = self.states[from_state].name
            to_state_name = self.states[to_state].name
            action_name = action.name if action else action_id
            print(f"   {from_state_name} -> [{action_name}] -> {to_state_name}")
        
        print("\n[OBJECTS]")
        for obj in self.objects.values():
            print(f"   - {obj}")
        
        print("="*70)


def main():
    import sys
    import os
    
    print("=" * 70)
    print("INSTRUCTION GRAPH LOADER (Petri Net + State Diagram)")
    print("=" * 70)
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = input("\nEnter path to JSON instruction file (default: coffee_linear.json): ").strip()
        if not json_file:
            json_file = "coffee_linear.json"
    
    if not os.path.exists(json_file):
        print(f"\n[ERROR] File {json_file} not found!")
        print("   Please create the configuration file or check the path.")
        return
    
    try:
        print(f"\nLoading graph from {json_file}...")
        graph = InstructionGraph.from_json(json_file)
        print("[OK] Graph loaded successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to load JSON: {e}")
        return
    
    print(f"\n[GRAPH INFO]")
    print(f"   Name: {graph.name}")
    print(f"   States: {len(graph.states)}")
    print(f"   Actions: {len(graph.actions)}")
    print(f"   Objects: {len(graph.objects)}")
    print(f"   Transitions: {len(graph.transitions)}")
    
    graph.print_ascii_graph()
    
    print("\n" + "="*70)
    print("CHOOSE MODE:")
    print("="*70)
    print("   1. Interactive step-by-step mode (manual control)")
    print("   2. Show graph information")
    print("   3. Visualize graph (states, actions, objects as separate nodes)")
    print("   0. Exit")
    print("="*70)
    
    choice = input("\nYour choice (0-3): ").strip()
    
    if choice == '1':
        print("\nStarting step-by-step mode...")
        input("Press Enter to begin...")
        graph.step_by_step_mode()
        
        print("\n[FINAL STATISTICS]")
        graph.print_statistics()
        print("\n[FULL HISTORY]")
        graph.show_history()
        
    elif choice == '2':
        print("\n[DETAILED INFORMATION]")
        graph.print_statistics()
        
    elif choice == '3':
        print("\nVisualizing graph...")
        graph.visualize("loaded_graph")
        print("[OK] Graph visualization complete!")
        
    elif choice == '0':
        print("\nGoodbye!")
        return
    
    else:
        print("\n[ERROR] Invalid choice!")
    
    result_file = json_file.replace('.json', '_result.json')
    print(f"\nSaving results to {result_file}...")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'execution_history': graph.execution_history,
            'final_state': graph.current_state_id,
            'objects_state': {name: obj.properties for name, obj in graph.objects.items()}
        }, f, indent=2, ensure_ascii=False)
    print("[OK] Results saved!")
    
    print("\n" + "="*70)
    print("Program finished")
    print("="*70)


if __name__ == "__main__":
    main()