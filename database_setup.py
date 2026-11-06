# -*- coding: utf-8 -*-
"""
database_setup.py
=================
Incremental, high-speed question bank generator for Grade 10 & 11 Sri Lankan Maths.
Every run APPENDS new unique questions using a fresh seed and MD5 content hashing.

Usage:
  python database_setup.py                        # Appends ~11,000 new unique questions
  python database_setup.py --per-lesson 500       # Appends ~28,500 new unique questions
  python database_setup.py --target-total 1000000 # Loops in batches until DB hits 1,000,000 questions
  python database_setup.py --reset                # Wipes DB and starts fresh
"""
import argparse
import hashlib
import json
import random
import sqlite3
import time
from pathlib import Path

import sympy as sp
from media import image_path

try:
    from long_questions import LONG_ROWS, LONG_PER_LESSON
except ImportError:
    LONG_ROWS, LONG_PER_LESSON = [], 40

DB_PATH = Path(__file__).with_name("exam_questions.db")
PER_LESSON = 150
DIFFS = ["Easy", "Average", "Advance"]
DIFF_SI = {"Easy": "පහසු", "Average": "සාමාන්‍ය", "Advance": "දුෂ්කර (තාර්කික)"}

SYLLABUS = {
    10: ["පරිමිතිය", "වර්ගමූලය", "භාග", "ද්වීපද ප්‍රකාශන", "ත්‍රිකෝණ අංගසාම්‍යය", "වර්ගඵලය",
         "වර්ගජ ප්‍රකාශනවල සාධක", "ත්‍රිකෝණ I", "ත්‍රිකෝණ II", "ප්‍රතිලෝම සමානුපාත", "දත්ත නිරූපණය",
         "වීජීය ප්‍රකාශනවල කුඩා පොදු ගුණාකාරය (කු.පො.ගු.)", "වීජීය භාග", "ප්‍රතිශත", "සමීකරණ",
         "සමාන්තරාස්‍ර I", "සමාන්තරාස්‍ර II", "කුලක", "ලඝුගණක I", "ලඝුගණක II", "ප්‍රස්තාර", "සීඝ්‍රතාව",
         "සූත්‍ර", "සමාන්තර ශ්‍රේණි", "වීජීය අසමානතා", "සංඛ්‍යාත ව්‍යාප්ති", "වෘත්තයක ජ්‍යාය", "නිර්මාණ",
         "පෘෂ්ඨයක වර්ගඵලය හා පරිමාව", "සම්භාවිතාව", "වෘත්තයක කෝණ", "පරිමාණ රූප"],
    11: ["තාත්වික සංඛ්‍යා", "දර්ශක හා ලඝුගණක I", "දර්ශක හා ලඝුගණක II", "ඝන වස්තුවල පෘෂ්ඨ වර්ගඵලය",
         "ඝන වස්තුවල පරිමාව", "ද්විපද ප්‍රකාශන", "වීජීය භාග", "සමාන්තර රේඛා අතර තල රූපවල වර්ගඵලය",
         "ප්‍රතිශත (හීන වන ශේෂ ක්‍රමයට පොළිය)", "කොටස් වෙළෙඳපොළ", "මධ්‍ය ලක්ෂ්‍ය ප්‍රමේයය", "ප්‍රස්තාර",
         "සමීකරණ", "සමකෝණී ත්‍රිකෝණ", "දත්ත නිරූපණය හා අර්ථකථනය", "ගුණෝත්තර ශ්‍රේණි", "පයිතගරස් ප්‍රමේයය",
         "ත්‍රිකෝණමිතිය", "න්‍යාස", "අසමානතා", "වෘත්ත චතුරස්‍ර", "ස්පර්ශක", "නිර්මාණ", "කුලක", "සම්භාවිතාව"],
}

x, y = sp.symbols("x y")
A_, B_ = sp.symbols("a b")
DEG = "^\\circ"


def L(e):
    return sp.latex(e)


def F(a, b):
    return "\\frac{%s}{%s}" % (a, b)


PI = F(22, 7)
TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (12, 35, 37), (9, 40, 41), (11, 60, 61)]
CHORD = [(5, 3, 4), (13, 5, 12), (17, 8, 15), (25, 7, 24), (29, 20, 21), (37, 12, 35), (41, 9, 40)]


def mk(content, steps, qtype="ව්‍යුහගත", img=None):
    return dict(content=content, steps=steps, qtype=qtype, img=img)


def table(head, rows):
    return ("| " + " | ".join(map(str, head)) + " |\n|" + "---|" * len(head) + "\n" +
            "\n".join("| " + " | ".join(map(str, rw)) + " |" for rw in rows))


def divisors(n):
    return [i for i in range(1, n + 1) if n % i == 0]


def money(v):
    return f"{float(v):,.2f}"


# =============================================================================
# GRADE 10 BUILDERS (d=0: Easy, d=1: Average, d=2: Advance Logical Thinking)
# =============================================================================
def b_perimeter(r, d):
    if d == 0:
        l, w = r.randint(5, 120), r.randint(3, 90)
        return mk(f"සෘජුකෝණාස්‍රාකාර ඉඩමක දිග ${l}$ m ද පළල ${w}$ m ද වේ. එහි පරිමිතිය සොයන්න.",
                  [("$P=2(l+w)$", 1), (f"$P=2({l}+{w})={2*(l+w)}$ m", 1)])
    k = r.randint(1, 80)
    R = 7 * k
    if d == 1:
        return mk(f"අරය ${R}$ cm වන වෘත්තයක පරිධිය සොයන්න. ($\\pi={PI}$)",
                  [("$C=2\\pi r$", 1), (f"$C=2\\times{PI}\\times{R}={44*k}$ cm", 2)])
    # Advance Logical: Composite shape (Rectangle + Semicircular cutout / attachment) or Algebraic ratio
    if r.random() < 0.5:
        L_rect = r.randint(15, 90)
        D_semi = 14 * k
        arc = 22 * k
        tot_p = 2 * L_rect + D_semi + arc
        return mk(f"දිග ${L_rect}$ cm හා පළල ${D_semi}$ cm වූ සෘජුකෝණාස්‍රාකාර තහඩුවක එක් පළල පාදයක් විෂ්කම්භය වන සේ "
                  f"අර්ධ වෘත්තාකාර කොටසක් කපා ඉවත් කර ඇත. ඉතිරි තහඩුවේ පරිමිතිය සොයන්න. ($\\pi={PI}$)",
                  [(f"අර්ධ වෘත්තාකාර චාප දිග $=\\frac{{1}}{{2}}\\times 2\\pi r = {PI}\\times{7*k}={arc}$ cm", 2),
                   (f"මුළු පරිමිතිය $= {L_rect}+{L_rect}+{D_semi}+{arc} = {tot_p}$ cm", 2)])
    else:
        diff = r.randint(4, 40)
        w = r.randint(6, 60)
        l = w + diff
        P = 2 * (l + w)
        return mk(f"සෘජුකෝණාස්‍රයක දිග, එහි පළලට වඩා ${diff}$ cm කින් වැඩිය. එහි පරිමිතිය ${P}$ cm නම්, "
                  f"සෘජුකෝණාස්‍රයේ දිග සහ පළල වෙන වෙනම සොයන්න.",
                  [(f"පළල $x$ නම් දිග $x+{diff}$ වේ. $2(x + x + {diff}) = {P}$", 1),
                   (f"$2x + {diff} = {P//2} \\Rightarrow 2x = {2*w}$", 1),
                   (f"පළල $={w}$ cm, දිග $={l}$ cm", 2)])


def b_sqrt(r, d):
    if d == 0:
        n = r.randint(11, 250)
        return mk(f"අගය සොයන්න: $\\sqrt{{{n*n}}}$", [(f"${n*n}={n}^2$", 1), (f"$\\sqrt{{{n*n}}}={n}$", 1)])
    a, b = r.randint(2, 25), r.choice([2, 3, 5, 6, 7, 10, 11, 13])
    if d == 1:
        return mk(f"සුළු කරන්න: $\\sqrt{{{a*a*b}}}$",
                  [(f"${a*a*b}={a*a}\\times{b}$", 1), (f"$\\sqrt{{{a*a}}}\\times\\sqrt{{{b}}}={a}\\sqrt{{{b}}}$", 2)])
    # Advance Logical: Solving for unknown parameter inside radical equation
    c = r.randint(2, 20)
    k_val = (a + c) ** 2 * b
    return mk(f"$\\sqrt{{{a*a*b}}} + \\sqrt{{{c*c*b}}} = \\sqrt{{k}}$ නම් $k$ හි සංඛ්‍යාත්මක අගය සොයන්න.",
              [(f"$\\sqrt{{{a*a*b}}}={a}\\sqrt{{{b}}}$ සහ $\\sqrt{{{c*c*b}}}={c}\\sqrt{{{b}}}$", 1),
               (f"වම් පස $={(a+c)}\\sqrt{{{b}}} = \\sqrt{{{(a+c)**2}\\times{b}}}$", 2),
               (f"$\\therefore k = {k_val}$", 1)])


def b_fraction(r, d):
    if d < 2:
        p = sp.Rational(r.randint(1, 25), r.randint(2, 25))
        q = sp.Rational(r.randint(1, 25), r.randint(2, 25))
        op, ans = [("+", p + q), ("\\times", p * q)][d]
        return mk(f"සුළු කරන්න: ${L(p)}{op}{L(q)}$",
                  [("පොදු හරය / ගුණිතය සැකසීම", 1), (f"පිළිතුර: ${L(ans)}$", 2)])
    # Advance Logical: Remainder word problem
    b1 = r.choice([3, 4, 5, 6, 8])
    a1 = r.randint(1, b1 - 1)
    b2 = r.choice([3, 4, 5, 7])
    a2 = r.randint(1, b2 - 1)
    f1 = sp.Rational(a1, b1)
    rem1 = 1 - f1
    f2 = rem1 * sp.Rational(a2, b2)
    rem_final = 1 - (f1 + f2)
    mult = r.randint(2, 25) * 100
    total_money = int(rem_final.q * mult)
    left_money = int(rem_final.p * mult)
    return mk(f"මිනිසෙක් තමා සතු මුදලින් ${L(f1)}$ ක් ආහාර සඳහා ද, ඉතිරි මුදලින් ${F(a2, b2)}$ ක් ප්‍රවාහනය සඳහා ද වැය කළේය. "
              f"දැන් ඔහු අත රු. ${left_money}$ ක් ඉතිරිව ඇත්නම්, මුලදී ඔහු සතුව තිබූ මුළු මුදල සොයන්න.",
              [(f"ආහාර වලට පසු ඉතිරිය $= 1 - {L(f1)} = {L(rem1)}$", 1),
               (f"ප්‍රවාහනයට වැය කළ කොටස $= {L(rem1)} \\times {F(a2, b2)} = {L(f2)}$", 1),
               (f"අවසාන ඉතිරි භාගය $= {L(rem1)} - {L(f2)} = {L(rem_final)}$", 1),
               (f"මුළු මුදල $= {left_money} \\div {L(rem_final)} = \\text{{රු. }}{total_money}$", 1)])


def b_binomial(r, d):
    a, b = r.randint(1, 20), r.randint(1, 20)
    if d < 2:
        e = [(x + a) * (x + b), (r.randint(2, 6) * x + a) * (r.randint(2, 6) * x - b)][d]
        return mk(f"ප්‍රසාරණය කර සුළු කරන්න: ${L(e)}$",
                  [("පද ගුණ කිරීම", 1), (f"${L(sp.expand(e))}$", 2)])
    # Advance Logical: Reciprocal identity x + 1/x = k -> find x^2 + 1/x^2
    k = r.randint(3, 25)
    return mk(f"$x + \\frac{{1}}{{x}} = {k}$ නම්, ද්විපද ප්‍රසාරණය භාවිතයෙන් $x^2 + \\frac{{1}}{{x^2}}$ හි අගය සොයන්න.",
              [(f"දෙපසම වර්ග කිරීමෙන්: $\\left(x + \\frac{{1}}{{x}}\\right)^2 = {k}^2$", 1),
               (f"$x^2 + 2(x)\\left(\\frac{{1}}{{x}}\\right) + \\frac{{1}}{{x^2}} = {k*k}$", 1),
               (f"$x^2 + \\frac{{1}}{{x^2}} = {k*k} - 2 = {k*k - 2}$", 2)])


