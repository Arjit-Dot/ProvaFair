import streamlit as st
from ui.service_page import render


def form():
    a, b, c, d = st.columns(4)
    return {"length_bits": int(a.selectbox("Length (bits)", [128, 192, 256, 384, 512], 2, key="ky_l")),
            "count": int(b.number_input("Count", 1, 64, 4, key="ky_c")),
            "format": c.selectbox("Format", ["hex", "base64"], key="ky_f"),
            "purpose": d.text_input("Purpose label", "api-token", key="ky_p")}


render("keys", "Keys, API tokens and nonces derived from a certified seed mixed with local OS randomness, so no single "
               "party is trusted (the cloud provider sees the raw hardware bits). Keys are shown once and never stored. "
               "Demo keys only; this does not replace a hardware security module.", form)
