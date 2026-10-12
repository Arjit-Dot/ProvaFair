import base64
import pathlib
import streamlit as st

LOCAL_VIDEO = pathlib.Path(__file__).parent.parent / "background.mp4"
VIDEO_URL = ""  # or a direct .mp4 URL

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{ --void:#050816; --ink:#e9f3ff; --muted:#8a9bb8; --photon:#7cf0ff; --photon-dim:rgba(124,240,255,.14);
  --alarm:#ff4d6d; --alarm-dim:rgba(255,77,109,.14); --amber:#ffc15e; --amber-dim:rgba(255,193,94,.14);
  --glass:rgba(10,16,38,.66); --edge:rgba(160,200,255,.16); }
.stAppDeployButton, [data-testid="stAppDeployButton"]{ display:none !important; }
html, body, .stApp{ font-family:'Space Grotesk',sans-serif; color:var(--ink); }
.stApp{ background:transparent !important; }
header[data-testid="stHeader"]{ background:rgba(5,8,22,.35) !important; backdrop-filter:blur(10px); }
.block-container{ padding-top:4.2rem; max-width:1180px; }
#pf-bg{ position:fixed; inset:0; z-index:-3; background:var(--void); overflow:hidden; }
#pf-bg video{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:.5; }
#pf-bg .aurora{ position:absolute; inset:-20%; animation:drift 22s ease-in-out infinite alternate;
  background: radial-gradient(40% 40% at 20% 30%, rgba(124,240,255,.22), transparent 60%),
  radial-gradient(35% 35% at 80% 20%, rgba(150,90,255,.20), transparent 60%),
  radial-gradient(40% 40% at 60% 85%, rgba(30,120,255,.20), transparent 60%); }
#pf-bg .shade{ position:absolute; inset:0; background:linear-gradient(180deg, rgba(5,8,22,.55), rgba(5,8,22,.85)); }
@keyframes drift{ to{ transform:translate3d(4%, -3%, 0) scale(1.12) rotate(4deg);} }

