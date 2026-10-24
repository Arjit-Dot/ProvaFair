"""Run with:  streamlit run app.py   (needs Streamlit 1.46+ for top navigation)"""
import streamlit as st
from ui import theme

st.set_page_config(page_title="ProvaFair | Verifiable Draws", layout="wide")
theme.setup()

services = [
    st.Page("views/ipo.py", title="IPO", url_path="ipo", default=True),
    st.Page("views/web3.py", title="Web3", url_path="web3"),
    st.Page("views/lottery.py", title="Lottery", url_path="lottery"),
    st.Page("views/keys.py", title="Keys", url_path="keys"),
]
evidence = [
    st.Page("views/verify_run.py", title="Verify a run", url_path="verify-run"),
    st.Page("views/ledger.py", title="Ledger"),
]
demo = [
    st.Page("views/live_draw.py", title="CHSH evidence", url_path="chsh"),
    st.Page("views/validation.py", title="Validation"),
    st.Page("views/verify.py", title="Verify a draw"),
    st.Page("views/insider_attack.py", title="Insider attack"),
]
sections = {"Services": services, "Evidence": evidence}
if st.sidebar.toggle("Demo pages", value=False, key="demo_show",
                     help="Show the demonstration pages: CHSH evidence, validation, verify a draw, insider attack."):
    sections["Demo"] = demo
st.navigation(sections, position="top").run()
