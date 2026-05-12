"""Точка входа в программу"""

import sys
import os
import json

from models import StateType
from graph import InstructionGraph
from visualization import visualize_graph
from labels import LabelManager
from debug_mode import DebugMode


def step_by_step_mode(graph: InstructionGraph, label_manager: LabelManager, json_file: str):
    """Интерактивный пошаговый режим с ранжированными рекомендациями (МАИ)"""
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
            
            # Показываем метки для действия
            if label_manager:
                labels = label_manager.get_labels_for_action(action)
                if labels:
                    label_names = [label.name for label in labels]
                    label_str = f"метки: {', '.join(label_names)}"
                    if len(label_str) > 48:
                        label_str = label_str[:45] + "..."
                    print(f"   |    | ({label_str:<46}) |                       |")
        
        print("   +----+--------------------------------------------------+-----------------------+")
        print("   | 0  | Завершить и сохранить результаты                 | -                     |")
        print("   | i  | Информация о действии (метки и рекомендации)     | -                     |")
        print("   | a  | Показать результаты МАИ (веса критериев)         | -                     |")
        print("   | q  | Показать историю                                 | -                     |")
        print("   | s  | Показать статистику                              | -                     |")
        print("   | v  | Визуализировать граф                             | -                     |")
        print("   +----+--------------------------------------------------+-----------------------+")
        
        choice = input("\nВаш выбор (номер действия или команда): ").strip().lower()
        
        if choice == '0':
            print("\nЗавершение пошагового режима...")
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
        elif choice == 'a':
            if label_manager:
                label_manager.display_criteria_info()
            continue
        elif choice == 'i':
            if available_actions:
                print("\n[ВЫБЕРИТЕ ДЕЙСТВИЕ ДЛЯ ПРОСМОТРА ИНФОРМАЦИИ]")
                for idx, (action, _) in enumerate(available_actions, 1):
                    labels = label_manager.get_labels_for_action(action) if label_manager else []
                    label_str = f" (метки: {', '.join([l.name for l in labels])})" if labels else ""
                    print(f"   {idx}. {action.name}{label_str}")
                try:
                    action_choice = int(input("Номер действия: "))
                    if 1 <= action_choice <= len(available_actions):
                        action, _ = available_actions[action_choice - 1]
                        print(f"\n[ИНФОРМАЦИЯ О ДЕЙСТВИИ: {action.name}]")
                        print(f"   Описание: {action.description}")
                        if action.required_objects:
                            print(f"   Требуемые объекты: {', '.join(action.required_objects)}")
                        if label_manager:
                            label_manager.display_recommendations_for_action(action, top_n=5)
                    else:
                        print("[ОШИБКА] Неверный номер!")
                except ValueError:
                    print("[ОШИБКА] Неверный ввод!")
            else:
                print("[ПРЕДУПРЕЖДЕНИЕ] Нет доступных действий!")
            continue
        
        # Попытка выполнить действие
        try:
            idx = int(choice)
            if 1 <= idx <= len(available_actions):
                action, next_state_id = available_actions[idx - 1]
                
                # Получаем топ-3 рекомендации для сохранения в историю
                recommendations_to_show = []
                if label_manager:
                    top_recs = label_manager.get_top_recommendations_for_action(action, top_n=3)
                    if top_recs:
                        print(f"\n[ТОП-3 РЕКОМЕНДАЦИИ (МАИ) ДЛЯ ДЕЙСТВИЯ: {action.name}]")
                        print("   " + "-"*55)
                        for rec in top_recs:
                            print(f"      {rec['rank']}. {rec['text']}")
                            print(f"         (оценка: {rec['score']:.4f})")
                            recommendations_to_show.append(rec)
                        print("   " + "-"*55)
                
                print(f"\nВыполнить действие: {action.name}?")
                confirm = input("   Подтвердить (y/n): ").strip().lower()
                
                if confirm == 'y':
                    print(f"\nВыполняется: {action.name}...")
                    success = graph.execute_action(action.id, recommendations=recommendations_to_show)
                    if success:
                        steps += 1
                else:
                    print("   Действие отменено.")
            else:
                print("[ОШИБКА] Неверный номер действия!")
        except ValueError:
            print("[ОШИБКА] Неверная команда! Введите номер действия или команду (0, i, a, q, s, v)")
    
    if steps >= max_steps:
        print(f"\n[ПРЕДУПРЕЖДЕНИЕ] Достигнуто максимальное количество шагов ({max_steps})!")
    
    print("\n" + "="*70)
    print(f"Пошаговый режим завершен. Выполнено шагов: {steps}")
    print("="*70)
    
    # Сохраняем результаты после выполнения
    result_file = json_file.replace('.json', '_result.json')
    print(f"\nСохранение результатов в {result_file}...")
    
    final_objects_state = graph.get_current_objects_state()
    
    history_data = []
    for step in graph.execution_history:
        history_data.append({
            'from_state': step.from_state,
            'from_state_name': step.from_state_name,
            'action_id': step.action_id,
            'action_name': step.action_name,
            'to_state': step.to_state,
            'to_state_name': step.to_state_name,
            'recommendations': step.recommendations
        })
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'execution_history': history_data,
            'total_steps': steps,
            'final_state_id': graph.current_state_id,
            'final_state_name': graph.states[graph.current_state_id].name if graph.current_state_id else None,
            'final_objects_state': final_objects_state
        }, f, indent=2, ensure_ascii=False)
    print("[УСПЕХ] Результаты сохранены!")


