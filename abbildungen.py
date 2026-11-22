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


def fig_nm(E):
    S, As = E.S, E.As_gew
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


def zeige_bewehrt(st, E):
    with st.expander("📐 N–M-Diagramm der Stütze", expanded=True):
        _zeige(st, fig_nm, E, breite=760)
        st.caption("Der Nachweis ist erfüllt, wenn der Lastpunkt innerhalb der blauen Kurve liegt. "
                   "Die orange Kurve schneidet die blaue bei N_Rd. Ein Knick oder Sprung in der orangen Kurve "
                   "entsteht dort, wo die Theorie II. Ordnung nötig wird (λ > λ_lim).")
