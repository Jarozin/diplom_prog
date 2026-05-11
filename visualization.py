"""Визуализация графа инструкций"""

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Patch
from matplotlib.lines import Line2D


def visualize_graph(graph, filename: str = "instruction_graph") -> None:
    """Визуализация графа с разделением на состояния, действия, объекты и субъекты"""
    try:
        G = nx.DiGraph()
        
        # Цвета для разных типов узлов
        state_color = '#AED6F1'      # светлый синий
        action_color = '#ABEBC6'     # светлый зеленый
        object_color = '#F9E79F'     # светлый желтый
        subject_color = '#F9E79F'    # субъекты (желтый)
        initial_color = '#F5B7B1'    # светлый красный
        final_color = '#D5D8DC'      # серый
        
        # Добавляем узлы состояний
        for state_id, state in graph.states.items():
            if state.state_type.value == "initial":
                color = initial_color
            elif state.state_type.value == "final":
                color = final_color
            else:
                color = state_color
            
            # Формируем подпись с состоянием объектов
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
        for action_id, action in graph.actions.items():
            G.add_node(f"action_{action_id}",
                      label=f"{action.name[:30]}",
                      type='action',
                      color=action_color)
        
        # Добавляем узлы объектов и субъектов
        for obj_name, obj in graph.objects.items():
            if obj.obj_type == "subject":
                node_type = 'subject'
                label = f"{obj_name}\n(субъект)"
                color = subject_color
            else:
                node_type = 'object'
                label = f"{obj_name}\n(объект)"
                color = object_color
            
            G.add_node(f"obj_{obj_name}",
                      label=label,
                      type=node_type,
                      color=color)
        
        # Добавляем ребра: состояние -> действие и действие -> состояние
        for (from_state, action_id), to_state in graph.transitions.items():
            action = graph.actions.get(action_id)
            if action:
                G.add_edge(f"state_{from_state}", f"action_{action_id}", edge_type='transition')
                G.add_edge(f"action_{action_id}", f"state_{to_state}", edge_type='transition')
        
        # Добавляем связи для объектов и субъектов
        subjects = {name for name, obj in graph.objects.items() if obj.obj_type == "subject"}
        objects = {name for name, obj in graph.objects.items() if obj.obj_type == "object"}
        
        for action_id, action in graph.actions.items():
            for obj_name in action.required_objects:
                if obj_name in subjects:
                    # Субъект -> Действие
                    G.add_edge(f"obj_{obj_name}", f"action_{action_id}", 
                              edge_type='subject', style='dashed')
                else:
                    # Действие -> Объект
                    G.add_edge(f"action_{action_id}", f"obj_{obj_name}", 
                              edge_type='object', style='dashed')
        
        # Позиционирование узлов
        pos = {}
        state_count = 0
        action_count = 0
        object_count = 0
        subject_count = 0
        
        for node, data in G.nodes(data=True):
            node_type = data.get('type', 'state')
            if node_type == 'state':
                pos[node] = (-3, state_count * 1.5 - 3)
                state_count += 1
            elif node_type == 'action':
                pos[node] = (0, action_count * 1.5 - 3)
                action_count += 1
            elif node_type == 'object':
                pos[node] = (3, object_count * 1.5 - 3)
                object_count += 1
            elif node_type == 'subject':
                pos[node] = (5, subject_count * 1.5 - 3)
                subject_count += 1
        
        # Создаем фигуру
        fig, ax = plt.subplots(figsize=(20, 14))
        
        # Рисуем узлы по типам
        for node_type, color in [('state', state_color), ('action', action_color), 
                                  ('object', object_color), ('subject', subject_color)]:
            nodes = [n for n, d in G.nodes(data=True) if d.get('type') == node_type]
            if nodes:
                nx.draw_networkx_nodes(G, pos, nodelist=nodes,
                                     node_color=color, node_size=2800,
                                     edgecolors='black', linewidths=1.5,
                                     alpha=0.9, ax=ax)
        
        # Выделяем начальные и конечные состояния
        initial_nodes = [f"state_{sid}" for sid, s in graph.states.items() 
                        if s.state_type.value == "initial"]
        final_nodes = [f"state_{sid}" for sid, s in graph.states.items() 
                      if s.state_type.value == "final"]
        
        if initial_nodes:
            nx.draw_networkx_nodes(G, pos, nodelist=initial_nodes,
                                 node_color=initial_color, node_size=2800,
                                 edgecolors='black', linewidths=2,
                                 alpha=0.9, ax=ax)
        
        if final_nodes:
            nx.draw_networkx_nodes(G, pos, nodelist=final_nodes,
                                 node_color=final_color, node_size=2800,
                                 edgecolors='black', linewidths=2,
                                 alpha=0.9, ax=ax)
        
        # Функция для рисования стрелки с отступом от узлов
        def draw_arrow_with_offset(ax, start, end, color='gray', 
                                   linewidth=1.5, linestyle='-', 
                                   alpha=0.7, offset=0.2):
            x1, y1 = pos[start]
            x2, y2 = pos[end]
            
            dx = x2 - x1
            dy = y2 - y1
            length = (dx**2 + dy**2)**0.5
            
            if length > 0:
                norm_dx = dx / length
                norm_dy = dy / length
                
                start_x = x1 + norm_dx * offset
                start_y = y1 + norm_dy * offset
                end_x = x2 - norm_dx * offset
                end_y = y2 - norm_dy * offset
                
                arrow = FancyArrowPatch((start_x, start_y), (end_x, end_y),
                                       arrowstyle='->', mutation_scale=15,
                                       color=color, linewidth=linewidth,
                                       linestyle=linestyle, alpha=alpha,
                                       zorder=2)
                ax.add_patch(arrow)
        
        # Рисуем ребра
        for u, v, d in G.edges(data=True):
            edge_type = d.get('edge_type', '')
            if edge_type == 'transition':
                draw_arrow_with_offset(ax, u, v, color='gray', 
                                      linewidth=1.5, linestyle='-', offset=0.2)
            elif edge_type == 'subject':
                draw_arrow_with_offset(ax, u, v, color='blue', 
                                      linewidth=1.5, linestyle='--', offset=0.2)
            elif edge_type == 'object':
                draw_arrow_with_offset(ax, u, v, color='green', 
                                      linewidth=1.5, linestyle='--', offset=0.2)
        
        # Подписи узлов
        labels = nx.get_node_attributes(G, 'label')
        for node, (x, y) in pos.items():
            label = labels.get(node, '')
            node_type = G.nodes[node].get('type', 'state')
            
            # Сдвигаем подпись
            offset_x, offset_y = 0, -0.15
            if node_type == 'object':
                offset_x, offset_y = 0.15, 0
            elif node_type == 'subject':
                offset_x, offset_y = 0.15, 0
            elif node_type == 'action':
                offset_x, offset_y = 0, -0.2
            
            ax.text(x + offset_x, y + offset_y, label, fontsize=8, 
                   fontweight='bold', ha='center', va='center', zorder=3,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                            edgecolor='gray', alpha=0.9))
        
        # Легенда
        legend_elements = [
            Patch(facecolor=state_color, alpha=0.8, edgecolor='black', 
                  label='Состояния (промежуточные)'),
            Patch(facecolor=action_color, alpha=0.8, edgecolor='black', 
                  label='Действия'),
            Patch(facecolor=object_color, alpha=0.8, edgecolor='black', 
                  label='Объекты (направление: действие → объект)'),
            Patch(facecolor=subject_color, alpha=0.8, edgecolor='black', 
                  label='Субъекты (направление: субъект → действие)'),
            Patch(facecolor=initial_color, alpha=0.8, edgecolor='black', 
                  label='Начальное состояние'),
            Patch(facecolor=final_color, alpha=0.8, edgecolor='black', 
                  label='Конечное состояние'),
            Line2D([0], [0], color='gray', linewidth=1.5, 
                   marker='>', markersize=10, markeredgewidth=1.5,
                   label='Переход (сплошная стрелка)'),
            Line2D([0], [0], color='blue', linewidth=1.5, linestyle='--',
                   marker='>', markersize=10, markeredgewidth=1.5,
                   label='Субъект → Действие (синий пунктир)'),
            Line2D([0], [0], color='green', linewidth=1.5, linestyle='--',
                   marker='>', markersize=10, markeredgewidth=1.5,
                   label='Действие → Объект (зеленый пунктир)')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=9, 
                 framealpha=0.9, bbox_to_anchor=(0, 1))
        
        ax.set_title(f"Граф инструкций: {graph.name}\n"
                    f"(Состояния, действия, объекты и субъекты как отдельные узлы)", 
                    fontsize=14, fontweight='bold')
        ax.axis('off')
        ax.set_aspect('equal')
        
        # Устанавливаем границы
        all_x = [pos[n][0] for n in pos]
        all_y = [pos[n][1] for n in pos]
        margin = 0.5
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        
        plt.tight_layout()
        plt.savefig(f"{filename}.png", dpi=300, bbox_inches='tight')
        print(f"[ИНФО] Граф сохранен как {filename}.png")
        plt.show()
    except Exception as e:
        print(f"[ПРЕДУПРЕЖДЕНИЕ] Визуализация не удалась: {e}")
        import traceback
        traceback.print_exc()