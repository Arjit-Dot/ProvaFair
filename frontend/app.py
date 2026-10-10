"""Run with:  streamlit run app.py   (needs Streamlit 1.46+ for top navigation)"""
import streamlit as st
from ui import theme

st.set_page_config(page_title="ProvaFair | Verifiable Draws", layout="wide")
theme.setup()

pages = [
    st.Page("views/live_draw.py", title="Live draw", default=True),
    st.Page("views/validation.py", title="Validation"),
    st.Page("views/verify.py", title="Verify a draw"),
    st.Page("views/ledger.py", title="Ledger"),
    st.Page("views/randomness.py", title="Randomness tests"),
    st.Page("views/insider_attack.py", title="Insider attack"),
]
st.navigation(pages, position="top").run()
