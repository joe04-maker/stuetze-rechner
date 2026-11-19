"""Streamlit-Oberfläche: Stahlbetonstütze – Nennkrümmungsverfahren (DIN EN 1992-1-1 mit NA)."""
import streamlit as st

import nennkruemmung_stuetze as nk

st.set_page_config(page_title="Stahlbetonstütze – Nennkrümmung", page_icon="🏗️", layout="wide")
st.title("🏗️ Stahlbetonstütze – Nennkrümmungsverfahren")
st.caption("DIN EN 1992-1-1 mit Nationalem Anhang Deutschland · Pendelstütze, Biegung um eine Achse")


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def basis(l0, fck, phi, c, bue, modus, dl, n):
    return dict(l0_m=l0, fck=fck, e0_cm=0.0, phi_ef=phi, c_nom_mm=c, d_bue_mm=float(bue),
                modus=modus, d_l=int(dl), n_st=int(n))


with st.sidebar:
    st.header("Eingaben")
    l0 = st.number_input("Knicklänge l0 (m)", 0.1, 20.0, 2.90, 0.05, format="%.2f")
    fck = st.selectbox("f_ck (N/mm²)", nk.FCK_OPTIONEN, index=nk.FCK_OPTIONEN.index(25))
    phi = st.number_input("Kriechzahl φ_ef (-)", 0.0, 5.0, 0.0, 0.1)
    c = st.number_input("Nennbetondeckung (mm)", 10.0, 80.0, 20.0, 1.0)
    bue = st.selectbox("Bügel Ø (mm)", [6, 8, 10, 12], index=1)
    modus_txt = st.radio("Bewehrung", ["Vorgeben (Standard: 4 Ø12, je Ecke 1 Stab)",
                                       "Automatisch wählen (kleinste ausreichende)"])
    modus = "fix" if modus_txt.startswith("Vorgeben") else "auto"
    dl = st.selectbox("Längsstab Ø (mm)", nk.STAB_D, index=0, disabled=modus == "auto")
    n = st.selectbox("Anzahl Stäbe (min. 4)", nk.STAB_N, index=0, disabled=modus == "auto")

tab1, tab2, tab3 = st.tabs(["Einzelberechnung", "Varianten", "Vergleich mit mb"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    b = c1.number_input("Breite b (cm)", 10.0, 200.0, 20.0, 1.0)
    h = c2.number_input("Höhe h (cm)", 10.0, 200.0, 20.0, 1.0)
    N = c3.number_input("Normalkraft N_Ed (kN)", 1.0, 100000.0, 645.3, 1.0)
    e0 = c4.number_input("Lastausmitte e0 (cm)", 0.0, 100.0, 0.0, 0.5)
    if st.button("Berechnen 🚀", type="primary"):
        try:
            kw = basis(l0, fck, phi, c, bue, modus, dl, n)
            kw["e0_cm"] = e0
            html(nk.ausgabe(nk.berechne(b, h, N_Ed_kN=N, **kw)))
        except ValueError as ex:
            html(nk._box("rot", f"❌ Eingabefehler: {ex}"))
        except Exception as ex:
            html(nk._box("rot", f"❌ {type(ex).__name__}: {ex}"))

with tab2:
    st.markdown("Eine Zeile je Variante: `b h N_Ed [fck [e0]]` (cm, cm, kN, N/mm², cm). "
                "Ohne e0 wird zentrisch gerechnet, ohne fck gilt der Wert links.")
    text = st.text_area("Varianten", "20 20 645,3\n20 20 528,3 25 2\n25 25 973,5\n25 25 792,9 25 2,5",
                        height=140)
    if st.button("Varianten rechnen 📋"):
        html(nk.varianten_html(text, basis(l0, fck, phi, c, bue, modus, dl, n)))

with tab3:
    st.markdown("Rechnet die sechs mb-BauStatik-Positionen (4 Ø12, N_Ed aus mb) mit diesem Programm nach.")
    if st.button("Vergleich mit mb-Ausdruck 📊"):
        html(nk.mb_vergleich_html(l0_m=l0, fck=fck, c_nom_mm=c, d_bue_mm=float(bue), phi_ef=phi))
