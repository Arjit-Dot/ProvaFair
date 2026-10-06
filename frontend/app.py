import base64
import html
import pathlib
import time

import requests
import streamlit as st

# ======================================================================
# CONFIGURATION
# ======================================================================
API_URL = "http://127.0.0.1:8000"

# Background video. Drop a file named "background.mp4" next to this script
# (it is embedded automatically) or point VIDEO_URL at any direct .mp4 link.
LOCAL_VIDEO = pathlib.Path(__file__).parent / "background.mp4"
VIDEO_URL = ""  # e.g. "https://your-cdn.com/quantum-loop.mp4"

PANEL_H = 380  # px. Every result panel reserves this height so nothing jumps.

st.set_page_config(page_title="ProvaFair | Quantum-Secured Draws", layout="wide")
# --- HIDE STREAMLIT BRANDING ---
hide_st_style = """
            <style>
            [data-testid="stToolbar"] {visibility: hidden !important;}
            header {visibility: hidden !important;}
            footer {visibility: hidden !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ======================================================================
# STATE
# ======================================================================
DEFAULTS = {
    "q_result": None, "q_error": None, "q_fresh": False,
    "a_result": None, "a_error": None, "a_fresh": False,
    "rigged_data": [], "show_public": False, "show_hacker": False,
    "fresh_public": False, "fresh_hacker": False,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset_demo():
    # Runs as a callback BEFORE the script reruns, so no st.rerun() is needed
    # and the page never flickers or reflows.
    st.session_state.rigged_data = []
    st.session_state.show_public = False
    st.session_state.show_hacker = False
    st.session_state.fresh_public = False
    st.session_state.fresh_hacker = False


# ======================================================================
# STYLE + BACKGROUND VIDEO
# ======================================================================
def video_src():
    if LOCAL_VIDEO.exists():
        b64 = base64.b64encode(LOCAL_VIDEO.read_bytes()).decode()
        return f"data:video/mp4;base64,{b64}"
    return VIDEO_URL


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root{
  --void:#050816; --ink:#e9f3ff; --muted:#8a9bb8;
  --photon:#7cf0ff; --photon-dim:rgba(124,240,255,.14);
  --alarm:#ff4d6d; --alarm-dim:rgba(255,77,109,.14);
  --glass:rgba(10,16,38,.62); --edge:rgba(160,200,255,.16);
}

html, body, .stApp{ font-family:'Space Grotesk',sans-serif; color:var(--ink); }
.stApp{ background:transparent !important; }
header[data-testid="stHeader"]{ background:transparent !important; }
.block-container{ padding-top:2.2rem; max-width:1180px; }

/* ---------- background layers ---------- */
#pf-bg{ position:fixed; inset:0; z-index:-3; background:var(--void); overflow:hidden; }
#pf-bg video{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:.55; }
#pf-bg .aurora{
  position:absolute; inset:-20%;
  background:
    radial-gradient(40% 40% at 20% 30%, rgba(124,240,255,.22), transparent 60%),
    radial-gradient(35% 35% at 80% 20%, rgba(150,90,255,.20), transparent 60%),
    radial-gradient(40% 40% at 60% 85%, rgba(30,120,255,.20), transparent 60%);
  animation: drift 22s ease-in-out infinite alternate;
}
#pf-bg .shade{ position:absolute; inset:0;
  background:linear-gradient(180deg, rgba(5,8,22,.55), rgba(5,8,22,.82)); }
@keyframes drift{ to{ transform:translate3d(4%, -3%, 0) scale(1.12) rotate(4deg);} }

/* ---------- hero ---------- */
.pf-hero h1{
  font-weight:700; font-size:clamp(2.2rem,5vw,3.6rem); letter-spacing:-.03em;
  margin:0 0 .4rem; line-height:1.05;
  background:linear-gradient(100deg,#fff 20%,var(--photon) 55%,#b9a2ff 90%);
  background-size:220% 100%; -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; animation:sheen 9s linear infinite;
}
@keyframes sheen{ to{ background-position:-220% 0; } }
.pf-hero p{ color:var(--muted); max-width:62ch; font-size:1.05rem; margin:0 0 .6rem; }
.pf-pulse{ display:inline-block; width:9px; height:9px; border-radius:50%;
  background:var(--photon); margin-right:.55rem; box-shadow:0 0 0 0 rgba(124,240,255,.7);
  animation:pulse 2s infinite; vertical-align:middle; }
@keyframes pulse{ 70%{ box-shadow:0 0 0 12px rgba(124,240,255,0);} 100%{ box-shadow:0 0 0 0 rgba(124,240,255,0);} }

/* ---------- Streamlit widgets ---------- */
div[data-baseweb="tab-list"]{ gap:.4rem; border-bottom:1px solid var(--edge); }
button[data-baseweb="tab"]{ background:transparent !important; color:var(--muted) !important;
  font-family:'Space Grotesk',sans-serif; font-weight:500; transition:color .25s; }
button[data-baseweb="tab"][aria-selected="true"]{ color:var(--photon) !important; }
div[data-baseweb="tab-highlight"]{ background:var(--photon) !important; box-shadow:0 0 14px var(--photon); }

.stButton>button{
  border-radius:10px; border:1px solid var(--edge); background:rgba(255,255,255,.04);
  color:var(--ink); font-weight:500; transition:all .25s ease; height:2.9rem;
}
.stButton>button:hover{ border-color:var(--photon); color:var(--photon);
  box-shadow:0 0 22px var(--photon-dim); transform:translateY(-1px); }
.stButton>button[kind="primary"]{
  background:linear-gradient(100deg,#2ad4ff,#7a6bff); color:#04101f; border:0; font-weight:700; }
.stButton>button[kind="primary"]:hover{ color:#04101f; box-shadow:0 0 30px rgba(90,170,255,.55); }
.stNumberInput input, .stTextInput input{
  background:rgba(255,255,255,.05) !important; color:var(--ink) !important;
  border:1px solid var(--edge) !important; border-radius:10px !important; }
label, .stToggle label p{ color:var(--muted) !important; }

/* ---------- fixed-size glass panel (prevents layout shift) ---------- */
.pf-panel{
  position:relative; min-height:__PANEL_H__px; height:__PANEL_H__px; overflow:auto;
  background:var(--glass); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border:1px solid var(--edge); border-radius:16px; padding:1.4rem 1.5rem;
  scrollbar-width:thin;
}
.pf-panel.ok{ border-color:rgba(124,240,255,.35); box-shadow:0 0 40px rgba(124,240,255,.07); }
.pf-panel.bad{ border-color:rgba(255,77,109,.4); box-shadow:0 0 40px rgba(255,77,109,.08); }
.pf-title{ font-size:.95rem; color:var(--muted); margin:0 0 .9rem; font-weight:500; }
.pf-empty{ height:100%; display:flex; flex-direction:column; align-items:center;
  justify-content:center; text-align:center; color:var(--muted); gap:.6rem; }
.pf-empty .ring{ width:46px; height:46px; border-radius:50%;
  border:2px solid var(--edge); border-top-color:var(--photon); animation:spin 3s linear infinite; }
.pf-empty .ring.fast{ animation-duration:.8s; }
@keyframes spin{ to{ transform:rotate(360deg);} }

.pf-score{ font-size:3rem; font-weight:700; letter-spacing:-.03em; line-height:1; }
.pf-score.ok{ color:var(--photon); } .pf-score.bad{ color:var(--alarm); }
.pf-note{ color:var(--muted); font-size:.88rem; margin-top:.35rem; }
.pf-chips{ display:flex; flex-wrap:wrap; gap:.55rem; margin:.4rem 0 1rem; }
.pf-chip{ min-width:3.1rem; text-align:center; padding:.55rem .85rem; border-radius:12px;
  font-family:'IBM Plex Mono',monospace; font-size:1.15rem; font-weight:500;
  background:var(--photon-dim); border:1px solid rgba(124,240,255,.4); color:var(--photon); }
.pf-chip.bad{ background:var(--alarm-dim); border-color:rgba(255,77,109,.45); color:var(--alarm); }
.pf-hash{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; word-break:break-all;
  background:rgba(0,0,0,.35); border:1px solid var(--edge); border-radius:10px;
  padding:.7rem .85rem; color:#bcd3ff; }
.pf-row{ display:flex; gap:1.5rem; flex-wrap:wrap; }
.pf-row>div{ flex:1 1 220px; }
.pf-kv{ color:var(--muted); font-size:.9rem; margin:.15rem 0; }
.pf-kv b{ color:var(--ink); font-weight:500; }

.pf-term{ font-family:'IBM Plex Mono',monospace; font-size:.86rem; line-height:1.75; }
.pf-term .l{ color:#9fb4d6; } .pf-term .g{ color:var(--photon); } .pf-term .r{ color:var(--alarm); }
.pf-banner{ margin-top:.8rem; padding:.7rem .9rem; border-radius:10px;
  background:var(--alarm-dim); border:1px solid rgba(255,77,109,.5); color:#ffc2cc; font-size:.9rem; }
.pf-bar{ height:3px; border-radius:3px; margin-top:.9rem; overflow:hidden; background:var(--edge); }
.pf-bar i{ display:block; height:100%; width:40%; background:var(--photon);
  animation:scan 1.1s ease-in-out infinite; box-shadow:0 0 12px var(--photon); }
@keyframes scan{ from{ transform:translateX(-100%);} to{ transform:translateX(260%);} }

/* ---------- cascade: children reveal one after another ---------- */
.play .fx{ opacity:0; animation:rise .55s cubic-bezier(.2,.8,.2,1) forwards;
  animation-delay:calc(var(--i) * 110ms); }
.play .pf-chip.fx{ animation-name:pop; }
@keyframes rise{ from{ opacity:0; transform:translateY(14px);} to{ opacity:1; transform:none;} }
@keyframes pop{ 0%{ opacity:0; transform:scale(.5);} 70%{ transform:scale(1.12);} 100%{ opacity:1; transform:scale(1);} }

@media (prefers-reduced-motion: reduce){
  .play .fx, #pf-bg .aurora, .pf-hero h1, .pf-pulse{ animation:none !important; opacity:1 !important; }
}
</style>
""".replace("__PANEL_H__", str(PANEL_H))


