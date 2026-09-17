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
        'cal
