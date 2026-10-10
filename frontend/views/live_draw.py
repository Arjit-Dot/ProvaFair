import streamlit as st
from ui import api
from ui.components import *

H_TOP, H_MID = 360, 470

st.markdown('<div class="pf-intro">Pick a use case, run a draw, and see the evidence: the CHSH score, how it was computed, '
            "and the circuit that produced it. If the score is too low the draw is blocked and no numbers appear.</div>",
            unsafe_allow_html=True)

UC, err = api.cached_get("/v2/usecases")
if err:
    st.markdown(error_panel(err, 200), unsafe_allow_html=True)
    st.stop()

ss = st.session_state
for k, v in {"ld_uc": "lottery", "ld_pool": UC["lottery"]["default_pool"], "ld_win": UC["lottery"]["default_winners"],
             "ld_result": None, "ld_fresh": False, "ld_error": None}.items():
    ss.setdefault(k, v)


def on_uc():
    ss.ld_pool = UC[ss.ld_uc]["default_pool"]
    ss.ld_win = UC[ss.ld_uc]["default_winners"]


c1, c2, c3, c4, c5 = st.columns([1.5, 1.3, 1, 1, 1])
with c1:
    st.selectbox("Use case", list(UC), format_func=lambda k: UC[k]["label"], key="ld_uc", on_change=on_uc)
with c2:
    mode_label = st.radio("Engine", ["Quantum", "Classical (seeded)"], key="ld_mode", horizontal=True)
with c3:
    st.number_input(f"Pool ({UC[ss.ld_uc]['noun']}s)", min_value=1, max_value=1_000_000, step=1, key="ld_pool")
with c4:
    st.number_input("Winners", min_value=1, max_value=50, step=1, key="ld_win")
with c5:
    st.write("")
    run = st.button("Run draw", type="primary")

verdict_slot = st.empty()
col_l, col_r = st.columns(2)
with col_l:
    win_slot = st.empty()
with col_r:
    corr_slot = st.empty()
circ_slot = st.empty()


def render(d, fresh):
    ch = d["chsh"]
    verdict_slot.markdown(panel(verdict_block(ch, d["certified"]), fresh, "ok" if d["certified"] else "bad", H_TOP),
                          unsafe_allow_html=True)
    if d["certified"]:
        body = (f'<div class="pf-title fx" style="--i:0">Selected {e(UC[d["use_case"]]["noun"])}s</div>'
                f'{chips(d["winners"], start=1)}')
    else:
        body = ('<div class="pf-lock fx" style="--i:0"><b>No numbers released</b>The physics check failed. A classical '
                "source cannot be trusted, so this draw produced no output.</div>")
    n = len(d["winners"] or [])
    body += (f'<div class="pf-kv fx" style="--i:{n + 1}">Draw ID <b>{e(d["draw_id"])}</b></div>'
             f'<div class="pf-title fx" style="--i:{n + 2};margin-top:.8rem">Ledger hash</div>'
             f'<div class="pf-hash fx" style="--i:{n + 3}">{e(d["hash"])}</div>'
             f'<div class="pf-title fx" style="--i:{n + 4}">Previous hash</div>'
             f'<div class="pf-hash fx" style="--i:{n + 5}">{e(d["prev_hash"])}</div>')
    win_slot.markdown(panel(body, fresh, "ok" if d["certified"] else "bad", H_MID), unsafe_allow_html=True)
    corr_slot.markdown(panel(correlation_inner(ch), fresh, "", H_MID), unsafe_allow_html=True)


if run:
    verdict_slot.markdown(empty_panel("Executing circuits and checking the Bell inequality", True, H_TOP), unsafe_allow_html=True)
    win_slot.markdown(empty_panel("Waiting for the physics check", False, H_MID), unsafe_allow_html=True)
    corr_slot.markdown(empty_panel("Waiting for the physics check", False, H_MID), unsafe_allow_html=True)
    data, err = api.call("POST", "/v2/draw", json={
        "mode": "quantum" if mode_label == "Quantum" else "classical", "use_case": ss.ld_uc,
        "pool_size": int(ss.ld_pool), "num_winners": int(ss.ld_win)})
    ss.ld_result, ss.ld_error, ss.ld_fresh = data, err, data is not None

if ss.ld_error:
    verdict_slot.markdown(error_panel(ss.ld_error, H_TOP), unsafe_allow_html=True)
    win_slot.markdown(empty_panel("No result", False, H_MID), unsafe_allow_html=True)
    corr_slot.markdown(empty_panel("No result", False, H_MID), unsafe_allow_html=True)
elif ss.ld_result:
    render(ss.ld_result, ss.ld_fresh)
    ss.ld_fresh = False
else:
    verdict_slot.markdown(empty_panel("Run a draw to see the live CHSH gauge.", False, H_TOP), unsafe_allow_html=True)
    win_slot.markdown(empty_panel("Selections appear here once the draw is certified.", False, H_MID), unsafe_allow_html=True)
    corr_slot.markdown(empty_panel("The four correlation terms appear here.", False, H_MID), unsafe_allow_html=True)

info, cerr = api.cached_get("/v2/circuit")
circ_slot.markdown(panel(circuit_inner(info), False, "", 330) if info else error_panel(cerr, 200), unsafe_allow_html=True)
