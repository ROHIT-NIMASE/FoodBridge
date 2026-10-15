"""Impact dashboard: resale and donation statistics."""
import pandas as pd
import streamlit as st

from utils import helpers as h

# Rough conversion factors used only for the headline "estimated" figures.
MEALS_PER_KG = 2.5
CO2E_KG_PER_KG_FOOD = 2.5


def _panel(stats, who):
    saved = stats["resold_kg"] + stats["donated_kg"]
    h.metric_row([("Food rescued", f"{h.qty(saved)} kg"),
                  ("Resold", f"{h.qty(stats['resold_kg'])} kg"),
                  ("Donated", f"{h.qty(stats['donated_kg'])} kg"),
                  ("Sales value", h.money(stats["revenue"]))])
    h.metric_row([("Completed orders", stats["orders_completed"]),
                  ("Completed donations", stats["donations_completed"]),
                  ("Est. meals", f"{saved * MEALS_PER_KG:,.0f}"),
                  ("Est. CO₂e avoided", f"{saved * CO2E_KG_PER_KG_FOOD:,.0f} kg")])
    if stats["timeline"]:
        df = pd.DataFrame(stats["timeline"]).rename(columns={"resold_kg": "Resold (kg)", "donated_kg": "Donated (kg)"})
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d %b")
        st.subheader("Food rescued over time")
        st.bar_chart(df.set_index("date"), color=["#1f6f4a", "#d97706"])
    else:
        st.info(f"No completed orders or collected donations yet for {who}. Statistics appear once a "
                "sale is marked completed or a donation is collected.")


def render():
    user = h.current_user()
    st.title("Impact")
    h.show_flashes()
    be = h.backend()
    tab_all, tab_me = st.tabs(["Across FoodBridge", "Your impact"])
    with tab_all:
        _panel(be.impact_stats(), "the platform")
    with tab_me:
        _panel(be.impact_stats(user["id"]), "you")
    st.caption(f"Only items measured in kg or L are counted. Meals (≈{MEALS_PER_KG} per kg) and CO₂e "
               f"(≈{CO2E_KG_PER_KG_FOOD} kg per kg of food) are rough estimates.")
