import streamlit as st
from ui.service_page import render


def form():
    game = st.radio("Game", ["numbers", "tickets"], horizontal=True, key="lt_game",
                    format_func=lambda g: "k-of-N numbers" if g == "numbers" else "Prize draw among tickets")
    a, b, c = st.columns(3)
    if game == "numbers":
        return {"game": "numbers", "pool": int(a.number_input("Pool (N)", 2, 100000, 49, key="lt_n")),
                "picks": int(b.number_input("Picks (k)", 1, 1000, 6, key="lt_k")),
                "bonus": bool(c.checkbox("Bonus ball", key="lt_b"))}
    return {"game": "tickets", "n_tickets": int(a.number_input("Tickets sold", 1, 100000, 10000, key="lt_t")),
            "tiers": [{"name": "Grand prize", "winners": 1},
                      {"name": "Second prize", "winners": int(b.number_input("Second-prize winners", 1, 1000, 4, key="lt_w"))}]}


render("lottery", "k-of-N number draws and winner selection among sold tickets, sampled without replacement using "
                  "unbiased integers. It fixes the generator, not ticket fraud or how winners are paid.", form)
