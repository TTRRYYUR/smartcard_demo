import os

import streamlit as st
import matplotlib.pyplot as plt

from db_service import (
    get_users,
    get_budget,
    get_stock,
    get_purchase_history,
    get_purchase_items,
    get_shopping_lists,
    get_shopping_list_items,
    save_shopping_list,
)
from predictor import predict_finished_products
from recommender import build_shopping_list, SCENARIOS
from menu import generate_menu


DB_NAME = "smartcart.db"


def check_database():
    """Проверяет, существует ли файл базы данных."""
    return os.path.exists(DB_NAME)


def get_yandex_credentials():
    """
    Достаёт ключ Yandex из переменных окружения
    или из .streamlit/secrets.toml.
    Если ключа нет, возвращает (None, None).
    """
    api_key = os.environ.get("YANDEX_API_KEY")
    folder_id = os.environ.get("YANDEX_FOLDER_ID")

    if api_key and folder_id:
        return api_key, folder_id

    if st.secrets.load_if_toml_exists():
        api_key = st.secrets.get("YANDEX_API_KEY")
        folder_id = st.secrets.get("YANDEX_FOLDER_ID")

    return api_key, folder_id


def show_nutrition_chart(protein, fat, carbs):
    """Рисует круговую диаграмму соотношения Б/Ж/У."""
    total = protein + fat + carbs

    if total <= 0:
        st.info("Недостаточно данных для диаграммы КБЖУ.")
        return

    labels = ['Белки', 'Жиры', 'Углеводы']
    sizes = [protein, fat, carbs]
    colors = ['#ff6b6b', '#ffd93d', '#6bcB77']

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct='%1.0f%%',
        startangle=90,
        textprops={'fontsize': 11}
    )
    ax.set_title('Соотношение Б/Ж/У в корзине', fontsize=12)

    st.pyplot(fig)


def show_overview(user_name, budget_df, stock_df, purchases_df):
    """Вкладка с общей сводкой по пользователю."""
    st.subheader("Обзор")

    default_budget = 0.0
    period_days = 0

    if not budget_df.empty:
        default_budget = float(budget_df.iloc[0]["amount"])
        period_days = int(budget_df.iloc[0]["period_days"])

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Пользователь", user_name)
    col2.metric("Бюджет", f"{default_budget:.0f} ₽")
    col3.metric("Период", f"{period_days} дн.")
    col4.metric("Покупок в истории", len(purchases_df))

    st.markdown("### Текущий бюджет")

    if budget_df.empty:
        st.info("Бюджет не найден.")
    else:
        st.dataframe(budget_df, width="stretch")

    st.markdown("### Запасы дома")

    if stock_df.empty:
        st.info("Запасов пока нет.")
    else:
        st.dataframe(stock_df, width="stretch")


def show_products():
    """Вкладка с каталогом продуктов и поиском."""
    st.subheader("Каталог продуктов")

    from db_service import get_products
    products_df = get_products()

    search = st.text_input("Поиск по названию или категории", "")

    view_df = products_df

    if search:
        search_lower = search.lower()

        mask = (
            products_df["name"].str.lower().str.contains(search_lower, na=False)
            | products_df["category"].str.lower().str.contains(search_lower, na=False)
        )

        view_df = products_df[mask]

    if view_df.empty:
        st.info("Ничего не найдено.")
    else:
        st.dataframe(view_df, width="stretch")


def show_stock(stock_df):
    """Вкладка с запасами пользователя."""
    st.subheader("Что уже есть дома")

    if stock_df.empty:
        st.info("Запасов пока нет.")
    else:
        st.dataframe(stock_df, width="stretch")


def show_history(purchases_df):
    """Вкладка с историей покупок и составом чеков."""
    st.subheader("История покупок")

    if purchases_df.empty:
        st.info("Покупок пока нет.")
        return

    st.dataframe(purchases_df, width="stretch")

    purchase_ids = purchases_df["id"].tolist()

    selected_id = st.selectbox(
        "Выберите покупку, чтобы посмотреть состав",
        purchase_ids
    )

    items_df = get_purchase_items(int(selected_id))

    st.markdown("### Состав покупки")

    if items_df.empty:
        st.info("В этой покупке нет товаров.")
    else:
        st.dataframe(items_df, width="stretch")


def show_recommendation(user_id, stock_df, default_budget):
    """Вкладка с генерацией списка покупок и меню."""
    st.subheader("Рекомендация списка покупок")

    st.write(
        "Алгоритм учитывает бюджет, запасы дома и историю покупок. "
        "Продукты ранжируются по оценке и добавляются, пока хватает бюджета."
    )