def inject_background():
    src = video_src()
    video = (
        f'<video autoplay muted loop playsinline><source src="{src}" type="video/mp4"></video>'
        if src else ""
    )
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div id="pf-bg"><div class="aurora"></div>{video}<div class="shade"></div></div>',
        unsafe_allow_html=True,
    )


# ======================================================================
# HTML BUILDERS (every panel has the same fixed size)
# ======================================================================
def e(x):
    return html.escape(str(x))


def fx(i):
    return f'class="fx" style="--i:{i}"'


def panel(inner, fresh=False, tone=""):
    cls = f"pf-panel {tone} {'play' if fresh else ''}"
    return f'<div class="{cls}">{inner}</div>'


def empty_panel(text, busy=False):
    ring = "ring fast" if busy else "ring"
    bar = '<div class="pf-bar" style="width:160px"><i></i></div>' if busy else ""
    return panel(f'<div class="pf-empty"><div class="{ring}"></div><div>{e(text)}</div>{bar}</div>')


def chips(winners, bad=False, start=2):
    cls = "pf-chip fx" + (" bad" if bad else "")
    items = "".join(
        f'<span class="{cls}" style="--i:{start + n}">{e(w)}</span>' for n, w in enumerate(winners)
    )
    return f'<div class="pf-chips">{items}</div>'


