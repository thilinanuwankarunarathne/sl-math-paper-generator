# -*- coding: utf-8 -*-
"""
media.py - Bunny.net Storage helpers + diagram (figure) renderer.
රූප සටහන් සාදා Bunny.net හි "maths" ෆෝල්ඩරයේ ගබඩා කරයි; ප්‍රශ්න පත්‍රය සාදන විට එතැනින් ලබා ගනී.

Config (env vars OR .streamlit/secrets.toml):
  BUNNY_STORAGE_ZONE  - storage zone name
  BUNNY_ACCESS_KEY    - the storage zone's *password* (Storage > FTP & API Access)
  BUNNY_REGION        - "" (Falkenstein, default) | ny | la | sg | syd | uk | se | br | jh
  BUNNY_CDN_URL       - pull zone URL, e.g. https://myzone.b-cdn.net
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests

FOLDER = "maths"
LOCAL_DIR = Path(__file__).with_name("images")


# ----------------------------------------------------------------------------
# Bunny.net
# ----------------------------------------------------------------------------
def cfg(key, default=""):
    v = os.getenv(key)
    if v:
        return v
    try:
        import streamlit as st
        return str(st.secrets.get(key, default))
    except Exception:
        return default


def bunny_ready():
    return bool(cfg("BUNNY_STORAGE_ZONE") and cfg("BUNNY_ACCESS_KEY") and cfg("BUNNY_CDN_URL"))


def _base():
    reg = cfg("BUNNY_REGION").strip()
    host = f"{reg}.storage.bunnycdn.com" if reg else "storage.bunnycdn.com"
    return f"https://{host}/{cfg('BUNNY_STORAGE_ZONE')}"


def _hdr():
    return {"AccessKey": cfg("BUNNY_ACCESS_KEY")}


def public_url(path):
    return f"{cfg('BUNNY_CDN_URL').rstrip('/')}/{path}"


def upload(path, data: bytes):
    r = requests.put(f"{_base()}/{path}", data=data, timeout=30,
                     headers={**_hdr(), "Content-Type": "application/octet-stream"})
    r.raise_for_status()


def list_remote():
    """Names of files already in the maths/ folder."""
    r = requests.get(f"{_base()}/{FOLDER}/", headers={**_hdr(), "Accept": "application/json"}, timeout=30)
    if r.status_code == 404:
        return set()
    r.raise_for_status()
    return {o["ObjectName"] for o in r.json()}


def image_path(kind, params):
    h = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    return f"{FOLDER}/{kind}_{h}.png"


def image_src(path, spec_json):
    """URL to show for a question image: Bunny CDN if configured, else local data-URI."""
    if bunny_ready():
        return public_url(path)
    f = LOCAL_DIR / path
    if not f.exists():
        spec = json.loads(spec_json)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(render(spec["kind"], spec["p"]))
    return "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()


# ----------------------------------------------------------------------------
# Diagram drawing (labels use digits/English letters only - no Sinhala font needed)
# ----------------------------------------------------------------------------
def _fig(w=3.6, h=3.0):
    fig, ax = plt.subplots(figsize=(w, h), dpi=110)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _png(fig):
    b = io.BytesIO()
    fig.savefig(b, format="png", bbox_inches="tight", facecolor="white", pad_inches=0.15)
    plt.close(fig)
    return b.getvalue()


def _txt(ax, P, c, text, k=0.35, **kw):
    """Text placed outside (k>0) or inside (k<0) a point P, relative to centre c."""
    v = np.array(P, float) - np.array(c, float)
    v = v / (np.linalg.norm(v) or 1)
    ax.text(*(np.array(P) + v * k), text, ha="center", va="center", fontsize=kw.pop("fs", 11), **kw)


def _poly(ax, pts, names):
    c = np.mean(pts, axis=0)
    arr = np.array(list(pts) + [pts[0]])
    ax.plot(arr[:, 0], arr[:, 1], "k-", lw=1.6)
    for p, n in zip(pts, names):
        _txt(ax, p, c, n, fontweight="bold")
    return c


def _side(ax, P, Q, c, text, k=0.3):
    m = np.array([(P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2])
    _txt(ax, m, c, text, k=k, fs=10, color="#1a4fa0")


def _right(ax, ab, bc, labels, ox=0.0, s=None, names="ABC"):
    """Right triangle, right angle at B. AB vertical, BC horizontal."""
    s = s or 3.5 / max(ab, bc)
    B, C, A = (ox, 0), (ox + bc * s, 0), (ox, ab * s)
    c = _poly(ax, [A, B, C], list(names))
    ax.add_patch(plt.Rectangle(B, .2, .2, fill=False, lw=1))
    _side(ax, A, B, c, labels[0])
    _side(ax, B, C, c, labels[1])
    _side(ax, A, C, c, labels[2])
    return A, B, C


def right_tri(p):
    fig, ax = _fig()
    A, B, C = _right(ax, p["ab"], p["bc"], [p["l_ab"], p["l_bc"], p["l_ac"]])
    if p.get("theta"):
        ax.text(C[0] - .8, C[1] + .15, "θ", fontsize=13)
    return _png(fig)


def similar(p):
    fig, ax = _fig(7, 3)
    s = 3.2 / max(p["t1"][0], p["t1"][1], p["t2"][0], p["t2"][1])
    _right(ax, p["t1"][0], p["t1"][1], p["l1"], 0, s, "ABC")
    _right(ax, p["t2"][0], p["t2"][1], p["l2"], p["t1"][1] * s + 1.3, s, "PQR")
    return _png(fig)


def tri_angles(p):
    A, B, C = (1.6, 3.0), (0, 0), (4, 0)
    fig, ax = _fig()
    c = _poly(ax, [A, B, C], list("ABC"))
    for P, key in ((A, "A"), (B, "B"), (C, "C")):
        _txt(ax, P, c, p[key], k=-0.75, fs=10, color="#b00020")
    if p.get("ext"):
        ax.plot([4, 5.6], [0, 0], "k-", lw=1.6)
        ax.text(5.8, 0, "D", fontweight="bold", va="center")
        ax.text(4.55, .3, p["ext"], fontsize=10, color="#b00020")
    return _png(fig)


def circle_angle(p):
    fig, ax = _fig()
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(2 * np.cos(t), 2 * np.sin(t), "k-", lw=1.4)
    O = (0, 0)
    pts = {n: (2 * np.cos(np.radians(a)), 2 * np.sin(np.radians(a))) for n, a in (("A", 215), ("B", 325), ("C", 90))}
    for a, b in (("C", "A"), ("C", "B")):
        ax.plot(*zip(pts[a], pts[b]), "k-", lw=1.4)
    for n in "AB":
        ax.plot(*zip(O, pts[n]), "k-", lw=1.4)
    ax.plot(0, 0, "ko", ms=3)
    for n, P in pts.items():
        _txt(ax, P, O, n, fontweight="bold")
    ax.text(.12, .12, "O", fontweight="bold")
    given_c = p["at"] == "C"
    ax.text(0, 1.35, p["val"] if given_c else "?", ha="center", color="#b00020", fontsize=10)
    ax.text(0, -.6, "?" if given_c else p["val"], ha="center", color="#b00020", fontsize=10)
    return _png(fig)


def cyclic(p):
    fig, ax = _fig()
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(2 * np.cos(t), 2 * np.sin(t), "k-", lw=1.2)
    ang = {"A": 120, "B": 200, "C": 320, "D": 50}
    pts = {n: (2 * np.cos(np.radians(a)), 2 * np.sin(np.radians(a))) for n, a in ang.items()}
    c = _poly(ax, [pts[n] for n in "ABCD"], list("ABCD"))
    for n in "ABCD":
        _txt(ax, pts[n], c, p[n], k=-0.75, fs=9, color="#b00020")
    return _png(fig)


def tangent(p):
    fig, ax = _fig()
    R = 2.0
    dd = R * p["d"] / p["r"]
    P = (dd, 0)
    T = (R * R / dd, R * np.sqrt(dd * dd - R * R) / dd)
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(R * np.cos(t), R * np.sin(t), "k-", lw=1.4)
    ax.plot([0, P[0]], [0, 0], "k--", lw=1)
    ax.plot([0, T[0]], [0, T[1]], "k-", lw=1.4)
    ax.plot([P[0], T[0]], [P[1], T[1]], "k-", lw=1.4)
    ax.text(-.2, -.25, "O", fontweight="bold")
    ax.text(P[0] + .1, -.25, "P", fontweight="bold")
    ax.text(T[0] - .1, T[1] + .2, "T", fontweight="bold")
    ax.text(T[0] / 2 - .35, T[1] / 2 + .05, p["l_r"], color="#1a4fa0", fontsize=10)
    ax.text(P[0] / 2, -.3, p["l_op"], color="#1a4fa0", fontsize=10, ha="center")
    ax.text((P[0] + T[0]) / 2 + .15, (P[1] + T[1]) / 2 + .1, p["l_pt"], color="#1a4fa0", fontsize=10)
    return _png(fig)


def chord(p):
    fig, ax = _fig()
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(2 * np.cos(t), 2 * np.sin(t), "k-", lw=1.4)
    my = -2 * p["om"] / p["r"]
    hx = np.sqrt(4 - my * my)
    A, B, M = (-hx, my), (hx, my), (0, my)
    ax.plot(*zip(A, B), "k-", lw=1.4)
    ax.plot([0, 0], [0, my], "k--", lw=1)
    ax.plot([0, B[0]], [0, B[1]], "k-", lw=1.2)
    for n, P, o in (("A", A, (-.25, -.15)), ("B", B, (.1, -.15)), ("M", M, (.1, -.3)), ("O", (0, 0), (.1, .1))):
        ax.text(P[0] + o[0], P[1] + o[1], n, fontweight="bold")
    ax.text(hx / 2 + .05, my / 2 + .15, p["l_r"], color="#1a4fa0", fontsize=10)
    ax.text(.1, my / 2, p["l_om"], color="#1a4fa0", fontsize=10)
    ax.text(0, my + .15, p["l_ab"], color="#1a4fa0", fontsize=10, ha="center")
    return _png(fig)


def para(p):
    A, B, C, D = (0, 0), (4, 0), (5.2, 2.4), (1.2, 2.4)
    fig, ax = _fig()
    c = _poly(ax, [A, B, C, D], list("ABCD"))
    for P, k in ((A, "A"), (B, "B"), (C, "C"), (D, "D")):
        _txt(ax, P, c, p[k], k=-0.8, fs=9, color="#b00020")
    return _png(fig)


def midpoint(p):
    A, B, C = (2, 3.2), (0, 0), (4.4, 0)
    P, Q = (1, 1.6), (3.2, 1.6)
    fig, ax = _fig()
    c = _poly(ax, [A, B, C], list("ABC"))
    ax.plot(*zip(P, Q), "k-", lw=1.4)
    for n, X, o in (("P", P, (-.3, 0)), ("Q", Q, (.3, 0))):
        ax.text(X[0] + o[0], X[1] + o[1], n, fontweight="bold", ha="center", va="center")
    ax.text(2.1, 1.8, p["l_pq"], color="#1a4fa0", fontsize=10, ha="center")
    ax.text(2.2, -.35, p["l_bc"], color="#1a4fa0", fontsize=10, ha="center")
    return _png(fig)


def graph(p):
    a, b, c, marks = p["a"], p["b"], p["c"], p.get("marks", [])
    xs = [m[0] for m in marks] + [0]
    lo, hi = min(xs) - 3, max(xs) + 3
    if a:
        xv = -b / (2 * a)
        lo, hi = min(lo, xv - 3), max(hi, xv + 3)
    X = np.linspace(lo, hi, 400)
    Y = a * X ** 2 + b * X + c
    fig, ax = plt.subplots(figsize=(3.8, 3.2), dpi=110)
    ax.plot(X, Y, color="#1a4fa0", lw=2)
    ys = [m[1] for m in marks] + [0]
    if a > 0:
        y0 = min(Y.min(), 0) - 1
        ax.set_ylim(y0, min(Y.max(), y0 + 16))
    elif a < 0:
        y1 = max(Y.max(), 0) + 1
        ax.set_ylim(max(Y.min(), y1 - 16), y1)
    else:
        ax.set_ylim(min(ys) - 3, max(ys) + 3)
    ax.set_xlim(lo, hi)
    for x0, y0 in marks:
        ax.plot(x0, y0, "ro")
        ax.annotate(f"({x0}, {y0})", (x0, y0), textcoords="offset points", xytext=(6, 6), fontsize=9)
    ax.axhline(0, color="k", lw=1)
    ax.axvline(0, color="k", lw=1)
    ax.grid(alpha=.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    return _png(fig)


def bar(p):
    fig, ax = plt.subplots(figsize=(4, 2.8), dpi=110)
    bars = ax.bar(p["labels"], p["values"], color="#3b7dd8")
    for b, v in zip(bars, p["values"]):
        ax.text(b.get_x() + b.get_width() / 2, v + .5, str(v), ha="center", fontsize=9)
    ax.set_ylim(0, max(p["values"]) * 1.2)
    ax.grid(axis="y", alpha=.3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return _png(fig)


RENDERERS = dict(right_tri=right_tri, similar=similar, tri_angles=tri_angles, circle_angle=circle_angle,
                 cyclic=cyclic, tangent=tangent, chord=chord, para=para, midpoint=midpoint,
                 graph=graph, bar=bar)


def render(kind, params) -> bytes:
    return RENDERERS[kind](params)