def b_congr(r, d):
    p, q, a = r.randint(3, 35), r.randint(3, 35), r.randrange(25, 135, 5)
    if d < 2:
        return mk(f"ABC හා PQR ත්‍රිකෝණවල $AB=PQ={p}$ cm, $\\angle B=\\angle Q={a}{DEG}$, $BC=QR={q}$ cm වේ. "
                  f"ත්‍රිකෝණ දෙක අංගසම බව සාධනය කරන්න.",
                  [("$AB=PQ$ (දී ඇත)", 1), (f"$\\angle ABC=\\angle PQR={a}{DEG}$ (දී ඇත)", 1), ("$BC=QR$ (දී ඇත)", 1),
                   ("$\\therefore \\triangle ABC\\equiv\\triangle PQR$ (පා.කෝ.පා.)", 1)], "සාධන")
    # Advance Logical Proof + Algebraic deduction
    x0 = r.randint(5, 25)
    k1 = r.randint(2, 5)
    c1 = p - k1 * x0
    return mk(f"AB හා CD රේඛා O හිදී එකිනෙක සමච්ඡේදනය වේ. (i) $\\triangle AOC \\equiv \\triangle BOD$ බව සාධනය කරන්න. "
              f"(ii) $AC = {p}$ cm සහ $BD = ({L(k1*x + c1)})$ cm නම් $x$ හි අගය සොයන්න.",
              [("$AO = OB$ සහ $CO = OD$ (දත්තය), $\\angle AOC = \\angle BOD$ (ප්‍රතිමුඛ කෝණ)", 2),
               ("$\\therefore \\triangle AOC \\equiv \\triangle BOD$ (පා.කෝ.පා.)", 1),
               (f"අනුරූප පාද සමාන බැවින් $AC = BD \\Rightarrow {L(k1*x + c1)} = {p} \\Rightarrow x = {x0}$", 1)], "සාධන")


def b_area(r, d):
    if d == 0:
        b, h = 2 * r.randint(2, 40), r.randint(3, 50)
        return mk(f"ත්‍රිකෝණයක පාදම ${b}$ cm ද උස ${h}$ cm ද වේ. එහි වර්ගඵලය සොයන්න.",
                  [(f"$A={F(1,2)}bh = {b*h//2}$ cm$^2$", 2)])
    if d == 1:
        a, b, h = r.randint(3, 40), r.randint(8, 50), r.randint(3, 35)
        return mk(f"සමාන්තර පාද ${a}$ cm හා ${b}$ cm ද ලම්බ දුර ${h}$ cm ද වන ත්‍රපීසියමක වර්ගඵලය සොයන්න.",
                  [(f"$A={F(1,2)}({a}+{b})\\times{h} = {L(sp.Rational((a+b)*h, 2))}$ cm$^2$", 3)])
    # Advance Logical: Uniform path around a rectangular garden
    L_in, W_in, path_w = r.randint(10, 60), r.randint(8, 45), r.randint(1, 5)
    L_out, W_out = L_in + 2 * path_w, W_in + 2 * path_w
    area_path = L_out * W_out - L_in * W_in
    return mk(f"දිග ${L_in}$ m හා පළල ${W_in}$ m වූ සෘජුකෝණාස්‍රාකාර ගෙවත්තක් වටා පිටතින් පළල ${path_w}$ m ක් වූ "
              f"ඒකාකාර පාරක් ඉදිකර ඇත. පාරේ වර්ගඵලය පමණක් සොයන්න.",
              [(f"පාර සහිත පිටත දිග $={L_in}+2({path_w})={L_out}$ m, පිටත පළල $={W_out}$ m", 1),
               (f"පිටත වර්ගඵලය $={L_out}\\times{W_out}={L_out*W_out}$ m$^2$, ඇතුළත වර්ගඵලය $={L_in*W_in}$ m$^2$", 2),
               (f"පාරේ වර්ගඵලය $={L_out*W_out}-{L_in*W_in}={area_path}$ m$^2$", 1)])


def b_factor(r, d):
    a, b = r.randint(1, 20), r.choice([-1, 1]) * r.randint(1, 20)
    if d < 2:
        c = 1 if d == 0 else r.randint(2, 5)
        e = sp.expand((c * x + a) * (x + b))
        return mk(f"සාධක සොයන්න: ${L(e)}$",
                  [("සාධක වෙන් කිරීම", 1), (f"${L(sp.factor(e))}$", 2)])
    # Advance Logical: Difference of two squares mental evaluation or grouping
    base = r.choice([100, 200, 500, 1000])
    k = r.randint(1, 15)
    n1, n2 = base - k, k
    val = (n1 + n2) * (n1 - n2)
    return mk(f"වර්ග දෙකක අන්තරයේ සාධක දැනුම භාවිතයෙන් ගුණ නොකර අගය සොයන්න: ${n1}^2 - {n2}^2$",
              [("$a^2 - b^2 = (a+b)(a-b)$ සූත්‍රය ආදේශ කිරීම", 1),
               (f"$= ({n1}+{n2})({n1}-{n2}) = {n1+n2} \\times {n1-n2}$", 1),
               (f"$= {val}$", 2)])


def b_tri_angle(r, d):
    if d == 0:
        a, b = r.randint(20, 85), r.randint(20, 75)
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ $\\angle A={a}{DEG}$ ද $\\angle B={b}{DEG}$ ද නම් $\\angle C$ සොයන්න.",
                  [("අභ්‍යන්තර කෝණ ඓක්‍යය $180^\\circ$", 1), (f"$\\angle C={180-a-b}{DEG}$", 2)],
                  img=("tri_angles", {"A": f"{a}°", "B": f"{b}°", "C": "?"}))
    if d == 1:
        a, b = r.randint(20, 85), r.randint(20, 75)
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ BC පාදය D දක්වා දික් කර ඇත. $\\angle A={a}{DEG}$, $\\angle B={b}{DEG}$ නම් "
                  f"බාහිර කෝණය $\\angle ACD$ සොයන්න.",
                  [("බාහිර කෝණය = සම්මුඛ අභ්‍යන්තර කෝණ ඓක්‍යය", 1), (f"$\\angle ACD={a+b}{DEG}$", 2)],
                  img=("tri_angles", {"A": f"{a}°", "B": f"{b}°", "C": "", "ext": "?"}))
    # Advance Logical: Angle bisector theorem in triangle (∠BOC = 90 + A/2)
    A_ang = 2 * r.randint(15, 65)
    ans = 90 + A_ang // 2
    return mk(f"ABC ත්‍රිකෝණයේ $\\angle A = {A_ang}{DEG}$ වේ. $\\angle ABC$ සහ $\\angle ACB$ හි කෝණ සමච්ඡේදක O හිදී හමුවේ නම්, "
              f"$\\angle BOC$ හි අගය තාර්කිකව සොයන්න.",
              [(f"$\\angle B + \\angle C = 180^\\circ - {A_ang}^\\circ = {180-A_ang}^\\circ$", 1),
               (f"$\\frac{{1}}{{2}}(\\angle B + \\angle C) = {(180-A_ang)//2}^\\circ$", 1),
               (f"$\\triangle BOC$ හි $\\angle BOC = 180^\\circ - {(180-A_ang)//2}^\\circ = {ans}{DEG}$", 2)])


def b_tri2(r, d):
    if d == 0:
        a = 2 * r.randint(10, 55)
        return mk(f"AB=AC වන ABC සමද්විපාද ත්‍රිකෝණයේ $\\angle A={a}{DEG}$ නම් $\\angle B$ සොයන්න.",
                  [("$\\angle B=\\angle C$", 1), (f"$\\angle B={90-a//2}{DEG}$", 2)])
    if d == 1:
        b = r.randint(20, 80)
        return mk(f"AB=AC වන ABC ත්‍රිකෝණයේ $\\angle B={b}{DEG}$ නම් $\\angle A$ සොයන්න.",
                  [(f"$\\angle C={b}{DEG}$", 1), (f"$\\angle A={180-2*b}{DEG}$", 2)])
    # Advance Logical: Exterior angle of isosceles triangle with algebra
    x0 = r.randint(6, 22)
    k1 = r.randint(2, 4)
    a = r.randint(2, 20)
    B_val = k1 * x0 + a
    if B_val >= 85:
        x0 = 8
        B_val = k1 * x0 + a
    ext_A = 2 * B_val
    return mk(f"AB=AC වන ABC සමද්විපාද ත්‍රිකෝණයේ BA පාදය D දක්වා දික් කර ඇත. බාහිර කෝණය $\\angle CAD = {ext_A}{DEG}$ වන අතර "
              f"$\\angle B = ({L(k1*x+a)}){DEG}$ නම් $x$ හි අගය සොයන්න.",
              [("$AB=AC$ බැවින් $\\angle B = \\angle C$", 1),
               (f"බාහිර කෝණ ප්‍රමේයයෙන් $\\angle CAD = \\angle B + \\angle C = 2\\angle B = {ext_A}{DEG}$", 1),
               (f"${L(k1*x+a)} = {B_val} \\Rightarrow x = {x0}$", 2)])


def b_inverse(r, d):
    if d == 0:
        a, days = r.choice([2, 3, 4, 5, 6, 8, 9, 10, 12, 15]), r.randint(4, 40)
        tot = a * days
        b = r.choice([v for v in divisors(tot) if v != a and v <= 80] or [a])
        return mk(f"සේවකයන් ${a}$ දෙනෙකුට වැඩක් දින ${days}$ කින් නිම කළ හැක. සේවකයන් ${b}$ දෙනෙකුට එම වැඩ නිම කිරීමට දින කීයක් ගතවේද?",
                  [(f"මුළු වැඩ $={a}\\times{days}={tot}$ මිනිස්-දින", 2), (f"දින ගණන $={tot//b}$", 2)])
    if d == 1:
        v, t, u = r.randrange(20, 140, 5), r.randint(2, 12), r.randrange(20, 140, 5)
        return mk(f"වේගය පැයට ${v}$ km වූ වාහනයකට ගමනක් යාමට පැය ${t}$ ක් ගතවේ. වේගය පැයට ${u}$ km නම් ගතවන කාලය සොයන්න.",
                  [(f"දුර $={v*t}$ km", 2), (f"කාලය $={L(sp.Rational(v*t,u))}$ පැය", 2)])
    # Advance Logical: Workers leaving mid-project
    men = r.randint(8, 25)
    total_days = r.randint(12, 30)
    worked_days = r.randint(3, total_days - 5)
    rem_days_orig = total_days - worked_days
    left_men = r.randint(2, men - 3)
    rem_men = men - left_men
    rem_work = men * rem_days_orig
    ans = sp.Rational(rem_work, rem_men)
    return mk(f"මිනිසුන් ${men}$ දෙනෙකුට වැඩක් දින ${total_days}$ කින් නිම කිරීමට ඇස්තමේන්තු කර ඇත. ඔවුන් දින ${worked_days}$ ක් වැඩ කළ පසු "
              f"මිනිසුන් ${left_men}$ දෙනෙක් ඉවත්ව ගියහ. ඉතිරි වැඩ කොටස නිම කිරීමට ඉතිරි මිනිසුන්ට තව දින කීයක් ගතවේද?",
              [(f"මුළු මිනිස්-දින $={men}\\times{total_days}={men*total_days}$", 1),
               (f"දින ${worked_days}$ කට පසු ඉතිරි මිනිස්-දින $={men}\\times({total_days}-{worked_days})={rem_work}$", 1),
               (f"ඉතිරි මිනිසුන් ගණන $={men}-{left_men}={rem_men}$", 1),
               (f"ගතවන දින ගණන $={F(rem_work, rem_men)}={L(ans)}$", 1)])


