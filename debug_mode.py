"""Режим дебага для эксперта - настройка весов МАИ и оценок рекомендаций"""

import json
import copy
from typing import Dict, List, Tuple, Any
from datetime import datetime
import os


class DebugMode:
    """Режим дебага для экспертной настройки системы"""
    
    def __init__(self, graph, label_manager):
        self.graph = graph
        self.label_manager = label_manager
        self.original_weights = None
        self.original_scores = None
        self.changes_log = []
        self.debug_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _format_float(self, value):
        """Форматирование float для вывода (убираем np.float64)"""
        if hasattr(value, 'item'):
            return f"{value.item():.4f}"
        return f"{float(value):.4f}"
    
    def _format_weights(self, weights):
        """Форматирование словаря весов для вывода"""
        return {k: float(v) for k, v in weights.items()}
    
    def run(self):
        """Запуск режима дебага"""
        print("\n" + "="*70)
        print("РЕЖИМ ДЕБАГА ДЛЯ ЭКСПЕРТА")
        print("="*70)
        print("\nВ этом режиме вы можете:")
        print("   1. Просматривать текущие веса критериев МАИ")
        print("   2. Изменять веса критериев")
        print("   3. Просматривать и изменять оценки рекомендаций для действий")
        print("   4. Пошагово выполнять инструкцию с отладкой")
        print("   5. Сохранять изменения в новый файл")
        print("\n" + "="*70)
        
        # Сохраняем оригинальные значения
        self._save_original_state()
        
        while True:
            print("\n[МЕНЮ РЕЖИМА ДЕБАГА]")
            print("   1. Показать текущие веса критериев МАИ")
            print("   2. Изменить веса критериев МАИ")
            print("   3. Показать все действия и их рекомендации с оценками")
            print("   4. Изменить оценки рекомендаций для действия")
            print("   5. Запустить пошаговое выполнение с отладкой")
            print("   6. Показать историю изменений")
            print("   7. Сохранить изменения в новый файл")
            print("   8. Сбросить к оригинальным настройкам")
            print("   0. Выход из режима дебага")
            
            choice = input("\nВаш выбор: ").strip()
            
            if choice == '1':
                self._show_criteria_weights()
            elif choice == '2':
                self._edit_criteria_weights()
            elif choice == '3':
                self._show_all_actions_with_scores()
            elif choice == '4':
                self._edit_action_recommendations()
            elif choice == '5':
                self._debug_step_by_step()
            elif choice == '6':
                self._show_changes_log()
            elif choice == '7':
                self._save_changes_to_file()
            elif choice == '8':
                self._reset_to_original()
            elif choice == '0':
                print("\nВозврат в главное меню...")
                break
            else:
                print("[ОШИБКА] Неверный выбор!")
    
    def _save_original_state(self):
        """Сохранение оригинального состояния"""
        # Сохраняем веса критериев
        weights = self.label_manager.ranker.criteria_ahp.weights
        self.original_weights = {k: float(v) for k, v in weights.items()}
        
        # Сохраняем оценки рекомендаций для всех действий
        self.original_scores = {}
        for action_id, action in self.graph.actions.items():
            recommendations = self.label_manager.get_recommendations_for_action(action)
            self.original_scores[action_id] = []
            for rec in recommendations:
                self.original_scores[action_id].append({
                    'text': rec['text'],
                    'scores': copy.deepcopy(rec.get('scores', {}))
                })
    
    def _show_criteria_weights(self):
        """Показать текущие веса критериев"""
        print("\n" + "="*60)
        print("ТЕКУЩИЕ ВЕСА КРИТЕРИЕВ МАИ")
        print("="*60)
        
        weights = self.label_manager.ranker.criteria_ahp.weights
        total = sum(weights.values())
        
        print("\n[ВЕСА]")
        for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            print(f"   {name}: {float(weight):.4f} ({float(weight):.1%})")
        
        print(f"\n   Сумма весов: {float(total):.4f}")
        
        # Показываем проверку согласованности
        print("\n[ПРОВЕРКА СОГЛАСОВАННОСТИ]")
        cr = self.label_manager.ranker.criteria_ahp.consistency_ratio
        print(f"   Отношение согласованности (ОС): {float(cr):.2%}")
        if self.label_manager.ranker.criteria_ahp.is_consistent:
            print("   Статус: СОГЛАСОВАНА (ОС < 10%)")
        else:
            print("   Статус: НЕ СОГЛАСОВАНА (ОС >= 10%) - рекомендуется пересмотреть сравнения")
    
    def _edit_criteria_weights(self):
        """Редактирование весов критериев"""
        print("\n" + "="*60)
        print("ИЗМЕНЕНИЕ ВЕСОВ КРИТЕРИЕВ МАИ")
        print("="*60)
        
        current_weights = {k: float(v) for k, v in self.label_manager.ranker.criteria_ahp.weights.items()}
        
        print("\nТекущие веса (сумма должна быть 1.0):")
        for name, weight in current_weights.items():
            print(f"   {name}: {weight:.4f}")
        
        print("\nВведите новые веса (сумма должна быть 1.0):")
        new_weights = {}
        total = 0
        
        for name in current_weights.keys():
            while True:
                try:
                    value = input(f"   {name} (текущий {current_weights[name]:.4f}): ").strip()
                    if not value:
                        value = current_weights[name]
                    else:
                        value = float(value)
                    new_weights[name] = value
                    total += value
                    break
                except ValueError:
                    print("   Ошибка! Введите число.")
        
        print(f"\nСумма введенных весов: {total:.4f}")
        
        if abs(total - 1.0) > 0.001:
            print("Сумма весов не равна 1.0. Нормализовать? (y/n): ")
            normalize = input().strip().lower()
            if normalize == 'y':
                for name in new_weights:
                    new_weights[name] /= total
                print("Веса нормализованы.")
        
        # Сохраняем старые веса для лога
        old_weights = current_weights.copy()
        
        # Применяем новые веса
        self.label_manager.ranker.criteria_ahp.weights = new_weights
        
        # Записываем изменение в лог
        self.changes_log.append({
            'timestamp': datetime.now().isoformat(),
            'type': 'criteria_weights',
            'old_values': old_weights,
            'new_values': new_weights.copy()
        })
        
        print("\n[УСПЕХ] Веса критериев обновлены!")
        
        # Показываем изменения
        print("\n[ИЗМЕНЕНИЯ]")
        for name in old_weights:
            old_val = old_weights[name]
            new_val = new_weights[name]
            if abs(old_val - new_val) > 0.001:
                print(f"   {name}: {old_val:.4f} -> {new_val:.4f} ({((new_val - old_val) * 100):+.1f}%)")
            else:
                print(f"   {name}: {old_val:.4f} (без изменений)")
        
        self._show_criteria_weights()
    
    def _show_all_actions_with_scores(self):
        """Показать все действия и их рекомендации с оценками"""
        print("\n" + "="*70)
        print("ВСЕ ДЕЙСТВИЯ И ИХ РЕКОМЕНДАЦИИ С ОЦЕНКАМИ")
        print("="*70)
        
        for action_id, action in self.graph.actions.items():
            print(f"\n[ДЕЙСТВИЕ] {action.name} (id: {action_id})")
            print(f"   Описание: {action.description}")
            
            recommendations = self.label_manager.get_recommendations_for_action(action)
            if not recommendations:
                print("   (нет рекомендаций для этого действия)")
                continue
            
            print(f"   Рекомендации ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                print(f"      {i}. {rec['text']}")
                scores = rec.get('scores', {})
                if scores:
                    print(f"         Оценки по критериям:")
                    for criterion, score in scores.items():
                        print(f"            {criterion}: {float(score):.2f}")
                else:
                    print("         (нет оценок по критериям)")
    
    def _edit_action_recommendations(self):
        """Редактирование оценок рекомендаций для действия"""
        print("\n" + "="*60)
        print("ИЗМЕНЕНИЕ ОЦЕНОК РЕКОМЕНДАЦИЙ")
        print("="*60)
        
        # Показываем список действий
        actions_list = list(self.graph.actions.values())
        print("\nВыберите действие:")
        for i, action in enumerate(actions_list, 1):
            print(f"   {i}. {action.name}")
        
        try:
            choice = int(input("\nНомер действия: ")) - 1
            if 0 <= choice < len(actions_list):
                action = actions_list[choice]
                self._edit_single_action_recommendations(action)
            else:
                print("[ОШИБКА] Неверный номер!")
        except ValueError:
            print("[ОШИБКА] Введите число!")
    
    def _edit_single_action_recommendations(self, action):
        """Редактирование рекомендаций для конкретного действия"""
        print(f"\n[РЕДАКТИРОВАНИЕ] Действие: {action.name}")
        
        recommendations = self.label_manager.get_recommendations_for_action(action)
        if not recommendations:
            print("Нет рекомендаций для редактирования.")
            return
        
        # Показываем рекомендации
        print("\nРекомендации:")
        criteria_names = list(self.label_manager.ranker.criteria_ahp.weights.keys())
        
        for i, rec in enumerate(recommendations, 1):
            print(f"\n   {i}. {rec['text']}")
            scores = rec.get('scores', {})
            for criterion in criteria_names:
                current_score = scores.get(criterion, 0.5)
                print(f"      {criterion}: {float(current_score):.2f}")
        
        # Выбираем рекомендацию для редактирования
        try:
            rec_choice = int(input("\nВыберите номер рекомендации для редактирования (0 - выход): "))
            if rec_choice == 0:
                return
            if 1 <= rec_choice <= len(recommendations):
                rec_index = rec_choice - 1
                rec = recommendations[rec_index]
                
                # Сохраняем оригинальные оценки до изменения
                old_scores = copy.deepcopy(rec.get('scores', {}))
                
                print(f"\nРедактирование: {rec['text']}")
                print("Введите новые оценки по критериям (0-1):")
                
                new_scores = {}
                for criterion in criteria_names:
                    current = old_scores.get(criterion, 0.5)
                    while True:
                        try:
                            value = input(f"   {criterion} (текущий {float(current):.2f}): ").strip()
                            if not value:
                                value = current
                            else:
                                value = float(value)
                                if value < 0:
                                    value = 0
                                elif value > 1:
                                    value = 1
                            new_scores[criterion] = value
                            break
                        except ValueError:
                            print("   Ошибка! Введите число.")
                
                # Обновляем scores в оригинальных данных
                self._update_recommendation_scores(action, rec['text'], new_scores)
                
                # Записываем изменение в лог с сохранением старых оценок
                rec_text_short = rec['text'][:80] + "..." if len(rec['text']) > 80 else rec['text']
                self.changes_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'recommendation_scores',
                    'action': action.name,
                    'recommendation': rec_text_short,
                    'old_scores': {k: float(v) for k, v in old_scores.items()},
                    'new_scores': {k: float(v) for k, v in new_scores.items()}
                })
                
                print("\n[УСПЕХ] Оценки обновлены!")
                
                # Показываем изменения для наглядности
                print("\n[ИЗМЕНЕНИЯ]")
                has_changes = False
                for criterion in criteria_names:
                    old_val = old_scores.get(criterion, 0.5)
                    new_val = new_scores.get(criterion, 0.5)
                    if abs(old_val - new_val) > 0.001:
                        print(f"   {criterion}: {float(old_val):.2f} -> {float(new_val):.2f} ({((new_val - old_val) * 100):+.1f}%)")
                        has_changes = True
                    else:
                        print(f"   {criterion}: {float(old_val):.2f} (без изменений)")
                
                if not has_changes:
                    print("   (изменений не было)")
            else:
                print("[ОШИБКА] Неверный номер!")
        except ValueError:
            print("[ОШИБКА] Введите число!")
    
    def _update_recommendation_scores(self, action, recommendation_text, new_scores):
        """Обновление оценок рекомендации в label_manager"""
        # Находим метки для действия
        labels = self.label_manager.get_labels_for_action(action)
        
        for label in labels:
            for rec in label.recommendations:
                if rec['text'] == recommendation_text:
                    if 'scores' not in rec:
                        rec['scores'] = {}
                    rec['scores'] = new_scores
                    break
    
    def _debug_step_by_step(self):
        """Пошаговое выполнение с отладкой"""
        print("\n" + "="*70)
        print("ПОШАГОВОЕ ВЫПОЛНЕНИЕ С ОТЛАДКОЙ")
        print("="*70)
        
        # Создаем копию графа для отладки
        debug_graph = self.graph
        
        steps = 0
        max_steps = 100
        
        while steps < max_steps:
            current_state = debug_graph.states[debug_graph.current_state_id]
            print("\n" + "-"*70)
            print(f"[ТЕКУЩЕЕ СОСТОЯНИЕ] {current_state.name}")
            print(f"   Описание: {current_state.description}")
            print(f"   Тип: {current_state.state_type.to_rus()}")
            
            if current_state.objects_state:
                print("\n   Состояние объектов:")
                formatted = debug_graph.format_objects_state(current_state.objects_state)
                print(formatted)
            
            if current_state.state_type.value in ["final", "error"]:
                print(f"\n{'[ДОСТИГНУТО КОНЕЧНОЕ СОСТОЯНИЕ]' if current_state.state_type.value == 'final' else '[ДОСТИГНУТО СОСТОЯНИЕ ОШИБКИ]'}")
                break
            
            available_actions = debug_graph.get_available_actions()
            
            if not available_actions:
                print("\n[ПРЕДУПРЕЖДЕНИЕ] Нет доступных действий!")
                break
            
            print(f"\n[ДОСТУПНЫЕ ДЕЙСТВИЯ]")
            for idx, (action, next_state_id) in enumerate(available_actions, 1):
                next_state = debug_graph.states[next_state_id]
                print(f"   {idx}. {action.name} -> {next_state.name}")
            
            print("\n[ОТЛАДОЧНАЯ ИНФОРМАЦИЯ]")
            print("   d - показать детальную информацию о действии")
            print("   w - показать текущие веса критериев")
            print("   e - редактировать веса критериев")
            print("   r - редактировать оценки рекомендаций")
            
            choice = input("\nВаш выбор (номер действия или команда): ").strip().lower()
            
            if choice == 'd':
                self._show_action_debug_info(available_actions)
                continue
            elif choice == 'w':
                self._show_criteria_weights()
                continue
            elif choice == 'e':
                self._edit_criteria_weights()
                continue
            elif choice == 'r':
                self._edit_action_recommendations()
                continue
            
            try:
                idx = int(choice)
                if 1 <= idx <= len(available_actions):
                    action, next_state_id = available_actions[idx - 1]
                    
                    # Показываем подробную отладочную информацию перед выполнением
                    self._show_action_debug_info([(action, next_state_id)])
                    
                    print(f"\nВыполнить действие: {action.name}?")
                    confirm = input("   Подтвердить (y/n): ").strip().lower()
                    
                    if confirm == 'y':
                        # Получаем топ-3 рекомендации
                        top_recs = self.label_manager.get_top_recommendations_for_action(action, top_n=3)
                        
                        print(f"\nВыполняется: {action.name}...")
                        success = debug_graph.execute_action(action.id, recommendations=top_recs)
                        if success:
                            steps += 1
                    else:
                        print("   Действие отменено.")
                else:
                    print("[ОШИБКА] Неверный номер!")
            except ValueError:
                print("[ОШИБКА] Неверная команда!")
        
        print("\n" + "="*70)
        print(f"Отладочное выполнение завершено. Выполнено шагов: {steps}")
        print("="*70)
    
    def _show_action_debug_info(self, actions):
        """Показать отладочную информацию о действиях"""
        weights = self.label_manager.ranker.criteria_ahp.weights
        weights_float = {k: float(v) for k, v in weights.items()}
        
        for action, _ in actions:
            print(f"\n[ОТЛАДКА] Действие: {action.name}")
            print(f"   Описание: {action.description}")
            
            # Показываем метки
            labels = self.label_manager.get_labels_for_action(action)
            if labels:
                print(f"   Метки: {', '.join([l.name for l in labels])}")
            
            # Показываем веса критериев (без np.float64)
            print(f"\n   Веса критериев:")
            for crit, w in weights_float.items():
                print(f"      {crit}: {w:.4f}")
            
            # Показываем рекомендации с расчетом оценок
            recommendations = self.label_manager.get_recommendations_for_action(action)
            if recommendations:
                print(f"\n   Рекомендации с расчетом оценок (МАИ):")
                ranked = self.label_manager.ranker.rank_recommendations(recommendations)
                
                for rec, score in ranked:
                    print(f"\n      Рекомендация: {rec['text']}")
                    print(f"      Итоговая оценка: {float(score):.4f}")
                    scores = rec.get('scores', {})
                    if scores:
                        print("      Оценки по критериям и вклад:")
                        for criterion, crit_score in scores.items():
                            contribution = weights_float.get(criterion, 0) * float(crit_score)
                            print(f"         {criterion}: {float(crit_score):.2f} (вклад: {contribution:.4f})")
            else:
                print("   (нет рекомендаций)")
    
    def _show_changes_log(self):
        """Показать историю изменений"""
        print("\n" + "="*60)
        print("ИСТОРИЯ ИЗМЕНЕНИЙ")
        print("="*60)
        
        if not self.changes_log:
            print("Изменений не было.")
            return
        
        for i, change in enumerate(self.changes_log, 1):
            print(f"\n{i}. {change['timestamp']}")
            print(f"   Тип: {change['type']}")
            
            if change['type'] == 'criteria_weights':
                print("   Изменение весов критериев:")
                print("      Было:")
                for k, v in change['old_values'].items():
                    print(f"         {k}: {v:.4f}")
                print("      Стало:")
                for k, v in change['new_values'].items():
                    diff = v - change['old_values'].get(k, 0)
                    print(f"         {k}: {v:.4f} ({diff:+.4f})")
            
            elif change['type'] == 'recommendation_scores':
                print(f"   Действие: {change['action']}")
                print(f"   Рекомендация: {change['recommendation']}")
                print("      Было:")
                for k, v in change['old_scores'].items():
                    print(f"         {k}: {v:.2f}")
                print("      Стало:")
                for k, v in change['new_scores'].items():
                    old_v = change['old_scores'].get(k, 0.5)
                    diff = v - old_v
                    print(f"         {k}: {v:.2f} ({diff:+.2f})")
    
    def _save_changes_to_file(self):
        """Сохранить изменения в новый файл"""
        print("\n" + "="*60)
        print("СОХРАНЕНИЕ ИЗМЕНЕНИЙ")
        print("="*60)
        
        # Создаем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохраняем измененные веса критериев
        weights_file = f"ahp_criteria_config_debug_{timestamp}.json"
        self._save_criteria_weights_to_file(weights_file)
        
        # Сохраняем измененные оценки рекомендаций
        labels_file = f"labels_config_debug_{timestamp}.json"
        self._save_labels_to_file(labels_file)
        
        # Сохраняем лог изменений
        log_file = f"debug_changes_{timestamp}.json"
        
        # Преобразуем веса для сохранения
        weights = self.label_manager.ranker.criteria_ahp.weights
        weights_float = {k: float(v) for k, v in weights.items()}
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': self.debug_session_id,
                'timestamp': timestamp,
                'changes': self.changes_log,
                'final_weights': weights_float
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n[УСПЕХ] Файлы сохранены:")
        print(f"   - {weights_file}")
        print(f"   - {labels_file}")
        print(f"   - {log_file}")
    
    def _save_criteria_weights_to_file(self, filename):
        """Сохранить веса критериев в файл, идентичный исходному формату"""
        weights = self.label_manager.ranker.criteria_ahp.weights
        criteria_names = list(weights.keys())
        
        # Восстанавливаем парные сравнения как отношения весов:
        # a_ij = w_i / w_j, округлённое до шкалы 1..9 или обратных значений
        pairwise = {}
        for i, name_i in enumerate(criteria_names):
            for j, name_j in enumerate(criteria_names):
                if i >= j:
                    continue
                ratio = weights[name_i] / weights[name_j]
                # Приводим к шкале Саати (1..9)
                if ratio >= 1:
                    value = min(9, round(ratio))
                else:
                    value = 1.0 / min(9, round(1.0 / ratio))
                pairwise[f"{name_i}_vs_{name_j}"] = value
        
        data = {
            "criteria": [{"name": name} for name in criteria_names],
            "pairwise_comparisons": pairwise,
            "calculated_weights": {k: float(v) for k, v in weights.items()},
            "note": "Generated from debug mode. Use 'calculated_weights' for direct loading."
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_labels_to_file(self, filename):
        """Сохранить изменённые метки и рекомендации в файл, идентичный исходному"""
        labels_data = []
        for label in self.label_manager.labels:
            rec_list = []
            for rec in label.recommendations:
                rec_list.append({
                    "text": rec['text'],
                    "scores": {k: float(v) for k, v in rec.get('scores', {}).items()}
                })
            labels_data.append({
                "name": label.name,
                "keywords": label.keywords,
                "recommendations": rec_list
            })
        
        data = {
            "labels": labels_data,
            "note": "Generated from debug mode"
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _reset_to_original(self):
        """Сбросить к оригинальным настройкам"""
        print("\nСбросить все изменения к оригинальным настройкам? (y/n): ")
        confirm = input().strip().lower()
        
        if confirm == 'y':
            # Восстанавливаем веса критериев
            self.label_manager.ranker.criteria_ahp.weights = copy.deepcopy(self.original_weights)
            
            # Восстанавливаем оценки рекомендаций
            for action_id, action in self.graph.actions.items():
                if action_id in self.original_scores:
                    # Обновляем рекомендации для действия
                    labels = self.label_manager.get_labels_for_action(action)
                    for label in labels:
                        for rec in label.recommendations:
                            for orig_rec in self.original_scores[action_id]:
                                if rec['text'] == orig_rec['text']:
                                    rec['scores'] = copy.deepcopy(orig_rec['scores'])
            
            self.changes_log = []
            print("\n[УСПЕХ] Настройки сброшены к оригинальным!")
        else:
            print("Сброс отменен.")