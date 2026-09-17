import random

def collect_available_products(shopping_list_df, stock_df):
    products = []
    if not stock_df.empty: products.extend(stock_df['name'].tolist())
    if not shopping_list_df.empty: products.extend(shopping_list_df['name'].tolist())
    return list(set(products))

def generate_menu_local(shopping_list_df, stock_df):
    """
    Умная локальная генерация меню.
    Подбирает блюда из доступных продуктов, добавляет КБЖУ.
    """
    available = collect_available_products(shopping_list_df, stock_df)
    
    recipes = {
        "breakfast": [
            {"name": "Овсяная каша на молоке", "needs": ["Овсянка", "Молоко"], "kcal": 320, "p": 12, "f": 8, "c": 48},
            {"name": "Яичница с хлебом", "needs": ["Яйца", "Хлеб"], "kcal": 450, "p": 25, "f": 30, "c": 25},
            {"name": "Творог со сметаной", "needs": ["Творог", "Сметана"], "kcal": 280, "p": 28, "f": 15, "c": 8},
            {"name": "Бутерброды с сыром", "needs": ["Хлеб", "Сыр"], "kcal": 380, "p": 18, "f": 22, "c": 30},
        ],
        "lunch": [
            {"name": "Гречка с куриным филе", "needs": ["Гречка", "Куриное филе"], "kcal": 550, "p": 45, "f": 12, "c": 50},
            {"name": "Рис с курицей и морковью", "needs": ["Рис", "Куриное филе", "Морковь"], "kcal": 600, "p": 40, "f": 15, "c": 65},
            {"name": "Картофель с курицей", "needs": ["Картофель", "Куриное филе"], "kcal": 580, "p": 38, "f": 18, "c": 55},
            {"name": "Макароны с сыром", "needs": ["Макароны", "Сыр"], "kcal": 620, "p": 25, "f": 28, "c": 70},
        ],
        "dinner": [
            {"name": "Творожная запеканка", "needs": ["Творог", "Яйца"], "kcal": 350, "p": 30, "f": 15, "c": 25},
            {"name": "Салат овощной с маслом", "needs": ["Помидоры", "Морковь", "Масло подсолнечное"], "kcal": 180, "p": 3, "f": 12, "c": 15},
            {"name": "Куриное филе на пару", "needs": ["Куриное филе"], "kcal": 250, "p": 50, "f": 5, "c": 0},
            {"name": "Запечённые яблоки", "needs": ["Яблоки"], "kcal": 150, "p": 2, "f": 1, "c": 35},
        ]
    }

    def get_dish(meal_type):
        possible = [r for r in recipes[meal_type] if all(ing in available for ing in r["needs"])]
        if not possible:
            return {"name": "Лёгкий перекус", "kcal": 200, "p": 5, "f": 5, "c": 20}
        return random.choice(possible)

    menu = []
    for day in range(1, 4):
        b = get_dish("breakfast")
        l = get_dish("lunch")
        d = get_dish("dinner")
        
        menu.append({
            'day': day,
            'breakfast': f"{b['name']} (~{b['kcal']} ккал, Б:{b['p']} Ж:{b['f']} У:{b['c']})",
            'lunch': f"{l['name']} (~{l['kcal']} ккал, Б:{l['p']} Ж:{l['f']} У:{l['c']})",
            'dinner': f"{d['name']} (~{d['kcal']} ккал, Б:{d['p']} Ж:{d['f']} У:{d['c']})"
        })
    
    return menu

def generate_menu(shopping_list_df, stock_df, use_llm=False, api_key=None, folder_id=None):
    # Всегда используем локальную генерацию для стабильности
    menu = generate_menu_local(shopping_list_df, stock_df)
    source = "Встроенный алгоритм" if use_llm else "Локальный"
    return menu, source