.pf-hero h1{ font-weight:700; font-size:clamp(2rem,4.5vw,3.2rem); letter-spacing:-.03em; margin:0 0 .3rem; line-height:1.05;
  background:linear-gradient(100deg,#fff 20%,var(--photon) 55%,#b9a2ff 90%); background-size:220% 100%;
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; animation:sheen 9s linear infinite; }
@keyframes sheen{ to{ background-position:-220% 0; } }
.pf-hero p{ color:var(--muted); max-width:68ch; font-size:1rem; margin:0 0 1rem; }
.pf-pulse{ display:inline-block; width:9px; height:9px; border-radius:50%; background:var(--photon); margin-right:.55rem;
  box-shadow:0 0 0 0 rgba(124,240,255,.7); animation:pulse 2s infinite; vertical-align:middle; }
@keyframes pulse{ 70%{ box-shadow:0 0 0 12px rgba(124,240,255,0);} 100%{ box-shadow:0 0 0 0 rgba(124,240,255,0);} }
.pf-intro{ color:var(--muted); max-width:80ch; margin:.2rem 0 1rem; }

.stButton>button{ border-radius:10px; border:1px solid var(--edge); background:rgba(255,255,255,.05); color:var(--ink);
  font-weight:500; transition:all .25s ease; height:2.9rem; }
.stButton>button:hover{ border-color:var(--photon); color:var(--photon); box-shadow:0 0 22px var(--photon-dim); transform:translateY(-1px); }
.stButton>button[kind="primary"]{ background:linear-gradient(100deg,#2ad4ff,#7a6bff); color:#04101f; border:0; font-weight:700; }
.stButton>button[kind="primary"]:hover{ color:#04101f; box-shadow:0 0 30px rgba(90,170,255,.55); }
.stNumberInput input, .stTextInput input, div[data-baseweb="select"]>div{ background:rgba(255,255,255,.05) !important;
  color:var(--ink) !important; border:1px solid var(--edge) !important; border-radius:10px !important; }
label, .stToggle label p, .stRadio label p{ color:var(--muted) !important; }

.pf-panel{ position:relative; overflow:auto; background:var(--glass); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border:1px solid var(--edge); border-radius:16px; padding:1.3rem 1.4rem; scrollbar-width:thin; box-sizing:border-box; }
.pf-panel.ok{ border-color:rgba(124,240,255,.35); box-shadow:0 0 40px rgba(124,240,255,.07); }
.pf-panel.bad{ border-color:rgba(255,77,109,.45); box-shadow:0 0 40px rgba(255,77,109,.09); }
.pf-title{ font-size:.92rem; color:var(--muted); margin:0 0 .7rem; font-weight:500; }
.pf-empty{ height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:var(--muted); gap:.6rem; }
.pf-empty .ring{ width:44px; height:44px; border-radius:50%; border:2px solid var(--edge); border-top-color:var(--photon); animation:spin 3s linear infinite; }
.pf-empty .ring.fast{ animation-duration:.8s; }
@keyframes spin{ to{ transform:rotate(360deg);} }
.pf-bar{ height:3px; width:160px; border-radius:3px; overflow:hidden; background:var(--edge); }
.pf-bar i{ display:block; height:100%; width:40%; background:var(--photon); animation:scan 1.1s ease-in-out infinite; box-shadow:0 0 12px var(--photon); }
@keyframes scan{ from{ transform:translateX(-100%);} to{ transform:translateX(260%);} }

.pf-verdict{ display:flex; align-items:baseline; gap:1rem; flex-wrap:wrap; margin-bottom:.3rem; }
.pf-verdict b{ font-size:2.1rem; letter-spacing:-.02em; line-height:1; }
.pf-verdict.ok b{ color:var(--photon); } .pf-verdict.bad b{ color:var(--alarm); }
.pf-verdict span{ color:var(--muted); font-size:.95rem; }
.pf-duo{ display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin:.4rem 0 1.6rem; }
.pf-card{ position:relative; border-radius:16px; padding:2.2rem 1.8rem; border:2px solid; display:flex; flex-direction:column; align-items:center; text-align:center; gap:1.1rem; min-height:260px; justify-content:center; }
.pf-card i{ font-style:normal; font-size:3.2rem; line-height:1; font-weight:800; }
.pf-card small{ font-size:.8rem; font-weight:700; letter-spacing:.2em; text-transform:uppercase; color:var(--ink); opacity:.8; }
.pf-card b{ font-size:2.6rem; font-weight:800; letter-spacing:.04em; line-height:1.2; }
.pf-card span{ color:var(--ink); font-size:1rem; font-weight:500; opacity:.9; line-height:1.5; }
.pf-card.ok{ background:linear-gradient(160deg,rgba(60,220,140,.30),rgba(60,220,140,.08)); border-color:#3cdc8c; box-shadow:0 0 28px rgba(60,220,140,.35); } .pf-card.ok b,.pf-card.ok i{ color:#3cdc8c; }
.pf-card.bad{ background:linear-gradient(160deg,rgba(255,77,109,.34),rgba(255,77,109,.08)); border-color:var(--alarm); box-shadow:0 0 28px rgba(255,77,109,.4); } .pf-card.bad b,.pf-card.bad i{ color:var(--alarm); }
.pf-card.draw.ok{ background:linear-gradient(160deg,rgba(60,220,140,.30),rgba(60,220,140,.08)); border-color:#3cdc8c; box-shadow:0 0 28px rgba(60,220,140,.35); } .pf-card.draw.ok b,.pf-card.draw.ok i{ color:#3cdc8c; }
.pf-card.draw.bad{ background:linear-gradient(160deg,rgba(255,77,109,.34),rgba(255,77,109,.08)); border-color:#ff4d6d; box-shadow:0 0 28px rgba(255,77,109,.4); } .pf-card.draw.bad b,.pf-card.draw.bad i{ color:#ff4d6d; }
.pf-card.auth.ok{ background:linear-gradient(160deg,rgba(124,240,255,.28),rgba(124,240,255,.07)); border-color:#7cf0ff; box-shadow:0 0 28px rgba(124,240,255,.35); } .pf-card.auth.ok b,.pf-card.auth.ok i{ color:#7cf0ff; }
.pf-card.auth.bad{ background:linear-gradient(160deg,rgba(255,159,67,.34),rgba(255,159,67,.08)); border-color:#ff9f43; box-shadow:0 0 28px rgba(255,159,67,.4); } .pf-card.auth.bad b,.pf-card.auth.bad i{ color:#ff9f43; }
.pf-keyrow{ display:flex; flex-wrap:wrap; gap:1rem; margin:1rem 0 1.4rem; }
.pf-keyrow div{ flex:1; min-width:120px; padding:1rem 1.2rem; line-height:1.4; border-radius:12px; background:var(--photon-dim); border:1px solid var(--photon); color:var(--muted); font-size:.75rem; letter-spacing:.12em; text-transform:uppercase; }
.pf-keyrow div b{ display:block; color:var(--ink); font-size:1.5rem; letter-spacing:0; text-transform:none; margin-top:.5rem; }
.pf-chips{ display:flex; flex-wrap:wrap; gap:.5rem; margin:.3rem 0 .9rem; }
.pf-chip{ padding:.5rem .8rem; border-radius:12px; font-family:'IBM Plex Mono',monospace; font-size:.9rem;
  background:var(--photon-dim); border:1px solid rgba(124,240,255,.4); color:var(--photon); }
.pf-chip.bad{ background:var(--alarm-dim); border-color:rgba(255,77,109,.45); color:var(--alarm); }
.pf-hash{ font-family:'IBM Plex Mono',monospace; font-size:.76rem; word-break:break-all; background:rgba(0,0,0,.35);
  border:1px solid var(--edge); border-radius:10px; padding:.55rem .75rem; color:#bcd3ff; margin-bottom:.6rem; }
.pf-kv{ color:var(--muted); font-size:.9rem; margin:.2rem 0; } .pf-kv b{ color:var(--ink); font-weight:500; }
.pf-note{ color:var(--muted); font-size:.86rem; }
.pf-lock{ display:flex; flex-direction:column; gap:.4rem; padding:1rem; border-radius:12px; background:var(--alarm-dim);
  border:1px solid rgba(255,77,109,.45); color:#ffc2cc; margin-bottom:.9rem; }
.pf-lock b{ font-size:1.05rem; color:var(--alarm); }

table.pf-t{ width:100%; border-collapse:collapse; font-size:.86rem; }
table.pf-t th{ text-align:left; color:var(--muted); font-weight:500; padding:.3rem .4rem; border-bottom:1px solid var(--edge); }
table.pf-t td{ padding:.4rem .4rem; border-bottom:1px solid rgba(160,200,255,.07); font-family:'IBM Plex Mono',monospace; }
table.pf-t tr.total td{ color:var(--photon); font-weight:500; border-bottom:0; }
table.pf-t tr.total.bad td{ color:var(--alarm); }
.pf-formula{ font-family:'IBM Plex Mono',monospace; font-size:.84rem; color:#bcd3ff; margin:.8rem 0 .3rem; line-height:1.7; }
.pf-rule{ margin-top:.6rem; padding:.55rem .75rem; border-radius:10px; font-size:.88rem; }
.pf-rule.ok{ background:var(--photon-dim); border:1px solid rgba(124,240,255,.35); color:var(--photon); }
.pf-rule.bad{ background:var(--alarm-dim); border:1px solid rgba(255,77,109,.45); color:#ffc2cc; }
pre.pf-circ{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; color:#bcd3ff; margin:0; overflow:auto; }
.pf-img{ max-width:100%; border-radius:10px; }

.pf-stat{ display:flex; gap:1.2rem; flex-wrap:wrap; margin-top:.8rem; }
.pf-stat>div{ flex:1 1 150px; padding:.8rem .9rem; border-radius:12px; border:1px solid var(--edge); background:rgba(255,255,255,.03); }
.pf-stat .n{ font-size:1.5rem; font-weight:700; line-height:1.1; } .pf-stat .l{ color:var(--muted); font-size:.8rem; }
.pf-stat .q{ color:var(--photon); } .pf-stat .c{ color:var(--alarm); }
.pill{ display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.78rem; font-weight:700; }
.pill.ok{ background:var(--photon-dim); color:var(--photon); border:1px solid rgba(124,240,255,.4); }
.pill.bad{ background:var(--alarm-dim); color:var(--alarm); border:1px solid rgba(255,77,109,.45); }
.pill.idle{ background:rgba(255,255,255,.06); color:var(--muted); border:1px solid var(--edge); }
.pill.warn{ background:var(--amber-dim); color:var(--amber); border:1px solid rgba(255,193,94,.45); }
.pf-test{ display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.7rem .85rem; margin-bottom:.5rem;
  border-radius:12px; border:1px solid var(--edge); background:rgba(255,255,255,.03); }
.pf-test .nm{ font-weight:500; } .pf-test .dt{ color:var(--muted); font-size:.8rem; font-family:'IBM Plex Mono',monospace; }
.pf-meter{ height:8px; border-radius:8px; background:var(--edge); position:relative; margin:.5rem 0 1rem; }
.pf-meter i{ position:absolute; top:-3px; width:3px; height:14px; background:var(--ink); border-radius:2px; }
.pf-meter u{ position:absolute; left:50%; top:-3px; width:2px; height:14px; background:var(--muted); }

.pf-link{ border:1px solid var(--edge); border-radius:12px; padding:.7rem .9rem; background:rgba(255,255,255,.03); }
.pf-link.bad{ border-color:rgba(255,77,109,.6); background:var(--alarm-dim); }
.pf-link.ok{ border-color:rgba(124,240,255,.35); }
.pf-link .top{ display:flex; justify-content:space-between; align-items:center; gap:.6rem; margin-bottom:.4rem; font-size:.9rem; }
.pf-link .h{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; color:#9fb4d6; line-height:1.55; word-break:break-all; }
.pf-link .h em{ color:var(--muted); font-style:normal; }
.pf-conn{ width:2px; height:16px; margin:0 auto; background:linear-gradient(var(--edge), var(--photon)); }

.pf-term{ font-family:'IBM Plex Mono',monospace; font-size:.84rem; line-height:1.75; }
.pf-term .l{ color:#9fb4d6; } .pf-term .g{ color:var(--photon); } .pf-term .r{ color:var(--alarm); }
.pf-banner{ margin-top:.8rem; padding:.7rem .9rem; border-radius:10px; font-size:.9rem; }
.pf-banner.bad{ background:var(--alarm-dim); border:1px solid rgba(255,77,109,.5); color:#ffc2cc; }
.pf-banner.ok{ background:var(--photon-dim); border:1px solid rgba(124,240,255,.4); color:var(--photon); }

.play .fx{ opacity:0; animation:rise .55s cubic-bezier(.2,.8,.2,1) forwards; animation-delay:calc(var(--i) * 90ms); }
.play .pf-chip.fx{ animation-name:pop; }
.play .bar.fx{ transform-box:fill-box; transform-origin:bottom; animation-name:grow; animation-duration:.7s; }
.play .mk{ animation:slide 1.3s cubic-bezier(.2,.8,.2,1) both; }
@keyframes rise{ from{ opacity:0; transform:translateY(12px);} to{ opacity:1; transform:none;} }
@keyframes pop{ 0%{ opacity:0; transform:scale(.5);} 70%{ transform:scale(1.1);} 100%{ opacity:1; transform:scale(1);} }
@keyframes grow{ from{ opacity:0; transform:scaleY(0);} to{ opacity:1; transform:scaleY(1);} }
@keyframes slide{ from{ transform:translateX(var(--from)); opacity:.2;} to{ transform:none; opacity:1;} }
svg text{ font-family:'Space Grotesk',sans-serif; }
@media (prefers-reduced-motion: reduce){ .play .fx, .play .mk, #pf-bg .aurora, .pf-hero h1, .pf-pulse{ animation:none !important; opacity:1 !important; } }
</style>
"""


def _video_src():
    if LOCAL_VIDEO.exists():
        return "data:video/mp4;base64," + base64.b64encode(LOCAL_VIDEO.read_bytes()).decode()
    return VIDEO_URL


def setup():
    """Call once from app.py, right after st.set_page_config."""
    src = _video_src()
    video = f'<video autoplay muted loop playsinline><source src="{src}" type="video/mp4"></video>' if src else ""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div id="pf-bg"><div class="aurora"></div>{video}<div class="shade"></div></div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="pf-hero"><h1>ProvaFair</h1><p><span class="pf-pulse"></span>Every draw ships with its evidence: '
        "the physics test, the numbers behind it, and a tamper-evident record.</p></div>",
        unsafe_allow_html=True)
