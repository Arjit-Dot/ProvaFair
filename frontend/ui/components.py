"""HTML/SVG building blocks. Every panel has a fixed height so layouts never shift."""
import html
import streamlit as st

LIMIT, QMAX = 2.0, 2.8284


def e(x):
    return html.escape(str(x))


def fx(i):
    return f'class="fx" style="--i:{i}"'


def panel(inner, fresh=False, tone="", h=360):
    return f'<div class="pf-panel {tone} {"play" if fresh else ""}" style="height:{h}px">{inner}</div>'


def empty_panel(text, busy=False, h=360):
    ring = "ring fast" if busy else "ring"
    bar = '<div class="pf-bar"><i></i></div>' if busy else ""
    return panel(f'<div class="pf-empty"><div class="{ring}"></div><div>{e(text)}</div>{bar}</div>', h=h)


def error_panel(msg, h=360):
    return panel(f'<div class="pf-empty"><div class="pf-verdict bad"><b>!</b></div><div>{e(msg)}</div></div>', tone="bad", h=h)


def chips(items, bad=False, start=0):
    cls = "pf-chip fx" + (" bad" if bad else "")
    return '<div class="pf-chips">' + "".join(
        f'<span class="{cls}" style="--i:{start + n}">{e(w)}</span>' for n, w in enumerate(items)) + "</div>"


def short(h, n=16):
    return f"{h[:n]}...{h[-6:]}" if h else "none"


# ----------------------------------------------------------------- gauge
def gauge_svg(S, margin, certified):
    X = lambda s: 30 + s / 3 * 580
    col = "#7cf0ff" if certified else "#ff4d6d"
    lo, hi = X(max(S - margin, 0)), X(min(S + margin, 3))
    return f"""
    <svg viewBox="0 0 640 150" width="100%" role="img" aria-label="CHSH score gauge">
      <rect x="{X(0)}" y="60" width="{X(2) - X(0)}" height="22" rx="4" fill="rgba(255,77,109,.22)"/>
      <rect x="{X(2)}" y="60" width="{X(3) - X(2)}" height="22" rx="4" fill="rgba(124,240,255,.18)"/>
      <rect x="{X(QMAX)}" y="60" width="{X(3) - X(QMAX)}" height="22" fill="rgba(255,255,255,.05)"/>
      <line x1="{X(LIMIT)}" y1="48" x2="{X(LIMIT)}" y2="96" stroke="#ff4d6d" stroke-width="2" stroke-dasharray="4 3"/>
      <line x1="{X(QMAX)}" y1="48" x2="{X(QMAX)}" y2="96" stroke="#7cf0ff" stroke-width="2" stroke-dasharray="4 3"/>
      <g fill="#8a9bb8" font-size="12" text-anchor="middle">
        {''.join(f'<text x="{X(t)}" y="108">{t}</text>' for t in (0, 1, 2, 3))}
      </g>
      <text x="{X(LIMIT)}" y="132" fill="#ff8da1" font-size="12" text-anchor="middle">S = 2 classical limit</text>
      <text x="{X(QMAX)}" y="132" fill="#7cf0ff" font-size="12" text-anchor="middle">S = 2.83 quantum max</text>
      <g class="mk" style="--from:{X(0) - X(S):.1f}px">
        <line x1="{lo}" y1="71" x2="{hi}" y2="71" stroke="{col}" stroke-width="3" stroke-linecap="round"/>
        <line x1="{lo}" y1="64" x2="{lo}" y2="78" stroke="{col}" stroke-width="2"/>
        <line x1="{hi}" y1="64" x2="{hi}" y2="78" stroke="{col}" stroke-width="2"/>
        <path d="M{X(S) - 7} 36 L{X(S) + 7} 36 L{X(S)} 52 Z" fill="{col}"/>
        <text x="{X(S)}" y="26" fill="{col}" font-size="15" font-weight="700" text-anchor="middle">S = {S:.3f} \u00b1 {margin:.3f}</text>
      </g>
    </svg>"""


