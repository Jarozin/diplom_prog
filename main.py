"""Точка входа в программу"""

import sys
import os
import json

from models import StateType
from graph import InstructionGraph
from visualization import visualize_graph


def step_by_step_mode(graph: InstructionGraph):
    """Интерактивный пошаговый режим"""
    print("\n" + "="*70)
    print("ИНТЕРАКТИВНЫЙ ПОШАГОВЫЙ РЕЖИМ")
    print("="*70)
    
    if graph.current_state_id is None:
        print("[ОШИБКА] Нет начального состояния!")
        return
    
    steps = 0
    max_steps = 100
    
    while steps < max_steps:
        current_state = graph.states[graph.current_state_id]
        print("\n" + "-"*70)
        print(f"[ТЕКУЩЕЕ СОСТОЯНИЕ] {current_state.name}")
        print(f"   Описание: {current_state.description}")
        print(f"   Тип: {current_state.state_type.to_rus()}")
        
        if current_state.objects_state:
            print("\n   Состояние объектов:")
            formatted = graph.format_objects_state(current_state.objects_state)
            print(formatted)
        
        if current_state.state_type in [StateType.FINAL, StateType.ERROR]:
            print(f"\n{'[ДОСТИГНУТО КОНЕЧНОЕ СОСТОЯНИЕ]' if current_state.state_type == StateType.FINAL else '[ДОСТИГНУТО СОСТОЯНИЕ ОШИБКИ]'}")
            break
        
        available_actions = graph.get_available_actions()
        
        if not available_actions:
            print("\n[ПРЕДУПРЕЖДЕНИЕ] Нет доступных действий из текущего состояния!")
            break
        
        print(f"\n[ДОСТУПНЫЕ ДЕЙСТВИЯ] ({len(available_actions)}):")
        print("   +----+--------------------------------------------------+-----------------------+")
        print("   | №  | Действие                                         | Следующее состояние   |")
        print("   +----+--------------------------------------------------+-----------------------+")
        
        for idx, (action, next_state_id) in enumerate(available_actions, 1):
            next_state = graph.states[next_state_id]
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
            graph.show_history()
            continue
        elif choice == 's':
            graph.print_statistics()
            continue
        elif choice == 'v':
            visualize_graph(graph, "step_visualization")
            continue
        
        try:
            idx = int(choice)
            if 1 <= idx <= len(available_actions):
                action, next_state_id = available_actions[idx - 1]
                
                print(f"\nВыполнить действие: {action.name}?")
                confirm = input("   Подтвердить (y/n): ").strip().lower()
                
                if confirm == 'y':
                    print(f"\nВыполняется: {action.name}...")
                    success = graph.execute_action(action.id)
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


def main():
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
        step_by_step_mode(graph)
        
        print("\n[ИТОГОВАЯ СТАТИСТИКА]")
        graph.print_statistics()
        print("\n[ПОЛНАЯ ИСТОРИЯ]")
        graph.show_history()
        
    elif choice == '2':
        print("\n[ДЕТАЛЬНАЯ ИНФОРМАЦИЯ]")
        graph.print_statistics()
        
    elif choice == '3':
        print("\nВизуализация графа...")
        visualize_graph(graph, "loaded_graph")
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