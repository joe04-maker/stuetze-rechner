"""Unbewehrte Stütze – Handrechnungs-Nachbildung nach Skript (Rechenweg unverändert aus dem Colab-Skript)."""
import math
import re

from nennkruemmung_stuetze import _box, _html_tabelle, _karte, fmt

FCK_OPTIONEN_UNBEW = (8, 12, 16, 20, 25, 30, 35)
LAM_LIM = 86.0


def rechne_unbewehrt(b_cm, h_cm, l0_m, fck, e0_cm, N_Ed_kN):
    if min(b_cm, h_cm, l0_m) <= 0:
        raise ValueError("b, h und l0 müssen größer als 0 sein.")
    if N_Ed_kN <= 0:
        raise ValueError("N_Ed muss größer als 0 sein.")
    l0_cm = l0_m * 100.0
    i_cm = h_cm / math.sqrt(12.0)
    lam = l0_cm / i_cm
    etot_cm = e0_cm + l0_cm / 400.0
    theta_roh = 1.14 * (1.0 - 2.0 * etot_cm / h_cm) - 0.02 * l0_cm / h_cm
    theta = max(0.1, min(theta_roh, 1.0))
    fcd_pl = 0.7 * fck / 1.5
    A_m2 = (b_cm / 100.0) * (h_cm / 100.0)
    N_Rd_MN = A_m2 * fcd_pl * theta
    N_Rd_kN = N_Rd_MN * 1000.0
    ausn = N_Ed_kN / N_Rd_kN if N_Rd_kN > 0 else float("inf")
    return dict(b=b_cm, h=h_cm, l0=l0_m, fck=fck, e0=e0_cm, N_Ed=N_Ed_kN, i=i_cm, lam=lam,
                etot=etot_cm, theta_roh=theta_roh, theta=theta, fcd_pl=fcd_pl,
                N_Rd_MN=N_Rd_MN, N_Rd=N_Rd_kN, ausn=ausn, ok=N_Ed_kN <= N_Rd_kN,
                lam_ok=lam <= LAM_LIM)


def ausgabe_unbewehrt(r):
    if r["ok"]:
        status = _box("gruen", f"✅ Tragfähigkeit nachgewiesen: N<sub>Ed</sub> ≤ N<sub>Rd</sub> "
                               f"(Ausnutzung: {fmt(r['ausn'] * 100, 1)} %)")
    else:
        status = _box("rot", f"⚠️ Die Einwirkung N<sub>Ed</sub> ({fmt(r['N_Ed'], 1)} kN) ist größer als der "
                             f"Widerstand N<sub>Rd</sub> ({fmt(r['N_Rd'], 1)} kN).<br>➔ "
                             f"<b>Die Stütze kann nicht unbewehrt ausgeführt werden!</b> "
                             f"(Ausnutzung: {fmt(r['ausn'] * 100, 1)} %)")
    hinweis = ""
    if abs(r["theta_roh"] - r["theta"]) > 1e-12:
        hinweis = (f'<div style="color:#856404;">⚠️ Θ rechnerisch {fmt(r["theta_roh"], 3)}, '
                   f'begrenzt auf {fmt(r["theta"], 3)} (Skript: 0,1 ≤ Θ ≤ 1,0).</div>')
    zeilen = [
        ("Normalkraft N<sub>Ed</sub>", f"{fmt(r['N_Ed'], 1)} kN"),
        ("Querschnitt b × h / Systemlänge l<sub>0</sub>", f"{fmt(r['b'], 0)} × {fmt(r['h'], 0)} cm / {fmt(r['l0'])} m"),
        ("Trägheitsradius i", f"{fmt(r['i'])} cm"),
        ("Schlankheit λ", f"{fmt(r['lam'])} (Grenzwert λ<sub>lim</sub> = {fmt(LAM_LIM, 0)}) → "
                          f"<b>{'Eingehalten (OK)' if r['lam_ok'] else 'Überschritten'}</b>"),
        ("Gesamtausmitte e<sub>tot</sub> = e<sub>0</sub> + l<sub>0</sub>/400", f"{fmt(r['etot'], 3)} cm"),
        ("Abminderungsbeiwert Θ", f"<b>{fmt(r['theta'], 3)}</b>"),
        ("Bemessungs-Druckfestigkeit f<sub>cd,pl</sub> = 0,7·f<sub>ck</sub>/1,5", f"{fmt(r['fcd_pl'], 3)} MN/m²"),
        ("<b>Maximale Tragfähigkeit N<sub>Rd</sub></b>",
         f'<b style="color:#28a745;font-size:1.2em;">{fmt(r["N_Rd"], 1)} kN</b> ({fmt(r["N_Rd_MN"], 3)} MN)'),
    ]
    tab = '<table style="border-collapse:collapse;color:#222;font-size:0.95em;">' + "".join(
        f'<tr><td style="padding:3px 28px 3px 0;">{a}</td><td style="padding:3px 0;">{b}</td></tr>'
        for a, b in zeilen) + "</table>"
    return _karte(f'<h3 style="margin-top:0;">📊 Ergebnisse nach Skript-Schema (unbewehrt)</h3>{tab}{hinweis}{status}')


def _zahl(t):
    return float(t.replace(",", "."))


def varianten_unbewehrt(text, l0_m, fck_std):
    kopf = ["b×h [cm]", "C", "e<sub>0</sub> [cm]", "λ", "Θ", "N<sub>Ed</sub> [kN]",
            "N<sub>Rd</sub> [kN]", "Ausnutzung", "Nachweis"]
    zeilen, anzahl = [], 0
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        anzahl += 1
        try:
            t = [x for x in re.split(r"[;\s]+", zeile) if x]
            if len(t) not in (3, 4, 5):
                raise ValueError("erwartet: b h N_Ed [fck [e0]]")
            b, h, N = _zahl(t[0]), _zahl(t[1]), _zahl(t[2])
            fck = _zahl(t[3]) if len(t) >= 4 else fck_std
            e0 = _zahl(t[4]) if len(t) == 5 else 0.0
            r = rechne_unbewehrt(b, h, l0_m, fck, e0, N)
            zeilen.append([f"{fmt(b, 0)}×{fmt(h, 0)}", f"{fck:.0f}", fmt(e0, 1), fmt(r["lam"], 1),
                           fmt(r["theta"], 3), fmt(N, 2), fmt(r["N_Rd"], 2),
                           f"{fmt(r['ausn'] * 100, 2)} %", "✅ erfüllt" if r["ok"] else "⚠️ nicht erfüllt"])
        except Exception as ex:
            zeilen.append(f"Zeile {nr}: „{zeile}“ → ❌ {ex}")
    if anzahl == 0:
        return _box("gelb", "Keine Varianten eingegeben (Format je Zeile: b h N_Ed [fck [e0]]).")
    return _karte('<h3 style="margin-top:0;">📋 Varianten (unbewehrt)</h3>'
                  + _html_tabelle(kopf, zeilen, links=(0,), status=8), farbe="#17a2b8")
