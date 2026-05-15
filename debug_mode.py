import json, copy, os
from datetime import datetime
from typing import Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


class DebugMode:
    def __init__(self, graph, label_manager):
        self.graph = graph
        self.label_manager = label_manager
        self.original_weights = None
        self.original_scores = None
        self.changes_log = []
        self.debug_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_current_comparison(self, c1, c2):
        idx1 = self.label_manager.ranker.criteria_ahp.criteria_names.index(c1)
        idx2 = self.label_manager.ranker.criteria_ahp.criteria_names.index(c2)
        return self.label_manager.ranker.criteria_ahp.pairwise_matrix[idx1, idx2]
    
    def run(self):
        print("\n" + "="*70)
        print("РЕЖИМ ДЕБАГА ДЛЯ ЭКСПЕРТА")
        print("="*70)
        self._save_original_state()
        while True:
            print("\n[МЕНЮ ДЕБАГА]")
            print("   1. Показать текущие веса")
            print("   2. Изменить веса через парные сравнения")
            print("   3. Показать все рекомендации с оценками")
            print("   4. Изменить оценки рекомендаций")
            print("   5. Пошаговое выполнение с отладкой")
            print("   6. История изменений")
            print("   7. Сохранить изменения в файлы")
            print("   8. Сбросить к оригиналу")
            print("   0. Выход")
            ch = input("Ваш выбор: ").strip()
            if ch == '0':
                break
            elif ch == '1':
                self._show_criteria_weights()
            elif ch == '2':
                self._edit_pairwise()
            elif ch == '3':
                self._show_all_recommendations()
            elif ch == '4':
                self._edit_action_recommendations()
            elif ch == '5':
                self._debug_step_by_step()
            elif ch == '6':
                self._show_changes_log()
            elif ch == '7':
                self._save_changes_to_file()
            elif ch == '8':
                self._reset_to_original()
            else:
                print("Неверный выбор")
    
    def _save_original_state(self):
        self.original_weights = copy.deepcopy(self.label_manager.ranker.criteria_ahp.weights)
        self.original_scores = {}
        for aid, act in self.graph.actions.items():
            recs = self.label_manager.get_recommendations_for_action(act)
            self.original_scores[aid] = copy.deepcopy(recs)
    
    def _show_criteria_weights(self):
        w = self.label_manager.ranker.criteria_ahp.weights
        print("\n=== ВЕСА КРИТЕРИЕВ ===")
        for k, v in w.items():
            print(f"   {k}: {v:.4f} ({v:.1%})")
        cr = self.label_manager.ranker.criteria_ahp.consistency_ratio
        print(f"Согласованность: ОС={cr:.2%}")
    
    def _edit_pairwise(self):
        ahp = self.label_manager.ranker.criteria_ahp
        crits = ahp.criteria_names
        n = len(crits)
        print("\n=== РЕДАКТИРОВАНИЕ ПАРНЫХ СРАВНЕНИЙ ===")
        print("Введите числа от 1 до 9. Если A важнее B – число >1, иначе <1.")
        comparisons = {}
        for i in range(n):
            for j in range(i+1, n):
                cur = self._get_current_comparison(crits[i], crits[j])
                while True:
                    try:
                        val = input(f"{crits[i]} vs {crits[j]} (текущее {cur:.1f}): ").strip()
                        if not val:
                            val = cur
                        else:
                            val = float(val)
                        comparisons[(crits[i], crits[j])] = val
                        break
                    except ValueError:
                        print("Ошибка, введите число")
        ahp.create_pairwise_matrix(crits, comparisons)
        ahp.calculate_weights()
        ahp.calculate_consistency()
        self.changes_log.append({
            'timestamp': datetime.now().isoformat(),
            'type': 'pairwise_edit',
            'new_comparisons': {f"{c1}_vs_{c2}": v for (c1,c2), v in comparisons.items()}
        })
        print("Веса пересчитаны.")
        self._show_criteria_weights()
    
    def _show_all_recommendations(self):
        for aid, act in self.graph.actions.items():
            print(f"\n[ДЕЙСТВИЕ] {act.name}")
            recs = self.label_manager.get_recommendations_for_action(act)
            if not recs:
                print("   нет рекомендаций")
                continue
            for i, r in enumerate(recs,1):
                print(f"   {i}. {r['text']}")
                for crit, sc in r.get('scores', {}).items():
                    print(f"      {crit}: {sc:.2f}")
    
    def _edit_action_recommendations(self):
        acts = list(self.graph.actions.values())
        print("Выберите действие:")
        for i, a in enumerate(acts,1):
            print(f"   {i}. {a.name}")
        try:
            idx = int(input("Номер: ")) - 1
            if idx < 0 or idx >= len(acts):
                print("Неверный номер")
                return
            action = acts[idx]
            recs = self.label_manager.get_recommendations_for_action(action)
            if not recs:
                print("Нет рекомендаций")
                return
            print("\nРекомендации:")
            for i, r in enumerate(recs,1):
                print(f"{i}. {r['text']}")
            r_idx = int(input("Номер рекомендации для изменения (0 - выход): ")) - 1
            if r_idx < 0 or r_idx >= len(recs):
                return
            rec = recs[r_idx]
            scores = rec.get('scores', {})
            new_scores = {}
            crits = self.label_manager.ranker.criteria_ahp.weights.keys()
            print("Введите новые оценки (0-1):")
            for c in crits:
                old = scores.get(c, 0.5)
                while True:
                    try:
                        v = input(f"   {c} (текущий {old:.2f}): ").strip()
                        if not v:
                            v = old
                        else:
                            v = float(v)
                            v = max(0, min(1, v))
                        new_scores[c] = v
                        break
                    except ValueError:
                        print("Ошибка")
            # обновляем scores в label_manager
            labels = self.label_manager.get_labels_for_action(action)
            for lbl in labels:
                for r in lbl.recommendations:
                    if r['text'] == rec['text']:
                        r['scores'] = new_scores
                        break
            self.changes_log.append({
                'timestamp': datetime.now().isoformat(),
                'type': 'rec_scores',
                'action': action.name,
                'recommendation': rec['text'],
                'old_scores': scores,
                'new_scores': new_scores
            })
            print("Оценки обновлены")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def _debug_step_by_step(self):
        print("\n=== ПОШАГОВОЕ ВЫПОЛНЕНИЕ С ОТЛАДКОЙ ===")
        # используем текущий граф
        steps = 0
        while True:
            cur = self.graph.states[self.graph.current_state_id]
            print(f"\n[{cur.name}]")
            avail = self.graph.get_available_actions()
            if not avail:
                print("Нет доступных действий")
                break
            for i, (act,_) in enumerate(avail,1):
                print(f"{i}. {act.name}")
            print("0 - выход")
            ch = input("Выберите действие или d для деталей: ").strip()
            if ch == '0':
                break
            if ch == 'd':
                self._show_action_debug_info(avail)
                continue
            try:
                idx = int(ch)-1
                if 0 <= idx < len(avail):
                    act, _ = avail[idx]
                    # показать детали
                    self._show_action_debug_info([(act, None)])
                    conf = input(f"Выполнить {act.name}? (y/n): ").strip().lower()
                    if conf == 'y':
                        top = self.label_manager.get_top_recommendations_for_action(act, 3)
                        self.graph.execute_action(act.id, recommendations=top)
                        steps += 1
                    else:
                        print("Отменено")
                else:
                    print("Неверный номер")
            except ValueError:
                print("Ошибка")
        print(f"Выполнено шагов: {steps}")
    
    def _show_action_debug_info(self, actions):
        w = self.label_manager.ranker.criteria_ahp.weights
        for act, _ in actions:
            print(f"\n=== ОТЛАДКА: {act.name} ===")
            print(f"Описание: {act.description}")
            labs = self.label_manager.get_labels_for_action(act)
            if labs:
                print(f"Метки: {', '.join(l.name for l in labs)}")
            recs = self.label_manager.get_recommendations_for_action(act)
            if recs:
                ranked = self.label_manager.ranker.rank_recommendations(recs)
                print("Рекомендации с оценками:")
                for r, s in ranked[:5]:
                    print(f"   {r['text']} -> {s:.4f}")
                    for crit, sc in r.get('scores', {}).items():
                        contr = w.get(crit,0) * sc
                        print(f"      {crit}: {sc:.2f} (вклад {contr:.4f})")
            else:
                print("Нет рекомендаций")
    
    def _show_changes_log(self):
        print("\n=== ИСТОРИЯ ИЗМЕНЕНИЙ ===")
        for i, ch in enumerate(self.changes_log,1):
            print(f"{i}. {ch['timestamp']} - {ch['type']}")
            if ch['type'] == 'pairwise_edit':
                for k,v in ch['new_comparisons'].items():
                    print(f"   {k}: {v}")
            elif ch['type'] == 'rec_scores':
                print(f"   Действие: {ch['action']}")
                print(f"   Рекомендация: {ch['recommendation'][:60]}")
                print("   Было:", ch['old_scores'])
                print("   Стало:", ch['new_scores'])
    
    def _save_criteria_weights_to_file(self, filename):
        ahp = self.label_manager.ranker.criteria_ahp
        crits = ahp.criteria_names
        # восстанавливаем парные сравнения из матрицы
        comps = {}
        for i in range(len(crits)):
            for j in range(i+1, len(crits)):
                val = ahp.pairwise_matrix[i,j]
                comps[f"{crits[i]}_vs_{crits[j]}"] = round(val, 3)
        data = {
            "criteria": [{"name": c} for c in crits],
            "pairwise_comparisons": comps,
            "calculated_weights": {k: float(v) for k,v in ahp.weights.items()},
            "note": "Generated from debug mode"
        }
        with open(os.path.join(DEBUG_DIR, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_labels_to_file(self, filename):
        labels_data = []
        for lab in self.label_manager.labels:
            recs = []
            for r in lab.recommendations:
                recs.append({
                    "text": r['text'],
                    "scores": {k: float(v) for k,v in r.get('scores',{}).items()}
                })
            labels_data.append({
                "name": lab.name,
                "keywords": lab.keywords,
                "recommendations": recs
            })
        data = {"labels": labels_data, "note": "Generated from debug mode"}
        with open(os.path.join(DEBUG_DIR, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_changes_to_file(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_criteria_weights_to_file(f"ahp_debug_{ts}.json")
        self._save_labels_to_file(f"labels_debug_{ts}.json")
        log = {
            'session_id': self.debug_session_id,
            'timestamp': ts,
            'changes': self.changes_log,
            'final_weights': {k:float(v) for k,v in self.label_manager.ranker.criteria_ahp.weights.items()}
        }
        with open(os.path.join(DEBUG_DIR, f"debug_log_{ts}.json"), 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        print(f"[СОХРАНЕНО] файлы в {DEBUG_DIR}")
    
    def _reset_to_original(self):
        if input("Сбросить все изменения? (y/n): ").lower() == 'y':
            self.label_manager.ranker.criteria_ahp.weights = copy.deepcopy(self.original_weights)
            # восстановить оценки рекомендаций
            for aid, act in self.graph.actions.items():
                if aid in self.original_scores:
                    orig = self.original_scores[aid]
                    # обновить рекомендации в label_manager
                    labels = self.label_manager.get_labels_for_action(act)
                    for lbl in labels:
                        for r in lbl.recommendations:
                            for o in orig:
                                if r['text'] == o['text']:
                                    r['scores'] = copy.deepcopy(o['scores'])
            self.changes_log = []
            print("Сброс выполнен")