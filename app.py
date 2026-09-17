import os
import streamlit as st
import matplotlib.pyplot as plt

from db_service import (
    get_users, get_budget, get_stock, get_purchase_history,
    get_purchase_items, get_shopping_lists, get_shopping_list_items, save_shopping_list,
)
from predictor import predict_finished_products
from recommender import build_shopping_list, SCENARIOS
from menu import generate_menu

DB_NAME = "smartcart.db"

def check_database():
    return os.path.exists(DB_NAME)

def show_nutrition_chart(protein, fat, carbs):
    total = protein + fat + carbs
    if total <= 0: return
    labels = ['Белки', 'Жиры', 'Углеводы']
    sizes = [protein, fat, carbs]
    colors = ['#ff6b6b', '#ffd93d', '#6bcB77']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%', startangle=90, textprops={'fontsize': 11})
    ax.set_title('Соотношение Б/Ж/У в корзине', fontsize=12)
    st.pyplot(fig)

def show_overview(user_name, budget_df, stock_df, purchases_df):
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
    if budget_df.empty: st.info("Бюджет не найден.")
    else: st.dataframe(budget_df, width="stretch")
    st.markdown("### Запасы дома")
    if stock_df.empty: st.info("Запасов пока нет.")
    else: st.dataframe(stock_df, width="stretch")

def show_products():
    st.subheader("Каталог продуктов")
    from db_service import get_products
    products_df = get_products()
    search = st.text_input("Поиск по названию или категории", "")
    view_df = products_df
    if search:
        mask = (products_df["name"].str.lower().str.contains(search.lower(), na=False) | 
                products_df["category"].str.lower().str.contains(search.lower(), na=False))
        view_df = products_df[mask]
    if view_df.empty: st.info("Ничего не найдено.")
    else: st.dataframe(view_df, width="stretch")

def show_stock(stock_df):
    st.subheader("Что уже есть дома")
    if stock_df.empty: st.info("Запасов пока нет.")
    else: st.dataframe(stock_df, width="stretch")

def show_history(purchases_df):
    st.subheader("История покупок")
    if purchases_df.empty: st.info("Покупок пока нет."); return
    st.dataframe(purchases_df, width="stretch")
    selected_id = st.selectbox("Выберите покупку", purchases_df["id"].tolist())
    items_df = get_purchase_items(int(selected_id))
    st.markdown("### Состав покупки")
    if items_df.empty: st.info("В этой покупке нет товаров.")
    else: st.dataframe(items_df, width="stretch")

