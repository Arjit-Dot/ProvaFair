import streamlit as st
from ui import api
from ui.components import *

H = 560
st.markdown('<div class="pf-intro">Enter a draw ID to re-check it: the stored score and margin, the shots used, the hash '
            "link to the previous draw, and whether the whole chain is intact.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("vf", None); ss.setdefault("vf_err", None); ss.setdefault("vf_fresh", False)

led, _ = api.call("GET", "/v2/ledger", params={"limit": 20})
recent = [x["draw_id"] for x in reversed(led["entries"])] if led else []
a, b, c = st.columns([2, 2, 1])
with a:
    typed = st.text_input("Draw ID", placeholder="DRAW-Q-...")
with b:
    pick = st.selectbox("Or pick a recent draw", [""] + recent)
with c:
    st.write(""); st.write("")
    go = st.button("Verify draw", type="primary")

slot = st.empty()
if go:
    did = (typed or pick).strip()
    if not did:
        ss.vf, ss.vf_err = None, "Enter or pick a draw ID first."
    else:
        slot.markdown(empty_panel("Recomputing hashes and checking the chain", True, H), unsafe_allow_html=True)
        ss.vf, ss.vf_err = api.call("GET", f"/v2/draw/{did}")
        ss.vf_fresh = ss.vf is not None

if ss.vf_err:
    slot.markdown(error_panel(ss.vf_err, H), unsafe_allow_html=True)
elif ss.vf:
    d = ss.vf
    ok_all = d["hash_ok"] and d["link_ok"] and d["chain_intact"]
    cert = d["rule_recheck"] == "PASS"
    def row(label, good, text):
        return f'<span class="pill {"ok" if good else "bad"}">{e(text)}</span> {e(label)}'
    win = chips(d["winners"], start=3) if d["winners"] else '<div class="pf-note fx" style="--i:3">No numbers were released (draw blocked).</div>'
    body = f"""
    <div class="pf-verdict {'ok' if ok_all else 'bad'} fx" style="--i:0"><b>{'RECORD AUTHENTIC' if ok_all else 'RECORD FAILS CHECKS'}</b>
    <span>{e(d['draw_id'])} | {e(d['event_name'])} | {e(d['timestamp'])}</span></div>
    <div class="fx" style="--i:1">{gauge_svg(d['chsh_score'], d['margin'], cert)}</div>
    <div class="pf-kv fx" style="--i:2">Status <b>{e(d['status'])}</b> | S <b>{d['chsh_score']} \u00b1 {d['margin']}</b> | shots <b>{d['shots']}</b> | rule re-check <b>{d['rule_recheck']}</b></div>
    {win}
    <div class="pf-kv fx" style="--i:5">{row('Own hash recomputes to the stored value', d['hash_ok'], 'MATCH' if d['hash_ok'] else 'MISMATCH')}</div>
    <div class="pf-kv fx" style="--i:6">{row('Link to the previous entry is correct', d['link_ok'], 'LINKED' if d['link_ok'] else 'BROKEN')}</div>
    <div class="pf-kv fx" style="--i:7">{row('Whole chain intact' + ('' if d['chain_intact'] else f" (first break: {d['chain_first_break']})"), d['chain_intact'], 'INTACT' if d['chain_intact'] else 'BROKEN')}</div>
    <div class="pf-title fx" style="--i:8;margin-top:.7rem">Stored hash</div><div class="pf-hash fx" style="--i:9">{e(d['hash'])}</div>
    <div class="pf-title fx" style="--i:10">Previous hash</div><div class="pf-hash fx" style="--i:11">{e(d['prev_hash'])}</div>"""
    slot.markdown(panel(body, ss.vf_fresh, "ok" if ok_all else "bad", H), unsafe_allow_html=True)
    ss.vf_fresh = False
else:
    slot.markdown(empty_panel("Enter a draw ID to verify it.", False, H), unsafe_allow_html=True)
