"""Vergleich bewehrte ↔ unbewehrte Stütze: gleiche Stützen, N_Rd,max nebeneinander."""
import re

import altair as alt
import pandas as pd
import streamlit as st

import nennkruemmung_stuetze as nk
import unbewehrt_stuetze as ub

FARBE_UNB = "#6c8ebf"
FARBE_BEW = "#c0392b"


def _zahl(t):
    return float(t.replace(",", "."))


@st.cache_data(show_spinner=False)
def n_rd_bewehrt(b, h, l0, fck, e0, phi, c, bue, d_l, n_st):
    """N_Rd,max [kN] der bewehrten Stütze, maßgebend ('Biegung'/'As,min')."""
    S = nk.Stuetze(b=b * 10, h=h * 10, l0=l0 * 1000, fck=float(fck), d1=c + bue + d_l / 2.0,
                   e0=e0 * 10, phi_ef=phi)
    As = n_st * 3.141592653589793 * d_l ** 2 / 4.0
    bieg, asmin = nk.n_rd_biegung(S, As), nk.n_rd_asmin(S, As)
    return min(bieg, asmin) / 1000.0, ("Biegung" if bieg <= asmin else "As,min")


def n_rd_unbewehrt(b, h, l0, fck, e0):
    return ub.rechne_unbewehrt(b, h, l0, fck, e0, 1.0)["N_Rd"]


def tabelle(faelle, l0, fck, phi, c, bue, d_l, n_st):
    zeilen = []
    for b, h, e0 in faelle:
        nb, massg = n_rd_bewehrt(b, h, l0, fck, e0, phi, c, bue, d_l, n_st)
        nu = n_rd_unbewehrt(b, h, l0, fck, e0)
        r = ub.rechne_unbewehrt(b, h, l0, fck, e0, 1.0)
        zeilen.append(dict(
            Fall=f"{b:.0f}×{h:.0f}, " + ("zentrisch" if e0 == 0 else f"e0 = {e0:g} cm"),
            **{"λ": r["lam"], "N_Rd unbewehrt [kN]": nu, "N_Rd bewehrt [kN]": nb,
               "Zuwachs [kN]": nb - nu, "Zuwachs [%]": (nb / nu - 1) * 100 if nu > 0 else float("nan"),
               "Faktor bew./unbew.": nb / nu if nu > 0 else float("nan"), "maßgebend (bewehrt)": massg}))
    return pd.DataFrame(zeilen)


