import streamlit as st
from ui import api
from ui.components import *

H = 330
st.markdown('<div class="pf-intro">500 runs of the quantum circuit against 500 runs of a classical (local hidden variable) '
            "model. Each run is a full CHSH test with 1,024 shots per setting.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("val", None); ss.setdefault("val_fresh", False); ss.setdefault("val_err", None)

a, b, _ = st.columns([1, 1, 3])
with a:
    run = st.button("Run validation", type="primary")
with b:
    rerun = st.button("Re-run from scratch")

slot = st.empty()
if run or rerun or ss.val is None and ss.val_err is None:
    slot.markdown(empty_panel("Running 1,000 CHSH tests", True, 520), unsafe_allow_html=True)
    ss.val, ss.val_err = api.call("GET", "/v2/validation", params={"runs": 500, "refresh": bool(rerun)}, timeout=300)
    ss.val_fresh = ss.val is not None

if ss.val_err:
    slot.markdown(error_panel(ss.val_err, 520), unsafe_allow_html=True)
    st.stop()

v = ss.val
q, c = v["quantum"], v["classical"]
slot.markdown(panel(
    f'<div class="pf-title fx" style="--i:0">Distribution of S: <span style="color:#7cf0ff">quantum</span> vs '
    f'<span style="color:#ff8da1">classical</span>, {v["runs"]} runs each</div>{hist_svg(q["S"], c["S"])}',
    ss.val_fresh, "", 380), unsafe_allow_html=True)

l, r = st.columns(2)
with l:
    st.markdown(panel(f'<div class="pf-title fx" style="--i:0">Quantum mode</div>{stat_cards(q, "quantum", "q")}'
                      f'<div class="pf-note fx" style="--i:5;margin-top:.8rem">Every run lands near the 2.83 maximum.</div>',
                      ss.val_fresh, "ok", 230), unsafe_allow_html=True)
with r:
    st.markdown(panel(f'<div class="pf-title fx" style="--i:0">Classical mode</div>{stat_cards(c, "classical", "c")}'
                      f'<div class="pf-note fx" style="--i:5;margin-top:.8rem">Centred on 2.0. {c["naive_above_2"]} runs scored above 2 '
                      f'by chance, which is why the 3\u03c3 margin is required.</div>', ss.val_fresh, "bad", 230),
                unsafe_allow_html=True)
ss.val_fresh = False
