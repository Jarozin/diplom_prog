import sys, os, json
from models import StateType
from graph import InstructionGraph
from visualization import visualize_graph
from labels import LabelManager
from debug_mode import DebugMode
from emergency import EmergencyHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_DIR = os.path.join(BASE_DIR, "graph")
RESULT_DIR = os.path.join(BASE_DIR, "result")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
EMERGENCY_DIR = os.path.join(BASE_DIR, "emergency")
os.makedirs(GRAPH_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(EMERGENCY_DIR, exist_ok=True)


def get_graph_description(filepath):
    """Извлекает описание графа из JSON-файла или возвращает имя файла."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('description', os.path.basename(filepath))
    except:
        return os.path.basename(filepath)


def select_graph_file():
    """Предлагает пользователю выбрать файл графа из папки graph или ввести вручную."""
    graph_files = [f for f in os.listdir(GRAPH_DIR) if f.endswith('.json')]
    if not graph_files:
        print("\n[ПРЕДУПРЕЖДЕНИЕ] В папке graph нет JSON-файлов. Будет предложен ручной ввод.")
        manual = input("Введите путь к JSON-файлу: ").strip()
        if os.path.exists(manual):
            return manual
        else:
            print("[ОШИБКА] Файл не найден")
            return None
    
    print("\nДоступные графы инструкций:")
    for i, fname in enumerate(graph_files, 1):
        full_path = os.path.join(GRAPH_DIR, fname)
        desc = get_graph_description(full_path)
        print(f"   {i}. {fname} – {desc}")
    print(f"   {len(graph_files)+1}. Ввести имя файла вручную")
    
    choice = input(f"\nВыберите номер (1-{len(graph_files)+1}): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(graph_files):
            return os.path.join(GRAPH_DIR, graph_files[idx])
        elif idx == len(graph_files):
            manual = input("Введите путь к JSON-файлу: ").strip()
            if os.path.exists(manual):
                return manual
            else:
                print("[ОШИБКА] Файл не найден")
                return None
        else:
            print("[ОШИБКА] Неверный номер")
            return None
    except ValueError:
        print("[ОШИБКА] Введите число")
        return None


def step_by_step_mode(graph: InstructionGraph, label_manager: LabelManager, json_file: str):
    print("\n" + "="*70)
    print("ИНТЕРАКТИВНЫЙ ПОШАГОВЫЙ РЕЖИМ")
    print("="*70)
    if graph.current_state_id is None:
        print("[ОШИБКА] Нет начального состояния!")
        return
    steps = 0
    max_steps = 100
    emergency_handler = EmergencyHandler(BASE_DIR, label_manager)

    while steps < max_steps:
        cur = graph.states[graph.current_state_id]
        print("\n" + "-"*70)
        print(f"[ТЕКУЩЕЕ СОСТОЯНИЕ] {cur.name}")
        print(f"   Описание: {cur.description}")
        print(f"   Тип: {cur.state_type.to_rus()}")
        if cur.objects_state:
            print("\n   Состояние объектов:")
            print(graph.format_objects_state(cur.objects_state))
        if cur.state_type in [StateType.FINAL, StateType.ERROR]:
            print(f"\n{'[ДОСТИГНУТО КОНЕЧНОЕ СОСТОЯНИЕ]' if cur.state_type == StateType.FINAL else '[ДОСТИГНУТО СОСТОЯНИЕ ОШИБКИ]'}")
            break
        available = graph.get_available_actions()
        if not available:
            print("\n[ПРЕДУПРЕЖДЕНИЕ] Нет доступных действий!")
            break
        print(f"\n[ДОСТУПНЫЕ ДЕЙСТВИЯ] ({len(available)}):")
        print("   +----+--------------------------------------------------+-----------------------+")
        print("   | №  | Действие                                         | Следующее состояние   |")
        print("   +----+--------------------------------------------------+-----------------------+")
        for idx, (act, next_id) in enumerate(available, 1):
            next_st = graph.states[next_id]
            name = act.name[:48] + "..." if len(act.name) > 48 else act.name
            print(f"   | {idx:2} | {name:<48} | {next_st.name:<21} |")
            if label_manager:
                lab = label_manager.get_labels_for_action(act)
                if lab:
                    labs = ", ".join([l.name for l in lab])
                    ls = f"метки: {labs}"
                    if len(ls) > 48:
                        ls = ls[:45]+"..."
                    print(f"   |    | ({ls:<46}) |                       |")
        print("   +----+--------------------------------------------------+-----------------------+")
        print("   | 0  | Завершить и сохранить результаты                 | -                     |")
        print("   | i  | Информация о действии                            | -                     |")
        print("   | a  | Показать веса критериев                          | -                     |")
        print("   | q  | Показать историю                                 | -                     |")
        print("   | s  | Показать статистику                              | -                     |")
        print("   | v  | Визуализировать граф                             | -                     |")
        print("   +----+--------------------------------------------------+-----------------------+")

        choice = input("\nВаш выбор: ").strip().lower()
        if choice == '0':
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
            if available:
                print("\n[ВЫБЕРИТЕ ДЕЙСТВИЕ]")
                for idx, (act, _) in enumerate(available, 1):
                    print(f"   {idx}. {act.name}")
                try:
                    a_choice = int(input("Номер: "))
                    if 1 <= a_choice <= len(available):
                        act, _ = available[a_choice-1]
                        print(f"\nДействие: {act.name}\n   {act.description}")
                        if act.required_objects:
                            print(f"   Требует: {', '.join(act.required_objects)}")
                        if label_manager:
                            label_manager.display_recommendations_for_action(act, top_n=5)
                    else:
                        print("[ОШИБКА] Неверный номер!")
                except ValueError:
                    print("[ОШИБКА] Введите число")
            continue

        try:
            idx = int(choice)
            if 1 <= idx <= len(available):
                act, _ = available[idx-1]
                recs = []
                if label_manager:
                    top = label_manager.get_top_recommendations_for_action(act, 3)
                    if top:
                        print(f"\n[ТОП-3 РЕКОМЕНДАЦИИ]")
                        for r in top:
                            print(f"      {r['rank']}. {r['text']} (оценка: {r['score']:.3f})")
                            recs.append(r)
                print(f"\nВыполнить {act.name}? (y/n): ")
                confirm = input().strip().lower()
                if confirm == 'y':
                    print(f"\nВыполняется {act.name}...")
                    if graph.execute_action(act.id, recommendations=recs):
                        steps += 1
                elif confirm == 'n':
                    print("Возникла ли аварийная ситуация? (y/n): ")
                    emergency = input().strip().lower()
                    if emergency == 'y':
                        scenarios = emergency_handler.get_emergency_scenarios_for_action(act)
                        if not scenarios:
                            print("Нет доступных аварийных сценариев для текущего контекста.")
                            continue
                        print("\nДоступные аварийные сценарии:")
                        for i, (sc_id, desc, _) in enumerate(scenarios, 1):
                            print(f"{i}. {desc}")
                        print("0. Отмена")
                        sc_choice = input("Выберите сценарий: ").strip()
                        if sc_choice != '0':
                            try:
                                sc_idx = int(sc_choice) - 1
                                if 0 <= sc_idx < len(scenarios):
                                    sc_id, _, _ = scenarios[sc_idx]
                                    return_to_original = emergency_handler.run_emergency_scenario(sc_id)
                                    if return_to_original:
                                        print("Возврат к основному рецепту.")
                                    else:
                                        print("Аварийный сценарий завершён. Возврат в главное меню.")
                                        return
                                else:
                                    print("Неверный выбор")
                            except ValueError:
                                print("Ошибка")
                    else:
                        print("Действие отменено, выберите другое действие.")
                        continue
                else:
                    print("Неверный ввод, действие не выполнено")
            else:
                print("[ОШИБКА] Неверный номер")
        except ValueError:
            print("[ОШИБКА] Неверная команда")

    if steps >= max_steps:
        print(f"\n[ПРЕДУПРЕЖДЕНИЕ] Максимум шагов {max_steps}")
    print(f"\nПошаговый режим завершён. Шагов: {steps}")

    # Сохранение результатов
    base = os.path.basename(json_file)
    out_file = os.path.join(RESULT_DIR, base.replace('.json', '_result.json'))
    with open(out_file, 'w', encoding='utf-8') as f:
        history = [{
            'from_state': h.from_state,
            'from_state_name': h.from_state_name,
            'action_id': h.action_id,
            'action_name': h.action_name,
            'to_state': h.to_state,
            'to_state_name': h.to_state_name,
            'recommendations': h.recommendations
        } for h in graph.execution_history]
        json.dump({
            'execution_history': history,
            'total_steps': steps,
            'final_state_id': graph.current_state_id,
            'final_state_name': graph.states[graph.current_state_id].name if graph.current_state_id else None,
            'final_objects_state': graph.get_current_objects_state()
        }, f, indent=2, ensure_ascii=False)
    print(f"[УСПЕХ] Результаты сохранены в {out_file}")


def reset_graph_state(graph, orig_file, label_manager):
    try:
        new = InstructionGraph.from_json(orig_file, label_manager)
        graph.name = new.name
        graph.states = new.states
        graph.actions = new.actions
        graph.objects = new.objects
        graph.transitions = new.transitions
        graph.current_state_id = new.current_state_id
        graph.execution_history = []
        print("[УСПЕХ] Состояние сброшено")
        return True
    except Exception as e:
        print(f"[ОШИБКА] {e}")
        return False


def change_profile(label_manager):
    print("\n" + "="*70)
    print("СМЕНА УРОВНЯ ЭКСПЕРТНОСТИ")
    print("="*70)
    print("   1. Новичок")
    print("   2. Опытный")
    print("   3. Эксперт")
    choice = input("Ваш выбор (1-3): ").strip()
    profile_map = {'1':'новичок', '2':'опытный', '3':'эксперт'}
    new_profile = profile_map.get(choice, 'опытный')
    labels_cfg = os.path.join(BASE_DIR, "labels_config.json")
    ahp_cfg = os.path.join(BASE_DIR, "ahp_criteria_config.json")
    new_lm = LabelManager(labels_cfg, ahp_cfg, profile=new_profile)
    return new_lm


def main():
    labels_cfg = os.path.join(BASE_DIR, "labels_config.json")
    ahp_cfg = os.path.join(BASE_DIR, "ahp_criteria_config.json")
    
    print("="*70)
    print("ПЕРСОНАЛИЗАЦИЯ ОПЫТА")
    print("="*70)
    print("Выберите ваш уровень экспертности:")
    print("   1. Новичок (безопасность важнее всего)")
    print("   2. Опытный (сбалансированный подход)")
    print("   3. Эксперт (приоритет на критичность и полезность)")
    prof_choice = input("\nВаш выбор (1-3): ").strip()
    profile_map = {'1':'новичок', '2':'опытный', '3':'эксперт'}
    profile = profile_map.get(prof_choice, 'опытный')
    
    label_manager = LabelManager(labels_cfg, ahp_cfg, profile=profile)
    
    json_file = None
    while True:
        print("="*70)
        print("ЗАГРУЗЧИК ГРАФА ИНСТРУКЦИЙ")
        print("="*70)
        if json_file is None:
            json_file = select_graph_file()
            if json_file is None:
                continue
        
        try:
            graph = InstructionGraph.from_json(json_file, label_manager)
            print("[УСПЕХ] Граф загружен")
        except Exception as e:
            print(f"[ОШИБКА] {e}")
            json_file = None
            continue
        
        graph.print_ascii_graph()
        while True:
            print("\n"+"="*70)
            print("ГЛАВНОЕ МЕНЮ")
            print("="*70)
            print("   1. Пошаговый режим")
            print("   2. Информация о графе")
            print("   3. Визуализация")
            print("   4. Все метки")
            print("   5. Веса критериев")
            print("   6. Режим дебага")
            print("   7. Загрузить другой граф")
            print("   8. Сбросить состояние")
            print("   9. Сменить уровень экспертности")
            print("   0. Выход")
            choice = input("Ваш выбор (0-9): ").strip()
            if choice == '0':
                print("До свидания!")
                return
            elif choice == '1':
                input("Нажмите Enter для начала...")
                step_by_step_mode(graph, label_manager, json_file)
                input("Нажмите Enter для возврата в меню")
            elif choice == '2':
                graph.print_statistics()
                input("Нажмите Enter")
            elif choice == '3':
                visualize_graph(graph, "loaded_graph")
                input("Нажмите Enter")
            elif choice == '4':
                print("\n[ВСЕ МЕТКИ]")
                for name, kw, recs in label_manager.get_all_labels_info():
                    print(f"\n{name}: {', '.join(kw)}")
                    for i, r in enumerate(recs,1):
                        txt = r['text'] if isinstance(r,dict) else r
                        print(f"   {i}. {txt[:100]}")
                input("Нажмите Enter")
            elif choice == '5':
                label_manager.display_criteria_info()
                input("Нажмите Enter")
            elif choice == '6':
                dm = DebugMode(graph, label_manager)
                dm.run()
                print("Возврат в главное меню")
            elif choice == '7':
                json_file = select_graph_file()
                if json_file is None:
                    print("Загрузка нового графа отменена, остаюсь в текущем.")
                else:
                    break  # выходим из внутреннего цикла для перезагрузки
            elif choice == '8':
                if reset_graph_state(graph, json_file, label_manager):
                    graph.print_ascii_graph()
                input("Нажмите Enter")
            elif choice == '9':
                new_lm = change_profile(label_manager)
                if new_lm:
                    label_manager = new_lm
                    graph.label_manager = label_manager
                    print(f"Уровень экспертности изменён. Новые веса:")
                    label_manager.display_criteria_info()
                else:
                    print("Не удалось сменить профиль")
                input("Нажмите Enter")
            else:
                print("Неверный выбор")


if __name__ == "__main__":
    main()