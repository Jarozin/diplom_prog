import os
import json
from typing import List, Dict, Optional, Tuple
from graph import InstructionGraph
from labels import LabelManager


class EmergencyHandler:
    def __init__(self, base_dir: str, label_manager: LabelManager):
        self.base_dir = base_dir
        self.emergency_dir = os.path.join(base_dir, "emergency")
        self.label_manager = label_manager
        self.scenarios_config = self._load_scenarios_config()
        os.makedirs(self.emergency_dir, exist_ok=True)

    def _load_scenarios_config(self) -> Dict:
        config_path = os.path.join(self.base_dir, "emergency_scenarios.json")
        if not os.path.exists(config_path):
            return {}
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_emergency_scenarios_for_action(self, action) -> List[Tuple[str, str, bool]]:
        """Возвращает список (id_сценария, описание, return_to_original) для доступных аварий"""
        labels = self.label_manager.get_labels_for_action(action)
        # Собираем все ключевые слова из меток действия
        action_keywords = set()
        for label in labels:
            action_keywords.update(label.keywords)
        # Ищем сценарии, у которых теги пересекаются с ключевыми словами действия
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
            # Загружаем граф без label_manager (можно передать тот же, но метки не обязательны)
            graph = InstructionGraph.from_json(filepath, self.label_manager)
            return graph
        except Exception as e:
            print(f"[ОШИБКА] Не удалось загрузить аварийный граф: {e}")
            return None

    def run_emergency_scenario(self, scenario_id: str) -> bool:
        """Запускает выполнение аварийного сценария. Возвращает флаг: нужно ли вернуться в исходный граф."""
        graph = self.load_emergency_graph(scenario_id)
        if not graph:
            return False
        info = self.scenarios_config.get(scenario_id, {})
        return_to_original = info.get('return_to_original', True)
        print(f"\n=== АВАРИЙНЫЙ СЦЕНАРИЙ: {info.get('description', scenario_id)} ===")
        print("Выполните следующие действия для устранения аварии.")
        self._run_emergency_steps(graph)
        print("\n=== АВАРИЙНЫЙ СЦЕНАРИЙ ЗАВЕРШЁН ===")
        return return_to_original

    def _run_emergency_steps(self, graph):
        """Мини-пошаговый режим для аварийного графа без лишних меню"""
        if graph.current_state_id is None:
            print("Нет начального состояния в аварийном сценарии")
            return
        steps = 0
        while True:
            cur_state = graph.states[graph.current_state_id]
            print(f"\n--- {cur_state.name} ---")
            print(cur_state.description)
            if cur_state.state_type.value == "final":
                print("Аварийный сценарий завершён.")
                break
            actions = graph.get_available_actions()
            if not actions:
                print("Нет доступных действий. Сценарий прерван.")
                break
            print("Доступные действия:")
            for i, (act, _) in enumerate(actions, 1):
                print(f"{i}. {act.name}: {act.description}")
            print("0. Прервать сценарий")
            choice = input("Выберите действие: ").strip()
            if choice == '0':
                print("Сценарий прерван пользователем.")
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(actions):
                    act, _ = actions[idx]
                    if input(f"Выполнить {act.name}? (y/n): ").lower() == 'y':
                        graph.execute_action(act.id, silent=False)
                        steps += 1
                    else:
                        print("Отменено")
                else:
                    print("Неверный номер")
            except ValueError:
                print("Ошибка ввода")
        print(f"Выполнено шагов аварийного сценария: {steps}")