def balken(df):
    lang = df.melt(id_vars="Fall", value_vars=["N_Rd unbewehrt [kN]", "N_Rd bewehrt [kN]"],
                   var_name="Stütze", value_name="N_Rd")
    lang["Stütze"] = lang["Stütze"].str.replace("N_Rd ", "").str.replace(" [kN]", "")
    reihenfolge = list(df["Fall"])
    basis = alt.Chart(lang).encode(
        x=alt.X("Fall:N", sort=reihenfolge, title=None, axis=alt.Axis(labelAngle=-30)),
        xOffset=alt.XOffset("Stütze:N", sort=["unbewehrt", "bewehrt"]),
        y=alt.Y("N_Rd:Q", title="N_Rd,max [kN]"),
        color=alt.Color("Stütze:N", sort=["unbewehrt", "bewehrt"],
                        scale=alt.Scale(domain=["unbewehrt", "bewehrt"], range=[FARBE_UNB, FARBE_BEW]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=["Fall", "Stütze", alt.Tooltip("N_Rd:Q", title="N_Rd [kN]", format=".1f")])
    text = basis.mark_text(dy=-6, fontSize=11).encode(text=alt.Text("N_Rd:Q", format=".0f"))
    return (basis.mark_bar() + text).properties(height=380)


def linie(b, h, l0, fck, phi, c, bue, d_l, n_st, e_max, schritte):
    daten = []
    for k in range(schritte + 1):
        e0 = e_max * k / schritte
        daten.append(dict(e0=e0, Stütze="unbewehrt", N=n_rd_unbewehrt(b, h, l0, fck, e0)))
        daten.append(dict(e0=e0, Stütze="bewehrt", N=n_rd_bewehrt(b, h, l0, fck, e0, phi, c, bue, d_l, n_st)[0]))
    df = pd.DataFrame(daten)
    return alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("e0:Q", title="Lastausmitte e0 [cm]"),
        y=alt.Y("N:Q", title="N_Rd,max [kN]", scale=alt.Scale(zero=True)),
        color=alt.Color("Stütze:N", scale=alt.Scale(domain=["unbewehrt", "bewehrt"],
                                                    range=[FARBE_UNB, FARBE_BEW]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=["Stütze", alt.Tooltip("e0:Q", format=".2f"), alt.Tooltip("N:Q", format=".1f")]
    ).properties(height=380)


def seite(l0, fck, phi, c, bue, d_l, n_st):
    st.markdown(f"Gleiche Stützen, **unbewehrt** (Skript-Rechenweg) gegen **bewehrt** ({n_st} Ø{d_l}, "
                f"Nennkrümmungsverfahren). Knicklänge l₀ = {l0:g} m, C{fck}/{fck + 5}, c_nom = {c:g} mm, "
                f"Bügel Ø{bue} und φ_ef = {phi:g} kommen aus der Seitenleiste. Bewehrung: immer wie dort "
                f"eingestellt (feste Stabwahl, auch im Automatik-Modus).")
    t1, t2, t3 = st.tabs(["Tabelle", "Balkendiagramm", "Verlauf über e0"])
    with t1:
        st.markdown("Eine Zeile je Fall: `b h e0` (cm, cm, cm). e0 = 0 bedeutet zentrisch.")
        text = st.text_area("Fälle", "20 20 0\n20 20 2\n25 25 0\n25 25 2,5\n30 30 0\n30 30 3",
                            height=150, key="vg_text")
        faelle, fehler = [], []
        for nr, z in enumerate(text.splitlines(), 1):
            z = z.strip()
            if not z or z.startswith("#"):
                continue
            try:
                t = [x for x in re.split(r"[;\s]+", z) if x]
                if len(t) not in (2, 3):
                    raise ValueError("erwartet: b h [e0]")
                faelle.append((_zahl(t[0]), _zahl(t[1]), _zahl(t[2]) if len(t) == 3 else 0.0))
            except Exception as ex:
                fehler.append(f"Zeile {nr}: „{z}“ → {ex}")
        for f in fehler:
            st.error(f)
        if st.button("Vergleich berechnen 📊", type="primary", key="vg_btn") or st.session_state.get("vg_df") is not None:
            if faelle:
                with st.spinner("Rechne …"):
                    df = tabelle(faelle, l0, fck, phi, c, bue, d_l, n_st)
                st.session_state["vg_df"] = df
        df = st.session_state.get("vg_df")
        if df is not None:
            st.dataframe(
                df.style.format({"λ": "{:.1f}", "N_Rd unbewehrt [kN]": "{:.1f}", "N_Rd bewehrt [kN]": "{:.1f}",
                                 "Zuwachs [kN]": "{:+.1f}", "Zuwachs [%]": "{:+.0f} %",
                                 "Faktor bew./unbew.": "{:.2f}"}, decimal=",") ,
                hide_index=True, width="stretch")
            st.download_button("Tabelle als CSV ⬇️", df.to_csv(index=False, sep=";", decimal=","),
                               "vergleich_bewehrt_unbewehrt.csv", "text/csv")
    with t2:
        df = st.session_state.get("vg_df")
        if df is None:
            st.info("Zuerst im Tab **Tabelle** auf „Vergleich berechnen“ klicken.")
        else:
            st.altair_chart(balken(df), width="stretch")
            st.caption("Als Bild speichern: Menü ⋮ oben rechts im Diagramm → „Save as PNG“.")
    with t3:
        a1, a2, a3, a4 = st.columns(4)
        b = a1.number_input("Breite b (cm)", 10.0, 200.0, 30.0, 5.0, key="vg_b")
        h = a2.number_input("Höhe h (cm)", 10.0, 200.0, 30.0, 5.0, key="vg_h")
        e_max = a3.number_input("e0 bis (cm)", 0.5, 100.0, round(h / 3, 1), 0.5, key="vg_emax")
        schritte = a4.selectbox("Punkte", [6, 8, 10, 12], index=2, key="vg_n")
        if st.button("Verlauf zeichnen 📈", key="vg_line_btn"):
            with st.spinner("Rechne …"):
                st.session_state["vg_line"] = linie(b, h, l0, fck, phi, c, bue, d_l, n_st, e_max, schritte)
        if st.session_state.get("vg_line") is not None:
            st.altair_chart(st.session_state["vg_line"], width="stretch")
            st.caption("Hinweis: Die unbewehrte Kurve endet bei großer Ausmitte am Mindestwert Θ = 0,1 "
                       "(Begrenzung im Skript). Als Bild speichern: Menü ⋮ → „Save as PNG“.")