def verdict_block(chsh, certified):
    tone = "ok" if certified else "bad"
    word = "DRAW CERTIFIED" if certified else "DRAW BLOCKED"
    sub = (f"S \u2212 3\u03c3 = {chsh['lower_bound']:.3f} is above 2, so the numbers are released."
           if certified else f"S \u2212 3\u03c3 = {chsh['lower_bound']:.3f} does not clear 2, so no numbers are released.")
    return (f'<div class="pf-verdict {tone} fx" style="--i:0"><b>{word}</b><span>{e(sub)}</span></div>'
            f'<div class="pf-note fx" style="--i:1">{e(chsh["rule"])}. The \u00b1 shown is 3\u03c3 (three standard errors).</div>'
            f'<div class="fx" style="--i:2">{gauge_svg(chsh["S"], chsh["margin"], certified)}</div>')


# ----------------------------------------------------------------- correlation table
def correlation_inner(chsh):
    rows = ""
    for i, r in enumerate(chsh["correlations"]):
        sgn = "+" if r["sign"] > 0 else "\u2212"
        rows += (f'<tr class="fx" style="--i:{i}"><td>E({r["pair"]})</td><td>{r["angle_a"]}\u00b0, {r["angle_b"]}\u00b0</td>'
                 f'<td>{r["n_same"]}/{r["n_diff"]}</td><td>{r["E"]:+.3f} \u00b1 {r["sigma"]:.3f}</td><td>{sgn}</td></tr>')
    cls = "" if chsh["certified"] else "bad"
    tone = "ok" if chsh["certified"] else "bad"
    return f"""
    <div class="pf-title">How the score is computed</div>
    <table class="pf-t"><tr><th>Term</th><th>Angles A, B</th><th>Same / differ</th><th>Correlation E</th><th>In S</th></tr>
    {rows}
    <tr class="total {cls} fx" style="--i:5"><td colspan="3">S = E(A0,B0) + E(A0,B1) + E(A1,B0) \u2212 E(A1,B1)</td>
    <td colspan="2">{chsh['S']:.4f} \u00b1 {chsh['sigma']:.4f}</td></tr></table>
    <div class="pf-formula fx" style="--i:6">E = (same \u2212 differ) / shots<br>\u03c3 = \u221a(\u03a3 (1 \u2212 E\u00b2) / shots)</div>
    <div class="pf-kv fx" style="--i:7">Shots: <b>{chsh['shots_per_setting']}</b> per setting, <b>{chsh['total_shots']}</b> in total</div>
    <div class="pf-rule {tone} fx" style="--i:8">{e(chsh['rule'])}: {chsh['S']:.3f} \u2212 {chsh['margin']:.3f} = {chsh['lower_bound']:.3f}
    ({'above' if chsh['certified'] else 'not above'} 2)</div>"""


# ----------------------------------------------------------------- circuit
def circuit_inner(info):
    img = (f'<img class="pf-img" src="data:image/png;base64,{info["png_b64"]}"/>' if info.get("png_b64")
           else f'<pre class="pf-circ">{e(info["text"])}</pre>')
    sets = " &nbsp;|&nbsp; ".join(f'{e(s["name"])} = {s["angle_deg"]}\u00b0' for s in info["settings"])
    return (f'<div class="pf-title">Qiskit circuit (setting A0, B0 shown)</div>{img}'
            f'<div class="pf-kv" style="margin-top:.6rem"><b>{e(info["caption"])}</b></div>'
            f'<div class="pf-note">Hadamard + CNOT make the Bell pair. The Ry gates choose the measurement angle. '
            f'Four angle pairs are run: {sets}.</div>')


