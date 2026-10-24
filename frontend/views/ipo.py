import streamlit as st
from ui.service_page import render


def form():
    a, b, c, d, e = st.columns(5)
    return {"total_shares": int(a.number_input("Shares offered", 1000, 10**9, 1_000_000, 1000, key="ipo_ts")),
            "retail_pct": float(b.number_input("Retail %", 1.0, 100.0, 35.0, 1.0, key="ipo_rp")),
            "lot_size": int(c.number_input("Lot size", 1, 100000, 100, 10, key="ipo_ls")),
            "price": float(d.number_input("Price", 0.01, 1e6, 100.0, key="ipo_pr")),
            "n_applicants": int(e.number_input("Applicants", 1, 100000, 5000, 100, key="ipo_na"))}


render("ipo", "Fair, reproducible allotment when an offer is oversubscribed. If applicants outnumber the retail lots, "
              "IDs are shuffled with a certified seed and the first ones win; the full order is published as the "
              "waiting list. Simplified model: one lot each, no duplicate or eligibility checks.", form)
