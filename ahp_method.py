"""Полная реализация метода анализа иерархий (МАИ) Саати"""

import numpy as np
from typing import Dict, List, Tuple, Any
import json


class AHPMethod:
    """
    Полная реализация метода анализа иерархий (МАИ)
    
    Включает:
    - Построение матриц парных сравнений
    - Вычисление собственных векторов через геометрическое среднее
    - Проверку согласованности (CR < 0.1)
    - Расчет глобальных приоритетов
    """
    
    # Шкала относительной важности Саати
    SCALE = {
        1: "Одинаковая важность",
        2: "Слабое превосходство",
        3: "Умеренное превосходство",
        4: "Существенное превосходство",
        5: "Значительное превосходство",
        6: "Очень сильное превосходство", 
        7: "Сильнейшее превосходство",
        8: "Подавляющее превосходство",
        9: "Абсолютное превосходство"
    }
    
    # Случайные индексы для проверки согласованности (таблица Саати)
    RANDOM_INDICES = {
        1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
        6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
        11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59
    }
    
    def __init__(self):
        self.criteria_names: List[str] = []
        self.pairwise_matrix: np.ndarray = None
        self.weights: Dict[str, float] = {}
        self.consistency_ratio: float = 0.0
        self.consistency_index: float = 0.0
        self.is_consistent: bool = False
    
    def create_pairwise_matrix(self, criteria: List[str], comparisons: Dict[Tuple[str, str], float]) -> np.ndarray:
        """
        Создание матрицы парных сравнений
        
        Args:
            criteria: список названий критериев
            comparisons: словарь сравнений вида {('крит1', 'крит2'): значение}
                         значение > 1 означает, что крит1 важнее крит2
        """
        n = len(criteria)
        matrix = np.ones((n, n))
        
        for i, crit_i in enumerate(criteria):
            for j, crit_j in enumerate(criteria):
                if i == j:
                    matrix[i][j] = 1
                elif i < j:
                    # Ищем сравнение
                    value = comparisons.get((crit_i, crit_j))
                    if value is None:
                        # Пробуем обратное сравнение
                        rev_value = comparisons.get((crit_j, crit_i))
                        if rev_value is not None:
                            value = 1.0 / rev_value
                        else:
                            value = 1.0
                    matrix[i][j] = value
                    matrix[j][i] = 1.0 / value
        
        self.pairwise_matrix = matrix
        self.criteria_names = criteria
        return matrix
    
    def calculate_weights(self) -> Dict[str, float]:
        """
        Вычисление весов критериев методом геометрического среднего (классический МАИ)
        
        Returns:
            словарь с весами критериев
        """
        if self.pairwise_matrix is None:
            raise ValueError("Матрица парных сравнений не создана")
        
        n = len(self.criteria_names)
        
        # 1. Вычисляем геометрическое среднее по строкам
        geometric_means = []
        for i in range(n):
            # Произведение элементов строки
            product = np.prod(self.pairwise_matrix[i, :])
            # Корень степени n
            gm = product ** (1.0 / n)
            geometric_means.append(gm)
        
        # 2. Нормализуем (делим на сумму геометрических средних)
        total = sum(geometric_means)
        weights = [gm / total for gm in geometric_means]
        
        # Преобразуем в обычные float
        self.weights = {name: float(weights[i]) for i, name in enumerate(self.criteria_names)}
        return self.weights
    
    def calculate_consistency(self) -> Tuple[float, float, bool]:
        """
        Проверка согласованности матрицы (классический метод Саати)
        
        Returns:
            (consistency_index, consistency_ratio, is_consistent)
            CR < 0.1 - матрица согласована
        """
        if self.pairwise_matrix is None:
            raise ValueError("Матрица парных сравнений не создана")
        
        n = len(self.criteria_names)
        weights_array = np.array(list(self.weights.values()))
        
        # 1. Вычисляем λ_max (главное собственное значение)
        #  λ_max = (1/n) * ∑ ( (A * w)_i / w_i )
        aw = self.pairwise_matrix @ weights_array
        lambda_max = np.mean(aw / weights_array)
        
        # 2. Индекс согласованности (Consistency Index)
        #    CI = (λ_max - n) / (n - 1)
        self.consistency_index = float((lambda_max - n) / (n - 1) if n > 1 else 0)
        
        # 3. Отношение согласованности (Consistency Ratio)
        #    CR = CI / RI
        ri = self.RANDOM_INDICES.get(n, 1.59)
        self.consistency_ratio = float(self.consistency_index / ri if ri > 0 else 0)
        
        # 4. Проверка согласованности
        self.is_consistent = self.consistency_ratio < 0.1
        
        return self.consistency_index, self.consistency_ratio, self.is_consistent
    
    def rank_alternatives(self, alternatives_scores: List[Dict[str, float]]) -> List[Tuple[Any, float]]:
        """
        Ранжирование альтернатив на основе весов критериев
        
        Args:
            alternatives_scores: список словарей с оценками альтернатив по критериям
                                 например: [{'альт1': {'крит1': 0.8, 'крит2': 0.6}}, ...]
        
        Returns:
            список кортежей (альтернатива, глобальный_приоритет), отсортированный по убыванию
        """
        results = []
        
        for alt_scores in alternatives_scores:
            alt_name = list(alt_scores.keys())[0]
            scores = list(alt_scores.values())[0]
            
            global_priority = 0.0
            for criterion, weight in self.weights.items():
                score = scores.get(criterion, 0.0)
                global_priority += weight * score
            
            results.append((alt_name, float(global_priority)))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def display_matrix(self) -> None:
        """Вывод матрицы парных сравнений"""
        if self.pairwise_matrix is None:
            print("Матрица не создана")
            return
        
        print("\n[МАТРИЦА ПАРНЫХ СРАВНЕНИЙ]")
        print(" " * 12, end="")
        for name in self.criteria_names:
            print(f"{name[:12]:>12}", end="")
        print()
        
        for i, name in enumerate(self.criteria_names):
            print(f"{name[:12]:<12}", end="")
            for j in range(len(self.criteria_names)):
                value = self.pairwise_matrix[i][j]
                print(f"{float(value):12.3f}", end="")
            print()
    
    def display_results(self) -> None:
        """Вывод результатов МАИ"""
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ МЕТОДА АНАЛИЗА ИЕРАРХИЙ")
        print("="*60)
        
        print("\n[ВЕСА КРИТЕРИЕВ (геометрическое среднее)]")
        for name, weight in sorted(self.weights.items(), key=lambda x: x[1], reverse=True):
            print(f"   {name}: {weight:.4f} ({weight:.1%})")
        
        print(f"\n[ПРОВЕРКА СОГЛАСОВАННОСТИ]")
        print(f"   Индекс согласованности (ИС): {self.consistency_index:.4f}")
        print(f"   Отношение согласованности (ОС): {self.consistency_ratio:.2%}")
        
        if self.is_consistent:
            print("   Результат: МАТРИЦА СОГЛАСОВАНА (ОС < 10%)")
        else:
            print("   Результат: МАТРИЦА НЕ СОГЛАСОВАНА (ОС >= 10%)")
            print("   Рекомендуется пересмотреть парные сравнения")
        
        self.display_matrix()


