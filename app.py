"""Streamlit-Oberfläche: Stahlbetonstütze – Nennkrümmungsverfahren (DIN EN 1992-1-1 mit NA)."""
import streamlit as st

import nennkruemmung_stuetze as nk
import unbewehrt_stuetze as ub
import vergleich
try:
    import abbildungen as abb          # N–M-Diagramm (braucht matplotlib); fehlt es, läuft das Programm trotzdem
except Exception as _ex:
    abb = None
    _ABB_FEHLER = f"{type(_ex).__name__}: {_ex}"

st.set_page_config(page_title="Tragfähigkeit von Betonstützen", page_icon="🏗️", layout="wide")
st.title("🏗️ Tragfähigkeit von Betonstützen")
st.caption("Bewehrte und unbewehrte Rechteckstütze · Nennkrümmungsverfahren nach DIN EN 1992-1-1 mit Nationalem Anhang Deutschland")


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def eigenlast(b_cm, h_cm, l_m):
    """Stützeneigengewicht G_k = b·h·l·25 kN/m³ [kN]."""
    return b_cm / 100.0 * h_cm / 100.0 * l_m * GAMMA_BETON if mit_g else 0.0


def ned(nk_kn, b_cm, h_cm, l_m):
    """Bemessungswert: N_Ed = 1,5·N_k (+ 1,35·G_k, wenn Eigenlast gewählt)."""
    return GAMMA_Q * nk_kn + GAMMA_G * eigenlast(b_cm, h_cm, l_m)


def zeilen_ned(text, l_m):
    """Variantenzeilen 'b h N_k …' -> 'b h N_Ed …' (3. Wert mit Teilsicherheitsbeiwerten)."""
    out = []
    for z in text.splitlines():
        t = z.replace(";", " ").split()
        if len(t) >= 3 and not z.strip().startswith("#"):
            try:
                t[2] = f"{ned(float(t[2].replace(',', '.')), float(t[0].replace(',', '.')), float(t[1].replace(',', '.')), l_m):.2f}".replace(".", ",")
                z = " ".join(t)
            except ValueError:
                pass
        out.append(z)
    return "\n".join(out)


GAMMA_Q, GAMMA_G, GAMMA_BETON = 1.5, 1.35, 25.0


def basis(l0, fck, phi, c, bue, modus, dl, n, d1, deck=None):
    return dict(l0_m=l0, fck=fck, e0_cm=0.0, phi_ef=phi, c_nom_mm=c, d_bue_mm=float(bue),
                modus=modus, d_l=int(dl), n_st=int(n), d1_mm=d1 or None, deck=deck)


