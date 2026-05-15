import os
import json
from typing import List, Dict, Optional, Tuple
from graph import InstructionGraph
from labels import LabelManager


class EmergencyHandler:
    def __init__(self, base_dir: str, label_manager: LabelManager, recursion_depth: int = 0, max_depth: int = 3):
        self.base_dir = base_dir
        self.emergency_dir = os.path.join(base_dir, "emergency")
        self.label_manager = label_manager
        self.scenarios_config = self._load_scenarios_config()
        self.recursion_depth = recursion_depth
        self.max_depth = max_depth
        os.makedirs(self.emergency_dir, exist_ok=True)

    def _load_scenarios_config(self) -> Dict:
        config_path = os.path.join(self.base_dir, "emergency_scenarios.json")
        if not os.path.exists(config_path):
            return {}
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_emergency_scenarios_for_action(self, action) -> List[Tuple[str, str, bool]]:
        """Возвращает список доступных аварийных сценариев для действия"""
        labels = self.label_manager.get_labels_for_action(action)
        action_keywords = set()
        for label in labels:
            action_keywords.update(label.keywords)
        result = []
        for sc_id, info in self.scenarios_config.items():
            sc_tags = set(info.get('tags', []))
            if sc_tags.intersection(action_keywords):
                result.append((sc_id, info['description'], info.get('return_to_original', True)))
        return result

    def load_emergency_graph(self, scenario_id: str) -> Optional[InstructionGraph]:
        if scenario_id not in self.scenarios_config:
            return None
        filename = self.scenarios_config[scenario_id]['file']
        filepath = os.path.join(self.emergency_dir, filename)
        if not os.path.exists(filepath):
            print(f"[ОШИБКА] Файл аварийного сценария {filepath} не найден")
            return None
        try:
            graph = InstructionGraph.from_json(filepath, self.label_manager)
            return graph
        except Exception as e:
            print(f"[ОШИБКА] Не удалось загрузить аварийный граф: {e}")
            return None

    def run_emergency_scenario(self, scenario_id: str) -> bool:
        """Запускает выполнение аварийного сценария с возможностью вложенных аварий"""
        if self.recursion_depth >= self.max_depth:
            print("[ПРЕДУПРЕЖДЕНИЕ] Достигнута максимальная глубина вложенных аварийных сценариев. Возврат в основной режим.")
            return True

        graph = self.load_emergency_graph(scenario_id)
        if not graph:
            return True  # при ошибке возвращаемся

        info = self.scenarios_config.get(scenario_id, {})
        return_to_original = info.get('return_to_original', True)
        print(f"\n{'='*70}")
        print(f"АВАРИЙНЫЙ СЦЕНАРИЙ: {info.get('description', scenario_id)} (уровень вложенности {self.recursion_depth+1})")
        print(f"{'='*70}")
        print("Выполните следующие действия для устранения аварии.")
        
        # Запускаем пошаговый режим для аварийного графа с возможностью вызова новых аварий
        self._run_emergency_steps(graph)
        
        print(f"\n--- АВАРИЙНЫЙ СЦЕНАРИЙ ЗАВЕРШЁН ---")
        return return_to_original

    def _run_emergency_steps(self, graph):
        """Пошаговое выполнение аварийного графа с поддержкой вложенных аварий"""
        if graph.current_state_id is None:
            print("Нет начального состояния в аварийном сценарии")
            return

        steps = 0
        max_steps = 50
        # Создаём обработчик для вложенного уровня
        nested_handler = EmergencyHandler(
            base_dir=self.base_dir,
            label_manager=self.label_manager,
            recursion_depth=self.recursion_depth + 1,
            max_depth=self.max_depth
        )

        while steps < max_steps:
            cur_state = graph.states[graph.current_state_id]
            print(f"\n--- {cur_state.name} ---")
            print(cur_state.description)
            if cur_state.objects_state:
                print("\nСостояние объектов:")
                for obj, props in cur_state.objects_state.items():
                    active = [k for k,v in props.items() if v is True]
                    if active:
                        print(f"   {obj}: {', '.join(active)}")
            if cur_state.state_type.value == "final":
                print("Аварийный сценарий успешно завершён.")
                break

            available = graph.get_available_actions()
            if not available:
                print("Нет доступных действий. Сценарий прерван.")
                break

            print("\nДоступные действия:")
            for i, (act, _) in enumerate(available, 1):
                print(f"{i}. {act.name}: {act.description}")
            print("0. Прервать сценарий")

            choice = input("Выберите действие: ").strip()
            if choice == '0':
                print("Сценарий прерван пользователем.")
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    act, _ = available[idx]
                    
                    # Показываем рекомендации (если есть)
                    recs = self.label_manager.get_top_recommendations_for_action(act, 3)
                    if recs:
                        print("\nРекомендации:")
                        for r in recs:
                            print(f"   {r['rank']}. {r['text']} (оценка: {r['score']:.3f})")

                    confirm = input(f"\nВыполнить {act.name}? (y/n): ").lower()
                    if confirm == 'y':
                        graph.execute_action(act.id, silent=False)
                        steps += 1
                    elif confirm == 'n':
                        # Возможна новая аварийная ситуация внутри аварийного сценария
                        print("Возникла ли новая аварийная ситуация? (y/n): ")
                        new_emergency = input().lower()
                        if new_emergency == 'y':
                            scenarios = nested_handler.get_emergency_scenarios_for_action(act)
                            if not scenarios:
                                print("Нет подходящих аварийных сценариев для текущей ситуации.")
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
                                        return_to_original = nested_handler.run_emergency_scenario(sc_id)
                                        if not return_to_original:
                                            print("Вложенный аварийный сценарий завершён. Прерываем текущий сценарий.")
                                            return
                                        # Иначе продолжаем текущий сценарий
                                    else:
                                        print("Неверный выбор")
                                except ValueError:
                                    print("Ошибка ввода")
                        else:
                            print("Действие отменено, выберите другое действие.")
                    else:
                        print("Неверный ввод")
                else:
                    print("Неверный номер")
            except ValueError:
                print("Ошибка ввода")

        print(f"\nВыполнено шагов аварийного сценария: {steps}")