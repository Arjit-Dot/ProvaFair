import streamlit as st
from ui.service_page import render


def form():
    a, b, c = st.columns(3)
    return {"n_validators": int(a.number_input("Validators", 1, 5000, 20, key="w3_n")),
            "seats": int(b.number_input("Seats", 1, 5000, 5, key="w3_s")),
            "epoch_id": int(c.number_input("Epoch ID", 0, 10**9, 1, key="w3_e"))}


render("web3", "Stake-weighted validator selection without replacement, plus a 32-byte randomness beacon. Stakes are "
               "uneven, so heavier validators are more likely to be picked, and nobody can bias the draw after seeing "
               "the seed. The beacon can be anchored on a testnet to fix the record publicly.", form)