with st.sidebar:
    st.header("Lasten")
    st.caption("Eingegeben wird die charakteristische Normalkraft N_k; N_Ed = 1,5·N_k (+ 1,35·G_k).")
    mit_g = st.checkbox("Eigenlast der Stütze berücksichtigen (G_k = b·h·l₀·25 kN/m³)", value=False)
    st.header("Gemeinsame Eingaben")
    st.caption("Gelten für die bewehrte und die unbewehrte Stütze und für den Vergleich.")
    l0 = st.number_input("Knicklänge l0 (m)", 0.1, 20.0, 2.90, 0.05, format="%.2f")
    fck = st.selectbox("f_ck (N/mm²)", nk.FCK_OPTIONEN, index=nk.FCK_OPTIONEN.index(25))
    phi = st.number_input("Kriechzahl φ_eff (-)", 0.0, 5.0, 2.0, 0.1)
    st.header("Nur bewehrte Stütze")
    modus_txt = st.radio("Bewehrung", ["Vorgeben (Standard: 4 Ø12, je Ecke 1 Stab)",
                                       "Automatisch wählen (kleinste ausreichende)"])
    modus = "fix" if modus_txt.startswith("Vorgeben") else "auto"
    w_bue, w_dl = st.columns(2)
    bue = w_bue.selectbox("Bügel Ø (mm)", [6, 8, 10, 12], index=1)
    dl = w_dl.selectbox("Längsstab Ø (mm)", nk.STAB_D, index=0, disabled=modus == "auto")
    n = st.selectbox("Anzahl Stäbe (min. 4)", nk.STAB_N, index=0, disabled=modus == "auto")
    st.markdown("**Betondeckung** (DIN EN 1992-1-1:2025-09, 6.5)")
    expo_sel = st.selectbox("Expositionsklasse", [nk.MANUELL] + list(nk.EXPO_KLASSEN), index=2,
                            help="c_nom = c_min + Δc_dev (6.1), c_min = max(c_min,dur; c_min,b; 10 mm) (6.2). "
                                 "„manuell“: c_nom unten selbst eingeben.")
    von_hand = expo_sel == nk.MANUELL
    verfahren = st.selectbox("Verfahren für c_min,dur", nk.VERFAHREN, disabled=von_hand)
    erc = st.selectbox("Expositionswiderstandsklasse (Zahl hinter XRC/XRDS)", nk.ERC_KLASSEN, index=4,
                       disabled=von_hand or verfahren != nk.VERFAHREN_ERC,
                       help="Tabelle 6.3 (XC) / 6.4 (XD, XS). Hängt vom festgelegten Beton ab (EN 206).")
    skl = st.selectbox("Anforderungsklasse (Anhang P)", nk.S_KLASSEN, index=3,
                       disabled=von_hand or verfahren != nk.VERFAHREN_P,
                       help="Tabelle P.2. Empfohlen: S4 bei 50 Jahren (Tabelle P.1).")
    nd = st.selectbox("Geplante Nutzungsdauer (Jahre)", nk.NUTZUNGSDAUER, disabled=von_hand)
    dcdev = st.selectbox("Vorhaltemaß Δc_dev (Tabelle 6.7)", list(nk.DC_DEV_FAELLE), disabled=von_hand)
    c_hand = st.number_input("Nennbetondeckung c_nom (mm), nur bei „manuell“", 10.0, 80.0, 20.0, 1.0,
                             disabled=not von_hand)
    deck = None if von_hand else dict(expo=expo_sel, verfahren=verfahren, erc=erc, sklasse=skl, nd=nd,
                                      dc_dev_fall=dcdev)
    if deck is None:
        c = c_hand
    else:
        try:
            dk = nk.betondeckung(d_bue=bue, **deck)
            c = dk["c_nom"]
            st.caption(f"c_min,dur = {dk['c_min_dur']:g}, c_min,b = {dk['c_min_b']:g} → c_min = {dk['c_min']:g}; "
                       f"Δc_dev = {dk['dc_dev']:g} → **c_nom = {c:g} mm**")
        except ValueError as ex:
            st.error(str(ex))
            st.stop()
    d1 = st.number_input("Achsabstand d1 (mm), 0 = aus c_nom", 0.0, 200.0, 0.0, 1.0, disabled=modus == "auto",
                         help="0: d1 = c_nom + Bügel-Ø + Stab-Ø/2. Nur im Modus „Vorgeben“. Bei „Automatisch wählen“ "
                              "wird d1 für den jeweils gewählten Stab immer neu berechnet.")
    if modus == "auto":
        d1 = 0.0

top_bew, top_unb, top_vg = st.tabs(["Bewehrte Stütze", "Unbewehrte Stütze", "Vergleich bewehrt ↔ unbewehrt"])