def b_datarep(r, d):
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    v = [r.randint(5, 95) for _ in labels]
    s = sum(v)
    head = "පසුගිය සතියේ දිනපතා විකුණුණු පොත් ගණන රූපයේ තීරු ප්‍රස්ථාරයෙන් දැක්වේ. "
    img = ("bar", {"labels": labels, "values": v})
    if d == 0:
        return mk(head + "සතිය තුළ විකුණුණු මුළු පොත් ගණන සොයන්න.",
                  [("තීරු අගයන් කියවීම", 1), (f"මුළු ගණන $={s}$", 2)], img=img)
    if d == 1:
        return mk(head + "දිනකට විකුණුණු පොත් ගණනේ මධ්‍යනය සොයන්න.",
                  [(f"මුළු ගණන $={s}$", 1), (f"මධ්‍යනය $={L(sp.Rational(s,5))}$", 2)], img=img)
    target_mean = r.randint(30, 80)
    sat_needed = max(5, 6 * target_mean - s)
    actual_new_mean = sp.Rational(s + sat_needed, 6)
    return mk(head + f"සෙනසුරාදා දිනයේත් පොත් විකිණීමෙන් පසු දින 6 මධ්‍යනය ${L(actual_new_mean)}$ ක් වූයේ නම්, "
              f"සෙනසුරාදා විකුණූ පොත් ගණන සොයන්න.",
              [(f"මුල් දින 5 මුළු පොත් ගණන $={s}$", 1),
               (f"දින 6 මුළු පොත් ගණන $=6 \\times {L(actual_new_mean)} = {s + sat_needed}$", 2),
               (f"සෙනසුරාදා විකුණූ ගණන $={s+sat_needed}-{s}={sat_needed}$", 1)], img=img)


def b_lcm(r, d):
    if d == 0:
        c1, c2 = r.randint(2, 20), r.randint(2, 20)
        i, j, k, l = [r.randint(1, 5) for _ in range(4)]
        e1, e2 = c1 * A_ ** i * B_ ** j, c2 * A_ ** k * B_ ** l
        return mk(f"කු.පො.ගු. සොයන්න: ${L(e1)}$ සහ ${L(e2)}$",
                  [(f"කු.පො.ගු. $={L(sp.lcm(e1, e2))}$", 3)])
    p, q, s = r.sample(range(1, 20), 3)
    if d == 1:
        e1, e2 = (x + p) * (x + q), (x + q) * (x + s)
    else:
        e1, e2 = sp.expand((x - p) * (x + q)), sp.expand(x ** 2 - p * p)
    return mk(f"කු.පො.ගු. සොයන්න: ${L(e1)}$ සහ ${L(e2)}$",
              [(f"සාධක: ${L(sp.factor(e1))}$ ; ${L(sp.factor(e2))}$", 2),
               (f"කු.පො.ගු. $={L(sp.factor(sp.lcm(sp.expand(e1), sp.expand(e2))))}$", 2)])


def b_algfrac(r, d):
    a, b = r.randint(1, 15), r.randint(1, 15)
    if d == 0:
        n, m = x ** 2 + (a + b) * x + a * b, x + a
        return mk(f"සුළු කරන්න: ${F(L(n), L(m))}$",
                  [(f"ලවයේ සාධක: ${L(sp.factor(n))}$", 1), (f"පිළිතුර: ${L(sp.cancel(n / m))}$", 2)])
    if d == 1:
        c1, c2 = r.randint(1, 6), r.randint(1, 6)
        n, m = c1 * (x ** 2 - a * a), c2 * (x ** 2 + a * x)
        return mk(f"සුළු කරන්න: ${F(L(n), L(m))}$",
                  [(f"සාධක: ${L(sp.factor(n))}$ හා ${L(sp.factor(m))}$", 2), (f"${L(sp.cancel(n / m))}$", 1)])
    # Advance Logical: Subtraction with quadratic denominator x^2 - a^2
    k1, k2 = r.randint(2, 9), r.randint(1, 8)
    expr = sp.Rational(k1) / (x ** 2 - a ** 2) - sp.Rational(k2) / (x - a)
    simp = sp.together(expr)
    return mk(f"තනි භාගයක් ලෙස සුළු කරන්න: $\\frac{{{k1}}}{{x^2-{a*a}}} - \\frac{{{k2}}}{{x-{a}}}$",
              [(f"$x^2-{a*a} = (x-{a})(x+{a})$ බැවින් පොදු හරය $(x-{a})(x+{a})$ ගැනීම", 1),
               (f"ලවය $= {k1} - {k2}(x+{a}) = {L(sp.expand(k1 - k2*(x+a)))}$", 2),
               (f"පිළිතුර: ${L(simp)}$", 1)])


def b_percent(r, d):
    P, p = r.randint(2, 200) * 100, r.randrange(5, 60, 5)
    inc = P * p // 100
    if d == 0:
        return mk(f"රු. ${P}$ ක් වූ භාණ්ඩයක මිල ${p}\\%$ කින් වැඩි කළ විට නව මිල සොයන්න.",
                  [(f"වැඩිවීම $={inc}$", 1), (f"නව මිල $={P+inc}$", 2)])
    if d == 1:
        return mk(f"රු. ${P}$ ක් වූ භාණ්ඩයක් ${p}\\%$ ක වට්ටමකට විකුණන ලදී. විකුණුම් මිල සොයන්න.",
                  [(f"වට්ටම $={inc}$", 1), (f"විකුණුම් මිල $={P-inc}$", 2)])
    # Advance Logical: Markup then discount -> net profit
    cost = r.randint(10, 150) * 100
    markup = r.choice([20, 25, 30, 40, 50])
    disc = r.choice([5, 10, 15, 20])
    marked = cost * (100 + markup) // 100
    sell = marked * (100 - disc) // 100
    profit = sell - cost
    return mk(f"වෙළෙන්දෙක් රු. ${cost}$ කට ගත් භාණ්ඩයක මිල ${markup}\\%$ ක ලාභයක් තබා ලකුණු කර, විකිණීමේදී ලකුණු කළ මිලෙන් "
              f"${disc}\\%$ ක වට්ටමක් ලබා දෙයි. ඔහුට ලැබෙන සත්‍ය ලාභය සොයන්න.",
              [(f"ලකුණු කළ මිල $= {cost} \\times \\frac{{{100+markup}}}{{100}} = \\text{{රු. }}{marked}$", 1),
               (f"විකුණුම් මිල $= {marked} \\times \\frac{{{100-disc}}}{{100}} = \\text{{රු. }}{sell}$", 2),
               (f"සත්‍ය ලාභය $= {sell} - {cost} = \\text{{රු. }}{profit}$", 1)])


def b_equation(r, d):
    if d == 0:
        a, s, b = r.randint(2, 18), r.randint(2, 40), r.randint(1, 50)
        c = a * s + b
        return mk(f"සමීකරණය විසඳන්න: ${a}x+{b}={c}$", [(f"${a}x={c-b}$", 1), (f"$x={s}$", 1)])
    s, t = r.randint(2, 25), r.randint(2, 25)
    if d == 1:
        (a1, b1), (a2, b2) = r.choice([((1, 1), (1, -1)), ((2, 1), (1, -1)), ((3, 2), (2, -1)), ((4, 3), (3, -2))])
        e1, e2 = sp.Eq(a1 * x + b1 * y, a1 * s + b1 * t), sp.Eq(a2 * x + b2 * y, a2 * s + b2 * t)
        return mk(f"සමගාමී සමීකරණ විසඳන්න:\n\n$$\\begin{{cases}}{L(e1)}\\\\{L(e2)}\\end{{cases}}$$",
                  [("එක් විචල්‍යයක් ඉවත් කිරීම", 2), (f"$x={s}, y={t}$", 2)])
    # Advance Logical: Simultaneous equation word problem
    p_pen, p_book = r.randint(20, 80), r.randint(90, 250)
    a1, b1 = r.randint(2, 6), r.randint(2, 5)
    a2, b2 = r.randint(2, 6), r.randint(2, 5)
    if a1 * b2 == a2 * b1:
        a2 += 1
    tot1 = a1 * p_book + b1 * p_pen
    tot2 = a2 * p_book + b2 * p_pen
    return mk(f"පොත් ${a1}$ ක් සහ පෑන් ${b1}$ ක මිල රු. ${tot1}$ කි. එම වර්ගයේම පොත් ${a2}$ ක් සහ පෑන් ${b2}$ ක මිල රු. ${tot2}$ කි. "
              f"සමගාමී සමීකරණ යුගලයක් ගොඩනඟා පොතක සහ පෑනක මිල වෙන වෙනම සොයන්න.",
              [(f"සමීකරණ: ${a1}x + {b1}y = {tot1}$ සහ ${a2}x + {b2}y = {tot2}$", 1),
               ("සංගුණක සමාන කර එක් විචල්‍යයක් ඉවත් කිරීම", 1),
               (f"පොතක මිල $x = \\text{{රු. }}{p_book}$, පෑනක මිල $y = \\text{{රු. }}{p_pen}$", 2)])


def b_para1(r, d):
    A = r.randint(35, 135)
    if d < 2:
        return mk(f"රූපයේ ABCD සමාන්තරාස්‍රයේ $\\angle A={A}{DEG}$ නම් $\\angle B$ හා $\\angle C$ සොයන්න.",
                  [(f"$\\angle B=180-{A}={180-A}{DEG}$", 2), (f"$\\angle C={A}{DEG}$", 1)],
                  img=("para", {"A": f"{A}°", "B": "?", "C": "?", "D": ""}))
    x0, a = r.randint(8, 32), r.randint(1, 25)
    b = 180 - 5 * x0 - a
    return mk(f"ABCD සමාන්තරාස්‍රයක $\\angle A=({L(2*x+a)}){DEG}$ ද $\\angle B=({L(3*x+b)}){DEG}$ ද වේ. $x$ හා $\\angle C$ සොයන්න.",
              [("ආසන්න කෝණ ඓක්‍යය $180^\\circ$ බැවින් ${L(5*x+a+b)}=180$", 1),
               (f"$x={x0}$", 1), (f"$\\angle C = \\angle A = {2*x0+a}{DEG}$", 2)])


def b_para2(r, d):
    b, h = r.randint(5, 60), r.randint(3, 45)
    if d == 0:
        return mk(f"සමාන්තරාස්‍රයක පාදම ${b}$ cm ද ලම්බ උස ${h}$ cm ද නම් වර්ගඵලය සොයන්න.",
                  [(f"$A={b}\\times{h}={b*h}$ cm$^2$", 2)])
    if d == 1:
        return mk(f"සමාන්තරාස්‍රයක වර්ගඵලය ${b*h}$ cm$^2$ ද පාදම ${b}$ cm ද නම් එහි ලම්බ උස සොයන්න.",
                  [(f"$h={F(b*h,b)}={h}$ cm", 2)])
    # Advance Logical: Two altitudes of a parallelogram
    k = r.randint(2, 10)
    b1, h1 = 4 * k, 3 * k
    b2 = 2 * k
    h2 = (b1 * h1) // b2
    return mk(f"ABCD සමාන්තරාස්‍රයේ $AB = {b1}$ cm හා $BC = {b2}$ cm වේ. AB හා DC අතර ලම්බ දුර ${h1}$ cm නම්, "
              f"AD හා BC අතර ලම්බ දුර සොයන්න.",
              [(f"සමාන්තරාස්‍රයේ වර්ගඵලය $= AB \\times h_1 = {b1}\\times{h1} = {b1*h1}$ cm$^2$", 2),
               (f"$BC \\times h_2 = {b1*h1} \\Rightarrow {b2} \\times h_2 = {b1*h1}$", 1),
               (f"$h_2 = {h2}$ cm", 1)])


def b_sets(r, d):
    a, b, c = r.randint(15, 65), r.randint(12, 60), r.randint(3, 14)
    u = a + b - c + r.randint(2, 25)
    if d == 0:
        return mk(f"$n(A)={a}$, $n(B)={b}$, $n(A\\cap B)={c}$ නම් $n(A\\cup B)$ සොයන්න.",
                  [(f"$n(A\\cup B)={a}+{b}-{c}={a+b-c}$", 2)])
    if d == 1:
        return mk(f"$n(\\varepsilon)={u}$, $n(A)={a}$, $n(B)={b}$, $n(A\\cap B)={c}$ නම් $n(A\\cup B)'$ සොයන්න.",
                  [(f"$n(A\\cup B)={a+b-c}$", 1), (f"$n(A\\cup B)'={u-(a+b-c)}$", 2)])
    # Advance Logical: Finding unknown intersection x when total & outside are given
    none_cnt = u - (a + b - c)
    return mk(f"සිසුන් ${u}$ දෙනෙකුගෙන් ${a}$ දෙනෙක් ගණිතය ද, ${b}$ දෙනෙක් විද්‍යාව ද හදාරති. විෂයයන් දෙකම නොහදාරන සිසුන් ගණන "
              f"${none_cnt}$ ක් නම්, (i) විෂයයන් දෙකම හදාරන ගණන (ii) ගණිතය පමණක් හදාරන ගණන සොයන්න.",
              [(f"$n(A\\cup B) = {u} - {none_cnt} = {a+b-c}$", 1),
               (f"$n(A\\cap B) = {a} + {b} - {a+b-c} = {c}$", 2),
               (f"ගණිතය පමණක් $= {a} - {c} = {a-c}$", 1)])


