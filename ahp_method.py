import json
import numpy as np
from typing import Dict, List, Tuple, Any


class AHPMethod:
    """Полная реализация МАИ с использованием pairwise comparisons"""
    
    RANDOM_INDICES = {1:0.00, 2:0.00, 3:0.58, 4:0.90, 5:1.12, 6:1.24, 7:1.32, 8:1.41, 9:1.45, 10:1.49}
    
    def __init__(self):
        self.criteria_names = []
        self.pairwise_matrix = None
        self.weights = {}
        self.consistency_ratio = 0.0
        self.consistency_index = 0.0
        self.lambda_max = 0.0
        self.is_consistent = False
    
    def create_pairwise_matrix(self, criteria: List[str], comparisons: Dict[Tuple[str,str], float]) -> np.ndarray:
        n = len(criteria)
        matrix = np.ones((n, n))
        for i, ci in enumerate(criteria):
            for j, cj in enumerate(criteria):
                if i == j: 
                    continue
                if i < j:
                    val = comparisons.get((ci, cj))
                    if val is None:
                        rev = comparisons.get((cj, ci))
                        val = 1.0 / rev if rev is not None else 1.0
                    matrix[i][j] = val
                    matrix[j][i] = 1.0 / val
        self.pairwise_matrix = matrix
        self.criteria_names = criteria
        return matrix
    
    def calculate_weights(self) -> Dict[str, float]:
        n = len(self.criteria_names)
        geometric_means = [np.prod(self.pairwise_matrix[i,:]) ** (1.0/n) for i in range(n)]
        total = sum(geometric_means)
        weights = [gm / total for gm in geometric_means]
        self.weights = {name: float(weights[i]) for i, name in enumerate(self.criteria_names)}
        return self.weights
    
    def calculate_consistency(self) -> Tuple[float, float, bool]:
        n = len(self.criteria_names)
        if n == 1:
            self.lambda_max = 1.0
            self.consistency_index = 0.0
            self.consistency_ratio = 0.0
            self.is_consistent = True
            return self.consistency_index, self.consistency_ratio, self.is_consistent
        weights_arr = np.array(list(self.weights.values()))
        aw = self.pairwise_matrix @ weights_arr
        self.lambda_max = np.mean(aw / weights_arr)
        self.consistency_index = (self.lambda_max - n) / (n - 1)
        ri = self.RANDOM_INDICES.get(n, 1.59)
        self.consistency_ratio = self.consistency_index / ri if ri > 0 else 0
        self.is_consistent = self.consistency_ratio < 0.1
        return self.consistency_index, self.consistency_ratio, self.is_consistent


class AHPRecommendationRanker:
    def __init__(self, config_file: str = "ahp_criteria_config.json", profile: str = "опытный"):
        self.criteria_names = []
        self.criteria_ahp = AHPMethod()
        self.load_config(config_file, profile)
    
    def load_config(self, config_file: str, profile: str) -> None:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.criteria_names = [c['name'] for c in data['criteria']]
        profile_data = data['profiles'].get(profile)
        if not profile_data:
            raise ValueError(f"Профиль {profile} не найден")
        comparisons_raw = profile_data['pairwise_comparisons']
        comparisons = {}
        for key, val in comparisons_raw.items():
            if '_vs_' in key:
                c1, c2 = key.split('_vs_')
                comparisons[(c1, c2)] = val
        self.criteria_ahp.create_pairwise_matrix(self.criteria_names, comparisons)
        self.criteria_ahp.calculate_weights()
        self.criteria_ahp.calculate_consistency()
        print(f"[ИНФО] Загружен профиль '{profile}'. Веса: {self.criteria_ahp.weights}")
    
    def calculate_recommendation_score(self, scores: Dict[str, float]) -> float:
        total = 0.0
        for crit, w in self.criteria_ahp.weights.items():
            total += w * scores.get(crit, 0.0)
        return float(total)
    
    def rank_recommendations(self, recommendations: List[Dict]) -> List[Tuple[Dict, float]]:
        if not recommendations:
            return []
        raw = [(rec, self.calculate_recommendation_score(rec.get('scores', {}))) for rec in recommendations]
        total = sum(s for _, s in raw)
        if total > 0:
            ranked = [(rec, s/total) for rec, s in raw]
        else:
            ranked = [(rec, 1.0/len(recommendations)) for rec in recommendations]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
    
    def get_top_recommendations(self, recommendations: List[Dict], top_n: int = 3) -> List[Dict]:
        ranked = self.rank_recommendations(recommendations)
        return [{'text': rec['text'], 'score': score, 'rank': i+1} for i, (rec, score) in enumerate(ranked[:top_n])]
    
    def display_top_recommendations(self, recommendations: List[Dict], action_name: str, top_n: int = 3) -> None:
        top = self.get_top_recommendations(recommendations, top_n)
        if not top:
            print("   (нет рекомендаций)")
            return
        print(f"\n   [ТОП-{top_n} РЕКОМЕНДАЦИЙ ДЛЯ {action_name}]")
        print("   " + "-"*55)
        for rec in top:
            print(f"      {rec['rank']}. {rec['text']} (оценка: {rec['score']:.3f})")
        print("   " + "-"*55)
    
    def display_criteria_info(self) -> None:
        print("\n=== ВЕСА КРИТЕРИЕВ (МАИ) ===")
        for name, w in self.criteria_ahp.weights.items():
            print(f"   {name}: {w:.1%}")
        print(f"Согласованность: ОС={self.criteria_ahp.consistency_ratio:.2%}")
        if not self.criteria_ahp.is_consistent:
            print("Предупреждение: матрица не согласована!")