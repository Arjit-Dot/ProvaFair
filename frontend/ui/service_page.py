"""Shared layout for the four service pages: mode selector, parameter form, run, result, verify."""
import streamlit as st
from ui import api
from ui.components import empty_panel, error_panel, panel, result_inner

H = 760
# the one demo action: "Run Live" fetches the saved IBM hardware job from IBM by its
# job ID, and falls back to the saved copy of the same job when IBM is busy or unreachable (shown in the badge).


def render(service: str, intro: str, form):
    """form() draws the service's parameter widgets and returns the params dict."""
    k = lambda n: f"{service}_{n}"
    ss = st.session_state
    for n in ("res", "err", "ver", "fresh"):
        ss.setdefault(k(n), None)
    st.markdown(f'<div class="pf-intro">{intro}</div>', unsafe_allow_html=True)

    with st.expander("Parameters", expanded=True):
        params = form()
    mode = "retrieve" if st.button("Run Live", type="primary", use_container_width=True, key=k("retrieve")) else None
    run = mode is not None
    slot = st.empty()

    if run:
        slot.markdown(empty_panel("Running circuits, checking the Bell inequality, then the service", True, H),
                      unsafe_allow_html=True)
        data, err = api.call("POST", f"/v3/{service}/draw", json={
            "params": params, "mode": mode, "scenario": "default", "shots": 1024},
            timeout=90)
        ss[k("res")], ss[k("err")], ss[k("ver")], ss[k("fresh")] = data, err, None, data is not None

    if ss[k("err")]:
        slot.markdown(error_panel(ss[k("err")], H), unsafe_allow_html=True)
    elif ss[k("res")]:
        r = ss[k("res")]
        slot.markdown(panel(result_inner(service, r, ss[k("ver")]), ss[k("fresh")],
                            "ok" if r["certificate"]["certified"] else "bad", H), unsafe_allow_html=True)
        ss[k("fresh")] = False
        if st.button("Verify this run (recompute all 5 checks)", key=k("verify")):
            v, verr = api.call("POST", f"/v3/verify/{service}/{r['receipt']['run_id']}")
            ss[k("ver")], ss[k("fresh")] = v, v is not None
            if verr:
                st.error(verr)
            st.rerun()
    else:
        slot.markdown(empty_panel("Set parameters, choose a source and run a draw.", False, H), unsafe_allow_html=True)
