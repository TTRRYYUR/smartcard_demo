
import os

import streamlit as st

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
from recommender import build_shopping_list
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

    # Предиктивная аналитика: что могло закончиться
    finished = predict_finished_products(user_id)

    if finished:
        st.info(
            "По статистике покупок могло закончиться: "
            + ", ".join(finished)
        )

    budget_input = st.number_input(
        "Бюджет на список",
        min_value=0.0,
        value=float(default_budget),
        step=100.0,
    )

    use_llm = st.checkbox(
        "Генерировать меню через YandexGPT (нужны интернет и ключ)"
    )

    if st.button("Собрать список"):
        result_df, total_price, nutrition = build_shopping_list(user_id, budget_input)

        st.session_state["rec_user_id"] = user_id
        st.session_state["rec_budget"] = float(budget_input)
        st.session_state["rec_result"] = result_df
        st.session_state["rec_total"] = total_price
        st.session_state["rec_nutrition"] = nutrition

        if result_df.empty:
            st.warning("Не удалось собрать список в рамках этого бюджета.")
            st.session_state["rec_menu"] = None
            st.session_state["rec_menu_source"] = ""
        else:
            api_key, folder_id = get_yandex_credentials()

            if use_llm:
                menu, menu_source = generate_menu(
                    result_df, stock_df, True, api_key, folder_id
                )
            else:
                menu, menu_source = generate_menu(
                    result_df, stock_df, False, None, None
                )

            st.session_state["rec_menu"] = menu
            st.session_state["rec_menu_source"] = menu_source

    if st.session_state.get("rec_user_id") != user_id:
        return

    result_df = st.session_state.get("rec_result")

    if result_df is None or result_df.empty:
        return

    total_price = st.session_state.get("rec_total", 0.0)
    nutrition = st.session_state.get("rec_nutrition", {})
    budget_used = st.session_state.get("rec_budget", 0.0)

    st.markdown("### Результат")

    col1, col2 = st.columns(2)
    col1.metric("Итоговая цена", f"{total_price:.2f} ₽")
    col2.metric(
        "Бюджет",
        f"{budget_used:.2f} ₽",
        f"остаток {budget_used - total_price:.2f} ₽",
    )

    col3, col4, col5, col6 = st.columns(4)
    col3.metric("Калории", f"{nutrition.get('total_calories', 0):.0f}")
    col4.metric("Белки", f"{nutrition.get('total_protein', 0):.1f} г")
    col5.metric("Жиры", f"{nutrition.get('total_fat', 0):.1f} г")
    col6.metric("Углеводы", f"{nutrition.get('total_carbs', 0):.1f} г")

    display_df = result_df[["name", "category", "unit", "price", "reason"]].copy()
    display_df.columns = ["Продукт", "Категория", "Ед.", "Цена", "Почему"]

    st.dataframe(display_df, width="stretch")

    menu = st.session_state.get("rec_menu")
    menu_source = st.session_state.get("rec_menu_source", "")

    if menu:
        st.markdown("### Меню на 3 дня")

        for day_menu in menu:
            st.markdown(f"**День {day_menu['day']}**")
            st.write(f"- Завтрак: {day_menu['breakfast']}")
            st.write(f"- Обед: {day_menu['lunch']}")
            st.write(f"- Ужин: {day_menu['dinner']}")

        st.caption(f"Меню сгенерировано: {menu_source}")

    if st.button("Сохранить список в базу"):
        items_to_save = []

        for _, row in result_df.iterrows():
            items_to_save.append({
                "product_id": int(row["product_id"]),
                "quantity": float(row["quantity"]),
                "estimated_price": float(row["estimated_price"]),
                "reason": row["reason"],
                "priority": int(row["priority"]),
            })

        saved_id = save_shopping_list(
            user_id,
            f"Список на {budget_used:.0f} ₽",
            budget_used,
            items_to_save,
        )

        st.success(
            f"Список сохранён в базу с ID {saved_id}. "
            "Смотри вкладку «Мои списки»."
        )


def show_my_lists(user_id):
    """Вкладка с сохранёнными списками покупок."""
    st.subheader("Мои списки")

    lists_df = get_shopping_lists(user_id)

    if lists_df.empty:
        st.info(
            "Сохранённых списков пока нет. "
            "Собери список во вкладке «Рекомендация» и сохрани его."
        )
        return

    st.dataframe(lists_df, width="stretch")

    list_ids = lists_df["id"].tolist()

    selected_id = st.selectbox("Выберите список", list_ids)

    items_df = get_shopping_list_items(int(selected_id))

    st.markdown("### Состав списка")

    if items_df.empty:
        st.info("Список пуст.")
    else:
        st.dataframe(items_df, width="stretch")


def main():
    st.set_page_config(
        page_title="SmartCart",
        page_icon="🛒",
        layout="wide",
    )

    st.title("🛒 SmartCart — умный список покупок")
    st.caption(
        "Прототип ИИ-помощника: бюджет + запасы дома + история покупок"
    )

    if not check_database():
        st.error("База данных smartcart.db не найдена. Запусти: python create_db.py")
        return

    users_df = get_users()

    if users_df.empty:
        st.warning("В базе нет пользователей. Запусти: python create_db.py")
        return

    st.sidebar.header("Пользователь")

    usernames = users_df["username"].tolist()
    selected_username = st.sidebar.selectbox("Выберите пользователя", usernames)

    user_row = users_df[users_df["username"] == selected_username].iloc[0]
    user_id = int(user_row["id"])

    budget_df = get_budget(user_id)
    stock_df = get_stock(user_id)
    purchases_df = get_purchase_history(user_id)

    default_budget = 3000.0

    if not budget_df.empty:
        default_budget = float(budget_df.iloc[0]["amount"])

    tabs = st.tabs(
        [
            "Обзор",
            "Продукты",
            "Запасы",
            "История",
            "Рекомендация",
            "Мои списки",
        ]
    )

    with tabs[0]:
        show_overview(selected_username, budget_df, stock_df, purchases_df)

    with tabs[1]:
        show_products()

    with tabs[2]:
        show_stock(stock_df)

    with tabs[3]:
        show_history(purchases_df)

    with tabs[4]:
        show_recommendation(user_id, stock_df, default_budget)

    with tabs[5]:
        show_my_lists(user_id)


if __name__ == "__main__":
    main()