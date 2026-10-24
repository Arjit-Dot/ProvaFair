import streamlit as st
from ui import api
from ui.components import checks_html, empty_panel, error_panel, mode_badge, panel

H = 520
st.markdown('<div class="pf-intro">Pick any recorded run and recompute everything from its saved files: the parameter '
            "commitment, the CHSH certificate, the seed, the service output and the ledger chain. Each check is "
            "reported separately.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("vr", None); ss.setdefault("vr_err", None); ss.setdefault("vr_fresh", False)

a, b, c, d = st.columns([1.2, 2.2, 2.2, 1])
with a:
    service = st.selectbox("Service", ["ipo", "web3", "lottery", "keys"], key="vr_service")
runs, _ = api.call("GET", f"/v3/{service}/runs", params={"limit": 30})
recent = [r["run_id"] for r in (runs["runs"] if runs else [])]
with b:
    typed = st.text_input("Run ID", placeholder="IPO-20261024-...", key="vr_typed")
with c:
    pick = st.selectbox("Or pick a recent run", [""] + recent, key="vr_pick")
with d:
    st.write(""); st.write("")
    go = st.button("Verify run", type="primary")

slot = st.empty()
if go:
    rid = (typed or pick).strip()
    if not rid:
        ss.vr, ss.vr_err = None, "Enter or pick a run ID first."
    else:
        slot.markdown(empty_panel("Recomputing from saved files", True, H), unsafe_allow_html=True)
        ss.vr, ss.vr_err = api.call("POST", f"/v3/verify/{service}/{rid}")
        ss.vr_fresh = ss.vr is not None
if ss.vr_err:
    slot.markdown(error_panel(ss.vr_err, H), unsafe_allow_html=True)
elif ss.vr:
    v = ss.vr
    slot.markdown(panel(mode_badge(v["badge"]) + f'<div class="pf-kv">Run <b>{v["run_id"]}</b></div>' + checks_html(v),
                        ss.vr_fresh, "ok" if v["all_ok"] else "bad", H), unsafe_allow_html=True)
    ss.vr_fresh = False
else:
    slot.markdown(empty_panel("Choose a run to verify.", False, H), unsafe_allow_html=True)