def b_logform(r, d):
    a, m = r.randint(2, 18), r.randint(2, 6)
    N = a ** m
    if d == 0:
        return mk(f"${a}^{{{m}}}={N}$ ලඝුගණක ආකාරයෙන් ලියන්න.", [(f"$\\log_{{{a}}}{N}={m}$", 2)])
    if d == 1:
        return mk(f"$\\log_{{{a}}}{N}={m}$ දර්ශක ආකාරයෙන් ලියන්න.", [(f"${a}^{{{m}}}={N}$", 2)])
    x0 = r.randint(2, 15)
    c = r.randint(1, 15)
    rhs_val = a ** m - c
    return mk(f"විසඳන්න: $\\log_{{{a}}}(x + {c}) = {m}$",
              [(f"දර්ශක ආකාරයට හැරවීමෙන්: $x + {c} = {a}^{{{m}}} = {N}$", 2),
               (f"$x = {N} - {c} = {rhs_val}$", 2)])


def b_logs(r, d):
    b = r.choice([2, 3, 5, 10])
    if d == 0:
        i, j = r.randint(1, 6), r.randint(1, 6)
        return mk(f"අගය සොයන්න: $\\log_{{{b}}}{b**i}+\\log_{{{b}}}{b**j}$", [(f"${i}+{j}={i+j}$", 2)])
    if d == 1:
        i, j = r.randint(3, 8), r.randint(1, 2)
        return mk(f"අගය සොයන්න: $\\log_{{{b}}}{b**i}-\\log_{{{b}}}{b**j}$", [(f"${i}-{j}={i-j}$", 2)])
    # Advance Logical: Logarithmic equation log_b(x) + log_b(k) = m
    m = r.randint(2, 5)
    k = r.randint(2, 9)
    ans = sp.Rational(b ** m, k)
    return mk(f"විසඳන්න: $\\log_{{{b}}}x + \\log_{{{b}}}{k} = {m}$",
              [(f"ලඝුගණක නීති අනුව $\\log_{{{b}}}({k}x) = {m}$", 1),
               (f"${k}x = {b}^{{{m}}} = {b**m}$", 2),
               (f"$x = {L(ans)}$", 1)])


def b_graph(r, d):
    m = r.choice([v for v in range(-12, 13) if v])
    if d == 0:
        c = r.randint(-20, 20)
        return mk(f"$y={L(m*x+c)}$ සරල රේඛාවේ අනුක්‍රමණය හා $y$-අන්තඃඛණ්ඩය ලියන්න.",
                  [(f"අනුක්‍රමණය $={m}$, $y$-අන්තඃඛණ්ඩය $={c}$", 2)])
    x0 = r.choice([v for v in range(-10, 11) if v])
    c = -m * x0
    img = ("graph", {"a": 0, "b": m, "c": c, "marks": [[0, c], [x0, 0]]})
    if d == 1:
        return mk("රූපයේ දැක්වෙන සරල රේඛාවේ අනුක්‍රමණය හා සමීකරණය සොයන්න.",
                  [(f"අනුක්‍රමණය $={F(-c, x0)}={m}$", 2), (f"සමීකරණය: $y={L(m*x+c)}$", 1)], img=img)
    p_x, p_y = r.randint(1, 8), r.randint(-10, 15)
    c_new = p_y - m * p_x
    return mk(f"රූපයේ දැක්වෙන සරල රේඛාවට සමාන්තරව $({p_x},{p_y})$ ලක්ෂ්‍යය හරහා යන සරල රේඛාවේ සමීකරණය සොයන්න.",
              [(f"දී ඇති රේඛාවේ අනුක්‍රමණය $m={F(-c, x0)}={m}$", 1),
               (f"$y = {m}x + c$ හි $({p_x},{p_y})$ ආදේශයෙන් ${p_y} = {m}({p_x}) + c \\Rightarrow c = {c_new}$", 2),
               (f"සමීකරණය: $y = {L(m*x+c_new)}$", 1)], img=img)


def b_speed(r, d):
    if d == 0:
        v, t = r.randrange(20, 140, 5), r.randint(2, 12)
        return mk(f"වාහනයක් පැය ${t}$ කින් කිලෝමීටර් ${v*t}$ ක් ගමන් කළේය. එහි වේගය සොයන්න.",
                  [(f"වේගය $={F(v*t,t)}={v}$ km/h", 2)])
    if d == 1:
        v, m = r.randrange(20, 140, 5), r.choice([15, 20, 30, 40, 45, 75, 90])
        return mk(f"පැයට ${v}$ km වේගයෙන් ගමන් කරන වාහනයක් මිනිත්තු ${m}$ ක් තුළ ගමන් කරන දුර සොයන්න.",
                  [(f"දුර $={v}\\times{F(m,60)}={L(sp.Rational(v*m,60))}$ km", 3)])
    # Advance Logical: Train passing a platform
    speed_ms = r.randint(10, 35)
    speed_kmh = speed_ms * 18 // 5
    if (speed_ms * 18) % 5 != 0:
        speed_ms = 5 * r.randint(2, 7)
        speed_kmh = speed_ms * 18 // 5
    L_train = r.randint(8, 30) * 10
    L_plat = r.randint(10, 40) * 10
    tot_d = L_train + L_plat
    t_sec = sp.Rational(tot_d, speed_ms)
    return mk(f"පැයට ${speed_kmh}$ km ක ඒකාකාර වේගයෙන් ධාවනය වන දිග ${L_train}$ m ක් වූ දුම්රියකට, දිග ${L_plat}$ m ක් වූ "
              f"වේදිකාවක් සම්පූර්ණයෙන්ම පසු කිරීමට ගතවන කාලය තත්පර වලින් සොයන්න.",
              [(f"වේගය $={speed_kmh} \\times \\frac{{5}}{{18}} = {speed_ms}$ m/s", 1),
               (f"ගමන් කළ යුතු මුළු දුර $={L_train} + {L_plat} = {tot_d}$ m", 1),
               (f"කාලය $={F(tot_d, speed_ms)} = {L(t_sec)}$ s", 2)])


def b_formula(r, d):
    if d == 0:
        u, a, t = r.randint(0, 30), r.randint(1, 12), r.randint(1, 15)
        return mk(f"$v=u+at$ සූත්‍රයේ $u={u}$, $a={a}$, $t={t}$ නම් $v$ සොයන්න.",
                  [(f"$v={u}+{a}\\times{t}={u+a*t}$", 2)])
    if d == 1:
        m, c = r.randint(2, 15), r.randint(1, 30)
        return mk(f"$y={m}x+{c}$ සූත්‍රයේ $x$ උක්ත කරන්න.",
                  [(f"$x={F('y-%d' % c, m)}$", 2)])
    k = r.randint(2, 12)
    return mk(f"$T = 2\\pi\\sqrt{{\\frac{{l}}{{g}}}}$ සූත්‍රයේ $l$ උක්ත කර, $T={2*k}\\pi$ විට $l$ හි අගය $g$ ඇසුරෙන් සොයන්න.",
              [("දෙපසම වර්ග කිරීමෙන්: $T^2 = 4\\pi^2\\frac{l}{g}$", 1),
               ("$l = \\frac{gT^2}{4\\pi^2}$", 2),
               (f"$T={2*k}\\pi$ ආදේශයෙන් $l = \\frac{{g({4*k*k}\\pi^2)}}{{4\\pi^2}} = {k*k}g$", 1)])


def b_ap(r, d):
    a, k, n = r.randint(1, 50), r.randint(2, 15), r.randint(8, 40)
    if d == 0:
        return mk(f"සමාන්තර ශ්‍රේණියක පළමු පදය ${a}$ ද පොදු අන්තරය ${k}$ ද නම් ${n}$ වන පදය සොයන්න.",
                  [(f"$T_{{{n}}}={a}+{n-1}\\times{k}={a+(n-1)*k}$", 2)])
    if d == 1:
        return mk(f"සමාන්තර ශ්‍රේණියක පළමු පදය ${a}$ ද පොදු අන්තරය ${k}$ ද නම් පළමු පද ${n}$ හි ඓක්‍යය සොයන්න.",
                  [(f"$S_{{{n}}}={F(n,2)}[{2*a}+{(n-1)*k}]={L(sp.Rational(n,2)*(2*a+(n-1)*k))}$", 3)])
    # Advance Logical: Given p-th and q-th terms, find a and d
    p, q = r.sample(range(3, 18), 2)
    if p > q:
        p, q = q, p
    Tp, Tq = a + (p - 1) * k, a + (q - 1) * k
    return mk(f"සමාන්තර ශ්‍රේණියක ${p}$ වන පදය ${Tp}$ වන අතර ${q}$ වන පදය ${Tq}$ වේ. එහි පොදු අන්තරය හා පළමු පදය සොයන්න.",
              [(f"$a + {p-1}d = {Tp}$ සහ $a + {q-1}d = {Tq}$", 1),
               (f"සමීකරණ අඩු කිරීමෙන් $({q-p})d = {Tq-Tp} \\Rightarrow d = {k}$", 2),
               (f"පළමු පදය $a = {Tp} - {(p-1)*k} = {a}$", 1)])


def b_ineq(r, d):
    a, s, b = r.randint(2, 15), r.randint(1, 20), r.randint(1, 30)
    lhs, ans, extra = [(f"{a}x+{b}>{a*s+b}", f"x>{s}", []),
                       (f"{a}x+{b}\\le{a*s+b}", f"x\\le{s}", []),
                       (f"{b}-{a}x>{b-a*s}", f"x<{s}", [("ඍණ සංගුණකයෙන් බෙදූ විට අසමානතා ලකුණ ආපසු හැරේ", 1),
                                                         (f"එබැවින් $x$ හි විශාලතම නිඛිල අගය $={s-1}$", 1)])][d]
    q_extra = " සහ $x$ ට ගත හැකි විශාලතම නිඛිල අගය ලියන්න" if d == 2 else ""
    return mk(f"අසමානතාව විසඳන්න{q_extra}: ${lhs}$",
              [("නියත පද සුළු කිරීම", 1), (f"${ans}$", 1)] + extra)


def b_freq(r, d):
    fs = [r.randint(1, 15) for _ in range(5)]
    s0 = r.randint(1, 30)
    st = r.choice([1, 2, 5, 10])
    xs = [s0 + i * st for i in range(5)]
    sf, sfx = sum(fs), sum(f * v for f, v in zip(fs, xs))
    if d < 2:
        return mk("පහත සංඛ්‍යාත ව්‍යාප්තියේ මධ්‍යනය සොයන්න.\n\n" +
                  table(["අගය ($x$)"] + xs, [["සංඛ්‍යාතය ($f$)"] + fs]),
                  [(f"$\\sum f={sf}, \\sum fx={sfx}$", 2), (f"මධ්‍යනය $={L(sp.Rational(sfx,sf))}$", 2)])
    # Advance Logical: Missing frequency k given mean
    k_val = fs[2]
    fs_shown = fs[:2] + ["k"] + fs[3:]
    mean_val = sp.Rational(sfx, sf)
    return mk(f"පහත සංඛ්‍යාත ව්‍යාප්තියේ මධ්‍යනය ${L(mean_val)}$ නම්, අজ্ঞාත සංඛ්‍යාතය $k$ හි අගය සොයන්න.\n\n" +
              table(["අගය ($x$)"] + xs, [["සංඛ්‍යාතය ($f$)"] + fs_shown]),
              [(f"$\\sum f = {sf - k_val} + k$ සහ $\\sum fx = {sfx - k_val*xs[2]} + {xs[2]}k$", 2),
               (f"$\\frac{{{sfx - k_val*xs[2]} + {xs[2]}k}}{{{sf - k_val} + k}} = {L(mean_val)}$ විසඳීමෙන් $k = {k_val}$", 2)])


