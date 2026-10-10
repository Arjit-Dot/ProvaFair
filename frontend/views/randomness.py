import streamlit as st
from ui import api
from ui.components import *

H = 430
st.markdown('<div class="pf-intro">A second line of evidence, independent of CHSH: three standard checks on the raw output bits. '
            "The quantum stream should pass all three. The seeded, slightly biased classical server should fail.</div>",
            unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("rn", None); ss.setdefault("rn_err", None); ss.setdefault("rn_fresh", False)

run = st.button("Run both engines", type="primary")
l, r = st.columns(2)
with l:
    ls = st.empty()
with r:
    rs = st.empty()

if run:
    ls.markdown(empty_panel("Generating quantum bits", True, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("Generating classical bits", True, H), unsafe_allow_html=True)
    out = {}
    for m in ("quantum", "classical"):
        out[m], ss.rn_err = api.call("POST", "/v2/draw", json={"mode": m, "pool_size": 100, "num_winners": 4, "record": False})
        if ss.rn_err: break
    ss.rn = out if not ss.rn_err else None
    ss.rn_fresh = ss.rn is not None

if ss.rn_err:
    ls.markdown(error_panel(ss.rn_err, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("No result", False, H), unsafe_allow_html=True)
elif ss.rn:
    for slot, m, title in ((ls, "quantum", "Quantum engine"), (rs, "classical", "Classical seeded PRNG")):
        rr = ss.rn[m]["randomness"]
        fails = sum(not t["passed"] for t in rr["tests"])
        head = (f'<div class="pf-verdict {"ok" if rr["all_passed"] else "bad"}"><b>{"3 of 3 passed" if rr["all_passed"] else f"{fails} of 3 failed"}</b></div>')
        bits = f'<div class="pf-hash fx" style="--i:6">{e(ss.rn[m]["bits_preview"])}</div><div class="pf-note fx" style="--i:7">First 96 raw bits</div>'
        slot.markdown(panel(head + tests_inner(rr, title) + bits, ss.rn_fresh, "ok" if rr["all_passed"] else "bad", H + 90),
                      unsafe_allow_html=True)
    ss.rn_fresh = False
else:
    ls.markdown(empty_panel("Press Run both engines.", False, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("Press Run both engines.", False, H), unsafe_allow_html=True)
