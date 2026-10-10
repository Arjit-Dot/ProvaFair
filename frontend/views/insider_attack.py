import streamlit as st
from ui import api
from ui.components import *

H = 440
st.markdown('<div class="pf-intro">An insider steals the seed of a standard pseudo-random lottery server. Watch them predict the '
            "next five draws exactly, then fail against certified quantum draws.</div>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("ia", None); ss.setdefault("ia_err", None); ss.setdefault("ia_fresh", False)

mode = st.radio("Draw type", ["Classical draw", "Quantum draw"], horizontal=True, key="ia_mode")
quantum = mode == "Quantum draw"
run = st.button("Run the attack", type="primary")
l, r = st.columns(2)
with l:
    ls = st.empty()
with r:
    rs = st.empty()

if run:
    ls.markdown(empty_panel("Running the public draws", True, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("Replaying the stolen seed", True, H), unsafe_allow_html=True)
    ss.ia, ss.ia_err = api.call("POST", "/v2/insider-attack", params={"rounds": 5}, timeout=120)
    ss.ia_fresh = ss.ia is not None


def terminal(lines):
    return '<div class="pf-term">' + "".join(
        f'<div class="fx {c}" style="--i:{i}">{e(t)}</div>' for i, (c, t) in enumerate(lines)) + "</div>"


if ss.ia_err:
    ls.markdown(error_panel(ss.ia_err, H), unsafe_allow_html=True)
    rs.markdown(empty_panel("No result", False, H), unsafe_allow_html=True)
elif ss.ia:
    d = ss.ia
    rows = d["quantum" if quantum else "classical"]
    n = len(rows)
    hits = d["quantum_hits" if quantum else "classical_hits"]
    pub = [("l", "$ tail draw.log" + ("  (CHSH-certified)" if quantum else ""))]
    for x in rows:
        extra = f'  S = {x["S"]}' if quantum else ""
        pub.append(("g", f'round {x["round"]}  winners {x["actual"]}{extra}'))
    atk = [("l", f"$ replay --seed {d['seed']}"), ("l", "[*] attacking quantum draws" if quantum else "[+] PRNG state rebuilt")]
    for x in rows:
        atk.append(("g" if x["match"] else "l",
                    f'round {x["round"]}  predicted {x["predicted"]}  ' + ("MATCH" if x["match"] else "MISS")))
    if quantum:
        atk.append(("g", f"[+] {hits} of {n} draws predicted. The seed is irrelevant."))
        banner = '<div class="pf-banner ok fx" style="--i:12">Certified draws cannot be predicted.</div>'
    else:
        atk.append(("r", f"[!] {hits} of {n} draws predicted exactly"))
        banner = '<div class="pf-banner bad fx" style="--i:12">Seeded server fully compromised.</div>'
    tone = "ok" if quantum else "bad"
    label = "Quantum" if quantum else "Classical"
    ls.markdown(panel(f'<div class="pf-title">Public draw ({label}): what people see</div>' + terminal(pub),
                      ss.ia_fresh, "ok", H + 60), unsafe_allow_html=True)
    rs.markdown(panel(f'<div class="pf-title">Attacker window ({label})</div>' + terminal(atk) + banner,
                      ss.ia_fresh, tone, H + 60), unsafe_allow_html=True)
    ss.ia_fresh = False
else:
    ls.markdown(empty_panel("Press Run the attack.", False, H + 60), unsafe_allow_html=True)
    rs.markdown(empty_panel("Press Run the attack.", False, H + 60), unsafe_allow_html=True)
