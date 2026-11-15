import random
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Payment Gateway Simulator", page_icon="💳", layout="wide"
)

st.title("💳 Симулятор платежного шлюза и смарт-роутинга")
st.markdown(
    "Моделирование потока: разделение на СБП и Карты + эквайринговый роутинг."
)

# Sidebar parameters
st.sidebar.header("⚙️ 1. Распределение методов оплаты (UX)")
share_sbp = st.sidebar.slider(
    "Доля СБП в общем потоке (%)", 0, 100, 50, 5, key="sbp_share"
)
share_cards = 100 - share_sbp
st.sidebar.info(
    f"💳 Доля оплат картами: **{share_cards}%** (распределяется между шлюзами"
    " ниже)"
)

st.sidebar.header("⚙️ 2. Настройки эквайеров")

# Gateway A
st.sidebar.subheader("Шлюз А (Премиум-банк / Карты)")
fee_a = st.sidebar.slider("Комиссия А (%)", 1.0, 4.0, 2.2, 0.1)
timeout_a = st.sidebar.slider("Риск таймаута А (%)", 0.0, 10.0, 1.0, 0.5)
decline_a = st.sidebar.slider("Риск реджекта А (%)", 0.0, 15.0, 3.0, 0.5)

# Gateway B
st.sidebar.subheader("Шлюз Б (Альтернативный / Карты)")
fee_b = st.sidebar.slider("Комиссия Б (%)", 0.5, 3.0, 1.5, 0.1)
timeout_b = st.sidebar.slider("Риск таймаута Б (%)", 0.0, 20.0, 6.0, 0.5)
decline_b = st.sidebar.slider("Риск реджекта Б (%)", 0.0, 25.0, 8.0, 0.5)

# SBP
st.sidebar.subheader("СБП (Система быстрых платежей)")
fee_sbp = st.sidebar.slider("Комиссия СБП (%)", 0.2, 1.5, 0.7, 0.1)
timeout_sbp = st.sidebar.slider("Риск таймаута СБП (%)", 0.0, 15.0, 3.0, 0.5)
decline_sbp = st.sidebar.slider("Риск реджекта СБП (%)", 0.0, 20.0, 4.0, 0.5)

st.sidebar.header("📊 3. Параметры симуляции")
n_tx = st.sidebar.number_input(
    "Количество транзакций в тесте", 100, 10000, 1000, 100
)
avg_amount = st.sidebar.number_input(
    "Средняя сумма платежа (руб)", 500, 100000, 3500, 500
)

use_smart_routing_for_cards = st.sidebar.checkbox(
    "Smart Routing для карт (всегда в самый дешевый карточный шлюз + Fallback)",
    True,
)

if not use_smart_routing_for_cards:
  st.sidebar.subheader("🎯 Сплит карточного трафика")
  card_share_a = st.sidebar.slider(
      "Доля Шлюза А среди карт (%)", 0, 100, 70, 5
  )
  card_share_b = 100 - card_share_a
else:
  card_share_a, card_share_b = 100, 0


def simulate_single_tx(amount, gw_name, fee, timeout_p, decline_p):
  rand_val = random.random() * 100
  if rand_val < timeout_p:
    return "TIMEOUT", gw_name, 0
  elif rand_val < timeout_p + decline_p:
    return "DECLINED", gw_name, 0
  else:
    fee_amount = amount * (fee / 100.0)
    return "SUCCESS", gw_name, fee_amount


