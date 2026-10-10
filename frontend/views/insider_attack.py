import streamlit as st
from ui import api
from ui.components import *

H = 440
st.markdown('<div class="pf-intro">An insider steals the seed of a standard pseudo-random lottery server. Watch them predict the '
            "next five draws exactly, then fail against certified quantum draws.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("ia", None); ss.setdefault("ia_err", None); ss.setdefault("ia_fresh", False)

run = st.button("Run the attack", type="primary")
l, r = st.columns(2)
with l:
    ls = st.empty()
with r:
    rs = st.empty()

if run:
    ls.markdown(empty_panel("Replaying the stolen seed", True, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("Running certified quantum draws", True, H), unsafe_allow_html=True)
    ss.ia, ss.ia_err = api.call("POST", "/v2/insider-attack", params={"rounds": 5}, timeout=120)
    ss.ia_fresh = ss.ia is not None


def terminal(rows, head, lines_extra, bad_is_match):
    lines = head[:]
    for x in rows:
        hit = x["match"]
        lines.append(("g" if hit else "l", f'round {x["round"]}  actual {x["actual"]}  predicted {x["predicted"]}  '
                      + ("MATCH" if hit else "MISS")))
    lines += lines_extra
    return '<div class="pf-term">' + "".join(
        f'<div class="fx {c}" style="--i:{i}">{e(t)}</div>' for i, (c, t) in enumerate(lines)) + "</div>"


if ss.ia_err:
    ls.markdown(error_panel(ss.ia_err, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("No result", False, H), unsafe_allow_html=True)
elif ss.ia:
    d = ss.ia
    n = len(d["classical"])
    t1 = terminal(d["classical"], [("l", f"$ replay --seed {d['seed']}"), ("g", "[+] PRNG state rebuilt")],
                  [("r", f"[!] {d['classical_hits']} of {n} draws predicted exactly")], True)
    t2 = terminal(d["quantum"], [("l", f"$ replay --seed {d['seed']}"), ("l", "[*] attacking certified draws")],
                  [("g", f"[+] {d['quantum_hits']} of {n} draws predicted. The seed is irrelevant.")], False)
    b1 = '<div class="pf-banner bad fx" style="--i:12">Seeded server fully compromised.</div>'
    b2 = '<div class="pf-banner ok fx" style="--i:12">Certified draws cannot be predicted. Each passed the CHSH check: ' \
         + ", ".join(f"S = {x['S']}" for x in d["quantum"]) + ".</div>"
    ls.markdown(panel('<div class="pf-title">Seeded PRNG server</div>' + t1 + b1, ss.ia_fresh, "bad", H + 60), unsafe_allow_html=True)
    rs.markdown(panel('<div class="pf-title">Certified quantum draws</div>' + t2 + b2, ss.ia_fresh, "ok", H + 60), unsafe_allow_html=True)
    ss.ia_fresh = False
else:
    ls.markdown(empty_panel("Press Run the attack.", False, H + 60), unsafe_allow_html=True)
    rs.markdown(empty_panel("Press Run the attack.", False, H + 60), unsafe_allow_html=True)
