import pandas as pd

from db_service import get_products, get_stock
from predictor import get_history_scores, predict_finished_products


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

    # Простая логика: если есть больше 1 единицы, снижаем приоритет
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

    # Комбинированная оценка: 50% калории, 50% белки
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

        # Итоговая оценка с весами
        # need_score: 40% - нужно ли сейчас
        # history_score: 30% - покупали ли раньше
        # value_score: 30% - выгодно ли

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

    # Нормализуем value_score
    if not scores_df.empty and scores_df['value_score'].max() > 0:
        scores_df['value_score_normalized'] = (
            scores_df['value_score'] / scores_df['value_score'].max()
        )
    else:
        scores_df['value_score_normalized'] = 0

    # Пересчитываем final_score с нормализованным value
    scores_df['final_score'] = (
        0.4 * scores_df['need_score'] +
        0.3 * scores_df['history_score'] +
        0.3 * scores_df['value_score_normalized']
    )

    return scores_df


def build_shopping_list(user_id, budget):
    """
    Главная функция: собирает список покупок в рамках бюджета.
    Возвращает DataFrame с рекомендованными продуктами и объяснениями.
    """
    products_df = get_products()
    stock_df = get_stock(user_id)

    history_scores = get_history_scores(user_id)
    finished_products = predict_finished_products(user_id)

    if products_df.empty:
        return pd.DataFrame(), 0.0, {}

    # Считаем оценки
    scores_df = calculate_product_scores(products_df, stock_df, history_scores)

    # Сортируем по итоговой оценке
    scores_df = scores_df.sort_values('final_score', ascending=False)

    # Жадный алгоритм: берём продукты, пока хватает бюджета
    selected = []
    total_price = 0.0

    for _, row in scores_df.iterrows():
        price = row['price']

        if total_price + price <= budget:
            # Формируем объяснение
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

            reason_text = "; ".join(reasons)

            selected.append({
                'product_id': int(row['product_id']),
                'name': row['name'],
                'category': row['category'],
                'unit': row['unit'],
                'quantity': 1.0,
                'price': row['price'],
                'total': row['price'],
                'calories': row['calories'],
                'protein': row['protein'],
                'fat': row['fat'],
                'carbs': row['carbs'],
                'reason': reason_text,
                'priority': 1,
                'estimated_price': row['price']
            })

            total_price += price

    if not selected:
        return pd.DataFrame(), 0.0, {}

    result_df = pd.DataFrame(selected)

    # Считаем итоговую питательность
    nutrition = {
        'total_calories': result_df['calories'].sum(),
        'total_protein': result_df['protein'].sum(),
        'total_fat': result_df['fat'].sum(),
        'total_carbs': result_df['carbs'].sum()
    }

    return result_df, total_price, nutrition