def quantum_panel(d, fresh):
    n = len(d["winners"])
    is_q = d.get("is_quantum")
    inner = f"""
    <div class="pf-row">
      <div {fx(0)}>
        <div class="pf-title">CHSH score. A quantum result must exceed 2.0</div>
        <div class="pf-score ok">{e(d['chsh_score'])}</div>
        <div class="pf-note">{'Entanglement verified. No hidden classical variables.' if is_q else 'Below the quantum threshold.'}</div>
      </div>
      <div {fx(1)}>
        <div class="pf-title">Draw ID</div>
        <div class="pf-kv"><b>{e(d['draw_id'])}</b></div>
      </div>
    </div>
    <div class="pf-title" style="margin-top:1.1rem" {fx(2)}>Selections</div>
    {chips(d['winners'], start=3)}
    <div class="pf-title" {fx(3 + n)}>Cryptographic receipt (SHA-256)</div>
    <div class="pf-hash" {fx(4 + n)}>{e(d['receipt_hash'])}</div>
    """
    return panel(inner, fresh, "ok")


def audit_panel(r, fresh):
    passed = r["chsh_score"] > 2.0
    tone = "ok" if passed else "bad"
    verdict = "Passed the quantum threshold." if passed else "Failed. Classical generation detected."
    inner = f"""
    <div class="pf-row">
      <div>
        <div {fx(0)} class="fx pf-kv">Event <b>{e(r['event_name'])}</b></div>
        <div {fx(1)} class="fx pf-kv">Timestamp <b>{e(r['timestamp'])}</b></div>
        <div {fx(2)} class="fx pf-kv">Status <b>{e(r['status'])}</b></div>
      </div>
      <div {fx(3)}>
        <div class="pf-title">Recorded CHSH score</div>
        <div class="pf-score {tone}">{e(r['chsh_score'])}</div>
        <div class="pf-note">{verdict}</div>
      </div>
    </div>
    <div class="pf-title" style="margin-top:1.1rem" {fx(4)}>Verified selections</div>
    {chips(r['winners'], bad=not passed, start=5)}
    <div class="pf-title" {fx(5 + len(r['winners']))}>Integrity hash</div>
    <div class="pf-hash" {fx(6 + len(r['winners']))}>{e(r['receipt_hash'])}</div>
    """
    return panel(inner, fresh, tone)