with top_bew:
    tab1, tab2, tab3 = st.tabs(["Einzelberechnung", "Varianten", "Vergleich mit mb"])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        b = c1.number_input("Breite b (cm)", 10.0, 200.0, 20.0, 1.0)
        h = c2.number_input("Höhe h (cm)", 10.0, 200.0, 20.0, 1.0)
        N = c3.number_input("Charakt. Normalkraft N_k (kN)", 1.0, 100000.0, 430.2, 1.0)
        e0 = c4.number_input("Lastausmitte e0 (cm)", 0.0, 100.0, 0.0, 0.5)
        if st.button("Berechnen 🚀", type="primary"):
            try:
                kw = basis(l0, fck, phi, c, bue, modus, dl, n, d1, deck)
                kw["e0_cm"] = e0
                G = eigenlast(b, h, l0)
                st.caption(f"N_Ed = 1,5 · {N:g}" + (f" + 1,35 · {G:.2f} (G_k = {b:g}·{h:g}·{l0:g}·25)" if mit_g else "")
                           + f" = {ned(N, b, h, l0):.2f} kN")
                E = nk.berechne(b, h, N_Ed_kN=ned(N, b, h, l0), **kw)
                html(nk.ausgabe(E))
                if abb is not None:
                    abb.zeige_bewehrt(st, E)
                else:
                    st.warning(f"N–M-Diagramm nicht verfügbar ({_ABB_FEHLER}). Prüfe, ob abbildungen.py im Ordner liegt "
                               "und in requirements.txt matplotlib steht.")
            except ValueError as ex:
                html(nk._box("rot", f"❌ Eingabefehler: {ex}"))
            except Exception as ex:
                html(nk._box("rot", f"❌ {type(ex).__name__}: {ex}"))

    with tab2:
        st.markdown("Eine Zeile je Variante: `b h N_k [fck [e0]]` (cm, cm, kN charakteristisch, N/mm², cm). "
                    "Ohne e0 wird zentrisch gerechnet, ohne fck gilt der Wert links.")
        text = st.text_area("Varianten", "20 20 430,2\n20 20 352,2 25 2\n25 25 649\n25 25 528,6 25 2,5",
                            height=140)
        if st.button("Varianten rechnen 📋"):
            html(nk.varianten_html(zeilen_ned(text, l0), basis(l0, fck, phi, c, bue, modus, dl, n, d1, deck)))

    with tab3:
        st.markdown("Rechnet die sechs mb-BauStatik-Positionen (4 Ø12, N_Ed aus mb) mit den Formeln von 2011 und φ_eff = 0 nach (wie mb), unabhängig vom Wert in der Seitenleiste.")
        if st.button("Vergleich mit mb-Ausdruck 📊"):
            html(nk.mb_vergleich_as_html())
        html(nk.mb_vergleich_html(l0_m=l0, fck=fck, c_nom_mm=c, d_bue_mm=float(bue), phi_ef=0.0))


with top_unb:
    st.markdown("Unbewehrte Stütze nach DIN EN 1992-1-1:2025-09, 14.4.5.2: N<sub>Rd</sub> = b·h·f<sub>cd,pl</sub>·Φ (Gl. 14.10), "
                "Φ nach Gl. (14.11), f<sub>cd,pl</sub> = 0,8·f<sub>cd</sub> (Gl. 14.1), f<sub>cd</sub> = 0,85·f<sub>ck</sub>/1,5. "
                "Knicklänge l<sub>0</sub>, f<sub>ck</sub> und Kriechzahl φ<sub>eff</sub> kommen aus der Seitenleiste.",
                unsafe_allow_html=True)
    u1, u2 = st.tabs(["Einzelberechnung", "Varianten"])
    with u1:
        a1, a2, a5, a6 = st.columns(4)
        ub_b = a1.number_input("Breite b (cm)", 10.0, 200.0, 30.0, 5.0, key="ub_b")
        ub_h = a2.number_input("Höhe h (cm)", 10.0, 200.0, 30.0, 5.0, key="ub_h")
        ub_e0 = a5.number_input("Ausmitte e0 (cm)", 0.0, 100.0, 0.0, 0.5, key="ub_e0")
        ub_N = a6.number_input("Charakt. Normalkraft N_k (kN)", 1.0, 100000.0, 200.0, 10.0, key="ub_N")
        st.caption(f"Aus der Seitenleiste: l₀ = {nk.fmt(l0, 2)} m, Beton {ub.fck_klasse(fck)}, φ_eff = {nk.fmt(phi, 2)}")
        if st.button("Berechnen 🚀", type="primary", key="ub_run"):
            try:
                html(ub.ausgabe_unbewehrt(ub.rechne_unbewehrt(ub_b, ub_h, l0, fck, ub_e0, ned(ub_N, ub_b, ub_h, l0), phi_ef=phi)))
            except Exception as ex:
                html(nk._box("rot", f"❌ Eingabefehler: {ex}"))
    with u2:
        st.markdown("Eine Zeile je Variante: `b h N_k [fck [e0]]` (cm, cm, kN charakteristisch, N/mm², cm). "
                    "Ohne e0 wird zentrisch gerechnet, ohne fck gilt der Wert in der Seitenleiste.")
        ub_text = st.text_area("Varianten", "20 20 100\n25 25 167 25 2,5\n30 30 267", height=120, key="ub_var")
        if st.button("Varianten rechnen 📋", key="ub_var_btn"):
            html(ub.varianten_unbewehrt(zeilen_ned(ub_text, l0), l0, fck, phi_ef=phi))

with top_vg:
    vergleich.seite(l0, fck, phi, c, bue, int(dl), int(n), d1)