# Run button
if st.button("🚀 Запустить симуляцию потока", type="primary"):
  gateways = {
      "Шлюз А (Карты)": {"fee": fee_a, "timeout": timeout_a, "decline": decline_a},
      "Шлюз Б (Карты)": {"fee": fee_b, "timeout": timeout_b, "decline": decline_b},
      "СБП": {"fee": fee_sbp, "timeout": timeout_sbp, "decline": decline_sbp},
  }

  card_gws = ["Шлюз А (Карты)", "Шлюз Б (Карты)"]
  sorted_card_gws = sorted(
      card_gws, key=lambda x: gateways[x]["fee"]
  ) # Самый дешевый карточный шлюз

  results = []

  for i in range(n_tx):
    amount = max(100, round(np.random.normal(avg_amount, avg_amount * 0.3), 2))

    # Шаг 1: Пользователь выбирает метод оплаты (СБП или Карты)
    payment_method = random.choices(
        ["СБП", "Карта"], weights=[share_sbp, share_cards], k=1
    )[0]

    if payment_method == "СБП":
      chosen_gw = "СБП"
    else:
      # Шаг 2: Выбираем эквайрера для карты
      if use_smart_routing_for_cards:
        chosen_gw = sorted_card_gws[0] # Направляем в более дешевый шлюз
      else:
        chosen_gw = random.choices(
            card_gws, weights=[card_share_a, card_share_b], k=1
        )[0]

    gw_config = gateways[chosen_gw]

    status, gw_used, fee_paid = simulate_single_tx(
        amount,
        chosen_gw,
        gw_config["fee"],
        gw_config["timeout"],
        gw_config["decline"],
    )

    # Шаг 3: Каскадный ретрив (Fallback) при таймауте
    if status == "TIMEOUT":
      if payment_method == "СБП":
        # Если СБП упала по таймауту, можем перебросить на дешевый карточный шлюз как фоллбек
        fallback_gw = sorted_card_gws[0]
        fb_config = gateways[fallback_gw]
        status, gw_used, fee_paid = simulate_single_tx(
            amount,
            fallback_gw + " (SBP Fallback)",
            fb_config["fee"],
            fb_config["timeout"],
            fb_config["decline"],
        )
      else:
        # Если упал один карточный шлюз, ретривим на второй карточный шлюз
        remaining_gws = [g for g in card_gws if g != chosen_gw]
        if remaining_gws:
          fallback_gw = remaining_gws[0]
          fb_config = gateways[fallback_gw]
          status, gw_used, fee_paid = simulate_single_tx(
              amount,
              fallback_gw + " (Card Fallback)",
              fb_config["fee"],
              fb_config["timeout"],
              fb_config["decline"],
          )

    results.append(
        {
            "tx_id": i + 1,
            "amount": amount,
            "method": payment_method,
            "gateway": gw_used,
            "status": status,
            "fee_paid": fee_paid,
        }
    )

  df = pd.DataFrame(results)

  # Метрики
  total_vol = df["amount"].sum()
  success_df = df[df["status"] == "SUCCESS"]
  success_vol = success_df["amount"].sum()
  success_rate = (len(success_df) / len(df)) * 100
  total_fees = success_df["fee_paid"].sum()
  effective_fee_rate = (
      (total_fees / success_vol) * 100 if success_vol > 0 else 0
  )

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Успешный оборот (GMV)", f"{success_vol:,.0f} ₽")
  col2.metric("Конверсия (Success Rate)", f"{success_rate:.1f}%")
  col3.metric("Расходы на эквайринг", f"{total_fees:,.2f} ₽")
  col4.metric("Эффективная ставка комиссий", f"{effective_fee_rate:.2f}%")

  st.markdown("---")

  col_a, col_b = st.columns(2)

  with col_a:
    st.subheader("Статусы транзакций")
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig_status = px.pie(
        status_counts,
        values="count",
        names="status",
        title="Общие исходы транзакций",
        hole=0.4,
    )
    st.plotly_chart(fig_status, use_container_width=True)

  with col_b:
    st.subheader("Нагрузка по шлюзам / методам")
    gw_counts = df["gateway"].value_counts().reset_index()
    gw_counts.columns = ["gateway", "count"]
    fig_gw = px.bar(
        gw_counts,
        x="gateway",
        y="count",
        title="Куда реально ушел трафик с учетом Fallback",
        color="gateway",
    )
    st.plotly_chart(fig_gw, use_container_width=True)

  st.subheader("Срез последних операций")
  st.dataframe(df.head(25), use_container_width=True)

else:
  st.info(
      "👈 Настройте долю СБП и карт в левой панели и нажмите **«Запустить"
      " симуляцию потока»**."
  )

