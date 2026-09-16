import requests

YANDEX_LLM_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def collect_available_products(shopping_list_df, stock_df):
    """Собирает все продукты, которые есть дома и которые предложили купить."""
    products = []

    if not stock_df.empty:
        products.extend(stock_df['name'].tolist())

    if not shopping_list_df.empty:
        products.extend(shopping_list_df['name'].tolist())

    return sorted(set(products))


def generate_menu_local(shopping_list_df, stock_df):
    """
    Генерирует простое меню на основе правил.
    Работает без интернета и без ключей.
    """
    available_products = collect_available_products(shopping_list_df, stock_df)

    breakfasts = []
    lunches = []
    dinners = []

    # Завтраки
    if 'Овсянка' in available_products and 'Молоко' in available_products:
        breakfasts.append("Овсяная каша на молоке")

    if 'Яйца' in available_products and 'Хлеб' in available_products:
        breakfasts.append("Яичница с хлебом")

    if 'Творог' in available_products:
        breakfasts.append("Творог со сметаной")

    # Обеды
    if 'Куриное филе' in available_products and 'Гречка' in available_products:
        lunches.append("Гречка с куриным филе")

    if 'Куриное филе' in available_products and 'Рис' in available_products:
        lunches.append("Рис с куриным филе")

    if 'Картофель' in available_products and 'Куриное филе' in available_products:
        lunches.append("Картофель с курицей")

    # Ужины
    if 'Творог' in available_products:
        dinners.append("Творожная запеканка")

    if 'Яйца' in available_products and 'Картофель' in available_products:
        dinners.append("Картофель с яйцом")

    if 'Куриное филе' in available_products and 'Морковь' in available_products:
        dinners.append("Куриное филе с морковью")

    menu = []

    for day in range(1, 4):
        breakfast = breakfasts[(day - 1) % len(breakfasts)] if breakfasts else "Завтрак не подобран"
        lunch = lunches[(day - 1) % len(lunches)] if lunches else "Обед не подобран"
        dinner = dinners[(day - 1) % len(dinners)] if dinners else "Ужин не подобран"

        menu.append({
            'day': day,
            'breakfast': breakfast,
            'lunch': lunch,
            'dinner': dinner
        })

    return menu


def build_menu_prompt(products):
    """Собирает промпт для YandexGPT."""
    products_text = "\n".join([f"- {p}" for p in products])

    prompt = f"""Ты — помощник по питанию.

У пользователя есть следующие продукты:
{products_text}

Составь простое меню на 3 дня.
Используй только эти продукты.
Ответ должен быть коротким и структурированным.

Формат ответа:
День 1:
Завтрак: [блюдо]
Обед: [блюдо]
Ужин: [блюдо]

День 2:
Завтрак: [блюдо]
Обед: [блюдо]
Ужин: [блюдо]

День 3:
Завтрак: [блюдо]
Обед: [блюдо]
Ужин: [блюдо]
"""
    return prompt


def parse_menu_text(menu_text):
    """
    Парсит текстовый ответ от YandexGPT в структурированное меню.
    """
    menu = []

    lines = menu_text.strip().split('\n')

    current_day = None

    for line in lines:
        line = line.strip()

        if line.startswith('День'):
            parts = line.split()

            if len(parts) >= 2:
                day_number = parts[1].rstrip(':')

                if day_number.isdigit():
                    current_day = int(day_number)
                    menu.append({
                        'day': current_day,
                        'breakfast': '',
                        'lunch': '',
                        'dinner': ''
                    })

        elif current_day is not None and ':' in line and menu:
            meal_type, dish = line.split(':', 1)
            meal_type = meal_type.strip().lower()
            dish = dish.strip()

            if 'завтрак' in meal_type:
                menu[-1]['breakfast'] = dish
            elif 'обед' in meal_type:
                menu[-1]['lunch'] = dish
            elif 'ужин' in meal_type:
                menu[-1]['dinner'] = dish

    if not menu:
        return None

    return menu


def generate_menu_yandex(shopping_list_df, stock_df, api_key, folder_id):
    """
    Генерирует меню через YandexGPT.
    Если что-то пошло не так, возвращает None.
    """
    if not api_key or not folder_id:
        return None

    products = collect_available_products(shopping_list_df, stock_df)

    if not products:
        return None

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }

    body = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.6,
            "maxTokens": "2000"
        },
        "messages": [
            {"role": "user", "text": build_menu_prompt(products)}
        ]
    }

    try:
        response = requests.post(
            YANDEX_LLM_URL,
            headers=headers,
            json=body,
            timeout=20
        )
    except Exception as e:
        print(f"Нет связи с YandexGPT: {e}")
        return None

    if response.status_code != 200:
        print(f"Ошибка YandexGPT: {response.status_code} {response.text}")
        return None

    data = response.json()
    alternatives = data.get("result", {}).get("alternatives", [])

    if not alternatives:
        return None

    menu_text = alternatives[0].get("message", {}).get("text")

    if not menu_text:
        return None

    return parse_menu_text(menu_text)


def generate_menu(shopping_list_df, stock_df, use_llm=False, api_key=None, folder_id=None):
    """
    Главная функция генерации меню.
    Сначала пробуем YandexGPT, если не вышло - локальные правила.
    """
    if use_llm:
        yandex_menu = generate_menu_yandex(
            shopping_list_df,
            stock_df,
            api_key,
            folder_id
        )

        if yandex_menu:
            return yandex_menu, "YandexGPT"

    local_menu = generate_menu_local(shopping_list_df, stock_df)
    return local_menu, "Локальный"