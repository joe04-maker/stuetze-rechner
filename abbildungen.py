"""N–M-Interaktionsdiagramm der bewehrten Stütze mit Lastpunkt (matplotlib).

Das Bild gehört zu den aktuellen Eingaben und wird nach „Berechnen" unter dem Ergebnis gezeigt.
"""
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import nennkruemmung_stuetze as nk

BLAU = "#2A6BD1"      # Beton / Widerstand
ORANGE = "#D4571F"    # Stahl / Einwirkung
GRUEN = "#2E8B57"
ROT = "#C0392B"
TINTE = "#222222"
GRAU = "#666666"
GITTER = "#DDDDDD"

_RC = {"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 9,
       "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRAU,
       "xtick.color": TINTE, "ytick.color": TINTE, "axes.labelcolor": TINTE, "text.color": TINTE}
MINUS = "−"


def K(v, d=1):
    """Zahl mit Dezimalkomma und echtem Minuszeichen."""
    t = f"{v:.{d}f}"
    if float(t) == 0:
        t = t.lstrip("-")
    return t.replace(".", ",").replace("-", MINUS)


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# =============================================================================
# N–M-Kurve mit Lastpunkt (bewehrt)
# =============================================================================
def _mrd_kurve(S, As):
    pts = []
    m0 = nk.m_rd(S, As, 0.0)
    if m0 is not None:
        pts.append((m0 / 1e6, 0.0))
    x = 5.0
    while x < 80000.0:
        N, M = nk.querschnitt(S, As, x)
        if N > 0:
            pts.append((M / 1e6, N / 1e3))
        x *= 1.012
    pts.append((0.0, nk.n_zentrisch(S, As) / 1e3))
    return np.array(pts)


def fig_nm(E, kurve=None):
    S, As = E.S, E.As_gew
    if kurve is None:
        kurve = _mrd_kurve(S, As)
    N0 = E.N0 / 1e3
    Ns = np.linspace(0.0, N0 * 0.999, 90)
    med = np.array([(N * nk.nennkruemmung(S, As, N * 1e3).e_tot / 1e3, N) for N in Ns])   # N [kN] * e_tot [mm] / 1000 -> kNm
    n_bieg = E.N_Rd_biegung / 1e3
    m_bieg = (nk.m_rd(S, As, E.N_Rd_biegung) or 0.0) / 1e6
    n_ed = E.N_Ed / 1e3
    m_ed = E.Med_Ned / 1e6
    ok = n_ed <= n_bieg * 1.0001
    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(6.2, 4.6))
        ax.fill(np.r_[kurve[:, 0], 0.0], np.r_[kurve[:, 1], 0.0], color=BLAU, alpha=0.07, lw=0)
        ax.plot(kurve[:, 0], kurve[:, 1], color=BLAU, lw=2.0, label="Querschnittswiderstand $M_{Rd}(N)$")
        ax.plot(med[:, 0], med[:, 1], color=ORANGE, lw=1.8, ls=(0, (5, 1.6)),
                label="Einwirkung $M_{Ed}(N) = N \\cdot e_{tot}$ (Nennkrümmung)")
        ax.plot([m_bieg], [n_bieg], "D", color="white", mec=TINTE, mew=1.6, ms=7, zorder=5, clip_on=False,
                label=f"$N_{{Rd}}$ aus Biegung = {K(n_bieg, 1)} kN")
        farbe = GRUEN if ok else ROT
        ax.plot([m_ed], [n_ed], "o", color=farbe, mec="white", mew=0.8, ms=8, zorder=6, clip_on=False,
                label=f"Lastpunkt $N_{{Ed}}$ = {K(n_ed, 1)} kN, $M_{{Ed}}$ = {K(m_ed, 1)} kNm")
        ax.set_xlim(0, max(kurve[:, 0].max(), m_ed) * 1.12)
        ax.set_ylim(0, max(N0, n_ed) * 1.08)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: K(v, 0)))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: K(v, 0)))
        ax.set_xlabel("Biegemoment $M$ in kNm")
        ax.set_ylabel("Normalkraft $N$ in kN")
        ax.grid(True, color=GITTER, lw=0.6)
        ax.set_axisbelow(True)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False, fontsize=8)
        ax.set_title("$N$–$M$-Interaktion der bewehrten Stütze", fontsize=9.5, loc="left")
        return fig


# =============================================================================
# Streamlit-Anzeige
# =============================================================================
def _zeige(st, fig_fn, *args, breite=None):
    try:
        kw = {} if breite is None else {"width": breite}        # Pixel; wird bei schmalem Fenster automatisch begrenzt
        st.image(_png(fig_fn(*args)), **kw)
    except Exception as ex:                          # eine Abbildung darf die Berechnung nie stören
        st.warning(f"Abbildung nicht möglich: {ex}")


