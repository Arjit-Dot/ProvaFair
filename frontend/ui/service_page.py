"""Shared layout for the four service pages: mode selector, parameter form, run, result, verify."""
import streamlit as st
from ui import api
from ui.components import MODE_PREVIEW, empty_panel, error_panel, live_status_html, mode_badge, panel, result_inner

H = 760
MODES = {"live": "Live (falls back to recorded)", "replay": "Replay recorded run", "sim": "Simulator",
         "control": "Control (no entanglement)", "classical": "Classical (rigged)"}


def render(service: str, intro: str, form):
    """form() draws the service's parameter widgets and returns the params dict."""
    k = lambda n: f"{service}_{n}"
    ss = st.session_state
    for n in ("res", "err", "ver", "fresh"):
        ss.setdefault(k(n), None)
    st.markdown(f'<div class="pf-intro">{intro}</div>', unsafe_allow_html=True)

    with st.expander("Parameters", expanded=True):
        params = form()
    c1, c2, c3, c4 = st.columns([2.4, 1.6, 1.2, 1])
    info, _ = api.cached_get("/v3/mode")
    default = (info or {}).get("default", "sim")
    with c1:
        mode = st.radio("Source of randomness", list(MODES), index=list(MODES).index(default) if default in MODES else 0,
                        format_func=MODES.get, horizontal=True, key=k("mode"))
    with c2:
        scenario = st.text_input("Scenario label", "default", key=k("scenario"),
                                 help="Changes the seed derivation, so one recorded run can show several scenarios.")
    with c3:
        shots = st.select_slider("Shots per setting", [256, 512, 1024, 2048, 4096], 1024, key=k("shots"))
    with c4:
        st.write("")
        run = st.button("Run draw", type="primary", key=k("run"))

    prev = MODE_PREVIEW[mode]
    st.markdown(mode_badge({"text": prev["text"], "tone": prev["tone"]},
                           "selected source (the result shows the verified badge)"), unsafe_allow_html=True)
    if mode == "live":
        live, _ = api.cached_get_short("/v3/live/status")
        st.markdown(live_status_html(live), unsafe_allow_html=True)
    slot = st.empty()

    if run:
        slot.markdown(empty_panel("Running circuits, checking the Bell inequality, then the service", True, H),
                      unsafe_allow_html=True)
        data, err = api.call("POST", f"/v3/{service}/draw", json={
            "params": params, "mode": mode, "scenario": scenario or "default", "shots": int(shots)},
            timeout=180 if mode == "live" else 90)
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
