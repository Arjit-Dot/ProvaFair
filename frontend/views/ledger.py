import streamlit as st
from ui import api
from ui.components import *

H = 560
st.markdown('<div class="pf-intro">Every draw is sealed into a hash chain: each entry contains the hash of the one before it. '
            "Editing any old record changes its hash, and the check below shows exactly where. The chain is tamper-evident: "
            "edits are not prevented, they are detected.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("lg_check", None); ss.setdefault("lg_fresh", False); ss.setdefault("lg_msg", None)

data, err = api.call("GET", "/v2/ledger", params={"limit": 12})
entries = data["entries"] if data else []
ids = [x["draw_id"] for x in entries]

c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1.6, 1.3, 1])
with c1:
    add = st.button("Add 3 sample draws")
with c2:
    verify = st.button("Verify chain", type="primary")
with c3:
    target = st.selectbox("Record to edit", ids, label_visibility="collapsed") if ids else None
with c4:
    tamper = st.button("Tamper with record (demo)")
with c5:
    restore = st.button("Restore")

slot = st.empty()
changed = False
if add:
    for m in ("quantum", "quantum", "classical"):
        _, err2 = api.call("POST", "/v2/draw", json={"mode": m, "use_case": "lottery", "pool_size": 100, "num_winners": 4})
        if err2: err = err2
    changed = True
if tamper and target:
    _, err2 = api.call("POST", f"/v2/ledger/tamper/{target}")
    err = err2 or err; changed = True
if restore:
    api.call("POST", "/v2/ledger/restore"); changed = True
if changed:
    ss.lg_check = None
    data, e2 = api.call("GET", "/v2/ledger", params={"limit": 12})
    entries = data["entries"] if data else []
if verify:
    slot.markdown(empty_panel("Re-computing every hash in the chain", True, H), unsafe_allow_html=True)
    ss.lg_check, err = api.call("POST", "/v2/ledger/verify")
    ss.lg_fresh = ss.lg_check is not None

if err:
    slot.markdown(error_panel(err, H), unsafe_allow_html=True)
elif not entries:
    slot.markdown(empty_panel("The ledger is empty. Add sample draws or run a draw on the Live draw page.", False, H), unsafe_allow_html=True)
else:
    chk = ss.lg_check
    status = {}
    if chk:
        for x in chk["entries"]:
            status[x["draw_id"]] = (("bad", "HASH MISMATCH") if not x["hash_ok"] else
                                    ("bad", "LINK BROKEN") if not x["link_ok"] else ("ok", "VERIFIED"))
        banner = (f'<div class="pf-banner ok fx" style="--i:0">Chain intact. {chk["checked"]} entries re-hashed, every link matches.</div>'
                  if chk["intact"] else
                  f'<div class="pf-banner bad fx" style="--i:0">Chain broken at entry {chk["first_break_index"] + 1} '
                  f'({e(chk["first_break_draw_id"])}). Its contents no longer match its hash.</div>')
    else:
        banner = '<div class="pf-banner fx" style="--i:0;border:1px solid var(--edge);color:var(--muted)">Not checked yet. Press Verify chain.</div>'
    cards = []
    for i, ent in enumerate(entries):
        cards.append(link_card(ent, ent["idx"], status.get(ent["draw_id"], ("idle", "")), i + 1))
    body = banner + '<div class="pf-conn"></div>'.join(cards)
    slot.markdown(panel(body, ss.lg_fresh, "bad" if chk and not chk["intact"] else "", H), unsafe_allow_html=True)
    ss.lg_fresh = False