def erlaeuterung(E, kurve):
    """Erklärtext zum Diagramm (HTML) mit den Zahlen der aktuellen Berechnung."""
    S, As = E.S, E.As_gew
    i_max = int(np.argmax(kurve[:, 0]))
    m_max, n_m_max = kurve[i_max, 0], kurve[i_max, 1]
    sig_s0 = min(S.fyd, nk.ES * nk.EPS_C2)
    n0 = E.N0 / 1e3
    m0 = nk.m_rd(S, As, 0.0)
    n_ed, m_ed = E.N_Ed / 1e3, E.Med_Ned / 1e6
    if E.Mrd_Ned is not None:
        m_rd_ned = E.Mrd_Ned / 1e6
        bei_last = (f"N<sub>Ed</sub> = {K(n_ed, 1)} kN: Der Querschnitt kann M<sub>Rd</sub> = "
                    f"<b>{K(m_rd_ned, 1)} kNm</b> aufnehmen. Die Einwirkung ist M<sub>Ed</sub> = {K(m_ed, 1)} kNm "
                    f"(Ausnutzung {K(100 * m_ed / m_rd_ned, 0)} %).")
    else:
        bei_last = (f"N<sub>Ed</sub> = {K(n_ed, 1)} kN liegt über der zentrischen "
                    f"Tragfähigkeit N<sub>0</sub>. Dafür gibt es kein M<sub>Rd</sub>, der Querschnitt reicht nicht.")
    return f"""
<div style="font-size:0.93em;line-height:1.5;">
<p><b>Blaue Kurve: Querschnittswiderstand M<sub>Rd</sub>(N)</b><br>
Sie zeigt das <b>größte Biegemoment, das der Querschnitt bei einer bestimmten Normalkraft N noch aufnehmen kann</b>.
Sie hängt nur vom Querschnitt ab, nicht von der Stützenlänge: Maße {K(S.b / 10, 0)} × {K(S.h / 10, 0)} cm,
Beton mit f<sub>cd</sub> = {K(S.fcd, 2)} N/mm², Bewehrung {E.n_st} Ø {E.d_l}
(A<sub>s</sub> = {K(As / 100, 2)} cm², f<sub>yd</sub> = {K(S.fyd, 1)} N/mm², Achsabstand d<sub>1</sub> = {K(S.d1, 0)} mm).</p>

<p><b>So entsteht ein Punkt der Kurve:</b></p>
<ol style="margin-top:0;">
<li>Man wählt eine Höhe x der Druckzone (Abstand der Nulllinie vom gedrückten Rand).</li>
<li>Daraus folgt die Dehnung über den Querschnitt: am gedrückten Rand 3,5 ‰ (Bruchstauchung des Betons),
nach innen nimmt sie linear bis zur Nulllinie auf 0 ab. Bei x &gt; h dreht sich die Dehnungsebene um einen Punkt
mit 2 ‰ bei 3/7 · h.</li>
<li>Aus den Dehnungen folgen die Spannungen: Beton nach dem Parabel-Rechteck-Diagramm (höchstens f<sub>cd</sub>),
Stahl elastisch-plastisch (höchstens f<sub>yd</sub>).</li>
<li>Spannung × Fläche ergibt die Kräfte. Alle Kräfte zusammen sind <b>N</b>. Alle Kräfte mal ihr Hebelarm zur
Querschnittsmitte zusammen sind <b>M<sub>Rd</sub></b>.</li>
</ol>
<p>Dann wählt man ein anderes x und erhält den nächsten Punkt. Alle Punkte zusammen sind die Kurve.</p>

<p><b>Besondere Punkte der Kurve:</b></p>
<ul style="margin-top:0;">
<li><b>Oben (M = 0):</b> zentrischer Druck, N<sub>0</sub> = A<sub>c</sub> · f<sub>cd</sub> + A<sub>s</sub> · σ<sub>s</sub>
= <b>{K(n0, 1)} kN</b> (Stahl bei 2 ‰, σ<sub>s</sub> = {K(sig_s0, 0)} N/mm²).</li>
<li><b>Unten (N = 0):</b> reine Biegung, M<sub>Rd</sub> = <b>{K((m0 or 0) / 1e6, 1)} kNm</b>.</li>
<li><b>Ganz rechts:</b> das größte Moment, M<sub>Rd,max</sub> = <b>{K(m_max, 1)} kNm</b> bei N ≈ {K(n_m_max, 0)} kN.
Das ist etwa der Balance-Punkt, bei dem Beton und Stahl gleichzeitig ihre Grenze erreichen.</li>
</ul>

<p><b>Bei deiner Last:</b> {bei_last}</p>

<p><b>Orange Kurve: Einwirkung M<sub>Ed</sub>(N) = N · e<sub>tot</sub></b><br>
Sie zeigt das Moment, das bei der jeweiligen Normalkraft wirklich entsteht (Nennkrümmungsverfahren, mit Imperfektion und
Verformung II. Ordnung). Sie hängt auch von der Stützenlänge ab. Wo sie die blaue Kurve schneidet, liegt N<sub>Rd</sub>.
Ein Knick oder Sprung entsteht dort, wo die Theorie II. Ordnung nötig wird (λ &gt; λ<sub>lim</sub>).</p>

<p><b>Merksatz:</b> Der Lastpunkt muss <b>innerhalb der blauen Kurve</b> liegen, dann gilt M<sub>Ed</sub> ≤ M<sub>Rd</sub> und
der Nachweis ist erfüllt.</p>
</div>
"""


def zeige_bewehrt(st, E):
    with st.expander("📐 N–M-Diagramm der Stütze", expanded=True):
        try:
            kurve = _mrd_kurve(E.S, E.As_gew)
        except Exception as ex:
            st.warning(f"Abbildung nicht möglich: {ex}")
            return
        _zeige(st, fig_nm, E, kurve, breite=760)
        try:
            st.markdown(erlaeuterung(E, kurve), unsafe_allow_html=True)
        except Exception as ex:
            st.warning(f"Erläuterung nicht möglich: {ex}")
