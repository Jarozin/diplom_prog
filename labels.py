"""Загрузка и управление метками и рекомендациями"""

import json
from typing import List, Dict, Set
from models import Label


class LabelManager:
    """Менеджер меток и рекомендаций"""
    
    def __init__(self, config_file: str = "labels_config.json"):
        self.labels: List[Label] = []
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
    
    def get_labels_for_action(self, action_name: str, action_description: str) -> List[Label]:
        """Получение меток, подходящих для действия"""
        text_to_check = f"{action_name} {action_description}"
        matched_labels = []
        
        for label in self.labels:
            if label.matches(text_to_check):
                matched_labels.append(label)
        
        return matched_labels
    
    def get_labels_for_text(self, text: str) -> List[Label]:
        """Получение меток, подходящих для произвольного текста"""
        matched_labels = []
        
        for label in self.labels:
            if label.matches(text):
                matched_labels.append(label)
        
        return matched_labels
    
    def get_recommendations_for_labels(self, labels: List[Label]) -> List[str]:
        """Сбор всех рекомендаций из списка меток"""
        all_recommendations = []
        seen = set()
        
        for label in labels:
            for rec in label.recommendations:
                if rec not in seen:
                    seen.add(rec)
                    all_recommendations.append(rec)
        
        return all_recommendations
    
    def display_recommendations(self, action_name: str, action_description: str) -> None:
        """Вывод рекомендаций для действия"""
        labels = self.get_labels_for_action(action_name, action_description)
        
        if not labels:
            print("   (нет рекомендаций)")
            return
        
        recommendations = self.get_recommendations_for_labels(labels)
        
        if recommendations:
            print("\n   [РЕКОМЕНДАЦИИ]")
            for i, rec in enumerate(recommendations, 1):
                print(f"      {i}. {rec}")
            
            # Показываем метки, которые вызвали рекомендации
            label_names = [label.name for label in labels]
            print(f"   (метки: {', '.join(label_names)})")