def b_chord(r, d):
    R, om, h = r.choice(CHORD)
    k = r.randint(1, 12)
    R, om, h = R * k, om * k, h * k
    if d == 0:
        lab, q = ("%d cm" % R, "%d cm" % om, "?"), f"වෘත්තයේ අරය ${R}$ cm ද කේන්ද්‍රයේ සිට AB ජ්‍යායට ලම්බ දුර OM=${om}$ cm ද නම් AB සොයන්න."
        steps = [(f"$AM=\\sqrt{{{R}^2-{om}^2}}={h}$ cm", 2), (f"$AB=2\\times{h}={2*h}$ cm", 1)]
    elif d == 1:
        lab, q = ("%d cm" % R, "?", "%d cm" % (2 * h)), f"වෘත්තයේ අරය ${R}$ cm ද AB ජ්‍යාය ${2*h}$ cm ද නම් OM සොයන්න."
        steps = [(f"$AM={h}$ cm", 1), (f"$OM=\\sqrt{{{R}^2-{h}^2}}={om}$ cm", 2)]
    else:
        lab, q = ("?", "%d cm" % om, "%d cm" % (2 * h)), f"AB ජ්‍යාය ${2*h}$ cm ද OM=${om}$ cm ද නම් වෘත්තයේ අරය හා පරිධිය ($\\pi$ ඇසුරෙන්) සොයන්න."
        steps = [(f"$AM={h}$ cm, $OB=\\sqrt{{{h}^2+{om}^2}}={R}$ cm", 2), (f"පරිධිය $=2\\pi({R})={2*R}\\pi$ cm", 2)]
    return mk("රූපයේ " + q, steps, img=("chord", {"r": R, "om": om, "l_r": lab[0], "l_om": lab[1], "l_ab": lab[2]}))


def b_construct(r, d):
    if d == 0:
        n = r.randint(40, 140) / 10
        return mk(f"${n}$ cm දිග AB රේඛා ඛණ්ඩයක් ඇඳ එහි ලම්බ සමච්ඡේදකය නිර්මාණය කරන්න.",
                  [(f"AB = {n} cm ඇඳීම", 1), ("ලම්බ සමච්ඡේදකය නිර්මාණය", 2)], "නිර්මාණ")
    if d == 1:
        while True:
            a, b, c = [r.randint(6, 20) / 2 for _ in range(3)]
            if a + b > c and a + c > b and b + c > a:
                break
        return mk(f"$AB={a}$ cm, $BC={b}$ cm, $CA={c}$ cm වන ABC ත්‍රිකෝණය නිර්මාණය කරන්න.",
                  [(f"AB = {a} cm ඇඳීම", 1), ("චාප මගින් C ලබා ගැනීම හා ත්‍රිකෝණය සම්පූර්ණ කිරීම", 3)], "නිර්මාණ")
    a, t, f = r.randint(45, 95) / 10, r.choice([30, 45, 60, 90]), r.choice([30, 45, 60])
    return mk(f"$BC={a}$ cm, $\\angle B={t}{DEG}$, $\\angle C={f}{DEG}$ වන ABC ත්‍රිකෝණය නිර්මාණය කර, එහි පරිවෘත්තය නිර්මාණය කරන්න.",
              [(f"BC = {a} cm හා කෝණ නිර්මාණයෙන් $\\triangle ABC$ ඇඳීම", 2),
               ("පාද දෙකක ලම්බ සමච්ඡේදක ඇඳ පරිකේන්ද්‍රය O ලබා ගැනීම", 1),
               ("පරිවෘත්තය ඇඳීම", 1)], "නිර්මාණ")


def solid(r, kind, what, d=0):
    k = r.randint(1, 15 if kind in ("cyl", "cone") else 35)
    R, h, P = 7 * k, r.randint(2, 35), sp.Rational(22, 7)
    if d == 2 and what == "vol":
        # Advance Logical: Melting cylinder into spheres / cones
        n_cones = 3 * r.randint(2, 12)
        h_cyl = r.randint(4, 24)
        h_cone = sp.Rational(3 * h_cyl, n_cones)
        return mk(f"අරය ${R}$ cm හා උස ${h_cyl}$ cm වූ ලෝහ සිලින්ඩරයක් උණු කර, එම අරයම ඇති සමාන කේතු ${n_cones}$ ක් සාදනු ලැබේ. "
                  f"ලෝහ අපතේ නොයන්නේ නම් එක් කේතුවක උස සොයන්න.",
                  [(f"සිලින්ඩර පරිමාව $= \\pi r^2({h_cyl})$", 1),
                   (f"කේතු ${n_cones}$ හි පරිමාව $= {n_cones}\\times\\frac{{1}}{{3}}\\pi r^2 h = \\pi r^2({h_cyl})$", 2),
                   (f"එක් කේතුවක උස $h = {L(h_cone)}$ cm", 1)])
    if kind == "cyl":
        nm = f"අරය ${R}$ cm හා උස ${h}$ cm වන සෘජු වෘත්ත සිලින්ඩරයක"
        t, f, v = ("පරිමාව", "\\pi r^2h", P * R * R * h) if what == "vol" else ("සම්පූර්ණ පෘෂ්ඨ වර්ගඵලය", "2\\pi r(r+h)", 2 * P * R * (R + h))
    elif kind == "cone":
        h, l = 24 * k, 25 * k
        nm = f"අරය ${R}$ cm හා {'ලම්බ උස ' + str(h) if what == 'vol' else 'ඇල උස ' + str(l)} cm වන කේතුවක"
        t, f, v = ("පරිමාව", "\\frac{1}{3}\\pi r^2h", P * R * R * h / 3) if what == "vol" else ("වක්‍ර පෘෂ්ඨ වර්ගඵලය", "\\pi rl", P * R * l)
    elif kind == "sph":
        nm = f"අරය ${R}$ cm වන ගෝලයක"
        t, f, v = ("පරිමාව", "\\frac{4}{3}\\pi r^3", sp.Rational(4, 3) * P * R ** 3) if what == "vol" else ("පෘෂ්ඨ වර්ගඵලය", "4\\pi r^2", 4 * P * R * R)
    else:
        nm = f"අරය ${R}$ cm වන අර්ධගෝලයක"
        t, f, v = ("පරිමාව", "\\frac{2}{3}\\pi r^3", sp.Rational(2, 3) * P * R ** 3) if what == "vol" else ("සම්පූර්ණ පෘෂ්ඨ වර්ගඵලය", "3\\pi r^2", 3 * P * R * R)
    unit = "cm$^3$" if what == "vol" else "cm$^2$"
    return mk(f"{nm} {t} සොයන්න. ($\\pi={PI}$)",
              [(f"සූත්‍රය: ${f}$", 1), (f"{t} $={L(v)}$ {unit}", 2)])


def b_solid10(r, d):
    return solid(r, r.choice(["cyl", "cone", "sph", "hem"]), "vol" if d != 1 else "area", d)


def b_prob(r, d):
    red, blue = r.randint(3, 25), r.randint(3, 25)
    n = red + blue
    if d == 0:
        return mk(f"බෑගයක රතු බෝල ${red}$ ක් හා නිල් බෝල ${blue}$ ක් ඇත. අහඹු ලෙස ගන්නා බෝලයක් රතු වීමේ සම්භාවිතාව සොයන්න.",
                  [(f"$P(\\text{{රතු}})={L(sp.Rational(red,n))}$", 2)])
    if d == 1:
        ans = sp.Rational(red, n) ** 2
        return mk(f"බෑගයක රතු බෝල ${red}$ ක් හා නිල් බෝල ${blue}$ ක් ඇත. ආදේශ සහිතව බෝල දෙකක් ගතහොත් දෙකම රතු වීමේ සම්භාවිතාව සොයන්න.",
                  [(f"${F(red,n)}\\times{F(red,n)}={L(ans)}$", 3)])
    # Advance Logical: Without replacement, probability of getting TWO DIFFERENT colors
    diff_col = 2 * sp.Rational(red, n) * sp.Rational(blue, n - 1)
    return mk(f"බෑගයක රතු බෝල ${red}$ ක් හා නිල් බෝල ${blue}$ ක් ඇත. ආදේශ නොකර අහඹු ලෙස බෝල දෙකක් ඉවතට ගතහොත්, "
              f"එම බෝල දෙක වර්ණ දෙකකින් යුක්ත වීමේ සම්භාවිතාව සොයන්න.",
              [(f"P(රතු, නිල්) $= {F(red,n)}\\times{F(blue,n-1)}$ සහ P(නිල්, රතු) $= {F(blue,n)}\\times{F(red,n-1)}$", 2),
               (f"මුළු සම්භාවිතාව $= 2 \\times {F(red*blue, n*(n-1))} = {L(diff_col)}$", 2)])


def b_circle_angle(r, d):
    a = r.randint(15, 85)
    if d < 2:
        return mk(f"රූපයේ O කේන්ද්‍රය වූ වෘත්තයේ $\\angle ACB={a}{DEG}$ නම් $\\angle AOB$ සොයන්න.",
                  [("කේන්ද්‍රයේ කෝණය = පරිධියේ කෝණය මෙන් දෙගුණයකි", 1), (f"$\\angle AOB={2*a}{DEG}$", 2)],
                  img=("circle_angle", {"at": "C", "val": f"{a}°"}))
    # Advance Logical: Finding base angle ∠OAB of isosceles triangle OAB given ∠ACB
    base_ang = 90 - a
    return mk(f"රූපයේ O කේන්ද්‍රය වූ වෘත්තයේ $\\angle ACB={a}{DEG}$ වේ. OA හා OB යා කළ විට සෑදෙන $\\triangle OAB$ හි $\\angle OAB$ හි අගය සොයන්න.",
              [(f"කේන්ද්‍රයේ කෝණය $\\angle AOB = 2 \\times {a}{DEG} = {2*a}{DEG}$", 1),
               ("$OA = OB$ (වෘත්තයේ අරයන්) බැවින් $\\angle OAB = \\angle OBA$", 1),
               (f"$\\angle OAB = \\frac{{180^\\circ - {2*a}^\\circ}}{{2}} = {base_ang}{DEG}$", 2)],
              img=("circle_angle", {"at": "C", "val": f"{a}°"}))


def b_scale(r, d):
    n = r.choice([100, 200, 250, 500, 1000, 2000, 5000])
    if d == 0:
        Ld = r.randint(4, 80) / 2
        return mk(f"පරිමාණය $1:{n}$ වන සැලසුමක රූපයේ දිග ${Ld}$ cm කි. සත්‍ය දිග මීටර් වලින් සොයන්න.",
                  [(f"සත්‍ය දිග $={L(sp.Rational(Ld)*n/100)}$ m", 2)])
    if d == 1:
        X = r.randint(5, 500)
        return mk(f"පරිමාණය $1:{n}$ වන සැලසුමක සත්‍ය දිග ${X}$ m ක් නිරූපණය වන දිග cm වලින් සොයන්න.",
                  [(f"රූප දිග $={L(sp.Rational(X*100,n))}$ cm", 2)])
    k, A = r.choice([2, 5, 10, 20, 25, 50]), r.randint(3, 60)
    return mk(f"සැලසුමක පරිමාණය $1:{k*100}$ වේ. සැලසුමේ ඉඩමක වර්ගඵලය ${A}$ cm$^2$ නම් ඉඩමේ සත්‍ය වර්ගඵලය m$^2$ වලින් සොයන්න.",
              [(f"$1\\text{{ cm}} \\equiv {k}\\text{{ m}}$ බැවින් වර්ගඵල පරිමාණය $1\\text{{ cm}}^2 \\equiv {k*k}\\text{{ m}}^2$", 2),
               (f"සත්‍ය වර්ගඵලය $={A}\\times{k*k}={A*k*k}$ m$^2$", 2)])


