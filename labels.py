"""Загрузка и управление метками и рекомендациями"""

import json
from typing import List, Dict, Set, Optional, Tuple
from models import Label, Action


class LabelManager:
    """Менеджер меток и рекомендаций"""
    
    def __init__(self, config_file: str = "labels_config.json"):
        self.labels: List[Label] = []
        self.action_labels_cache: Dict[str, List[Label]] = {}
        self.load_config(config_file)
    
    def load_config(self, config_file: str) -> None:
        """Загрузка конфигурации меток из JSON"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for label_data in data.get('labels', []):
                label = Label(
                    name=label_data['name'],
                    keywords=label_data['keywords'],
                    recommendations=label_data['recommendations']
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
    
    def get_recommendations_for_action(self, action: Action) -> List[str]:
        """Получение всех рекомендаций для действия"""
        labels = self.get_labels_for_action(action)
        all_recommendations = []
        seen = set()
        
        for label in labels:
            for rec in label.recommendations:
                if rec not in seen:
                    seen.add(rec)
                    all_recommendations.append(rec)
        
        return all_recommendations
    
    def display_recommendations_for_action(self, action: Action) -> None:
        """Вывод рекомендаций для действия"""
        labels = self.get_labels_for_action(action)
        recommendations = self.get_recommendations_for_action(action)
        
        if not recommendations:
            print("   (нет рекомендаций для этого действия)")
            return
        
        print(f"\n   [РЕКОМЕНДАЦИИ ДЛЯ ДЕЙСТВИЯ: {action.name}]")
        print("   " + "-"*50)
        for i, rec in enumerate(recommendations, 1):
            print(f"      {i}. {rec}")
        
        # Показываем метки, которые вызвали рекомендации
        if labels:
            label_names = [label.name for label in labels]
            print(f"\n   (основано на метках: {', '.join(label_names)})")
        print("   " + "-"*50)
    
    def get_all_labels_info(self) -> List[Tuple[str, List[str], List[str]]]:
        """Получение информации о всех метках"""
        result = []
        for label in self.labels:
            result.append((label.name, label.keywords, label.recommendations))
        return result