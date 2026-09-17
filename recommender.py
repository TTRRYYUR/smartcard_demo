import pandas as pd

from db_service import get_products, get_stock
from predictor import get_history_scores, predict_finished_products

# Продукты для догрузки количества
SCALABLE_PRODUCTS = {
    "Молоко", "Яйца", "Куриное филе", "Хлеб", "Картофель",
    "Бананы", "Яблоки", "Рис", "Гречка", "Макароны",
    "Кефир", "Творог", "Морковь", "Помидоры", "Сыр", "Масло подсолнечное"
}

MAX_QUANTITY_PER_PRODUCT = 4

# Сценарии с УСИЛЕННЫМИ весами, чтобы разница была видна на диаграмме
SCENARIOS = {
    "balanced": {
        "label": "⚖️ Сбалансированный",
        "need_w": 0.4, "history_w": 0.3, "value_w": 0.3,
        "cal_w": 0.25, "protein_w": 0.25, "fat_w": 0.25, "carbs_w": 0.25,
    },
    "protein": {
        "label": "🥩 Белковый",
        "need_w": 0.2, "history_w": 0.1, "value_w": 0.7, # Максимальный упор на выгоду белка
        "cal_w": 0.0, "protein_w": 1.0, "fat_w": 0.0, "carbs_w": 0.0, # Только белки важны
    },
    "calories": {
        "label": "⚡ Калорийный",
        "need_w": 0.2, "history_w": 0.1, "value_w": 0.7,
        "cal_w": 1.0, "protein_w": 0.0, "fat_w": 0.0, "carbs_w": 0.0, # Только калории
    },
    "economy": {
        "label": "💰 Экономный",
        "need_w": 0.6, "history_w": 0.2, "value_w": 0.2,
        "cal_w": 0.25, "protein_w": 0.25, "fat_w": 0.25, "carbs_w": 0.25,
        "economy_mode": True, # Режим минимальной цены
    },
}

def get_scenario(scenario_key):
    return SCENARIOS.get(scenario_key, SCENARIOS["balanced"])

def calculate_need_score(product_name, stock_df):
    if stock_df.empty: return 1.0
    stock_items = stock_df[stock_df['name'] == product_name]
    if stock_items.empty: return 1.0
    quantity = stock_items.iloc[0]['quantity']
    if quantity >= 1.0: return 0.1
    elif quantity >= 0.5: return 0.4
    else: return 0.8

def calculate_value_score(row, scenario):
    price = row['price']
    if price <= 0: return 0.0

    if scenario.get("economy_mode"):
        # В экономном режиме дешевизна важнее всего (обратная цена)
        return 1000.0 / price 

    # В остальных режимах считаем "плотность" нужного нутриента на рубль
    nutrient_value = (
        scenario["cal_w"] * row['calories'] +
        scenario["protein_w"] * row['protein'] * 15 + # Усиливаем вес белка
        scenario["fat_w"] * row['fat'] * 9 +
        scenario["carbs_w"] * row['carbs'] * 4
    )
    
    return nutrient_value / price

def calculate_product_scores(products_df, stock_df, history_scores, scenario):
    scores = []
    for _, row in products_df.iterrows():
        product_name = row['name']
        need_score = calculate_need_score(product_name, stock_df)
        history_score = history_scores.get(product_name, 0.0)
        value_score = calculate_value_score(row, scenario)

        final_score = (
            scenario["need_w"] * need_score +
            scenario["history_w"] * history_score +
            scenario["value_w"] * value_score
        )

        scores.append({
            'product_id': int(row['id']),
            'name': product_name,
            'category': row['category'],
            'unit': row['unit'],
            'price': row['price'],
            'calories': row['calories'],
            'protein': row['protein'],
            'fat': row['fat'],
            'carbs': row['carbs'],
            'need_score': need_score,
            'history_score': history_score,
            'value_score': value_score,
            'final_score': final_score
        })

    scores_df = pd.DataFrame(scores)

    if not scores_df.empty and scores_df['value_score'].max() > 0:
        scores_df['value_score_normalized'] = scores_df['value_score'] / scores_df['value_score'].max()
    else:
        scores_df['value_score_normalized'] = 0

    # Пересчитываем финальный скор с нормализованной выгодой
    scores_df['final_score'] = (
        scenario["need_w"] * scores_df['need_score'] +
        scenario["history_w"] * scores_df['history_score'] +
        scenario["value_w"] * scores_df['value_score_normalized']
    )

    return scores_df