def public_panel(draws, fresh):
    parts = []
    for i, d in enumerate(draws):
        parts.append(
            f'<div {fx(i * 3)}><div class="pf-title">Draw {i + 1}</div></div>'
            f'{chips(d["winners"], start=i * 3 + 1)}'
            f'<div class="pf-note fx" style="--i:{i * 3 + 2};margin:-.5rem 0 1rem">'
            f'CHSH {e(d["chsh_score"])}. Classical limit is 2.0.</div>'
        )
    return panel("".join(parts), fresh)


def hacker_panel(draws, fresh):
    lines = [
        ("l", "$ load --seed boot_seed.bin"),
        ("g", "[+] seed recovered from server memory"),
        ("g", "[+] PRNG state rebuilt"),
    ]
    for i, d in enumerate(draws):
        lines.append(("g", f"[+] predicted draw {i + 1}: {d['winners']}"))
    lines.append(("r", "[!] all predictions match production output"))
    body = "".join(
        f'<div class="fx {c}" style="--i:{n}">{e(t)}</div>' for n, (c, t) in enumerate(lines)
    )
    banner = (
        f'<div class="pf-banner fx" style="--i:{len(lines) + 1}">'
        "Output sequence matched exactly. Draw integrity compromised.</div>"
    )
    return panel(f'<div class="pf-term">{body}</div>{banner}', fresh, "bad")


# ======================================================================
# BACKEND CALLS
# ======================================================================
def fetch_rigged_draws():
    draws = []
    for _ in range(3):
        try:
            res = requests.post(
                f"{API_URL}/draw/rigged", json={"num_winners": 4, "pool_size": 100}, timeout=10
            ).json()
            draws.append(
                {"winners": res["winners"], "chsh_score": res["chsh_score"], "status": res["status"]}
            )
            time.sleep(0.1)
        except Exception:
            return []
    return draws


# ======================================================================
# PAGE
# ======================================================================
inject_background()