class AHPRecommendationRanker:
    """Ранжирование рекомендаций с использованием полного МАИ"""
    
    def __init__(self, criteria_config_file: str = "ahp_criteria_config.json"):
        self.criteria_names: List[str] = []
        self.criteria_ahp: AHPMethod = AHPMethod()
        self.load_criteria_config(criteria_config_file)
    
    def load_criteria_config(self, config_file: str) -> None:
        """Загрузка конфигурации критериев и парных сравнений"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.criteria_names = [c['name'] for c in data.get('criteria', [])]
            
            # Загружаем парные сравнения
            comparisons_raw = data.get('pairwise_comparisons', {})
            comparisons = {}
            
            for key, value in comparisons_raw.items():
                if '_vs_' in key:
                    crit1, crit2 = key.split('_vs_')
                    comparisons[(crit1, crit2)] = value
            
            # Создаем матрицу парных сравнений и вычисляем веса через геометрическое среднее
            if comparisons and len(self.criteria_names) > 1:
                self.criteria_ahp.create_pairwise_matrix(self.criteria_names, comparisons)
                self.criteria_ahp.calculate_weights()
                self.criteria_ahp.calculate_consistency()
            
            print(f"[ИНФО] Загружено {len(self.criteria_names)} критериев для МАИ")
            if self.criteria_ahp.is_consistent:
                print(f"[ИНФО] Матрица согласована (ОС={self.criteria_ahp.consistency_ratio:.2%})")
            else:
                print(f"[ПРЕДУПРЕЖДЕНИЕ] Матрица не согласована! (ОС={self.criteria_ahp.consistency_ratio:.2%})")
                
        except FileNotFoundError:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл {config_file} не найден. Используются стандартные веса.")
            self._set_default_weights()
        except Exception as e:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка загрузки критериев: {e}")
            self._set_default_weights()
    
    def _set_default_weights(self) -> None:
        """Установка стандартных весов через геометрическое среднее"""
        self.criteria_names = ['безопасность', 'полезность', 'актуальность', 'срочность', 'сложность']
        
        # Стандартные парные сравнения (по шкале Саати)
        comparisons = {
            ('безопасность', 'полезность'): 2,
            ('безопасность', 'актуальность'): 3,
            ('безопасность', 'срочность'): 4,
            ('безопасность', 'сложность'): 5,
            ('полезность', 'актуальность'): 2,
            ('полезность', 'срочность'): 3,
            ('полезность', 'сложность'): 4,
            ('актуальность', 'срочность'): 2,
            ('актуальность', 'сложность'): 3,
            ('срочность', 'сложность'): 2,
        }
        
        self.criteria_ahp.create_pairwise_matrix(self.criteria_names, comparisons)
        self.criteria_ahp.calculate_weights()
        self.criteria_ahp.calculate_consistency()
    
    def calculate_recommendation_score(self, scores: Dict[str, float]) -> float:
        """
        Вычисление интегральной оценки рекомендации с использованием весов МАИ
        
        Args:
            scores: оценки рекомендации по критериям
        
        Returns:
            взвешенная сумма (глобальный приоритет)
        """
        total = 0.0
        for criterion, weight in self.criteria_ahp.weights.items():
            score = scores.get(criterion, 0.0)
            total += weight * score
        return float(total)
    
    def rank_recommendations(self, recommendations: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        Ранжирование рекомендаций с использованием весов МАИ
        
        Args:
            recommendations: список рекомендаций с полем 'scores'
        
        Returns:
            список кортежей (рекомендация, оценка), отсортированный по убыванию
            Оценки нормализованы так, что их сумма = 1
        """
        if not recommendations:
            return []
        
        # 1. Вычисляем сырые оценки
        raw_scores = []
        for rec in recommendations:
            score = self.calculate_recommendation_score(rec.get('scores', {}))
            raw_scores.append(score)
        
        # 2. Нормализуем, чтобы сумма = 1
        total_raw = sum(raw_scores)
        if total_raw > 0:
            normalized_scores = [score / total_raw for score in raw_scores]
        else:
            normalized_scores = [1.0 / len(recommendations) for _ in recommendations]
        
        # 3. Формируем результат
        ranked = list(zip(recommendations, [float(s) for s in normalized_scores]))
        
        # 4. Сортируем по убыванию
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked
    
    def get_top_recommendations(self, recommendations: List[Dict], top_n: int = 3) -> List[Dict]:
        """
        Получение топ-N рекомендаций на основе МАИ
        
        Args:
            recommendations: список рекомендаций
            top_n: количество рекомендаций для возврата
        
        Returns:
            список лучших рекомендаций с оценками
        """
        ranked = self.rank_recommendations(recommendations)
        top_recommendations = []
        
        for i, (rec, score) in enumerate(ranked[:top_n], 1):
            top_recommendations.append({
                'text': rec['text'],
                'score': float(score),
                'rank': i
            })
        
        return top_recommendations
    
    def display_top_recommendations(self, recommendations: List[Dict], action_name: str, top_n: int = 3) -> None:
        """
        Вывод топ-N рекомендаций для действия
        
        Args:
            recommendations: список рекомендаций
            action_name: название действия
            top_n: количество рекомендаций для вывода
        """
        top_recs = self.get_top_recommendations(recommendations, top_n)
        
        if not top_recs:
            print("   (нет рекомендаций для этого действия)")
            return
        
        print(f"\n   [ТОП-{top_n} РЕКОМЕНДАЦИЙ (МАИ) ДЛЯ ДЕЙСТВИЯ: {action_name}]")
        print("   " + "-"*55)
        for rec in top_recs:
            print(f"      {rec['rank']}. {rec['text']}")
            print(f"         (оценка: {rec['score']:.4f})")
        print("   " + "-"*55)
    
    def display_criteria_info(self) -> None:
        """Вывод информации о критериях и их весах (по МАИ)"""
        self.criteria_ahp.display_results()