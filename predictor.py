import pandas as pd

from db_service import get_all_purchase_items


def analyze_purchase_frequency(user_id):
    """
    Анализирует историю покупок и считает, как часто пользователь покупает каждый продукт.
    Возвращает словарь: {product_name: {count, avg_days_between, days_since_last}}
    """
    history_df = get_all_purchase_items(user_id)

    if history_df.empty:
        return {}

    history_df['purchased_at'] = pd.to_datetime(history_df['purchased_at'])

    result = {}

    for product_name in history_df['name'].unique():
        product_history = history_df[history_df['name'] == product_name]
        product_history = product_history.sort_values('purchased_at')

        purchase_count = len(product_history)

        if purchase_count < 2:
            # Мало данных, пропускаем
            continue

        dates = product_history['purchased_at'].tolist()

        # Считаем интервалы между покупками
        intervals = []
        for i in range(1, len(dates)):
            days = (dates[i] - dates[i-1]).days
            intervals.append(days)

        avg_days_between = sum(intervals) / len(intervals) if intervals else 0

        # Сколько дней прошло с последней покупки
        last_purchase = dates[-1]
        now = pd.Timestamp.now()
        days_since_last = (now - last_purchase).days

        result[product_name] = {
            'count': purchase_count,
            'avg_days_between': avg_days_between,
            'days_since_last': days_since_last,
            'product_id': int(product_history.iloc[0]['product_id'])
        }

    return result


def predict_finished_products(user_id, threshold=0.8):
    """
    Предсказывает, какие продукты могли закончиться.
    threshold = 0.8 означает: если прошло 80% от среднего интервала, считаем что закончилось.

    Возвращает список названий продуктов.
    """
    frequency = analyze_purchase_frequency(user_id)

    finished = []

    for product_name, data in frequency.items():
        if data['avg_days_between'] == 0:
            continue

        ratio = data['days_since_last'] / data['avg_days_between']

        if ratio >= threshold:
            finished.append(product_name)

    return finished


def get_history_scores(user_id):
    """
    Возвращает словарь оценок на основе истории покупок.
    Чем чаще покупают продукт, тем выше оценка.
    """
    frequency = analyze_purchase_frequency(user_id)

    scores = {}

    if not frequency:
        return scores

    # Нормализуем оценки (максимум 1.0)
    max_count = max(data['count'] for data in frequency.values())

    for product_name, data in frequency.items():
        score = data['count'] / max_count if max_count > 0 else 0
        scores[product_name] = score

    return scores