# =============================================================================
# GRADE 11 BUILDERS
# =============================================================================
def b_realnum(r, d):
    if d == 0:
        a, b = r.randint(2, 20), r.choice([2, 3, 5, 6, 7, 10, 11, 13])
        return mk(f"සුළු කරන්න: $\\sqrt{{{a*a*b}}}$", [(f"$={a}\\sqrt{{{b}}}$", 2)])
    if d == 1:
        b, c = r.choice([2, 3, 5, 6, 7, 10, 11]), r.randint(1, 15)
        sq = "\\sqrt{%d}" % b
        return mk(f"හරය පරිමේය කරන්න: ${F(c, sq)}$", [(f"${F('%d%s' % (c, sq), b)}$", 2)])
    # Advance Logical: Conjugate rationalization 1 / (a + sqrt(b))
    a = r.randint(2, 9)
    b = r.choice([v for v in [2, 3, 5, 6, 7, 10, 11] if v != a * a])
    denom = a * a - b
    c = abs(denom) * r.randint(1, 5)
    ans = sp.simplify(c / (a + sp.sqrt(b)))
    return mk(f"හරය පරිමේය කර සරලතම ආකාරයෙන් දක්වන්න: $\\frac{{{c}}}{{{a}+\\sqrt{{{b}}}}}$",
              [(f"ලවය හා හරය ප්‍රතිබද්ධය වන $({a}-\\sqrt{{{b}}})$ ගෙන් ගුණ කිරීම", 1),
               (f"හරය $= {a}^2 - (\\sqrt{{{b}}})^2 = {denom}$", 1),
               (f"පිළිතුර $= {L(ans)}$", 2)])


def b_idx(r, d):
    a = r.randint(2, 9)
    if d < 2:
        m, n = r.randint(2, 12), r.randint(2, 12)
        p = r.randint(1, m + n - 1)
        return mk(f"සුළු කරන්න: ${a}^{{{m}}}\\times{a}^{{{n}}}\\div{a}^{{{p}}}$", [(f"${a}^{{{m+n-p}}}$", 2)])
    # Advance Logical: Different bases power equation (e.g. a^(cx-k) = (a^2)^m)
    b_base = r.choice([2, 3, 5])
    s = r.randint(2, 15)
    c, k = r.randint(2, 5), r.randint(1, 9)
    lhs_exp = c * s - k
    return mk(f"$x$ සඳහා විසඳන්න: ${b_base}^{{{c}x-{k}}} = {b_base**2}^{{{lhs_exp}/2}}$" if lhs_exp % 2 else
              f"$x$ සඳහා විසඳන්න: ${b_base}^{{{c}x-{k}}} = ({b_base**2})^{{{lhs_exp//2}}}$",
              [(f"දකුණු පස ${b_base}$ පාදයෙන් ලිවූ විට දර්ශකය $={lhs_exp}$", 1),
               (f"${c}x - {k} = {lhs_exp} \\Rightarrow x = {s}$", 2)])


def b_sa(r, d):
    return solid(r, r.choice(["cyl", "cone", "sph", "hem"]), "area", d)


def b_vol(r, d):
    return solid(r, r.choice(["cyl", "cone", "sph", "hem"]), "vol", d)


def b_binom11(r, d):
    a = r.randint(1, 20)
    if d == 0:
        p = r.randint(1, 6)
        e = (p * x + r.choice([a, -a])) ** 2
        return mk(f"ප්‍රසාරණය කරන්න: ${L(e)}$", [(f"${L(sp.expand(e))}$", 2)])
    if d == 1:
        p = r.randint(1, 8)
        e = (p * x + a) * (p * x - a)
        return mk(f"ප්‍රසාරණය කරන්න: ${L(e)}$", [(f"${L(sp.expand(e))}$", 2)])
    # Advance Logical: Given a+b and ab, find a^2 + b^2 or (a-b)^2
    u, v = r.randint(2, 15), r.randint(1, 15)
    s_uv, p_uv = u + v, u * v
    return mk(f"$a + b = {s_uv}$ සහ $ab = {p_uv}$ නම්, $a$ හා $b$ වෙන වෙනම නොසොයා (i) $a^2 + b^2$ (ii) $(a-b)^2$ හි අගයන් සොයන්න.",
              [(f"$a^2+b^2 = (a+b)^2 - 2ab = {s_uv}^2 - 2({p_uv}) = {s_uv**2 - 2*p_uv}$", 2),
               (f"$(a-b)^2 = (a^2+b^2) - 2ab = {s_uv**2 - 4*p_uv}$", 2)])


def b_algfrac2(r, d):
    a, b = r.sample(range(1, 15), 2)
    p, q = r.randint(1, 9), r.randint(1, 9)
    if d < 2:
        sg = 1 if d == 0 else -1
        e1, e2 = sp.Rational(p) / (x + a), sg * sp.Rational(q) / (x + b)
        shown = f"{F(p, L(x+a))}{'+' if sg>0 else '-'}{F(q, L(x+b))}"
        return mk(f"සුළු කරන්න: ${shown}$", [(f"${L(sp.together(e1+e2))}$", 3)])
    n1, m1, n2, m2 = x ** 2 - a * a, x + b, x + a, x ** 2 - b * b
    return mk(f"සුළු කරන්න: ${F(L(n1), L(m1))}\\div{F(L(n2), L(m2))}$",
              [("බෙදීම ගුණ කිරීමක් ලෙස පෙරළා සාධක වෙන් කිරීම", 2), (f"${L(sp.cancel(n1/m1*m2/n2))}$", 2)])


def b_betweenpar(r, d):
    b, h = r.randint(4, 45), r.randint(3, 35)
    if d == 0:
        return mk(f"AB හා DC සමාන්තර රේඛා අතර ABCD සමාන්තරාස්‍රයේ AB=${b}$ cm ද ලම්බ දුර ${h}$ cm ද නම් වර්ගඵලය සොයන්න.",
                  [(f"$={b*h}$ cm$^2$", 2)])
    if d == 1:
        return mk(f"AB හා DC සමාන්තර රේඛා අතර ABCD සමාන්තරාස්‍රයේ වර්ගඵලය ${2*b*h}$ cm$^2$ වේ. DC මත E ගෙන සාදන $\\triangle ABE$ හි වර්ගඵලය සොයන්න.",
                  [(f"${b*h}$ cm$^2$", 2)])
    return mk(f"ABCD සමාන්තරාස්‍රයේ DC පාදය මත E ලක්ෂ්‍යයක් පිහිටයි. $\\triangle ADE$ සහ $\\triangle BCE$ හි වර්ගඵල පිළිවෙලින් ${b}$ cm$^2$ හා ${h}$ cm$^2$ නම්, "
              f"$\\triangle ABE$ හි සහ ABCD සමාන්තරාස්‍රයේ වර්ගඵල සොයන්න.",
              [(f"$\\triangle ABE = \\frac{{1}}{{2}}\\text{{(ABCD)}}$ බැවින් $\\triangle ABE = \\triangle ADE + \\triangle BCE = {b+h}$ cm$^2$", 2),
               (f"සමාන්තරාස්‍රයේ වර්ගඵලය $= 2 \\times {b+h} = {2*(b+h)}$ cm$^2$", 2)])


def b_reducing(r, d):
    P = r.randint(2, 120) * 1000
    p = r.choice([6, 8, 10, 12, 15, 18, 20, 24])
    m = r.choice([10, 12, 15, 18, 20, 24])
    if d < 2:
        n = 2
        A = sp.Rational(P) * (1 + sp.Rational(p, 100)) ** n
        return mk(f"රු. ${P}$ ක් වාර්ෂික ${p}\\%$ වැල් පොළී ක්‍රමයට වසර ${n}$ කට තැන්පත් කළ විට අවසාන මුදල සොයන්න.",
                  [(f"පළමු වසර පොළිය $=\\text{{රු. }}{money(P*sp.Rational(p,100))}$", 1),
                   (f"අවසන් මුදල $=\\text{{රු. }}{money(A)}$", 2)])
    # Advance Logical: Reducing balance monthly installment calculation
    month_u = P // m
    n_u = m * (m + 1) // 2
    tot_int = sp.Rational(month_u * p * n_u, 1200)
    return mk(f"රු. ${P}$ ක ණයක් වාර්ෂික ${p}\\%$ හීන වන ශේෂ පොළී ක්‍රමය යටතේ සමාන මාසික වාරික ${m}$ කින් ගෙවා නිම කිරීමට එකඟ විය. "
              f"මුළු කාලය සඳහා ගෙවිය යුතු මුළු පොළිය සොයන්න.",
              [(f"මසකට ගෙවන මුල් ණය කොටස $=\\frac{{{P}}}{{{m}}}={month_u}$", 1),
               (f"මාස ඒකක ගණන $=\\frac{{{m}({m}+1)}}{{2}}={n_u}$", 1),
               (f"මුළු පොළිය $={month_u}\\times\\frac{{{p}}}{{100}}\\times\\frac{{1}}{{12}}\\times{n_u}=\\text{{රු. }}{money(tot_int)}$", 2)])


def b_shares(r, d):
    N = r.randrange(100, 6000, 50)
    P = r.choice([40, 50, 60, 75, 80, 100, 120, 150, 200])
    D = r.choice([3, 4, 5, 6, 8, 10, 12, 15])
    if d == 0:
        return mk(f"රු. ${P}$ බැගින් කොටස් ${N}$ ක් මිල දී ගත් අයකුට කොටසකට රු. ${D}$ ක ලාභාංශයක් ලැබේ. ආයෝජනය හා වාර්ෂික ලාභාංශය සොයන්න.",
                  [(f"ආයෝජනය $={N*P}$, ලාභාංශය $={N*D}$", 3)])
    if d == 1:
        return mk(f"රු. ${P}$ බැගින් මිල දී ගත් කොටසකට වසරකට රු. ${D}$ ක ලාභාංශයක් ලැබේ. ලාභාංශ ප්‍රතිශතය (දශම 2කට) සොයන්න.",
                  [(f"$={D*100/P:.2f}\\%$", 3)])
    P2 = P + r.choice([10, 20, 25, 30, 40])
    cap_gain = N * (P2 - P)
    tot_gain = cap_gain + N * D
    return mk(f"ආයෝජකයෙක් රු. ${P}$ බැගින් කොටස් ${N}$ ක් මිලදී ගෙන, කොටසකට රු. ${D}$ ක වාර්ෂික ලාභාංශය ලබා ගැනීමෙන් පසු, "
              f"කොටසක් රු. ${P2}$ බැගින් සියලු කොටස් විකුණා දැමීය. ලාභාංශය සහ ප්‍රාග්ධන ලාභය ඇතුළු මුළු ලාභය සොයන්න.",
              [(f"ලාභාංශ ආදායම $={N}\\times{D}=\\text{{රු. }}{N*D}$", 1),
               (f"ප්‍රාග්ධන ලාභය $={N}\\times({P2}-{P})=\\text{{රු. }}{cap_gain}$", 2),
               (f"මුළු ලාභය $=\\text{{රු. }}{tot_gain}$", 1)])


def b_midpoint(r, d):
    if d == 0:
        q = r.randint(2, 60)
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ AB හා AC පාදවල මධ්‍ය ලක්ෂ්‍ය P හා Q වේ. $PQ={q}$ cm නම් BC සොයන්න.",
                  [(f"$BC=2\\times{q}={2*q}$ cm", 2)], img=("midpoint", {"l_pq": f"{q} cm", "l_bc": "?"}))
    if d == 1:
        a, b, c = [2 * r.randint(2, 30) for _ in range(3)]
        return mk(f"ABC ත්‍රිකෝණයේ $AB={a}$ cm, $BC={b}$ cm, $CA={c}$ cm වේ. පාදවල මධ්‍ය ලක්ෂ්‍ය යා කිරීමෙන් සෑදෙන ත්‍රිකෝණයේ පරිමිතිය සොයන්න.",
                  [(f"$={(a+b+c)//2}$ cm", 3)])
    s, a, b, k = r.randint(2, 18), r.randint(1, 5), r.randint(1, 9), r.randint(1, 6)
    c, dd = 2 * a + k, 2 * b - k * s
    return mk(f"ABC ත්‍රිකෝණයේ AB, AC හි මධ්‍ය ලක්ෂ්‍ය P, Q වේ. $PQ=({L(a*x+b)})$ cm ද $BC=({L(c*x+dd)})$ cm ද නම් $x$ හා BC සොයන්න.",
              [("$BC=2PQ$ බැවින් ${L(c*x+dd)}=2({L(a*x+b)})$", 2), (f"$x={s}, BC={c*s+dd}$ cm", 2)])


