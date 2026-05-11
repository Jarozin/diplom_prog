# 1. Импортируем библиотеку
from saatypy.ahp import AHPBuilder

# 2. Строим модель: указываем критерии и альтернативы
model = (AHPBuilder()
    .add_criteria(["price", "quality", "service"]) # Критерии
    .add_alternatives(["A", "B", "C"])             # Альтернативы
    .build())

# 3. Определяем важность критериев (веса)
model.set_criteria_weights({"price": 0.5, "quality": 0.3, "service": 0.2})

# 4. Проводим парные сравнения альтернатив по каждому критерию
# Например, для критерия "price": A немного лучше B (2), A значительно лучше C (3), B лучше C (1.5)
for crit in ["price", "quality", "service"]:
    model.set_alt_priorities(crit, {
        ("A", "B"): 2.0,
        ("A", "C"): 3.0,
        ("B", "C"): 1.5
    })

# 5. Получаем и выводим итоговые приоритеты альтернатив
priorities, labels = model.alternative_priorities()
print(dict(zip(labels, priorities)))