def build_reason(row, finished_products):
    reasons = []
    if row['need_score'] >= 0.8: reasons.append("Нет дома")
    if row['history_score'] > 0.5: reasons.append("Часто покупаете")
    if row['name'] in finished_products: reasons.append("По статистике закончилось")
    if row['value_score_normalized'] > 0.7: reasons.append("Выгодная цена")
    if not reasons: reasons.append("Хороший вариант")
    return "; ".join(reasons)

def make_item(row, quantity, reason):
    price = row['price']
    return {
        'product_id': int(row['product_id']),
        'name': row['name'],
        'category': row['category'],
        'unit': row['unit'],
        'quantity': float(quantity),
        'price': price,
        'total': price * quantity,
        'calories': row['calories'] * quantity,
        'protein': row['protein'] * quantity,
        'fat': row['fat'] * quantity,
        'carbs': row['carbs'] * quantity,
        'reason': reason,
        'priority': 1,
        'estimated_price': price * quantity
    }

def make_item_from_existing(item, new_quantity):
    unit_price = item['price'] / item['quantity'] if item['quantity'] > 0 else item['price']
    unit_calories = item['calories'] / item['quantity'] if item['quantity'] > 0 else item['calories']
    unit_protein = item['protein'] / item['quantity'] if item['quantity'] > 0 else item['protein']
    unit_fat = item['fat'] / item['quantity'] if item['quantity'] > 0 else item['fat']
    unit_carbs = item['carbs'] / item['quantity'] if item['quantity'] > 0 else item['carbs']

    return {
        'product_id': item['product_id'],
        'name': item['name'],
        'category': item['category'],
        'unit': item['unit'],
        'quantity': float(new_quantity),
        'price': unit_price,
        'total': unit_price * new_quantity,
        'calories': unit_calories * new_quantity,
        'protein': unit_protein * new_quantity,
        'fat': unit_fat * new_quantity,
        'carbs': unit_carbs * new_quantity,
        'reason': item['reason'],
        'priority': item['priority'],
        'estimated_price': unit_price * new_quantity
    }

def scale_up_basket(selected, remaining_budget):
    if remaining_budget <= 0: return selected, remaining_budget
    
    scalable_indices = [i for i, item in enumerate(selected) if item['name'] in SCALABLE_PRODUCTS]
    if not scalable_indices: return selected, remaining_budget

    cursor = 0
    while remaining_budget > 0 and cursor < len(scalable_indices) * MAX_QUANTITY_PER_PRODUCT:
        idx = scalable_indices[cursor % len(scalable_indices)]
        item = selected[idx]

        if item['quantity'] >= MAX_QUANTITY_PER_PRODUCT:
            cursor += 1
            continue

        unit_price = item['price']
        if unit_price <= 0 or remaining_budget < unit_price:
            cursor += 1
            continue

        new_quantity = item['quantity'] + 1
        selected[idx] = make_item_from_existing(item, new_quantity)
        remaining_budget -= unit_price
        cursor += 1

    return selected, remaining_budget

def build_shopping_list(user_id, budget, scenario_key="balanced"):
    products_df = get_products()
    stock_df = get_stock(user_id)
    history_scores = get_history_scores(user_id)
    finished_products = predict_finished_products(user_id)
    scenario = get_scenario(scenario_key)

    if products_df.empty: return pd.DataFrame(), 0.0, {}

    scores_df = calculate_product_scores(products_df, stock_df, history_scores, scenario)
    scores_df = scores_df.sort_values('final_score', ascending=False)

    selected = []
    total_price = 0.0

    for _, row in scores_df.iterrows():
        price = row['price']
        if total_price + price <= budget:
            reason = build_reason(row, finished_products)
            selected.append(make_item(row, 1, reason))
            total_price += price

    if not selected: return pd.DataFrame(), 0.0, {}

    remaining_budget = budget - total_price
    selected, remaining_budget = scale_up_basket(selected, remaining_budget)

    result_df = pd.DataFrame(selected)
    final_total = result_df['total'].sum()

    nutrition = {
        'total_calories': result_df['calories'].sum(),
        'total_protein': result_df['protein'].sum(),
        'total_fat': result_df['fat'].sum(),
        'total_carbs': result_df['carbs'].sum()
    }

    return result_df, final_total, nutrition