def b_graph11(r, d):
    if d == 0:
        a, h, k = r.choice([1, -1]), r.randint(-8, 8), r.randint(-12, 12)
        e = sp.expand(a * (x - h) ** 2 + k)
        co = [int(e.coeff(x, 2)), int(e.coeff(x, 1)), int(e.coeff(x, 0))]
        return mk(f"රූපයේ දැක්වෙන $y={L(e)}$ ප්‍රස්ථාරයේ හැරුම් ලක්ෂ්‍යය හා සමමිති අක්ෂයේ සමීකරණය ලියන්න.",
                  [(f"හැරුම් ලක්ෂ්‍යය $({h},{k})$, සමමිති අක්ෂය $x={h}$", 3)],
                  img=("graph", {"a": co[0], "b": co[1], "c": co[2], "marks": []}))
    p, q = r.sample(range(-9, 10), 2)
    e = sp.expand((x - p) * (x - q))
    img = ("graph", {"a": 1, "b": -(p + q), "c": p * q, "marks": [[p, 0], [q, 0]]})
    if d == 1:
        return mk(f"රූපයේ දැක්වෙන ප්‍රස්ථාරය $y=x^2+bx+c$ ආකාරයේ ය. $x$-අන්තඃඛණ්ඩ $({p},0)$ හා $({q},0)$ නම් සමීකරණය සොයන්න.",
                  [(f"$y={L(e)}$", 3)], img=img)
    xv, yv = sp.Rational(p + q, 2), -sp.Rational((p - q) ** 2, 4)
    return mk(f"රූපයේ දැක්වෙන $y={L(e)}$ ප්‍රස්ථාරයේ (i) අවම අගය (ii) $y \\le 0$ වන $x$ හි අගය පරාසය ලියන්න.",
              [(f"හැරුම් ලක්ෂ්‍යයේ $x={L(xv)}$ බැවින් අවම අගය $y={L(yv)}$", 2),
               (f"$y \\le 0$ පරාසය: ${min(p,q)} \\le x \\le {max(p,q)}$", 2)], img=img)


def b_quadratic(r, d):
    if d == 0:
        a, b = r.choice([v for v in range(-12, 13) if v]), r.choice([v for v in range(-12, 13) if v])
        e = sp.expand((x + a) * (x + b))
        return mk(f"විසඳන්න: ${L(e)}=0$", [(f"$x={L(sp.solve(e, x))}$", 3)])
    if d == 1:
        e = sp.expand((r.randint(2, 5) * x + r.randint(1, 11)) * (x - r.randint(1, 11)))
        return mk(f"විසඳන්න: ${L(e)}=0$", [(f"සාධක: ${L(sp.factor(e))}=0$", 1), (f"$x={L(sp.solve(e, x))}$", 2)])
    # Advance Logical: Roots alpha, beta synthesis OR geometry word problem
    w = r.randint(4, 25)
    diff = r.randint(2, 15)
    l = w + diff
    area = l * w
    return mk(f"සෘජුකෝණාස්‍රයක දිග එහි පළලට වඩා ${diff}$ cm කින් වැඩි වන අතර එහි වර්ගඵලය ${area}$ cm$^2$ වේ. "
              f"පළල $x$ ලෙස ගෙන වර්ගජ සමීකරණයක් ගොඩනඟා එය විසඳීමෙන් දිග සහ පළල සොයන්න.",
              [(f"$x(x + {diff}) = {area} \\Rightarrow x^2 + {diff}x - {area} = 0$", 1),
               (f"$(x - {w})(x + {l}) = 0$", 1),
               (f"$x > 0$ බැවින් පළල $={w}$ cm සහ දිග $={l}$ cm", 2)])


def b_similar(r, d):
    a, b, c = r.choice(TRIPLES)
    k1, k2 = r.sample(range(1, 10), 2)
    t1, t2 = [k1 * a, k1 * b, k1 * c], [k2 * a, k2 * b, k2 * c]
    if d == 0:
        return mk(f"රූපයේ ABC හා PQR ත්‍රිකෝණ සමකෝණී වේ. දී ඇති දිගවල් ඇසුරෙන් $QR$ සොයන්න.",
                  [(f"$QR={k2*b}$ cm", 2)],
                  img=("similar", {"t1": t1[:2], "t2": t2[:2], "l1": [f"{t1[0]}", f"{t1[1]}", f"{t1[2]}"],
                                   "l2": [f"{t2[0]}", "?", f"{t2[2]}"]}))
    if d == 1:
        return mk(f"රූපයේ ABC හා PQR ත්‍රිකෝණ සමකෝණී වේ. $PR={k2*c}$ cm නම් $PQ$ හා $QR$ සොයන්න.",
                  [(f"$PQ={k2*a}$ cm, $QR={k2*b}$ cm", 3)],
                  img=("similar", {"t1": t1[:2], "t2": t2[:2], "l1": [f"{t1[0]}", f"{t1[1]}", f"{t1[2]}"],
                                   "l2": ["?", "?", f"{t2[2]}"]}))
    A1 = sp.Rational(k1 * a * k1 * b, 2)
    return mk(f"ABC හා PQR සමකෝණී ත්‍රිකෝණවල අනුරූප පාද $AB={k1*a}$ cm හා $PQ={k2*a}$ cm වේ. $\\triangle ABC$ හි වර්ගඵලය "
              f"${L(A1)}$ cm$^2$ නම් $\\triangle PQR$ හි වර්ගඵලය සොයන්න.",
              [(f"වර්ගඵල අනුපාතය $=\\left({F(k2,k1)}\\right)^2$", 2),
               (f"PQR වර්ගඵලය $={L(A1*sp.Rational(k2,k1)**2)}$ cm$^2$", 2)])


def b_stats11(r, d):
    n = r.choice([7, 11, 15])
    data = sorted(r.randint(1, 95) for _ in range(n))
    lo, up = data[:n // 2], data[n // 2 + 1:]
    q1, q3, med = lo[len(lo) // 2], up[len(up) // 2], data[n // 2]
    ds = ", ".join(map(str, data))
    if d == 0:
        return mk(f"දත්ත: ${ds}$. මධ්‍යනය හා මධ්‍යස්ථය සොයන්න.",
                  [(f"මධ්‍යනය $={L(sp.Rational(sum(data), n))}$, මධ්‍යස්ථය $={med}$", 3)])
    if d == 1:
        return mk(f"දත්ත: ${ds}$. $Q_1, Q_3$ හා අන්තර් චතුර්ථක පරාසය (IQR) සොයන්න.",
                  [(f"$Q_1={q1}, Q_3={q3}, IQR={q3-q1}$", 3)])
    return mk(f"ආරෝහණ පිළිවෙලට ඇති දත්ත: ${ds}$. එහි අන්තර් චතුර්ථක පරාසය හා පරාසය අතර අනුපාතය සරලතම ආකාරයෙන් සොයන්න.",
              [(f"$IQR = {q3}-{q1} = {q3-q1}$ සහ පරාසය $= {data[-1]}-{data[0]} = {data[-1]-data[0]}$", 2),
               (f"අනුපාතය $= {q3-q1} : {data[-1]-data[0]}$", 2)])


def b_gp(r, d):
    a, q, n = r.randint(1, 12), r.choice([2, 3, 4, 5]), r.randint(4, 9)
    if d == 0:
        return mk(f"ගුණෝත්තර ශ්‍රේණියක පළමු පදය ${a}$ ද පොදු අනුපාතය ${q}$ ද නම් ${n}$ වන පදය සොයන්න.",
                  [(f"$T_{{{n}}}={a*q**(n-1)}$", 2)])
    if d == 1:
        return mk(f"ගුණෝත්තර ශ්‍රේණියක පළමු පදය ${a}$ ද පොදු අනුපාතය ${q}$ ද නම් පළමු පද ${n}$ හි ඓක්‍යය සොයන්න.",
                  [(f"$S_{{{n}}}={a*(q**n-1)//(q-1)}$", 3)])
    # Advance Logical: Geometric mean (x-a), x, (x+b) in GP
    t1 = a
    t2 = a * q
    t3 = a * q * q
    k_shift = r.randint(1, 15)
    return mk(f"${t1 - k_shift} + x$, ${t2 - k_shift} + x$, ${t3 - k_shift} + x$ යන පද තුන ගුණෝත්තර ශ්‍රේණියක අනුයාත පද තුනක් නම්, "
              f"$x$ හි අගය සහ පොදු අනුපාතය සොයන්න.",
              [(f"$\\frac{{{t2-k_shift}+x}}{{{t1-k_shift}+x}} = \\frac{{{t3-k_shift}+x}}{{{t2-k_shift}+x}}$", 1),
               (f"$({t2-k_shift}+x)^2 = ({t1-k_shift}+x)({t3-k_shift}+x)$ විසඳීමෙන් $x = {k_shift}$", 2),
               (f"පද තුන ${t1}, {t2}, {t3}$ බැවින් පොදු අනුපාතය $r = {q}$", 1)])


def b_pyth(r, d):
    a, b, c = r.choice(TRIPLES)
    k = r.randint(1, 12)
    a, b, c = a * k, b * k, c * k
    if d == 0:
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ $\\angle B=90^\\circ$, $AB={a}$ cm, $BC={b}$ cm නම් AC සොයන්න.",
                  [(f"$AC=\\sqrt{{{a}^2+{b}^2}}={c}$ cm", 2)],
                  img=("right_tri", {"ab": a, "bc": b, "l_ab": f"{a}", "l_bc": f"{b}", "l_ac": "?"}))
    if d == 1:
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ $\\angle B=90^\\circ$, $AC={c}$ cm, $AB={a}$ cm නම් BC සොයන්න.",
                  [(f"$BC=\\sqrt{{{c}^2-{a}^2}}={b}$ cm", 2)],
                  img=("right_tri", {"ab": a, "bc": b, "l_ab": f"{a}", "l_bc": "?", "l_ac": f"{c}"}))
    # Advance Logical: Altitude to hypotenuse BD = (AB*BC)/AC
    bd = sp.Rational(a * b, c)
    return mk(f"රූපයේ $\\angle B=90^\\circ$ වූ ABC සෘජුකෝණී ත්‍රිකෝණයේ $AB={a}$ cm හා $BC={b}$ cm වේ. B ශීර්ෂයේ සිට AC කර්ණයට "
              f"ඇඳි ලම්බයේ දිග සොයන්න.",
              [(f"පයිතගරස් ප්‍රමේයයෙන් $AC = \\sqrt{{{a}^2+{b}^2}} = {c}$ cm", 1),
               (f"ත්‍රිකෝණයේ වර්ගඵලය $= \\frac{{1}}{{2}}\\times{a}\\times{b} = \\frac{{1}}{{2}}\\times{c}\\times h$", 2),
               (f"ලම්බ උස $h = {F(a*b, c)} = {L(bd)}$ cm", 1)],
              img=("right_tri", {"ab": a, "bc": b, "l_ab": f"{a}", "l_bc": f"{b}", "l_ac": "?"}))


def b_trig(r, d):
    a, b, c = r.choice(TRIPLES)
    k = r.randint(1, 12)
    o, ad, h = a * k, b * k, c * k
    img = lambda lo, la, lh: ("right_tri", {"ab": o, "bc": ad, "l_ab": lo, "l_bc": la, "l_ac": lh, "theta": True})
    if d == 0:
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ $\\angle B=90^\\circ$, $AB={o}$ cm, $AC={h}$ cm නම් $\\sin\\theta$ සොයන්න.",
                  [(f"$\\sin\\theta={L(sp.Rational(o,h))}$", 2)], img=img(f"{o}", "", f"{h}"))
    if d == 1:
        return mk(f"රූපයේ ABC ත්‍රිකෝණයේ $\\angle B=90^\\circ$, $AB={o}$ cm, $BC={ad}$ cm, $AC={h}$ cm නම් $\\cos\\theta$ හා $\\tan\\theta$ සොයන්න.",
                  [(f"$\\cos\\theta={L(sp.Rational(ad,h))}, \\tan\\theta={L(sp.Rational(o,ad))}$", 3)], img=img(f"{o}", f"{ad}", f"{h}"))
    # Advance Logical: Evaluate trigonometric expression without finding theta
    val = sp.Rational(o + ad, o - ad) if o != ad else sp.Rational(o, h)
    return mk(f"රූපයේ $\\angle B=90^\\circ$ වන අතර $\\tan\\theta = {L(sp.Rational(o,ad))}$ වේ. $\\sin^2\\theta + \\cos^2\\theta$ හා "
              f"$\\frac{{\\sin\\theta + \\cos\\theta}}{{\\sin\\theta - \\cos\\theta}}$ හි අගයන් සොයන්න.",
              [(f"$AC = {h}$ බැවින් $\\sin\\theta = {F(o,h)}$ සහ $\\cos\\theta = {F(ad,h)}$", 1),
               ("$\\sin^2\\theta + \\cos^2\\theta = 1$", 1),
               (f"$\\frac{{\\sin\\theta + \\cos\\theta}}{{\\sin\\theta - \\cos\\theta}} = {L(val)}$", 2)], img=img(f"{o}", f"{ad}", "?"))


