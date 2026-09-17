import requests
import urllib3
import uuid

# Отключаем предупреждения SSL (для GigaChat это важно)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

def collect_available_products(shopping_list_df, stock_df):
    products = []
    if not stock_df.empty:
        products.extend(stock_df['name'].tolist())
    if not shopping_list_df.empty:
        products.extend(shopping_list_df['name'].tolist())
    return sorted(set(products))

def generate_menu_local(shopping_list_df, stock_df):
    available_products = collect_available_products(shopping_list_df, stock_df)
    breakfasts, lunches, dinners = [], [], []

    if 'Овсянка' in available_products and 'Молоко' in available_products: breakfasts.append("Овсяная каша на молоке")
    if 'Яйца' in available_products and 'Хлеб' in available_products: breakfasts.append("Яичница с хлебом")
    if 'Творог' in available_products: breakfasts.append("Творог со сметаной")
    if 'Куриное филе' in available_products and 'Гречка' in available_products: lunches.append("Гречка с куриным филе")
    if 'Куриное филе' in available_products and 'Рис' in available_products: lunches.append("Рис с куриным филе")
    if 'Картофель' in available_products and 'Куриное филе' in available_products: lunches.append("Картофель с курицей")
    if 'Творог' in available_products: dinners.append("Творожная запеканка")
    if 'Яйца' in available_products and 'Картофель' in available_products: dinners.append("Картофель с яйцом")
    if 'Куриное филе' in available_products and 'Морковь' in available_products: dinners.append("Куриное филе с морковью")

    menu = []
    for day in range(1, 4):
        b = breakfasts[(day - 1) % len(breakfasts)] if breakfasts else "Завтрак не подобран"
        l = lunches[(day - 1) % len(lunches)] if lunches else "Обед не подобран"
        d = dinners[(day - 1) % len(dinners)] if dinners else "Ужин не подобран"
        menu.append({'day': day, 'breakfast': b, 'lunch': l, 'dinner': d})
    return menu

def build_menu_prompt(products):
    products_text = "\n".join([f"- {p}" for p in products])
    return f"""Ты — помощник по питанию. Отвечай только на русском языке.
У пользователя есть: {products_text}
Составь меню на 3 дня из этих продуктов.
Формат:
День 1:
Завтрак: [блюдо] (~[ккал] ккал, Б:[б] Ж:[ж] У:[у]) — [польза]
Обед: [блюдо] (~[ккал] ккал, Б:[б] Ж:[ж] У:[у]) — [польза]
Ужин: [блюдо] (~[ккал] ккал, Б:[б] Ж:[ж] У:[у]) — [польза]
... (и так для 3 дней)"""

def parse_menu_text(menu_text):
    menu = []
    lines = menu_text.strip().split('\n')
    current_day = None
    for line in lines:
        line = line.strip()
        if line.startswith('День'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].rstrip(':').isdigit():
                current_day = int(parts[1].rstrip(':'))
                menu.append({'day': current_day, 'breakfast': '', 'lunch': '', 'dinner': ''})
        elif current_day is not None and ':' in line and menu:
            meal_type, dish = line.split(':', 1)
            meal_type = meal_type.strip().lower()
            dish = dish.strip()
            if 'завтрак' in meal_type: menu[-1]['breakfast'] = dish
            elif 'обед' in meal_type: menu[-1]['lunch'] = dish
            elif 'ужин' in meal_type: menu[-1]['dinner'] = dish
    return menu if menu else None

def get_gigachat_token(auth_key):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {auth_key}"
    }
    data = {"scope": "GIGACHAT_API_PERS"}
    
    try:
        # verify=False критически важно для Сбера
        r = requests.post(GIGACHAT_AUTH_URL, headers=headers, data=data, verify=False, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token"), None
        else:
            return None, f"Ошибка авторизации ({r.status_code}): {r.text[:200]}"
    except Exception as e:
        return None, f"Ошибка сети/SSL при авторизации: {str(e)}"

def generate_menu_gigachat(shopping_list_df, stock_df, auth_key):
    if not auth_key:
        return None, "Ключ GIGACHAT_AUTH_KEY не найден в секретах!"
    
    products = collect_available_products(shopping_list_df, stock_df)
    if not products: return None, "Нет продуктов для меню"

    token, error = get_gigachat_token(auth_key)
    if not token: return None, error

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    body = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": build_menu_prompt(products)}],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    try:
        r = requests.post(GIGACHAT_API_URL, headers=headers, json=body, verify=False, timeout=30)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            return parse_menu_text(content), None
        else:
            return None, f"Ошибка API GigaChat ({r.status_code}): {r.text[:200]}"
    except Exception as e:
        return None, f"Ошибка при генерации: {str(e)}"

def generate_menu(shopping_list_df, stock_df, use_llm=False, api_key=None, folder_id=None):
    if use_llm:
        giga_menu, error_msg = generate_menu_gigachat(shopping_list_df, stock_df, api_key)
        if giga_menu:
            return giga_menu, "GigaChat"
        else:
            # Возвращаем локальное меню, но в source пишем ошибку
            local_menu = generate_menu_local(shopping_list_df, stock_df)
            return local_menu, f"ERROR: {error_msg}"
    
    return generate_menu_local(shopping_list_df, stock_df), "Локальный"