def show_recommendation(user_id, stock_df, default_budget):
    st.subheader("Рекомендация списка покупок")
    st.write("Алгоритм учитывает бюджет, запасы дома и историю покупок.")
    
    finished = predict_finished_products(user_id)
    if finished: st.info("По статистике могло закончиться: " + ", ".join(finished))

    budget_input = st.number_input("Бюджет на список", min_value=0.0, value=float(default_budget), step=100.0)
    use_llm = st.checkbox("Составить меню на 3 дня")

    st.markdown("### Стратегия питания")
    scenario_options = {key: cfg["label"] for key, cfg in SCENARIOS.items()}
    selected_label = st.radio("Выберите сценарий", list(scenario_options.values()), index=0, horizontal=True)
    scenario_key = next((k for k, v in SCENARIOS.items() if v["label"] == selected_label), "balanced")

    if st.button("Собрать список"):
        result_df, total_price, nutrition = build_shopping_list(user_id, budget_input, scenario_key)
        st.session_state.update({
            "rec_user_id": user_id, "rec_budget": float(budget_input), "rec_scenario": scenario_key,
            "rec_result": result_df, "rec_total": total_price, "rec_nutrition": nutrition
        })

        if result_df.empty:
            st.warning("Не удалось собрать список.")
            st.session_state["rec_menu"] = None
        else:
            # Генерируем меню всегда локально для скорости и надёжности
            menu, menu_source = generate_menu(result_df, stock_df, use_llm, None, None)
            st.session_state["rec_menu"] = menu
            st.session_state["rec_menu_source"] = menu_source

    if st.session_state.get("rec_user_id") != user_id: return
    result_df = st.session_state.get("rec_result")
    if result_df is None or result_df.empty: return

    total_price = st.session_state.get("rec_total", 0.0)
    nutrition = st.session_state.get("rec_nutrition", {})
    budget_used = st.session_state.get("rec_budget", 0.0)

    st.markdown("### Результат")
    ratio = min(total_price / budget_used if budget_used > 0 else 0.0, 1.0)
    st.progress(ratio, text=f"Использовано бюджета: {total_price:.0f} / {budget_used:.0f} ₽")

    col1, col2 = st.columns(2)
    col1.metric("Итоговая цена", f"{total_price:.2f} ₽")
    col2.metric("Бюджет", f"{budget_used:.2f} ₽", f"остаток {budget_used - total_price:.2f} ₽")

    st.markdown("### Питание корзины")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Калории", f"{nutrition.get('total_calories', 0):.0f}")
        c2.metric("Белки", f"{nutrition.get('total_protein', 0):.1f} г")
        c3.metric("Жиры", f"{nutrition.get('total_fat', 0):.1f} г")
        c4.metric("Углеводы", f"{nutrition.get('total_carbs', 0):.1f} г")
    with col_b:
        show_nutrition_chart(nutrition.get('total_protein', 0), nutrition.get('total_fat', 0), nutrition.get('total_carbs', 0))

    display_df = result_df[["name", "category", "quantity", "unit", "total", "reason"]].copy()
    display_df.columns = ["Продукт", "Категория", "Кол-во", "Ед.", "Сумма", "Почему"]
    display_df["Кол-во"] = display_df["Кол-во"].astype(int)
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

        if menu_source == "Встроенный алгоритм":
            st.success("✅ Меню сгенерировано встроенным алгоритмом")
        else:
            st.caption("Меню составлено по правилам")

    if st.button("Сохранить список в базу"):
        items_to_save = [{
            "product_id": int(row["product_id"]), "quantity": float(row["quantity"]),
            "estimated_price": float(row["estimated_price"]), "reason": row["reason"], "priority": int(row["priority"])
        } for _, row in result_df.iterrows()]
        
        saved_id = save_shopping_list(user_id, f"Список на {budget_used:.0f} ₽", budget_used, items_to_save)
        st.success(f"Список сохранён в базу с ID {saved_id}.")

def show_my_lists(user_id):
    st.subheader("Мои списки")
    lists_df = get_shopping_lists(user_id)
    if lists_df.empty: st.info("Сохранённых списков пока нет."); return
    st.dataframe(lists_df, width="stretch")
    selected_id = st.selectbox("Выберите список", lists_df["id"].tolist())
    items_df = get_shopping_list_items(int(selected_id))
    st.markdown("### Состав списка")
    if items_df.empty: st.info("Список пуст.")
    else: st.dataframe(items_df, width="stretch")

def main():
    st.set_page_config(page_title="SmartCart", page_icon="🛒", layout="wide")
    st.title("🛒 SmartCart — умный список покупок")
    st.caption("Прототип ИИ-помощника: бюджет + запасы дома + история покупок")

    if not check_database():
        with st.spinner("Создаю базу данных..."):
            from db_setup import create_database
            create_database()

    users_df = get_users()
    if users_df.empty: st.warning("В базе нет пользователей."); return

    st.sidebar.header("Пользователь")
    selected_username = st.sidebar.selectbox("Выберите пользователя", users_df["username"].tolist())
    user_id = int(users_df[users_df["username"] == selected_username].iloc[0]["id"])

    budget_df = get_budget(user_id)
    stock_df = get_stock(user_id)
    purchases_df = get_purchase_history(user_id)
    default_budget = float(budget_df.iloc[0]["amount"]) if not budget_df.empty else 3000.0

    tabs = st.tabs(["Обзор", "Продукты", "Запасы", "История", "Рекомендация", "Мои списки"])
    with tabs[0]: show_overview(selected_username, budget_df, stock_df, purchases_df)
    with tabs[1]: show_products()
    with tabs[2]: show_stock(stock_df)
    with tabs[3]: show_history(purchases_df)
    with tabs[4]: show_recommendation(user_id, stock_df, default_budget)
    with tabs[5]: show_my_lists(user_id)

if __name__ == "__main__":
    main()