def b_matrix(r, d):
    def M():
        return sp.Matrix(2, 2, [r.randint(-7, 11) for _ in range(4)])
    A, B = M(), M()
    if d == 0:
        return mk(f"$A={L(A)}$, $B={L(B)}$ නම් $A+B$ සොයන්න.", [(f"$A+B={L(A+B)}$", 2)])
    if d == 1:
        return mk(f"$A={L(A)}$, $B={L(B)}$ නම් $AB$ සොයන්න.", [(f"$AB={L(A*B)}$", 3)])
    while A.det() == 0:
        A = M()
    return mk(f"$A={L(A)}$ න්‍යාසයේ නිශ්චායකය හා ප්‍රතිලෝම න්‍යාසය $A^{{-1}}$ සොයන්න.",
              [(f"$|A|={A.det()}$", 1), (f"$A^{{-1}}={L(A.inv())}$", 3)])


def b_ineq11(r, d):
    m, b, lo = r.randint(1, 8), r.randint(-12, 12), r.randint(-8, 6)
    hi = lo + r.randint(2, 8)
    if d == 0:
        s = r.randint(-8, 12)
        return mk(f"අසමානතාව විසඳන්න: ${L(m*x+b)}>{m*s+b}$", [(f"$x>{s}$", 2)])
    lhs = f"{m*lo+b}<{L(m*x+b)}\\le{m*hi+b}"
    steps = [(f"සියලු පදවලින් ${b}$ අඩු කර ${m}$ ගෙන් බෙදීම", 1), (f"${lo}<x\\le{hi}$", 2)]
    if d == 1:
        return mk(f"විසඳන්න: ${lhs}$", steps)
    return mk(f"${lhs}$ අසමානතාව සපුරාලන සියලු නිඛිල අගයන්ගේ ඓක්‍යය සොයන්න.",
              steps + [(f"නිඛිල අගයන්ගේ ඓක්‍යය $={sum(range(lo + 1, hi + 1))}$", 1)])


def b_cyclic(r, d):
    if d == 0:
        a = r.randint(45, 135)
        return mk(f"රූපයේ ABCD වෘත්ත චතුරස්‍රයක $\\angle A={a}{DEG}$ නම් $\\angle C$ සොයන්න.",
                  [(f"$\\angle C=180-{a}={180-a}{DEG}$", 2)],
                  img=("cyclic", {"A": f"{a}°", "B": "", "C": "?", "D": ""}))
    if d == 1:
        a, b = r.randint(45, 135), r.randint(45, 135)
        return mk(f"රූපයේ ABCD වෘත්ත චතුරස්‍රයක $\\angle A={a}{DEG}$ ද $\\angle B={b}{DEG}$ ද නම් $\\angle C$ හා $\\angle D$ සොයන්න.",
                  [(f"$\\angle C={180-a}{DEG}, \\angle D={180-b}{DEG}$", 3)],
                  img=("cyclic", {"A": f"{a}°", "B": f"{b}°", "C": "?", "D": "?"}))
    x0, a, c = r.randint(8, 30), r.randint(1, 4), r.randint(1, 4)
    bb = r.randint(0, 20)
    dd = 180 - bb - (a + c) * x0
    return mk(f"ABCD වෘත්ත චතුරස්‍රයක $\\angle A=({L(a*x+bb)}){DEG}$ ද $\\angle C=({L(c*x+dd)}){DEG}$ ද නම් $x$ හා $\\angle A$ සොයන්න.",
              [(f"${L((a+c)*x+bb+dd)}=180 \\Rightarrow x={x0}$", 2), (f"$\\angle A={a*x0+bb}{DEG}$", 2)])


def b_tangent(r, d):
    if d == 0:
        a, b, c = r.choice(TRIPLES[:5])
        k = r.randint(1, 10)
        R, T, P = a * k, b * k, c * k
        return mk(f"රූපයේ O කේන්ද්‍රය වූ වෘත්තයේ අරය ${R}$ cm වේ. $OP={P}$ cm නම් ස්පර්ශකය PT සොයන්න.",
                  [(f"$PT=\\sqrt{{{P}^2-{R}^2}}={T}$ cm", 3)],
                  img=("tangent", {"r": R, "d": P, "l_r": f"{R}", "l_op": f"{P}", "l_pt": "?"}))
    if d == 1:
        a, b = r.randint(1, 15), r.randint(1, 15)
        x0 = a + b
        return mk(f"P සිට වෘත්තයට ඇඳි ස්පර්ශක PA, PB වේ. $PA=({L(2*x+a)})$ cm ද $PB=({L(3*x-b)})$ cm ද නම් $x$ සොයන්න.",
                  [("$PA=PB$ බැවින් $x=" + f"{x0}$", 3)])
    t = 2 * r.randint(18, 68)
    return mk(f"O කේන්ද්‍රය වූ වෘත්තයට PA, PB ස්පර්ශක වන අතර $\\angle APB={t}{DEG}$ වේ. (i) $\\angle AOB$ (ii) $\\angle OAB$ සොයන්න.",
              [(f"$\\angle AOB = 180^\\circ - {t}^\\circ = {180-t}{DEG}$", 2),
               (f"$OA=OB$ බැවින් $\\angle OAB = \\frac{{180^\\circ - {180-t}^\\circ}}{{2}} = {t//2}{DEG}$", 2)])


# =============================================================================
# Master Table & Database Engine
# =============================================================================
ARI, ALG, GEO, MEA, STA, SET_ = "අංක ගණිතය", "වීජ ගණිතය", "ජ්‍යාමිතිය", "මිනුම්", "සංඛ්‍යානය හා සම්භාවිතාව", "කුලක"
_B10 = [(MEA, b_perimeter), (ARI, b_sqrt), (ARI, b_fraction), (ALG, b_binomial), (GEO, b_congr), (MEA, b_area),
        (ALG, b_factor), (GEO, b_tri_angle), (GEO, b_tri2), (ARI, b_inverse), (STA, b_datarep), (ALG, b_lcm),
        (ALG, b_algfrac), (ARI, b_percent), (ALG, b_equation), (GEO, b_para1), (MEA, b_para2), (SET_, b_sets),
        (ALG, b_logform), (ALG, b_logs), (ALG, b_graph), (MEA, b_speed), (ALG, b_formula), (ALG, b_ap),
        (ALG, b_ineq), (STA, b_freq), (GEO, b_chord), (GEO, b_construct), (MEA, b_solid10), (STA, b_prob),
        (GEO, b_circle_angle), (MEA, b_scale)]
_B11 = [(ARI, b_realnum), (ALG, b_idx), (ALG, b_logs), (MEA, b_sa), (MEA, b_vol), (ALG, b_binom11),
        (ALG, b_algfrac2), (MEA, b_betweenpar), (ARI, b_reducing), (ARI, b_shares), (GEO, b_midpoint),
        (ALG, b_graph11), (ALG, b_quadratic), (GEO, b_similar), (STA, b_stats11), (ALG, b_gp), (GEO, b_pyth),
        (GEO, b_trig), (ALG, b_matrix), (ALG, b_ineq11), (GEO, b_cyclic), (GEO, b_tangent), (GEO, b_construct),
        (SET_, b_sets), (STA, b_prob)]

ROWS = ([(10, l, c, f) for l, (c, f) in zip(SYLLABUS[10], _B10)] +
        [(11, l, c, f) for l, (c, f) in zip(SYLLABUS[11], _B11)])

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    grade          INTEGER NOT NULL CHECK (grade IN (10, 11)),
    category       TEXT    NOT NULL,
    lesson         TEXT    NOT NULL,
    difficulty     TEXT    NOT NULL CHECK (difficulty IN ('Easy','Average','Advance')),
    question_type  TEXT    NOT NULL,
    content        TEXT    NOT NULL,
    image_url      TEXT,
    image_spec     TEXT,
    marks          INTEGER NOT NULL CHECK (marks > 0),
    marking_scheme TEXT    NOT NULL,
    content_hash   TEXT    UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_filter ON questions (grade, lesson, difficulty, question_type);
"""


def _hash_q(grade, lesson, content):
    return hashlib.md5(f"{grade}|{lesson}|{content}".encode("utf-8")).hexdigest()


def ensure_schema_migration(con):
    """Ensures existing DBs without content_hash get upgraded without losing data."""
    con.executescript(SCHEMA)
    cols = [r[1] for r in con.execute("PRAGMA table_info(questions)").fetchall()]
    if "content_hash" not in cols:
        con.execute("ALTER TABLE questions ADD COLUMN content_hash TEXT")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_q_hash ON questions(content_hash)")


def generate_questions_batch(seed=None, per_lesson=PER_LESSON):
    if seed is None:
        seed = time.time_ns() ^ random.getrandbits(64)
    rng, out = random.Random(seed), []
    for grade, lesson, cat, fn in ROWS + LONG_ROWS:
        is_long = (grade, lesson, cat, fn) in LONG_ROWS
        per = LONG_PER_LESSON if is_long else per_lesson
        seen = set()
        for i in range(per):
            d = i % 3
            for _ in range(15):
                q = fn(rng, d)
                if q["content"] not in seen:
                    seen.add(q["content"])
                    break
            marks = sum(m for _, m in q["steps"])
            scheme = {"total": marks, "steps": [{"step": s, "marks": m} for s, m in q["steps"]]}
            path = spec = None
            if q["img"]:
                kind, p = q["img"]
                path, spec = image_path(kind, p), json.dumps({"kind": kind, "p": p})
            chash = _hash_q(grade, lesson, q["content"])
            out.append((grade, cat, lesson, DIFFS[d], q["qtype"], q["content"], path, spec, marks,
                        json.dumps(scheme, ensure_ascii=False), chash))
    return out


def init_db(force=False, per_lesson=PER_LESSON, append=True):
    """Initializes or appends new unique questions to the database."""
    with sqlite3.connect(DB_PATH) as con:
        if force:
            con.execute("DROP TABLE IF EXISTS questions")
        ensure_schema_migration(con)
        before = con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if before == 0 or append:
            rows = generate_questions_batch(seed=None, per_lesson=per_lesson)
            con.executemany(
                "INSERT OR IGNORE INTO questions (grade,category,lesson,difficulty,question_type,content,"
                "image_url,image_spec,marks,marking_scheme,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows
            )
            con.commit()
        after = con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        return before, after


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grow the Sinhala Maths Question Database.")
    parser.add_argument("--per-lesson", type=int, default=PER_LESSON, help="Questions to attempt per lesson in this run")
    parser.add_argument("--target-total", type=int, default=0, help="Keep generating batches until total DB hits this number (e.g. 1000000)")
    parser.add_argument("--reset", action="store_true", help="Drop existing table and rebuild from scratch")
    args = parser.parse_args()

    if args.target_total > 0:
        with sqlite3.connect(DB_PATH) as con:
            if args.reset:
                con.execute("DROP TABLE IF EXISTS questions")
            ensure_schema_migration(con)
            curr = con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        print(f"Starting bulk generation toward {args.target_total:,} questions (Current: {curr:,})...")
        batch_no = 0
        while curr < args.target_total:
            batch_no += 1
            b, curr = init_db(force=False, per_lesson=args.per_lesson, append=True)
            added = curr - b
            print(f"[Batch {batch_no}] Added +{added:,} new unique questions | Total in DB: {curr:,}")
            if added == 0:
                print("Reached saturation for current parameter ranges.")
                break
    else:
        before, after = init_db(force=args.reset, per_lesson=args.per_lesson, append=True)
        with sqlite3.connect(DB_PATH) as c:
            im = c.execute("SELECT COUNT(image_url) FROM questions").fetchone()[0]
        print(f"Previous count: {before:,} | Newly added: +{after - before:,} | Total Questions in DB: {after:,} (with figures: {im:,})")