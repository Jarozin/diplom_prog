import json
from typing import List, Dict, Set, Optional, Tuple
from models import Label, Action
from ahp_method import AHPRecommendationRanker


class LabelManager:
    def __init__(self, config_file: str = "labels_config.json", ahp_config_file: str = "ahp_criteria_config.json", profile: str = "опытный"):
        self.labels: List[Label] = []
        self.action_labels_cache: Dict[str, List[Label]] = {}
        self.current_profile = profile
        self.ranker = AHPRecommendationRanker(ahp_config_file, profile)
        self.load_config(config_file)
    
    def load_config(self, config_file: str) -> None:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for label_data in data.get('labels', []):
                recommendations = label_data.get('recommendations', [])
                formatted = []
                for rec in recommendations:
                    if isinstance(rec, str):
                        formatted.append({'text': rec, 'scores': {}})
                    else:
                        formatted.append(rec)
                label = Label(
                    name=label_data['name'],
                    keywords=label_data['keywords'],
                    recommendations=formatted
                )
                self.labels.append(label)
            print(f"[ИНФО] Загружено {len(self.labels)} меток из {config_file}")
        except FileNotFoundError:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл {config_file} не найден.")
        except Exception as e:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка загрузки меток: {e}")
    
    def get_labels_for_action(self, action: Action) -> List[Label]:
        if action.id in self.action_labels_cache:
            return self.action_labels_cache[action.id]
        text = f"{action.name} {action.description}"
        matched = [label for label in self.labels if label.matches(text)]
        self.action_labels_cache[action.id] = matched
        return matched
    
    def get_recommendations_for_action(self, action: Action) -> List[Dict]:
        labels = self.get_labels_for_action(action)
        uniq = {}
        for label in labels:
            for rec in label.recommendations:
                text = rec.get('text', '') if isinstance(rec, dict) else rec
                if text and text not in uniq:
                    uniq[text] = rec if isinstance(rec, dict) else {'text': text, 'scores': {}}
        return list(uniq.values())
    
    def get_top_recommendations_for_action(self, action: Action, top_n: int = 3) -> List[Dict]:
        recs = self.get_recommendations_for_action(action)
        return self.ranker.get_top_recommendations(recs, top_n)
    
    def display_recommendations_for_action(self, action: Action, top_n: int = 3) -> None:
        recs = self.get_recommendations_for_action(action)
        self.ranker.display_top_recommendations(recs, action.name, top_n)
    
    def display_criteria_info(self) -> None:
        self.ranker.display_criteria_info()
    
    def get_all_labels_info(self):
        return [(l.name, l.keywords, l.recommendations) for l in self.labels]