st.markdown(
    """
    <div class="pf-hero">
      <h1>ProvaFair</h1>
      <p><span class="pf-pulse"></span>Draws secured by quantum mechanics. Every result carries a
      physics-backed proof of randomness, so no seed can be manipulated and no insider can rig the outcome.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

developer_mode = st.toggle("Enable vulnerability assessment", value=False, key="dev_mode")

# Always three tabs: the layout never changes when the toggle flips.
tab_quantum, tab_audit, tab_hacker = st.tabs(
    ["Quantum engine", "Audit ledger", "Vulnerability demo"]
)

# ----------------------------------------------------------------------
# TAB 1: QUANTUM DRAW
# ----------------------------------------------------------------------
with tab_quantum:
    st.write("")
    # Notice the new vertical_alignment parameter
    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    with c1:
        pool_size = st.number_input("Participants in pool", min_value=1, value=100, step=1, key="q_pool")
    with c2:
        num_winners = st.number_input("Winners to select", min_value=1, value=4, step=1, key="q_win")
    with c3:
        # Remove the st.write("") completely
        run_q = st.button("Run quantum draw", type="primary", use_container_width=True)

    q_slot = st.empty()

    if run_q:
        q_slot.markdown(empty_panel("Running Bell test and measuring entangled pairs", busy=True), unsafe_allow_html=True)
        try:
            resp = requests.post(
                f"{API_URL}/draw/quantum",
                json={"num_winners": num_winners, "pool_size": pool_size},
                timeout=60,
            )
            if resp.status_code == 200:
                st.session_state.q_result = resp.json()
                st.session_state.q_error = None
                st.session_state.q_fresh = True
            else:
                st.session_state.q_result = None
                st.session_state.q_error = f"The backend returned status {resp.status_code}. Check the engine logs."
        except Exception as ex:
            st.session_state.q_result = None
            st.session_state.q_error = f"Cannot reach the FastAPI backend at {API_URL}. Details: {ex}"

    if st.session_state.q_error:
        q_slot.markdown(
            panel(f'<div class="pf-empty"><div class="pf-score bad">!</div><div>{e(st.session_state.q_error)}</div></div>', False, "bad"),
            unsafe_allow_html=True,
        )
    elif st.session_state.q_result:
        q_slot.markdown(quantum_panel(st.session_state.q_result, st.session_state.q_fresh), unsafe_allow_html=True)
        st.session_state.q_fresh = False
    else:
        q_slot.markdown(empty_panel("Set the pool and run a draw. Results appear here."), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# TAB 2: AUDIT LEDGER
# ----------------------------------------------------------------------
with tab_audit:
    st.write("")
    a1, a2 = st.columns([3, 1])
    a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
    with a1:
        search_id = st.text_input("Transaction ID", placeholder="DRAW-Q-...")
    with a2:
        # Remove the double st.write("") completely
        run_a = st.button("Verify record", use_container_width=True)

    a_slot = st.empty()

    if run_a:
        if not search_id:
            st.session_state.a_result = None
            st.session_state.a_error = "Enter a transaction ID to verify."
        else:
            a_slot.markdown(empty_panel("Checking the ledger", busy=True), unsafe_allow_html=True)
            try:
                resp = requests.get(f"{API_URL}/verify/{search_id}", timeout=15)
                if resp.status_code == 200:
                    st.session_state.a_result = resp.json()
                    st.session_state.a_error = None
                    st.session_state.a_fresh = True
                else:
                    st.session_state.a_result = None
                    st.session_state.a_error = f"No record found for {search_id}. Check the ID and try again."
            except Exception:
                st.session_state.a_result = None
                st.session_state.a_error = "Cannot reach the database backend. Confirm the API is running."

    if st.session_state.a_error:
        a_slot.markdown(
            panel(f'<div class="pf-empty"><div class="pf-score bad">!</div><div>{e(st.session_state.a_error)}</div></div>', False, "bad"),
            unsafe_allow_html=True,
        )
    elif st.session_state.a_result:
        a_slot.markdown(audit_panel(st.session_state.a_result, st.session_state.a_fresh), unsafe_allow_html=True)
        st.session_state.a_fresh = False
    else:
        a_slot.markdown(empty_panel("Enter a transaction ID to check it against the ledger."), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# TAB 3: VULNERABILITY DEMO
# ----------------------------------------------------------------------
with tab_hacker:
    st.write("")
    if not developer_mode:
        st.markdown(
            empty_panel("Turn on \"Enable vulnerability assessment\" above to unlock this demo."),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="pf-note" style="margin:0 0 1rem">A classical PRNG is deterministic. '
            "An attacker who gets the boot seed can compute every future draw.</div>",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            run_pub = st.button("Start production draws", key="pub_btn", use_container_width=True)
        with b2:
            run_hack = st.button("Run exploit", key="hack_btn", use_container_width=True)
        with b3:
            st.button("Reset demo", key="reset_btn", on_click=reset_demo, use_container_width=True)

        if run_pub or run_hack:
            with st.spinner("Contacting classical engine"):
                if not st.session_state.rigged_data:
                    st.session_state.rigged_data = fetch_rigged_draws()
            if run_pub:
                st.session_state.show_public = True
                st.session_state.fresh_public = True
            if run_hack:
                st.session_state.show_hacker = True
                st.session_state.fresh_hacker = True

        col_pub, col_hack = st.columns(2)
        data = st.session_state.rigged_data

        with col_pub:
            st.markdown('<div class="pf-title">Production server</div>', unsafe_allow_html=True)
            if st.session_state.show_public and data:
                st.markdown(public_panel(data, st.session_state.fresh_public), unsafe_allow_html=True)
                st.session_state.fresh_public = False
            elif st.session_state.show_public:
                st.markdown(empty_panel("The backend returned no data. Start the API and try again."), unsafe_allow_html=True)
            else:
                st.markdown(empty_panel("Waiting for the first draw sequence."), unsafe_allow_html=True)

        with col_hack:
            st.markdown('<div class="pf-title">Attacker terminal</div>', unsafe_allow_html=True)
            if st.session_state.show_hacker and data:
                st.markdown(hacker_panel(data, st.session_state.fresh_hacker), unsafe_allow_html=True)
                st.session_state.fresh_hacker = False
            else:
                st.markdown(empty_panel("Terminal idle. Run the exploit to predict the draws."), unsafe_allow_html=True)