def reset_graph_state(graph: InstructionGraph, original_json_file: str, label_manager: LabelManager):
    """Сброс состояния графа к начальному"""
    print("\n[СБРОС СОСТОЯНИЯ ГРАФА]")
    
    # Сохраняем имя графа
    graph_name = graph.name
    
    # Создаем новый граф из того же JSON файла
    try:
        new_graph = InstructionGraph.from_json(original_json_file, label_manager)
        
        # Копируем все атрибуты из нового графа в старый
        graph.name = new_graph.name
        graph.states = new_graph.states
        graph.actions = new_graph.actions
        graph.objects = new_graph.objects
        graph.transitions = new_graph.transitions
        graph.current_state_id = new_graph.current_state_id
        graph.execution_history = []  # Очищаем историю
        graph.tokens = {}  # Очищаем токены, если есть
        
        print("[УСПЕХ] Состояние графа сброшено к начальному")
        return True
    except Exception as e:
        print(f"[ОШИБКА] Не удалось сбросить состояние: {e}")
        return False


def main():
    # Бесконечный цикл для возврата в главное меню
    json_file = None
    
    while True:
        print("=" * 70)
        print("ЗАГРУЗЧИК ГРАФА ИНСТРУКЦИЙ (Сеть Петри + Диаграмма состояний)")
        print("=" * 70)
        
        # Загружаем менеджер меток (с полным МАИ)
        labels_config = "labels_config.json"
        ahp_config = "ahp_criteria_config.json"
        label_manager = LabelManager(labels_config, ahp_config)
        
        # Запрашиваем файл инструкции, если еще не загружен
        if json_file is None:
            if len(sys.argv) > 1:
                json_file = sys.argv[1]
            else:
                json_file = input("\nВведите путь к JSON файлу с инструкцией (по умолчанию: coffee_linear.json): ").strip()
                if not json_file:
                    json_file = "coffee_linear.json"
        
        # Проверка существования файла
        while not os.path.exists(json_file):
            print(f"\n[ОШИБКА] Файл {json_file} не найден!")
            json_file = input("Введите правильный путь к JSON файлу (или 'exit' для выхода): ").strip()
            if json_file.lower() == 'exit':
                print("\nДо свидания!")
                return
        
        try:
            print(f"\nЗагрузка графа из {json_file}...")
            graph = InstructionGraph.from_json(json_file, label_manager)
            print("[УСПЕХ] Граф успешно загружен!")
        except Exception as e:
            print(f"[ОШИБКА] Не удалось загрузить JSON: {e}")
            json_file = None
            continue
        
        print(f"\n[ИНФОРМАЦИЯ О ГРАФЕ]")
        print(f"   Название: {graph.name}")
        print(f"   Состояний: {len(graph.states)}")
        print(f"   Действий: {len(graph.actions)}")
        print(f"   Объектов: {len(graph.objects)}")
        print(f"   Переходов: {len(graph.transitions)}")
        
        graph.print_ascii_graph()
        
        # Главное меню
        while True:
            print("\n" + "="*70)
            print("ГЛАВНОЕ МЕНЮ")
            print("="*70)
            print("   1. Интерактивный пошаговый режим (с ранжированными рекомендациями)")
            print("   2. Показать информацию о графе")
            print("   3. Визуализировать граф (состояния, действия, объекты)")
            print("   4. Показать все метки и рекомендации")
            print("   5. Показать результаты МАИ (веса критериев и проверка согласованности)")
            print("   6. РЕЖИМ ДЕБАГА ДЛЯ ЭКСПЕРТА (настройка весов и оценок)")
            print("   7. Загрузить другой граф")
            print("   8. Сбросить состояние графа к начальному")
            print("   0. Выход из программы")
            print("="*70)
            
            choice = input("\nВаш выбор (0-8): ").strip()
            
            if choice == '1':
                print("\nЗапуск пошагового режима...")
                input("Нажмите Enter для начала...")
                step_by_step_mode(graph, label_manager, json_file)
                
                print("\n[ИТОГОВАЯ СТАТИСТИКА]")
                graph.print_statistics()
                print("\n[ПОЛНАЯ ИСТОРИЯ]")
                graph.show_history()
                
                input("\nНажмите Enter для возврата в главное меню...")
                
            elif choice == '2':
                print("\n[ДЕТАЛЬНАЯ ИНФОРМАЦИЯ]")
                graph.print_statistics()
                input("\nНажмите Enter для продолжения...")
                
            elif choice == '3':
                print("\nВизуализация графа...")
                visualize_graph(graph, "loaded_graph")
                print("[УСПЕХ] Визуализация графа завершена!")
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '4':
                print("\n[ВСЕ МЕТКИ И РЕКОМЕНДАЦИИ]")
                print("="*70)
                for label in label_manager.labels:
                    print(f"\nМетка: {label.name}")
                    print(f"   Ключевые слова: {', '.join(label.keywords)}")
                    print(f"   Рекомендации с оценками:")
                    for i, rec in enumerate(label.recommendations, 1):
                        text = rec.get('text', '') if isinstance(rec, dict) else rec
                        scores = rec.get('scores', {}) if isinstance(rec, dict) else {}
                        scores_str = ", ".join([f"{k}={v:.2f}" for k, v in scores.items()])
                        print(f"      {i}. {text}")
                        if scores_str:
                            print(f"         оценки: {scores_str}")
                print("\n" + "="*70)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '5':
                if label_manager:
                    label_manager.display_criteria_info()
                else:
                    print("[ОШИБКА] Информация о критериях недоступна!")
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '6':
                debug_mode = DebugMode(graph, label_manager)
                debug_mode.run()
                print("\n[ИНФО] Возврат в главное меню...")
            
            elif choice == '7':
                print("\n[ЗАГРУЗКА ДРУГОГО ГРАФА]")
                new_json_file = input("Введите путь к JSON файлу: ").strip()
                if new_json_file and os.path.exists(new_json_file):
                    json_file = new_json_file
                    print(f"Загрузка {json_file}...")
                    break  # Выход из внутреннего цикла для загрузки нового графа
                else:
                    print("[ОШИБКА] Файл не найден! Остаюсь в текущем графе.")
            
            elif choice == '8':
                # Сброс состояния графа к начальному
                if reset_graph_state(graph, json_file, label_manager):
                    print("\n[ИНФОРМАЦИЯ ПОСЛЕ СБРОСА]")
                    graph.print_ascii_graph()
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '0':
                print("\nДо свидания!")
                return
            
            else:
                print("\n[ОШИБКА] Неверный выбор!")
                input("Нажмите Enter для продолжения...")


if __name__ == "__main__":
    main()