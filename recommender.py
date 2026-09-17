import pandas as pd

from db_service import get_products, get_stock
from predictor import get_history_scores, predict_finished_products


# Продукты, которые имеет смысл покупать в большем количестве.
# Для них разрешаем увеличивать количество, если остался бюджет.
SCALABLE_PRODUCTS = {
    "Молоко",
    "Яйца",
    "Куриное филе",
    "Хлеб",
    "Картофель",
    "Бананы",
    "Яблоки",
    "Рис",
    "Гречка",
    "Макароны",
    "Кефир",
    "Творог",
    "Морковь",
    "Помидоры",
}

# Максимальное количество единиц одного продукта в корзине.
MAX_QUANTITY_PER_PRODUCT = 4


def calculate_need_score(product_name, stock_df):
    """
    Считает, насколько продукт нужен прямо сейчас.
    Если есть дома - низкая оценка, если нет - высокая.
    """
    if stock_df.empty:
        return 1.0

    stock_items = stock_df[stock_df['name'] == product_name]

    if stock_items.empty:
        return 1.0

    quantity = stock_items.iloc[0]['quantity']

    if quantity >= 1.0:
        return 0.2
    elif quantity >= 0.5:
        return 0.5
    else:
        return 0.8


def calculate_value_score(row):
    """
    Считает выгоду продукта: питательность за рубль.
    Используем калории и белки.
    """
    price = row['price']

    if price <= 0:
        return 0.0

    calories = row['calories']
    protein = row['protein']

    score = (0.5 * calories + 0.5 * protein * 10) / price

    return score


def calculate_product_scores(products_df, stock_df, history_scores):
    """
    Считает итоговую оценку для каждого продукта.
    """
    scores = []

    for _, row in products_df.iterrows():
        product_name = row['name']

        need_score = calculate_need_score(product_name, stock_df)

        history_score = history_scores.get(product_name, 0.0)

        value_score = calculate_value_score(row)

        final_score = (
            0.4 * need_score +
            0.3 * history_score +
            0.3 * value_score
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
        scores_df['value_score_normalized'] = (
            scores_df['value_score'] / scores_df['value_score'].max()
        )
    else:
        scores_df['value_score_normalized'] = 0

    scores_df['final_score'] = (
        0.4 * scores_df['need_score'] +
        0.3 * scores_df['history_score'] +
        0.3 * scores_df['value_score_normalized']
    )

    return scores_df


def build_reason(row, finished_products):
    """Формирует текстовое объяснение, почему продукт в списке."""
    reasons = []

    if row['need_score'] >= 0.8:
        reasons.append("Нет дома")

    if row['history_score'] > 0.5:
        reasons.append("Часто покупаете")

    if row['name'] in finished_products:
        reasons.append("По статистике закончилось")

    if row['value_score_normalized'] > 0.7:
        reasons.append("Выгодная цена")

    if not reasons:
        reasons.append("Хороший вариант")

    return "; ".join(reasons)


def make_item(row, quantity, reason):
    """Собирает одну позицию корзины с учётом количества."""
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


def scale_up_basket(selected, remaining_budget):
    """
    Распределяет оставшийся бюджет на увеличение количества
    ходовых товаров. Возвращает обновлённый список и новый остаток.
    """
    if remaining_budget <= 0:
        return selected, remaining_budget

    # Индексы позиций, которые можно масштабировать
    scalable_indices = [
        i for i, item in enumerate(selected)
        if item['name'] in SCALABLE_PRODUCTS
    ]

    if not scalable_indices:
        return selected, remaining_budget

    # Добавляем по кругу по 1 штуке, пока хватает бюджета и не достигли лимита
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

        # Увеличиваем количество на 1
        new_quantity = item['quantity'] + 1
        selected[idx] = make_item_from_existing(item, new_quantity)

        remaining_budget -= unit_price
        cursor += 1

    return selected, remaining_budget


def make_item_from_existing(item, new_quantity):
    """Пересобирает позицию из уже существующей с новым количеством."""
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


def build_shopping_list(user_id, budget):
    """
    Главная функция: собирает список покупок в рамках бюджета.
    Сначала набирает базовую корзину, потом догружает количество
    ходовых товаров на оставшийся бюджет.
    """
    products_df = get_products()
    stock_df = get_stock(user_id)

    history_scores = get_history_scores(user_id)
    finished_products = predict_finished_products(user_id)

    if products_df.empty:
        return pd.DataFrame(), 0.0, {}

    scores_df = calculate_product_scores(products_df, stock_df, history_scores)
    scores_df = scores_df.sort_values('final_score', ascending=False)

    # --- Этап 1: базовая корзина (по 1 штуке, пока хватает бюджета) ---
    selected = []
    total_price = 0.0

    for _, row in scores_df.iterrows():
        price = row['price']

        if total_price + price <= budget:
            reason = build_reason(row, finished_products)
            selected.append(make_item(row, 1, reason))
            total_price += price

    if not selected:
        return pd.DataFrame(), 0.0, {}

    # --- Этап 2: догрузка количества ходовых товаров на остаток ---
    remaining_budget = budget - total_price
    selected, remaining_budget = scale_up_basket(selected, remaining_budget)

    result_df = pd.DataFrame(selected)

    # Итоговая цена после догрузки
    final_total = result_df['total'].sum()

    nutrition = {
        'total_calories': result_df['calories'].sum(),
        'total_protein': result_df['protein'].sum(),
        'total_fat': result_df['fat'].sum(),
        'total_carbs': result_df['carbs'].sum()
    }

    return result_df, final_total, nutrition
