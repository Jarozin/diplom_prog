"""Загрузка и управление метками и рекомендациями"""

import json
from typing import List, Dict, Set, Optional, Tuple
from models import Label, Action
from ahp_method import AHPRecommendationRanker


class LabelManager:
    """Менеджер меток и рекомендаций с использованием полного МАИ"""
    
    def __init__(self, config_file: str = "labels_config.json", ahp_config_file: str = "ahp_criteria_config.json"):
        self.labels: List[Label] = []
        self.action_labels_cache: Dict[str, List[Label]] = {}
        self.ranker: AHPRecommendationRanker = AHPRecommendationRanker(ahp_config_file)
        self.load_config(config_file)
    
    def load_config(self, config_file: str) -> None:
        """Загрузка конфигурации меток из JSON"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for label_data in data.get('labels', []):
                recommendations = label_data.get('recommendations', [])
                
                # Преобразуем рекомендации в нужный формат
                formatted_recs = []
                for rec in recommendations:
                    if isinstance(rec, str):
                        formatted_recs.append({'text': rec, 'scores': {}})
                    else:
                        formatted_recs.append(rec)
                
                label = Label(
                    name=label_data['name'],
                    keywords=label_data['keywords'],
                    recommendations=formatted_recs
                )
                self.labels.append(label)
            
            print(f"[ИНФО] Загружено {len(self.labels)} меток из {config_file}")
        except FileNotFoundError:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл {config_file} не найден. Метки не будут использоваться.")
        except Exception as e:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка загрузки меток: {e}")
    
    def get_labels_for_action(self, action: Action) -> List[Label]:
        """Получение меток, подходящих для действия (с кэшированием)"""
        if action.id in self.action_labels_cache:
            return self.action_labels_cache[action.id]
        
        text_to_check = f"{action.name} {action.description}"
        matched_labels = []
        
        for label in self.labels:
            if label.matches(text_to_check):
                matched_labels.append(label)
        
        self.action_labels_cache[action.id] = matched_labels
        return matched_labels
    
    def get_recommendations_for_action(self, action: Action) -> List[Dict]:
        """Получение всех рекомендаций для действия (с оценками)"""
        labels = self.get_labels_for_action(action)
        all_recommendations = []
        seen_texts = set()
        
        for label in labels:
            for rec in label.recommendations:
                text = rec.get('text', '') if isinstance(rec, dict) else rec
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    if isinstance(rec, dict):
                        all_recommendations.append(rec)
                    else:
                        all_recommendations.append({'text': rec, 'scores': {}})
        
        return all_recommendations
    
    def get_top_recommendations_for_action(self, action: Action, top_n: int = 3) -> List[Dict]:
        """Получение топ-N рекомендаций для действия (ранжированных по полному МАИ)"""
        recommendations = self.get_recommendations_for_action(action)
        if not recommendations:
            return []
        
        return self.ranker.get_top_recommendations(recommendations, top_n)
    
    def display_recommendations_for_action(self, action: Action, top_n: int = 3) -> None:
        """Вывод топ-N рекомендаций для действия"""
        self.ranker.display_top_recommendations(
            self.get_recommendations_for_action(action), 
            action.name, 
            top_n
        )
    
    def get_all_labels_info(self) -> List[Tuple[str, List[str], List[Dict]]]:
        """Получение информации о всех метках"""
        result = []
        for label in self.labels:
            result.append((label.name, label.keywords, label.recommendations))
        return result
    
    def display_criteria_info(self) -> None:
        """Вывод информации о критериях МАИ"""
        self.ranker.display_criteria_info()