"""Компиляция условий из JSON в исполняемые функции"""

from typing import Dict, List, Callable, Any


def compile_conditions(conditions: List[Dict], graph_ref) -> List[Callable]:
    """Компиляция условий из JSON в исполняемые функции"""
    compiled = []
    
    for cond in conditions:
        cond_type = cond.get('type')
        
        if cond_type == 'object_property':
            obj_name = cond['object']
            prop_name = cond['property']
            operator = cond['operator']
            value = cond['value']
            
            def make_check(obj_name, prop_name, operator, value, graph):
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
            
            compiled.append(make_check(obj_name, prop_name, operator, value, graph_ref))
        
        elif cond_type == 'set_property':
            obj_name = cond['object']
            prop_name = cond['property']
            value = cond['value']
            
            def make_setter(obj_name, prop_name, value, graph):
                def setter(context):
                    if 'next_state_id' in context:
                        next_state = graph.states.get(context['next_state_id'])
                        if next_state:
                            if obj_name not in next_state.objects_state:
                                next_state.objects_state[obj_name] = {}
                            next_state.objects_state[obj_name][prop_name] = value
                return setter
            
            compiled.append(make_setter(obj_name, prop_name, value, graph_ref))
        
        elif cond_type == 'modify_property':
            obj_name = cond['object']
            prop_name = cond['property']
            operation = cond['operation']
            value = cond['value']
            
            def make_modifier(obj_name, prop_name, operation, value, graph):
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
            
            compiled.append(make_modifier(obj_name, prop_name, operation, value, graph_ref))
        
        elif cond_type == 'print':
            message_template = cond.get('message', '')
            
            def make_printer(message_template, graph):
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
            
            compiled.append(make_printer(message_template, graph_ref))
    
    return compiled