# ----------------------------------------------------------------- histogram
def hist_svg(q, c, lo=1.5, hi=3.1, step=0.04):
    nb = int(round((hi - lo) / step))
    def bins(v):
        out = [0] * nb
        for x in v:
            out[min(max(int((x - lo) / step), 0), nb - 1)] += 1
        return out
    bq, bc = bins(q), bins(c)
    top = max(max(bq), max(bc), 1)
    W, H, L, B = 660, 280, 44, 40
    X = lambda s: L + (s - lo) / (hi - lo) * (W - L - 10)
    Y = lambda n: H - B - n / top * (H - B - 30)
    bw = (W - L - 10) / nb
    bars = ""
    for i in range(nb):
        for arr, col, op in ((bc, "#ff4d6d", .72), (bq, "#7cf0ff", .72)):
            if arr[i]:
                bars += (f'<rect class="bar fx" style="--i:{i // 2}" x="{L + i * bw + 1:.1f}" y="{Y(arr[i]):.1f}" '
                         f'width="{bw - 2:.1f}" height="{H - B - Y(arr[i]):.1f}" fill="{col}" opacity="{op}" rx="2"/>')
    ticks = "".join(f'<text x="{X(t)}" y="{H - 20}" fill="#8a9bb8" font-size="12" text-anchor="middle">{t}</text>'
                    for t in (1.5, 2.0, 2.5, 3.0))
    return f"""<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Histogram of S, quantum versus classical">
      <line x1="{L}" y1="{H - B}" x2="{W - 10}" y2="{H - B}" stroke="rgba(160,200,255,.3)"/>
      {bars}{ticks}
      <line x1="{X(2)}" y1="20" x2="{X(2)}" y2="{H - B}" stroke="#ff8da1" stroke-width="2" stroke-dasharray="5 4"/>
      <line x1="{X(QMAX)}" y1="20" x2="{X(QMAX)}" y2="{H - B}" stroke="#7cf0ff" stroke-width="2" stroke-dasharray="5 4"/>
      <text x="{X(2) - 6}" y="16" fill="#ff8da1" font-size="12" text-anchor="end">S = 2 limit</text>
      <text x="{X(QMAX) + 6}" y="16" fill="#7cf0ff" font-size="12">S = 2.83 max</text>
      <text x="{(W + L) / 2}" y="{H - 3}" fill="#8a9bb8" font-size="12" text-anchor="middle">CHSH score S per run</text>
      <text x="14" y="{(H - B) / 2 + 20}" fill="#8a9bb8" font-size="12" text-anchor="middle" transform="rotate(-90 14 {(H - B) / 2 + 20})">runs</text>
    </svg>"""


def stat_cards(m, label, cls):
    return (f'<div class="pf-stat"><div><div class="n {cls}">{m["mean"]:.3f}</div><div class="l">{label} mean S</div></div>'
            f'<div><div class="n {cls}">{m["std"]:.3f}</div><div class="l">spread (std dev)</div></div>'
            f'<div><div class="n {cls}">{m["passed"]}</div><div class="l">passed the 3\u03c3 rule</div></div>'
            f'<div><div class="n {cls}">{m["failed"]}</div><div class="l">blocked</div></div></div>')


# ----------------------------------------------------------------- randomness tests
def tests_inner(r, title):
    cards = ""
    for i, t in enumerate(r["tests"]):
        pill = '<span class="pill ok">PASS</span>' if t["passed"] else '<span class="pill bad">FAIL</span>'
        p = f' p = {t["p_value"]}' if t["p_value"] is not None else ""
        cards += (f'<div class="pf-test fx" style="--i:{i + 1}"><div><div class="nm">{e(t["name"])}</div>'
                  f'<div class="dt">{e(t["detail"])}{p}</div></div>{pill}</div>')
    frac = r["ones_fraction"]
    meter = f'<div class="pf-meter fx" style="--i:4"><u></u><i style="left:{frac * 100:.1f}%"></i></div>'
    return (f'<div class="pf-title fx" style="--i:0">{e(title)}: {r["n_bits"]} bits, {frac * 100:.1f}% ones</div>'
            f'{cards}{meter}<div class="pf-note fx" style="--i:5">Needle = share of 1s. The grey line marks 50%.</div>')


# ----------------------------------------------------------------- ledger card
def link_card(ent, idx, status, i):
    tone = {"ok": "ok", "bad": "bad", "idle": ""}[status[0]]
    pill = {"ok": '<span class="pill ok">VERIFIED</span>', "idle": '<span class="pill idle">UNCHECKED</span>',
            "bad": f'<span class="pill bad">{e(status[1])}</span>'}[status[0]]
    tam = ' <span class="pill warn">EDITED</span>' if ent.get("tampered") else ""
    return (f'<div class="pf-link {tone} fx" style="--i:{i}"><div class="top"><span><b>#{idx}</b> {e(ent["draw_id"])} '
            f'<span class="pf-note">{e(ent["status"])}, S = {ent["chsh_score"]}</span>{tam}</span>{pill}</div>'
            f'<div class="h"><em>hash </em>{e(short(ent["hash"], 24))}<br><em>prev </em>{e(short(ent["prev_hash"], 24))}</div></div>')
