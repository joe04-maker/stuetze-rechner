# @title 🏗️ Stahlbetonstütze – Nennkrümmungsverfahren (DIN EN 1992-1-1 mit NA Deutschland)
"""
Bewehrte Rechteckstütze, Biegung um eine Achse, Bewehrung in 2 Lagen (As/2 je Seite).
Vorgehen: Pendelstütze, Nennkrümmungsverfahren:

  * Schlankheit, Grenzschlankheit (NA 5.8.3.1), Imperfektion e_i = l0/400
  * Momente I. Ordnung entlang der Stütze: M0Ed(x) = N·(e_i + Ausmitte(x)),
    Ausmitte linear zwischen Fuß und Kopf
  * Moment II. Ordnung: M2(x) = N·e2·sin(π·x/l0)  (Nennkrümmung, EC2 5.8.8)
  * Bemessung am kritischen Schnitt:  max_x [M0Ed(x) + M2(x)]  <=  M_Rd(N)
  * maximale Tragfähigkeit N_Rd,max = min( Biegung ; Mindestbewehrung N = As·f_yd/0,15 )
  * erforderliche Bewehrung, Stabwahl, Varianten-Tabelle, Vergleich mit mb-Ausdruck

Einheiten im Code: N, mm  (Eingabe in der Oberfläche: kN, cm, m).
"""
import math
import re
from dataclasses import dataclass

try:                                   # nur für Colab nötig (nicht für Streamlit)
    import ipywidgets as widgets
    from IPython.display import HTML, display
except ImportError:
    widgets = HTML = display = None

# =============================================================================
# 1) KONSTANTEN
# =============================================================================
ES = 200_000.0        # E-Modul Betonstahl [N/mm²]
FYK = 500.0           # B500B [N/mm²]
GAMMA_C = 1.5
GAMMA_S = 1.15
ALPHA_CC = 0.85       # NA Deutschland
EPS_C2 = 0.002        # Parabel-Rechteck-Diagramm (fck <= 50)
EPS_CU = 0.0035
N_STREIFEN = 200      # Betonstreifen für die Integration
K_ASMIN = 0.15        # A_s,min = 0,15·N_Ed/f_yd   (NA 9.5.2(2), Gl. 9.12DE)
AUSN_MAX = 100.01     # Nachweis erfüllt, solange die auf 2 Stellen gerundete Ausnutzung <= 100,01 % ist
STAB_D = (12, 14, 16, 20, 25, 28)       # Ø_min = 12 mm (NA)
STAB_N = (4, 6, 8, 10, 12)              # gerade Anzahl, mind. 4 (je Ecke 1 Stab)
FCK_OPTIONEN = (12, 16, 20, 25, 30, 35, 40, 45, 50)


def fmt(x, nd=2):
    """Zahl mit Dezimalkomma; None/inf/nan -> Strich."""
    if x is None or (isinstance(x, float) and (math.isinf(x) or math.isnan(x))):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",")


# =============================================================================
# 1b) BETONDECKUNG nach DIN EN 1992-1-1:2025-09 (= EN 1992-1-1:2023), Abschnitt 6.5
#     (6.1)  c_nom = c_min + Δc_dev
#     (6.2)  c_min = max{ c_min,dur + ΣΔc ; c_min,b ; 10 mm }
#     c_min,dur: Tabelle 6.3 (Karbonatisierung XC) / Tabelle 6.4 (Chloride XS, XD) in Abhängigkeit von
#                Expositionswiderstandsklasse (XRC / XRDS) und Nutzungsdauer (50 / 100 Jahre), oder
#                alternativ Anhang P (Anforderungsklasse S1 ... S6, Tabelle P.2)
#     c_min,b  : Tabelle 6.5, Einzelstäbe = Stabdurchmesser (bei der Stütze der außen liegende Bügel)
#     Δc_dev   : Tabelle 6.7 (NDP)
#     ΣΔc = 0 angesetzt (keine Reduktionen/Erhöhungen); empfohlene Werte, Nationaler Anhang nicht berücksichtigt.
# =============================================================================
VERFAHREN_ERC = "ERC (Tabelle 6.3 / 6.4)"
VERFAHREN_P = "Anhang P (Anforderungsklasse S1–S6)"
VERFAHREN = (VERFAHREN_ERC, VERFAHREN_P)
EXPO_KLASSEN = ("X0", "XC1", "XC2", "XC3", "XC4", "XD1", "XD2", "XD3", "XS1", "XS2", "XS3")
ERC_KLASSEN = (0.5, 1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10)        # Zahl hinter XRC bzw. XRDS
S_KLASSEN = ("S1", "S2", "S3", "S4", "S5", "S6")
NUTZUNGSDAUER = (50, 100)
MANUELL = "manuell"

# Tabelle 6.3: Spalten XC1(50,100) XC2(50,100) XC3(50,100) XC4(50,100)
_T63 = {0.5: (10, 10, 10, 10, 10, 10, 10, 10), 1: (10, 10, 10, 10, 10, 15, 10, 15),
        2: (10, 15, 10, 15, 15, 25, 15, 25), 3: (10, 15, 15, 20, 20, 30, 20, 30),
        4: (10, 20, 15, 25, 25, 35, 25, 40), 5: (15, 25, 20, 30, 25, 45, 30, 45),
        6: (15, 25, 25, 35, 35, 55, 40, 55), 7: (15, 30, 25, 40, 40, 60, 45, 60)}
_C63 = ("XC1", "XC2", "XC3", "XC4")
# Tabelle 6.4: Spalten XS1 XS2 XS3 XD1 XD2 XD3, je (50, 100); None = in der Norm "—"
_T64 = {0.5: (20, 20, 20, 30, 30, 40, 20, 20, 20, 30, 30, 40),
        1: (20, 25, 25, 35, 35, 45, 20, 25, 25, 35, 35, 45),
        1.5: (25, 30, 30, 40, 40, 50, 25, 30, 30, 40, 40, 50),
        2: (25, 30, 35, 45, 45, 55, 25, 30, 35, 45, 45, 55),
        3: (30, 35, 40, 50, 55, 65, 30, 35, 40, 50, 55, 65),
        4: (30, 40, 50, 60, 60, 80, 30, 40, 50, 60, 60, 80),
        5: (35, 45, 60, 70, 70, None, 35, 45, 60, 70, 70, None),
        6: (40, 50, 65, 80, None, None, 40, 50, 65, 80, None, None),
        8: (45, 55, 75, None, None, None, 45, 55, 75, None, None, None),
        10: (50, 65, 80, None, None, None, 50, 65, 80, None, None, None)}
_C64 = ("XS1", "XS2", "XS3", "XD1", "XD2", "XD3")
# Tabelle P.2 (unlegierter Betonstahl): Spalten X0, XC1, XC2/XC3, XC4, XD1/XS1, XD2/XS2, XD3/XS3
_TP2 = {"S1": (10, 10, 10, 15, 20, 25, 30), "S2": (10, 10, 15, 20, 25, 30, 35),
        "S3": (10, 10, 20, 25, 30, 35, 40), "S4": (10, 15, 25, 30, 35, 40, 45),
        "S5": (15, 20, 30, 35, 40, 45, 50), "S6": (20, 25, 35, 40, 45, 50, 55)}
_P_SPALTE = {"X0": 0, "XC1": 1, "XC2": 2, "XC3": 2, "XC4": 3, "XD1": 4, "XS1": 4,
             "XD2": 5, "XS2": 5, "XD3": 6, "XS3": 6}
# Tabelle 6.7 (NDP): Vorhaltemaß Δc_dev [mm]
DC_DEV_FAELLE = {
    "Fall 1: Toleranzklasse 1 (allgemein)": 10,
    "Fall 2: Toleranzklasse 2": 5,
    "Fall 3: Qualitätssicherung mit Messung der Betondeckung": 5,
    "Fall 4: genaues Messgerät, nichtkonforme Bauteile ausgesondert": 0,
    "Fall 5: XC1, Korrosionsrisiko unerheblich": 5}
DC_DEV_STANDARD = "Fall 1: Toleranzklasse 1 (allgemein)"


def betondeckung(expo, d_bue, verfahren=VERFAHREN_ERC, erc=3, sklasse="S4", nd=50,
                 dc_dev_fall=DC_DEV_STANDARD):
    """Nennmaß der Betondeckung [mm] nach EC2:2025-09, 6.5. Rückgabe: dict mit allen Zwischenwerten."""
    if expo not in EXPO_KLASSEN:
        raise ValueError(f"Unbekannte Expositionsklasse: {expo}")
    if nd not in NUTZUNGSDAUER:
        raise ValueError("Nutzungsdauer: 50 oder 100 Jahre.")
    if dc_dev_fall not in DC_DEV_FAELLE:
        raise ValueError("Unbekannter Fall für Δc_dev.")
    if dc_dev_fall.startswith("Fall 5") and expo != "XC1":
        raise ValueError("Fall 5 (Δc_dev = 5 mm) gilt nur für XC1.")
    spalte = 0 if nd == 50 else 1
    if verfahren == VERFAHREN_ERC:
        if expo == "X0":
            raise ValueError("Für X0 enthalten Tabelle 6.3 und 6.4 keine Werte. Anhang P verwenden.")
        if expo in _C63:
            tab, namen, kurz = _T63, _C63, "XRC"
        else:
            tab, namen, kurz = _T64, _C64, "XRDS"
        if erc not in tab:
            raise ValueError(f"{kurz} {erc:g} gibt es für {expo} nicht "
                             f"(Tabelle {'6.3' if tab is _T63 else '6.4'}: {', '.join(f'{k:g}' for k in tab)}).")
        c_dur = tab[erc][2 * namen.index(expo) + spalte]
        if c_dur is None:
            raise ValueError(f"{expo} / {kurz} {erc:g} / {nd} Jahre: in Tabelle 6.4 nicht zulässig (—).")
        klasse_txt = f"{kurz} {erc:g}".replace(".", ",")
    else:
        if sklasse not in _TP2:
            raise ValueError("Anforderungsklasse S1 bis S6.")
        idx = min(int(sklasse[1]) - 1 + (2 if nd == 100 else 0), 5)      # 100 Jahre: Klasse um 2 erhöht (Tab. P.1)
        eff = f"S{idx + 1}"
        c_dur = _TP2[eff][_P_SPALTE[expo]]
        klasse_txt = sklasse if eff == sklasse else f"{sklasse} → {eff} (100 Jahre)"
    c_min_b = float(d_bue)                                   # Tabelle 6.5: Einzelstab = Stabdurchmesser (Bügel)
    c_min = max(float(c_dur), c_min_b, 10.0)                 # (6.2) mit ΣΔc = 0
    dc_dev = float(DC_DEV_FAELLE[dc_dev_fall])
    return dict(expo=expo, verfahren=verfahren, klasse=klasse_txt, nd=nd, c_min_b=c_min_b,
                c_min_dur=float(c_dur), c_min=c_min, dc_dev=dc_dev, dc_dev_fall=dc_dev_fall,
                c_nom=c_min + dc_dev)                        # (6.1)


# =============================================================================
# 2) MODELL DER STÜTZE
# =============================================================================
@dataclass(frozen=True)
class Stuetze:
    b: float                  # Breite [mm]
    h: float                  # Höhe in Biegerichtung [mm]
    l0: float                 # Knicklänge [mm] (Pendelstütze: = Systemlänge)
    fck: float                # [N/mm²]
    d1: float                 # Achsabstand der Bewehrung vom Rand [mm]
    e0: float = 0.0           # planmäßige Ausmitte der Last am Kopf [mm] (Fuß: momentenfrei)
    phi_ef: float = 0.0       # effektive Kriechzahl [-]
    mit_emin: bool = False    # Mindestausmitte max(h/30; 20 mm) zusätzlich ansetzen
    ausgabe: str = "2025"     # "2025" = DIN EN 1992-1-1:2025-09 (Anhang O.7); "2011" = DIN EN 1992-1-1:2011 + NA

    def __post_init__(self):
        if min(self.b, self.h, self.l0) <= 0:
            raise ValueError("b, h und l0 müssen größer als 0 sein.")
        if not (12 <= self.fck <= 50):
            raise ValueError("f_ck muss zwischen 12 und 50 N/mm² liegen "
                             "(Parabel-Rechteck-Diagramm gilt bis C50/60).")
        if self.e0 < 0 or self.phi_ef < 0:
            raise ValueError("e0 und φ_ef dürfen nicht negativ sein.")
        if not (0 < self.d1 < self.h / 2):
            raise ValueError(f"Achsabstand d1 = {self.d1:.1f} mm passt nicht zur Höhe "
                             f"h = {self.h:.0f} mm (0 < d1 < h/2).")

    @property
    def fcd(self):
        return ALPHA_CC * self.fck / GAMMA_C

    @property
    def fyd(self):
        return FYK / GAMMA_S

    @property
    def Ac(self):
        return self.b * self.h

    @property
    def i(self):
        return self.h / math.sqrt(12.0)

    @property
    def lam(self):
        return self.l0 / self.i


# =============================================================================
# 3) QUERSCHNITTSWIDERSTAND (Dehnungsebene, Parabel-Rechteck-Diagramm)
#    Druck positiv. Moment um die Querschnittsmitte.
# =============================================================================
def beton_spannung(eps, fcd):
    if eps <= 0.0:
        return 0.0
    if eps < EPS_C2:
        return fcd * (1.0 - (1.0 - eps / EPS_C2) ** 2)
    return fcd


def querschnitt(S, As, x):
    """Innere Kräfte N [N] und Moment M [Nmm] bei Druckzonenhöhe x [mm]."""
    h, b, d1, fcd, fyd = S.h, S.b, S.d1, S.fcd, S.fyd
    if x <= h:
        kappa = EPS_CU / x                         # 3,5 ‰ am Druckrand
    else:
        kappa = EPS_C2 / (x - 3.0 * h / 7.0)       # Drehpunkt 2 ‰ bei 3h/7
    dy = h / N_STREIFEN
    N = 0.0
    M = 0.0
    for k in range(N_STREIFEN):
        y = (k + 0.5) * dy
        F = beton_spannung(kappa * (x - y), fcd) * b * dy
        N += F
        M += F * (h / 2.0 - y)
    for y in (d1, h - d1):
        sig = max(-fyd, min(fyd, ES * kappa * (x - y)))
        F = sig * As / 2.0
        N += F
        M += F * (h / 2.0 - y)
    return N, M


def m_rd(S, As, N):
    """Aufnehmbares Moment bei Normalkraft N (Bisektion über x). None: N nicht aufnehmbar."""
    lo, hi = 1.0, 1.0e5
    if N < querschnitt(S, As, lo)[0] or N > querschnitt(S, As, hi)[0]:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if querschnitt(S, As, mid)[0] < N:
            lo = mid
        else:
            hi = mid
    return querschnitt(S, As, 0.5 * (lo + hi))[1]


def n_zentrisch(S, As):
    """Zentrische Querschnittstragfähigkeit (Stahl bei ε_c2 = 2 ‰)."""
    return S.Ac * S.fcd + As * min(S.fyd, ES * EPS_C2)


# =============================================================================
# 4) NENNKRÜMMUNGSVERFAHREN (EC2 5.8.8, NA) mit Momentenverlauf
# =============================================================================
@dataclass
class Kruemmung:
    n: float
    omega: float
    lam: float
    lam_lim: float
    theorie2: bool
    e_i: float                # Imperfektion e_i = l0/400 [mm]
    e_min: float              # Mindestausmitte max(h/30; 20 mm) [mm]
    e_kopf: float             # Ausmitte I. Ordnung am Kopf  (e0 + e_i) [mm]
    e_fuss: float             # Ausmitte I. Ordnung am Fuß   (e0,u + e_i) [mm]
    k1: float = 0.0
    Kr: float = 0.0
    Kphi: float = 1.0
    inv_r0: float = 0.0       # [1/mm]
    inv_r: float = 0.0        # [1/mm]
    e2: float = 0.0           # größte Zusatzausmitte (Stützenmitte) [mm]
    xi_krit: float = 1.0      # kritischer Schnitt x/l0 (0 = Fuß, 1 = Kopf)
    e0_krit: float = 0.0      # Ausmitte I. Ordnung am kritischen Schnitt [mm]
    e2_krit: float = 0.0      # Zusatzausmitte am kritischen Schnitt [mm]
    e_tot: float = 0.0        # = e0_krit + e2_krit  (maßgebend für M_Ed = N·e_tot)


def _kritischer_schnitt(e_fuss, e_kopf, e2):
    """Maximum von g(ξ) = e_fuss + (e_kopf − e_fuss)·ξ + e2·sin(π·ξ) über ξ ∈ [0; 1]."""
    kand = [(e_fuss, 0.0), (e_kopf, 1.0)]
    d = e_kopf - e_fuss
    if e2 > 0.0 and abs(d) < math.pi * e2:
        xi = math.acos(-d / (math.pi * e2)) / math.pi
        kand.append((e_fuss + d * xi + e2 * math.sin(math.pi * xi), xi))
    return max(kand)


def nennkruemmung(S, As, N):
    omega = As * S.fyd / (S.Ac * S.fcd)
    n = max(N / (S.Ac * S.fcd), 1e-6)
    lam = S.lam
    if S.ausgabe == "2011":
        lam_lim = 25.0 if n >= 0.41 else 16.0 / math.sqrt(n)     # DIN EN 1992-1-1/NA 5.8.3.1(1)
    else:                                                    # EN 1992-1-1:2023, Gl. (O.12)
        A = 1.0 / (1.0 + 0.2 * S.phi_ef)
        B = math.sqrt(1.0 + 2.0 * omega)
        C = 0.7                                              # C = 1,7 − r_m, r_m = 1,0 (konservativ)
        lam_lim = 20.0 * A * B * C / math.sqrt(n)

    e_i = S.l0 / 400.0                                       # = θ_i · l0/2, θ_i = 1/200
    e_min = max(S.h / 30.0, 20.0)
    e_kopf = S.e0 + e_i
    e_fuss = e_i                                             # Fuß: nur Imperfektion
    if S.mit_emin:
        e_kopf = max(e_kopf, e_min)
        e_fuss = max(e_fuss, e_min)

    k = Kruemmung(n=n, omega=omega, lam=lam, lam_lim=lam_lim, theorie2=lam > lam_lim,
                  e_i=e_i, e_min=e_min, e_kopf=e_kopf, e_fuss=e_fuss)

    if k.theorie2:
        d = S.h - S.d1                                       # d = h/2 + i_s (2 Lagen)
        if S.ausgabe == "2011":
            k.inv_r0 = (S.fyd / ES) / (0.45 * d)             # 2011: 1/r0 = εyd/(0,45 d)
        else:
            k.inv_r0 = 2.0 * (S.fyd / ES) / (S.h - 2.0 * S.d1)   # 2025, Gl. (O.19): 1/r0 = 2 εyd/(d − d')
        n_u, n_bal = 1.0 + omega, 0.4
        k.Kr = min(1.0, max(0.0, (n_u - n) / (n_u - n_bal)))
        beta = max(0.0, 0.35 + S.fck / 200.0 - lam / 150.0)
        k.Kphi = max(1.0, 1.0 + beta * S.phi_ef)
        if S.ausgabe == "2011":
            k.k1 = 1.0 if lam >= 35.0 else min(1.0, max(0.0, lam / 10.0 - 2.5))
        else:
            k.k1 = 1.0                                       # 2025: kein k1 in O.7.3
        k.inv_r = k.k1 * k.Kr * k.Kphi * k.inv_r0
        k.e2 = k.inv_r * S.l0 ** 2 / 10.0

    g, xi = _kritischer_schnitt(e_fuss, e_kopf, k.e2)
    k.xi_krit = xi
    k.e0_krit = e_fuss + (e_kopf - e_fuss) * xi
    k.e2_krit = k.e2 * math.sin(math.pi * xi)
    k.e_tot = g
    return k


def nachweis(S, As, N):
    """(ok, M_Rd, M_Ed, Kruemmung) für Normalkraft N."""
    k = nennkruemmung(S, As, N)
    Mrd = m_rd(S, As, N)
    Med = N * k.e_tot
    return (Mrd is not None and Mrd >= Med), Mrd, Med, k


def n_rd_biegung(S, As):
    """Größte Normalkraft mit M_Ed(N) <= M_Rd(N) (Bisektion)."""
    lo, hi = 0.0, querschnitt(S, As, 1.0e5)[0]
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if nachweis(S, As, mid)[0]:
            lo = mid
        else:
            hi = mid
    return lo


def as_min(ausgabe, N, Ac, fyd):
    """Mindest-Längsbewehrung [mm²].
    2011 (NA 9.5.2(2), Gl. 9.12DE): 0,15·N_Ed/f_yd.
    2025 (DIN EN 1992-1-1:2025-09, Tabelle 12.3 (NDP), Zeile 1): max(0,1·N_Ed/f_yd; 0,002·A_c)."""
    if ausgabe == "2011":
        return K_ASMIN * N / fyd
    return max(0.1 * N / fyd, 0.002 * Ac)


def n_rd_asmin(S, As):
    """Normalkraft, bis zu der As >= A_s,min erfüllt ist (2011: As·fyd/0,15; 2025: As·fyd/0,1, sofern As >= 0,002·Ac)."""
    if S.ausgabe == "2011":
        return As * S.fyd / K_ASMIN
    return As * S.fyd / 0.1 if As >= 0.002 * S.Ac else 0.0


def n_rd_max(S, As):
    """Maximale Tragfähigkeit: kleinerer Wert aus Biegung und Mindestbewehrung."""
    return min(n_rd_biegung(S, As), n_rd_asmin(S, As))


def as_erforderlich(S, N_Ed):
    """Kleinste Bewehrungsfläche [mm²] aus der Biegebemessung für N_Ed (ohne A_s,min).
    None: auch mit As,max nicht möglich."""
    As_max = 0.04 * S.Ac
    if nachweis(S, 0.0, N_Ed)[0]:
        return 0.0
    if not nachweis(S, As_max, N_Ed)[0]:
        return None
    lo, hi = 0.0, As_max
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if nachweis(S, mid, N_Ed)[0]:
            hi = mid
        else:
            lo = mid
    return hi


# =============================================================================
# 5) GESAMTBERECHNUNG
# =============================================================================
@dataclass
class Ergebnis:
    S: Stuetze
    N_Ed: float
    n_st: int
    d_l: int
    d_bue: float
    As_gew: float
    As_min: float
    As_max: float
    As_erf: object            # float | None  (Biegebemessung)
    N_Rd: float               # = min(N_Rd_biegung, N_Rd_asmin)
    N_Rd_biegung: float
    N_Rd_asmin: float
    massgebend: str
    ok_N: bool
    Mrd_Ned: object           # float | None
    Med_Ned: float
    kru: Kruemmung
    N0: float
    a_clear: float
    hinweise: list
    modus: str
    gefunden: bool = True     # False: keine Bewehrung (<= 4 % Ac) reicht (Auto-Modus)
    deckung: object = None    # dict aus betondeckung() oder None (c_nom von Hand)
    d1_manuell: bool = False  # d1 wurde von Hand vorgegeben (nur Modus 'fix')


def _stab_kandidaten(b, c_nom, d_bue, As_min, As_max):
    out = []
    for n in STAB_N:
        for d in STAB_D:
            As = n * math.pi * d ** 2 / 4.0
            if As < As_min or As > As_max:
                continue
            n_seite = n // 2
            a = (b - 2.0 * (c_nom + d_bue) - n_seite * d) / (n_seite - 1)
            if a < max(float(d), 20.0):
                continue
            out.append((As, n, d))
    # Praxis: zuerst 4 Stäbe (je Ecke 1 Stab) mit steigendem Ø, erst danach 6, 8, 10, 12 Stäbe
    return sorted(out, key=lambda t: (t[1], t[2]))


def berechne(b_cm, h_cm, l0_m, fck, e0_cm, N_Ed_kN, phi_ef, c_nom_mm, d_bue_mm,
             mit_emin=False, modus="fix", d_l=12, n_st=4, d1_mm=None, deck=None, ausgabe="2025"):
    """modus 'fix': Bewehrung n_st Ø d_l vorgegeben.  modus 'auto': kleinste ausreichende Stabwahl.
    e0_cm = Lastausmitte am Kopf (Pendelstütze, Fuß momentenfrei).
    d1_mm = Achsabstand vom Rand (nur Modus 'fix'); None/0 = automatisch c_nom + Bügel-Ø + Stab-Ø/2.
            Im Modus 'auto' wird d1 immer aus c_nom und dem gewählten Stab-Ø berechnet.
    deck = dict(expo=..., verfahren=..., erc=..., sklasse=..., nd=..., dc_dev_fall=...): c_nom nach EC2 6.5 berechnen
           (c_nom_mm wird ignoriert); None: c_nom_mm von Hand."""
    if N_Ed_kN <= 0:
        raise ValueError("N_Ed muss größer als 0 sein.")
    b, h, l0 = b_cm * 10.0, h_cm * 10.0, l0_m * 1000.0
    N_Ed = N_Ed_kN * 1000.0
    base = dict(b=b, h=h, l0=l0, fck=float(fck), e0=e0_cm * 10.0,
                phi_ef=phi_ef, mit_emin=mit_emin, ausgabe=ausgabe)

    fyd = FYK / GAMMA_S
    As_min = as_min(ausgabe, N_Ed, b * h, fyd)  # 2011: NA 9.5.2(2); 2025: Tab. 12.3 (NDP) Zeile 1
    As_max = 0.04 * b * h
    hinweise = []
    gefunden = True
    deckung = None
    if deck:
        deckung = betondeckung(d_bue=d_bue_mm, **deck)
        c_nom_mm = deckung["c_nom"]
    d1_fest = float(d1_mm) if (d1_mm and modus == "fix") else 0.0

    def d1_von(d_stab):
        return d1_fest if d1_fest else c_nom_mm + d_bue_mm + d_stab / 2.0

    if modus == "fix":
        if d_l < 12:
            raise ValueError("Längsstab-Ø muss mindestens 12 mm betragen (NA).")
        if n_st < 4 or n_st % 2:
            raise ValueError("Stabanzahl: gerade und mindestens 4 (je Ecke 1 Stab).")
        S = Stuetze(d1=d1_von(d_l), **base)
        As_gew = n_st * math.pi * d_l ** 2 / 4.0
        n_seite = n_st // 2
        a_clear = (b - 2.0 * (c_nom_mm + d_bue_mm) - n_seite * d_l) / (n_seite - 1)
    elif modus == "auto":
        wahl = None
        for As_k, n_k, d_k in _stab_kandidaten(b, c_nom_mm, d_bue_mm, As_min, As_max):
            d1_k = d1_von(d_k)
            if d1_k >= h / 2.0:
                continue
            S_k = Stuetze(d1=d1_k, **base)
            if nachweis(S_k, As_k, N_Ed)[0]:
                wahl = (S_k, As_k, n_k, d_k)
                break
        if wahl is None:                       # nichts reicht: zeige größte zulässige Wahl
            gefunden = False
            kand = _stab_kandidaten(b, c_nom_mm, d_bue_mm, 0.0, As_max)
            if not kand:
                raise ValueError("Mit diesen Maßen passt keine Stabwahl in den Querschnitt.")
            As_k, n_k, d_k = max(kand)
            wahl = (Stuetze(d1=d1_von(d_k), **base), As_k, n_k, d_k)
            hinweise.append("Auch die größte zulässige Bewehrung reicht nicht aus: "
                            "Querschnitt vergrößern oder Betongüte erhöhen.")
        S, As_gew, n_st, d_l = wahl
        n_seite = n_st // 2
        a_clear = (b - 2.0 * (c_nom_mm + d_bue_mm) - n_seite * d_l) / (n_seite - 1)
    else:
        raise ValueError("Unbekannter Modus.")

    if As_gew < As_min:
        hinweise.append(f"A_s,vorh {fmt(As_gew / 100)} cm² < A_s,min {fmt(As_min / 100)} cm² "
                        f"(0,15·N_Ed/f_yd).")
    if As_gew > As_max:
        hinweise.append(f"A_s,vorh {fmt(As_gew / 100)} cm² > A_s,max {fmt(As_max / 100)} cm².")
    if a_clear < max(float(d_l), 20.0):
        hinweise.append(f"Lichter Stababstand {fmt(a_clear, 0)} mm < {max(d_l, 20)} mm.")
    if deckung and deckung["c_nom"] + d_bue_mm < d_l:
        hinweise.append(f"Betondeckung der Längsstäbe c_nom + Ø_Bügel = {fmt(deckung['c_nom'] + d_bue_mm, 0)} mm < Stab-Ø {d_l} mm "
                        f"(c_min,b, Tabelle 6.5).")
    if d_bue_mm < max(6.0, d_l / 4.0):
        hinweise.append(f"Bügel-Ø {fmt(d_bue_mm, 0)} mm < Mindestwert {fmt(max(6.0, d_l / 4.0), 1)} mm.")

    ok_Ned, Mrd, Med, kru = nachweis(S, As_gew, N_Ed)
    N_bieg = n_rd_biegung(S, As_gew)
    N_asmin = n_rd_asmin(S, As_gew)
    N_Rd = min(N_bieg, N_asmin)
    massg = "Biegung (Nennkrümmung)" if N_bieg <= N_asmin else "Mindestbewehrung A_s,min"
    N0 = n_zentrisch(S, As_gew)
    if N_Ed > N0:
        hinweise.append("N_Ed ist größer als die zentrische Querschnittstragfähigkeit.")

    return Ergebnis(S=S, N_Ed=N_Ed, n_st=n_st, d_l=d_l, d_bue=d_bue_mm, As_gew=As_gew,
                    As_min=As_min, As_max=As_max, As_erf=as_erforderlich(S, N_Ed),
                    N_Rd=N_Rd, N_Rd_biegung=N_bieg, N_Rd_asmin=N_asmin, massgebend=massg,
                    ok_N=(N_Rd > 0 and round(N_Ed / N_Rd * 100.0, 2) <= AUSN_MAX), Mrd_Ned=Mrd, Med_Ned=Med, kru=kru,
                    N0=N0, a_clear=a_clear, hinweise=hinweise, modus=modus,
                    gefunden=gefunden, deckung=deckung, d1_manuell=bool(d1_fest))


# =============================================================================
# 6) AUSGABE
# =============================================================================
def _box(farbe, text):
    stil = {"gruen": ("#d4edda", "#155724", "#c3e6cb"),
            "rot": ("#f8d7da", "#721c24", "#f5c6cb"),
            "gelb": ("#fff3cd", "#856404", "#ffeeba")}[farbe]
    return (f'<div style="margin:10px 0;padding:12px;background:{stil[0]};color:{stil[1]};'
            f'border:1px solid {stil[2]};border-radius:5px;font-weight:bold;">{text}</div>')


def _karte(inhalt, farbe="#007bff"):
    """Heller Kasten mit festem Text-/Hintergrund, damit es im hellen UND dunklen Colab-Design lesbar ist."""
    return (f'<div style="background:#f7f9fa;color:#222;padding:14px 18px;border-radius:8px;'
            f'border-left:5px solid {farbe};font-family:sans-serif;margin:8px 0;">{inhalt}</div>')


def _tabelle(zeilen):
    """Zweispaltige Liste (Name | Wert) mit Zwischenüberschriften ("H", Text)."""
    html = '<table style="border-collapse:collapse;font-size:0.95em;color:#222;">'
    for z in zeilen:
        if z[0] == "H":
            html += (f'<tr><td colspan="2" style="padding:12px 4px 4px 0;font-weight:bold;'
                     f'border-bottom:1px solid #9fb0c0;">{z[1]}</td></tr>')
        else:
            html += (f'<tr><td style="padding:3px 28px 3px 0;">{z[0]}</td>'
                     f'<td style="padding:3px 0;">{z[1]}</td></tr>')
    return html + "</table>"


_TH = "padding:8px 14px;background:#e3ebf3;border-bottom:2px solid #9fb0c0;white-space:nowrap;font-weight:600;"
_TD = "padding:7px 14px;white-space:nowrap;border-bottom:1px solid #dde3ea;"


def _html_tabelle(kopf, zeilen, gruppen=None, links=(0,), status=None, fett_zeile=None):
    """Einheitliche Tabelle mit Zellabständen, Trennlinien, Zebra-Streifen und Scrollleiste.

    kopf       Spaltenüberschriften (HTML)
    zeilen     Liste von Zellenlisten; ein String statt Liste = Fehlerzeile über alle Spalten
    gruppen    optional [(Text, Spaltenanzahl), ...] als obere Überschriftenzeile
    links      Spaltenindizes mit linksbündigem Text (alle anderen rechtsbündig)
    status     Index einer Statusspalte (✅ grün, sonst rot), zentriert
    fett_zeile Index einer hervorgehobenen Zeile
    """
    n = len(kopf)
    html = ('<div style="overflow-x:auto;max-width:100%;margin:6px 0 12px 0;">'
            '<table style="border-collapse:collapse;font-size:0.92em;background:#fff;color:#222;'
            'border:1px solid #c9d3dd;">')
    if gruppen:
        html += '<tr>' + "".join(
            f'<th colspan="{span}" style="{_TH}text-align:center;border-left:1px solid #c9d3dd;'
            f'padding-top:6px;padding-bottom:6px;">{text}</th>' for text, span in gruppen) + '</tr>'
    html += '<tr>' + "".join(
        f'<th style="{_TH}text-align:{"left" if i in links else ("center" if i == status else "right")};">{c}</th>'
        for i, c in enumerate(kopf)) + '</tr>'
    for r, z in enumerate(zeilen):
        if isinstance(z, str):
            html += (f'<tr><td colspan="{n}" style="{_TD}background:#f8d7da;color:#721c24;'
                     f'font-weight:600;">{z}</td></tr>')
            continue
        bg = "#ffffff" if r % 2 == 0 else "#f4f7fa"
        html += '<tr>'
        for i, c in enumerate(z):
            stil = f"{_TD}background:{bg};text-align:{'left' if i in links else 'right'};"
            if r == fett_zeile:
                stil += "font-weight:700;background:#fff3cd;"
            if i == status:
                farbe = ("background:#d4edda;color:#155724;" if "✅" in c else
                         "background:#f8d7da;color:#721c24;")
                stil = f"{_TD}{farbe}text-align:center;font-weight:700;"
            html += f'<td style="{stil}">{c}</td>'
        html += '</tr>'
    return html + '</table></div>'


def momente_entlang(S, N, k):
    """Momente [kNm] an Kopf, kritischem Schnitt und Fuß: Liste (x [m], M0Ed, M2, MEd)."""
    xis = [1.0]
    if 1e-9 < k.xi_krit < 1.0 - 1e-9:
        xis.append(k.xi_krit)
    xis.append(0.0)
    zeilen = []
    for xi in xis:
        m0 = N * (k.e_fuss + (k.e_kopf - k.e_fuss) * xi) / 1e6
        m2 = N * k.e2 * math.sin(math.pi * xi) / 1e6
        zeilen.append((xi * S.l0 / 1000.0, m0, m2, m0 + m2))
    return zeilen


def momententabelle(S, N, k):
    kopf = ["x [m]", "M<sub>0Ed</sub> [kNm]", "M<sub>2</sub> [kNm]", "M<sub>Ed</sub> [kNm]"]
    zeilen = [[fmt(x), fmt(m0), fmt(m2), fmt(med)] for x, m0, m2, med in momente_entlang(S, N, k)]
    return _html_tabelle(kopf, zeilen, links=())


def iterationstabelle(S, As, N_rd):
    """Tabelle wie in der Arbeit: M_Ed(N) gegen M_Rd(N) um N_Rd,Biegung herum."""
    kopf = ["N [kN]", "n", "K<sub>r</sub>", "e<sub>2</sub> [mm]", "e<sub>tot</sub> [mm]",
            "M<sub>Ed</sub> [kNm]", "M<sub>Rd</sub> [kNm]", "M<sub>Ed</sub>/M<sub>Rd</sub>"]
    zeilen, fett = [], None
    for j, f in enumerate((0.85, 0.92, 0.97, 1.0, 1.03, 1.08)):
        N = N_rd * f
        _, Mrd, Med, k = nachweis(S, As, N)
        if f == 1.0:
            fett = j
        zeilen.append([fmt(N / 1000), fmt(k.n, 3), fmt(k.Kr, 3), fmt(k.e2), fmt(k.e_tot),
                       fmt(Med / 1e6, 3), fmt(None if Mrd is None else Mrd / 1e6, 3),
                       fmt(None if Mrd is None else Med / Mrd, 3)])
    return _html_tabelle(kopf, zeilen, links=(), fett_zeile=fett)


def ausgabe(E):
    S, k = E.S, E.kru
    N_Ed = E.N_Ed
    ausn_N = N_Ed / E.N_Rd if E.N_Rd > 0 else float("inf")
    rho = E.As_gew / S.Ac * 100.0
    d_bue_min = max(6.0, E.d_l / 4.0)
    s_max = min(20.0 * E.d_l, min(S.b, S.h), 400.0)

    if E.ok_N and not E.hinweise:
        status = _box("gruen", f"✅ Nachweis erfüllt: N<sub>Ed</sub> = {fmt(N_Ed / 1000, 2)} kN ≤ "
                               f"N<sub>Rd,max</sub> = {fmt(E.N_Rd / 1000, 2)} kN "
                               f"(Ausnutzung {fmt(ausn_N * 100, 2)} %, maßgebend: {E.massgebend})")
    elif E.ok_N:
        status = _box("gelb", f"⚠️ Tragfähigkeit erfüllt ({fmt(ausn_N * 100, 2)} %), aber Hinweise beachten.")
    else:
        status = _box("rot", f"⚠️ Nachweis NICHT erfüllt: N<sub>Ed</sub> = {fmt(N_Ed / 1000, 2)} kN &gt; "
                             f"N<sub>Rd,max</sub> = {fmt(E.N_Rd / 1000, 2)} kN "
                             f"(Ausnutzung {fmt(ausn_N * 100, 2)} %, maßgebend: {E.massgebend})")
    hin = "".join(f'<div style="color:#856404;">⚠️ {t}</div>' for t in E.hinweise)

    Mrd_txt = "–" if E.Mrd_Ned is None else fmt(E.Mrd_Ned / 1e6, 3) + " kNm"
    ausn_M = "–" if E.Mrd_Ned is None else fmt(E.Med_Ned / E.Mrd_Ned * 100, 1) + " %"
    e_y = max(k.e_i, k.e_min) if S.mit_emin else k.e_i          # Gegenrichtung: nur Imperfektion
    My = N_Ed * (e_y + k.e2) / 1e6
    As_massg = None if E.As_erf is None else max(E.As_erf, E.As_min)
    as1_txt = ("–" if As_massg is None else
               f"{fmt(As_massg / 4 / 100, 3)} cm²" + (" (M: Mindestbewehrung maßgebend)"
                                                    if E.As_erf is not None and E.As_min > E.As_erf else ""))

    zeilen = [
        ("H", "Eingang"),
        ("Querschnitt b × h", f"{fmt(S.b / 10, 0)} × {fmt(S.h / 10, 0)} cm, C{S.fck:.0f}/B500B, l<sub>0</sub> = {fmt(S.l0 / 1000)} m"),
        ("Bewehrung", f"{E.n_st} Ø{E.d_l}" + (" (je Ecke 1 Stab)" if E.n_st == 4 else "")
         + f" → A<sub>s</sub> = {fmt(E.As_gew / 100, 3)} cm² (" + ("vorgegeben" if E.modus == "fix" else "automatisch gewählt: zuerst 4 Stäbe, Ø steigend") + ")"),
        ("N<sub>Ed</sub>", f"{fmt(N_Ed / 1000, 2)} kN"),
        ("Lastausmitte e<sub>0</sub> (am Kopf)", f"{fmt(S.e0 / 10, 2)} cm"),
    ] + ([("H", f"Betondeckung nach EC2 (DIN EN 1992-1-1:2025-09, 6.5), Expositionsklasse {E.deckung['expo']}"),
        ("Verfahren / Klasse / Nutzungsdauer", f"{E.deckung['verfahren']}: {E.deckung['klasse']}, {E.deckung['nd']} Jahre"),
        ("c<sub>min,dur</sub> (Tabelle 6.3 / 6.4 bzw. P.2)", f"{fmt(E.deckung['c_min_dur'], 0)} mm"),
        ("c<sub>min,b</sub> = Stabdurchmesser (Bügel)", f"{fmt(E.deckung['c_min_b'], 0)} mm"),
        ("c<sub>min</sub> = max(c<sub>min,dur</sub>; c<sub>min,b</sub>; 10 mm)  (6.2)", f"{fmt(E.deckung['c_min'], 0)} mm"),
        (f"Δc<sub>dev</sub> (Tabelle 6.7, {E.deckung['dc_dev_fall'].split(':')[0]})", f"{fmt(E.deckung['dc_dev'], 0)} mm"),
        ("c<sub>nom</sub> = c<sub>min</sub> + Δc<sub>dev</sub>  (6.1)", f"<b>{fmt(E.deckung['c_nom'], 0)} mm</b>")]
        if E.deckung else [("H", "Achsabstand")]) + [
        ("Achsabstand d<sub>1</sub> = c<sub>nom</sub> + Ø<sub>Bügel</sub> + Ø<sub>Längsstab</sub>/2" if not E.d1_manuell
         else "Achsabstand d<sub>1</sub> (von Hand vorgegeben)", f"{fmt(S.d1, 1)} mm"),
        ("Nutzhöhe d = h − d<sub>1</sub>", f"{fmt(S.h - S.d1, 1)} mm"),
        ("H", "Baustoffe"),
        ("f<sub>cd</sub> / f<sub>yd</sub>", f"{fmt(S.fcd, 3)} / {fmt(S.fyd, 3)} N/mm²"),
        ("ω = A<sub>s</sub>·f<sub>yd</sub>/(A<sub>c</sub>·f<sub>cd</sub>)", fmt(k.omega, 4)),
        ("H", "Schlankheit"),
        ("i / λ", f"{fmt(S.i, 2)} mm / {fmt(k.lam, 2)}"),
        ("n = N<sub>Ed</sub>/(A<sub>c</sub>·f<sub>cd</sub>)", fmt(k.n, 4)),
        ("λ<sub>lim</sub> (" + ("NA 5.8.3.1" if S.ausgabe == "2011" else "EN 1992-1-1:2023, Gl. O.12") + ")", fmt(k.lam_lim, 2) + (" → Theorie II. Ordnung nötig" if k.theorie2 else " → Theorie I. Ordnung genügt")),
        ("H", "Nennkrümmung (Imperfektion, Θ<sub>i</sub> = 1/200, c = 10)"),
        ("e<sub>i</sub> = l<sub>0</sub>/400", f"{fmt(k.e_i / 10, 2)} cm"),
    ]
    if S.mit_emin:
        zeilen.append(("e<sub>min</sub> = max(h/30; 20 mm), zusätzlich angesetzt", f"{fmt(k.e_min / 10, 2)} cm"))
    zeilen += [
        ("e<sub>Kopf</sub> = e<sub>0</sub> + e<sub>i</sub> / e<sub>Fuß</sub>", f"{fmt(k.e_kopf / 10, 2)} cm / {fmt(k.e_fuss / 10, 2)} cm"),
    ]
    if k.theorie2:
        if S.ausgabe == "2011":      # k1 gibt es nur in DIN EN 1992-1-1/NA (2011); EN 1992-1-1:2023 kennt es nicht
            zeilen += [
                ("K<sub>r</sub>", fmt(k.Kr, 3)),
                ("k<sub>1</sub> / K<sub>φ</sub>", f"{fmt(k.k1, 3)} / {fmt(k.Kphi, 3)}"),
                ("1/r<sub>0</sub> = ε<sub>yd</sub>/(0,45·d)", f"{fmt(k.inv_r0 * 1000, 6)} 1/m"),
                ("1/r = K<sub>r</sub>·K<sub>φ</sub>·(1/r<sub>0</sub>)", f"{fmt(k.Kr * k.Kphi * k.inv_r0 * 1000, 6)} 1/m"),
                ("e<sub>2</sub> = k<sub>1</sub>·(1/r)·l<sub>0</sub>²/10", f"{fmt(k.e2 / 10, 3)} cm"),
            ]
        else:
            zeilen += [
                ("K<sub>r</sub> / K<sub>φ</sub>", f"{fmt(k.Kr, 3)} / {fmt(k.Kphi, 3)}"),
                ("1/r<sub>0</sub> = 2·ε<sub>yd</sub>/(d − d′), Gl. O.19", f"{fmt(k.inv_r0 * 1000, 6)} 1/m"),
                ("1/r = K<sub>r</sub>·K<sub>φ</sub>·(1/r<sub>0</sub>)", f"{fmt(k.Kr * k.Kphi * k.inv_r0 * 1000, 6)} 1/m"),
                ("e<sub>2</sub> = (1/r)·l<sub>0</sub>²/10", f"{fmt(k.e2 / 10, 3)} cm"),
            ]
    zeilen += [
        ("Kritischer Schnitt x", f"{fmt(k.xi_krit * S.l0 / 1000)} m"),
        ("e<sub>tot</sub> = e<sub>0,krit</sub> + e<sub>2,krit</sub>", f"{fmt(k.e0_krit / 10, 2)} + {fmt(k.e2_krit / 10, 2)} = {fmt(k.e_tot / 10, 2)} cm"),
        ("M<sub>Ed,z</sub> = max [M<sub>0Ed</sub> + M<sub>2</sub>]", f"{fmt(E.Med_Ned / 1e6, 3)} kNm"),
        ("M<sub>Ed,y</sub> (Gegenrichtung: nur Imperfektion + M<sub>2</sub>)", f"{fmt(My, 3)} kNm"),
        ("H", "Querschnittswiderstand"),
        ("M<sub>Rd</sub>(N<sub>Ed</sub>)", Mrd_txt),
        ("M<sub>Ed</sub>/M<sub>Rd</sub>", ausn_M),
        ("Zentrische Querschnittstragfähigkeit (ohne Knicken)", f"{fmt(E.N0 / 1000, 1)} kN"),
        ("H", "Maximale Tragfähigkeit"),
        ("N<sub>Rd</sub> aus Biegung (M<sub>Ed</sub> = M<sub>Rd</sub>)", f"{fmt(E.N_Rd_biegung / 1000, 2)} kN"),
        ("N<sub>Rd</sub> aus A<sub>s,min</sub> (N = A<sub>s</sub>·f<sub>yd</sub>/" + ("0,15" if S.ausgabe == "2011" else "0,1") + ")", f"{fmt(E.N_Rd_asmin / 1000, 2)} kN"),
        ("<b>N<sub>Rd,max</sub></b> = Minimum, maßgebend: " + E.massgebend,
         f'<b style="color:#28a745;font-size:1.15em;">{fmt(E.N_Rd / 1000, 2)} kN</b>'),
        ("Ausnutzung N<sub>Ed</sub>/N<sub>Rd,max</sub>", f"<b>{fmt(ausn_N * 100, 2)} %</b>"),
        ("H", "Bewehrung"),
        (("A<sub>s,min</sub> = 0,15·N<sub>Ed</sub>/f<sub>yd</sub> (NA 9.5.2)" if S.ausgabe == "2011" else "A<sub>s,min</sub> = max(0,1·N<sub>Ed</sub>/f<sub>yd</sub>; 0,002·A<sub>c</sub>) (EC2:2025, Tab. 12.3)"), f"{fmt(E.As_min / 100, 3)} cm²"),
        ("A<sub>s,max</sub> = 0,04·A<sub>c</sub>", f"{fmt(E.As_max / 100, 2)} cm²"),
        ("Bewehrungsgrad ρ", f"{fmt(rho, 3)} %"),
        ("A<sub>s,erf</sub> aus Biegung (für N<sub>Ed</sub>)",
         ("&gt; A<sub>s,max</sub> (nicht erreichbar)" if E.As_erf is None else f"{fmt(E.As_erf / 100, 3)} cm²")),
        ("A<sub>s1</sub> je Ecke = max(A<sub>s,erf</sub>; A<sub>s,min</sub>)/4", as1_txt),
        ("Bügel", f"Ø{fmt(E.d_bue, 0)} (min. Ø{fmt(d_bue_min, 1)}), s ≤ {fmt(s_max, 0)} mm (EC2 9.5.3)"),
    ]

    return _karte(f"""
      <h3 style="margin-top:0;">📊 Nennkrümmungsverfahren – Ergebnisse</h3>
      {status}{hin}
      {_tabelle(zeilen)}
      <h4 style="margin:18px 0 4px 0;">Momente entlang der Stütze bei N<sub>Ed</sub> (Kopf, kritischer Schnitt, Fuß)</h4>
      {momententabelle(S, N_Ed, k)}
      <h4 style="margin:18px 0 4px 0;">Iteration um N<sub>Rd</sub> aus Biegung (M<sub>Ed</sub>(N) gegen M<sub>Rd</sub>(N))</h4>
      {iterationstabelle(S, E.As_gew, E.N_Rd_biegung)}
      <p style="font-size:0.85em;color:#555;">
        Annahmen: f<sub>cd</sub> = {ALPHA_CC}·f<sub>ck</sub>/{GAMMA_C}, f<sub>yd</sub> = 500/{GAMMA_S}; Parabel-Rechteck-Diagramm;
        Bewehrung in 2 Lagen (A<sub>s</sub>/2 je Seite); einachsige Biegung um die Achse mit Höhe h, die Gegenrichtung
        (nur Imperfektion) wird getrennt betrachtet, keine zweiachsige Interaktion. Moment I. Ordnung linear
        zwischen Fuß und Kopf, M<sub>2</sub>(x) = N·e<sub>2</sub>·sin(π·x/l<sub>0</sub>). Mindestausmitte nur, wenn ihr Schalter aktiv ist.
        Bügelabstand: Verschärfungen des NA an Decken/Stößen separat prüfen.
      </p>""")


# =============================================================================
# 7) VARIANTEN
# =============================================================================
def _zahl(text):
    return float(text.replace(",", "."))


def varianten_html(text, basis):
    """Jede Zeile: 'b h N_Ed [fck [e0_Kopf]]'  (cm cm kN [N/mm² [cm]]); Trenner: Leerzeichen oder ';'.
    Dezimalkomma erlaubt. Alle anderen Eingaben kommen aus `basis` (dict für berechne)."""
    kopf = ["b×h [cm]", "C", "e<sub>0</sub> [cm]", "λ", "Bewehrung", "A<sub>s,vorh</sub> [cm²]",
            "N<sub>Ed</sub> [kN]", "N<sub>Rd,max</sub> [kN]",
            "Ausnutzung", "maßgebend", "A<sub>s,erf</sub> [cm²]", "Nachweis"]
    zeilen_html = []
    anzahl = 0
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        anzahl += 1
        try:
            teile = [t for t in re.split(r"[;\s]+", zeile) if t]
            if len(teile) not in (3, 4, 5):
                raise ValueError("erwartet: b h N_Ed [fck [e0]]")
            b, h, N_Ed = _zahl(teile[0]), _zahl(teile[1]), _zahl(teile[2])
            kw = dict(basis)
            kw["e0_cm"] = 0.0                     # ohne Angabe in der Zeile: zentrisch
            if len(teile) >= 4:
                kw["fck"] = _zahl(teile[3])
            if len(teile) == 5:
                kw["e0_cm"] = _zahl(teile[4])
            E = berechne(b, h, N_Ed_kN=N_Ed, **kw)
            ausn = E.N_Ed / E.N_Rd if E.N_Rd > 0 else float("inf")
            ok = E.ok_N and E.gefunden
            zellen = [f"{fmt(b, 0)}×{fmt(h, 0)}", f"{E.S.fck:.0f}", fmt(E.S.e0 / 10, 1),
                      fmt(E.kru.lam, 1), f"{E.n_st} Ø{E.d_l}", fmt(E.As_gew / 100, 3),
                      fmt(N_Ed, 2), fmt(E.N_Rd / 1000, 2),
                      f"{fmt(ausn * 100, 2)} %",
                      "Biegung" if E.N_Rd_biegung <= E.N_Rd_asmin else "A<sub>s,min</sub>",
                      "&gt; max" if E.As_erf is None else fmt(E.As_erf / 100, 3),
                      "✅ erfüllt" if ok else "⚠️ nicht erfüllt"]
        except Exception as ex:                      # Eingabefehler in einer Zeile stoppen nicht alles
            zellen = f"Zeile {nr}: „{zeile}“ → ❌ {ex}"
        zeilen_html.append(zellen)
    if anzahl == 0:
        return _box("gelb", "Keine Varianten eingegeben (Format je Zeile: b h N_Ed [fck [e0]]).")
    return _karte(
        '<h3 style="margin-top:0;">📋 Varianten</h3>'
        + _html_tabelle(kopf, zeilen_html, links=(0, 4, 9), status=11)
        + '<p style="font-size:0.85em;color:#555;">Alle weiteren Eingaben (Knicklänge, Deckung, Bügel, Bewehrung …) '
          'kommen aus den Feldern oben. Erfüllt, solange die Ausnutzung höchstens 100,01 % beträgt.</p>',
        farbe="#17a2b8")


# =============================================================================
# 8) VERGLEICH MIT DEM MB-AUSDRUCK (mb BauStatik S401.de, Bachelorarbeit Original)
#    Spalten: Name, h [cm], e0 Kopf [cm], N_Ed [kN], K_r, 1/r [1/m], e2 [cm], MEd,z [kNm], MEd,y [kNm]
# =============================================================================
MB_DATEN = [
    ("20×20 zentrisch", 20, 0.0, 645.30, 0.22, 6.40e-3, 0.54, 8.14, 8.14),
    ("20×20 exzentrisch", 20, 2.0, 528.30, 0.44, 1.27e-2, 1.07, 15.80, 9.48),
    ("25×25 zentrisch", 25, 0.0, 973.50, 0.15, 3.33e-3, 0.28, 9.78, 9.78),
    ("25×25 exzentrisch", 25, 2.5, 792.90, 0.40, 8.88e-3, 0.75, 25.57, 11.66),
    ("30×30 zentrisch", 30, 0.0, 1309.50, 0.17, 3.06e-3, 0.22, 12.35, 12.35),
    ("30×30 exzentrisch", 30, 3.0, 1093.05, 0.39, 7.15e-3, 0.51, 40.72, 13.49),
]


def mb_vergleich_html(l0_m=2.90, fck=25, c_nom_mm=20.0, d_bue_mm=8.0, phi_ef=0.0):
    """Rechnet die sechs mb-Positionen (4 Ø12, N_Ed aus mb) mit diesem Code nach."""
    gruppen = [("Eingabe", 2), ("K<sub>r</sub>", 2), ("1/r [10<sup>-3</sup>/m]", 2),
               ("e<sub>2</sub> [cm]", 2), ("M<sub>Ed,z</sub> [kNm]", 2), ("M<sub>Ed,y</sub> [kNm]", 2),
               ("Ergebnis dieses Codes", 5)]
    kopf = ["Fall", "N<sub>Ed</sub> mb [kN]", "mb", "hier", "mb", "hier", "mb", "hier",
            "mb", "hier", "mb", "hier",
            "M<sub>Ed,z</sub>/M<sub>Rd</sub>", "A<sub>s,min</sub>/A<sub>s</sub>",
            "N<sub>Rd,max</sub> [kN]", "N<sub>Ed</sub>/N<sub>Rd,max</sub>", "maßgebend"]
    zeilen_html = []
    for name, h, e0, N, Kr, ir, e2, Mz, My in MB_DATEN:
        E = berechne(h, h, N_Ed_kN=N, l0_m=l0_m, fck=fck, e0_cm=e0, phi_ef=phi_ef,
                     c_nom_mm=c_nom_mm, d_bue_mm=d_bue_mm, modus="fix", d_l=12, n_st=4, ausgabe="2011")
        k = E.kru
        My_h = E.N_Ed * (k.e_i + k.e2) / 1e6
        Mz_h = E.Med_Ned / 1e6
        ausn_M = E.Med_Ned / E.Mrd_Ned if E.Mrd_Ned else float("inf")
        zeilen_html.append([
            name, fmt(N, 2),
            fmt(Kr), fmt(k.Kr), fmt(ir * 1e3, 2), fmt(k.Kr * k.Kphi * k.inv_r0 * 1e6, 2),
            fmt(e2), fmt(k.e2 / 10), fmt(Mz), fmt(Mz_h), fmt(My), fmt(My_h),
            fmt(ausn_M, 3), fmt(E.As_min / E.As_gew, 3),
            fmt(E.N_Rd / 1000, 1), fmt(N / (E.N_Rd / 1000), 3),
            "Biegung" if E.N_Rd_biegung <= E.N_Rd_asmin else "A<sub>s,min</sub>"])
    return _karte(
        '<h3 style="margin-top:0;">📊 Vergleich mit dem mb-Ausdruck (4 Ø12, N<sub>Ed</sub> aus mb)</h3>'
        + _html_tabelle(kopf, zeilen_html, gruppen=gruppen, links=(0, 16))
        + '<p style="font-size:0.85em;color:#555;">mb rundet K<sub>r</sub>, e<sub>2</sub> und M auf 2 Stellen und '
          'wertet x im 0,1-m-Raster aus (kritischer Schnitt 1,40 m statt 1,45 m). Ein Wert von '
          'M<sub>Ed,z</sub>/M<sub>Rd</sub> ≈ 1,00 zeigt: mb wurde mit dieser Last bis an die Grenze belastet. '
          'Beim Fall 30×30 zentrisch begrenzt die Mindestbewehrung (A<sub>s,min</sub>/A<sub>s</sub> ≈ 1,00).</p>',
        farbe="#ffc107")


# mb-Ausdruck "Test1911" (Querschnitt 25x25, C25/30, XC1, l0 = 2,90 m, N_Ed = 1299 kN, e0 = 0):
# mb bestimmt die erforderliche Bewehrung. Betondeckung: c_nom = 20 mm, cv = 36 mm, d' = 50 mm.
MB_AS = dict(N=1299.0, h=25.0, fck=25, l0=2.90, d1=50.0, lam=40.2, e_i=0.73, Kr=0.15, k1=1.00,
             inv_r=3.66e-3, e2=0.31, x=1.40, M0=9.42, M2=3.99, MEd=13.41, As=13.39, As1=3.35)


def mb_vergleich_as_html():
    """Vergleich 'erforderliche Bewehrung' mit dem mb-Ausdruck Test1911 (d' = 50 mm)."""
    d = MB_AS
    S = Stuetze(b=d["h"] * 10, h=d["h"] * 10, l0=d["l0"] * 1000, fck=float(d["fck"]), d1=d["d1"], ausgabe="2011")
    N = d["N"] * 1000.0
    As = as_erforderlich(S, N)
    k = nennkruemmung(S, As, N)
    xi = k.xi_krit
    M0 = N * k.e_kopf / 1e6
    M2 = N * k.e2 * math.sin(math.pi * xi) / 1e6
    MEd = k.e_tot * N / 1e6
    zeilen_def = [
        ("N<sub>Ed</sub> [kN]", d["N"], d["N"], 2),
        ("Achsabstand d' [mm]", d["d1"], S.d1, 1),
        ("Schlankheit λ", d["lam"], k.lam, 1),
        ("e<sub>i</sub> [cm]", d["e_i"], k.e_i / 10, 2),
        ("K<sub>r</sub>", d["Kr"], k.Kr, 2),
        ("k<sub>1</sub>", d["k1"], k.k1, 2),
        ("1/r [10<sup>-3</sup>/m]", d["inv_r"] * 1e3, k.Kr * k.Kphi * k.inv_r0 * 1e6, 2),
        ("e<sub>2</sub> [cm]", d["e2"], k.e2 / 10, 2),
        ("kritischer Schnitt x [m] (mb: 0,1-m-Raster)", d["x"], xi * S.l0 / 1000.0, 2),
        ("M<sub>0Ed</sub> [kNm]", d["M0"], M0, 2),
        ("M<sub>2</sub> [kNm]", d["M2"], M2, 2),
        ("M<sub>Ed</sub> [kNm]", d["MEd"], MEd, 2),
        ("A<sub>s,erf</sub> gesamt [cm²]", d["As"], As / 100.0, 2),
        ("A<sub>s1</sub> je Ecke [cm²]", d["As1"], As / 400.0, 2),
    ]
    zeilen = []
    for name, mbv, hier, nd in zeilen_def:
        abw = "–" if mbv == 0 else f"{(hier / mbv - 1) * 100:+.2f} %".replace(".", ",")
        zeilen.append([name, fmt(mbv, nd), fmt(hier, nd), abw])
    return _karte(
        '<h3 style="margin-top:0;">📊 Vergleich: erforderliche Bewehrung (mb-Ausdruck „Test1911“)</h3>'
        '<div style="font-size:0.9em;margin-bottom:6px;">25×25 cm, C25/30, XC1, l<sub>0</sub> = 2,90 m, N<sub>Ed</sub> = 1299 kN, e<sub>0</sub> = 0. '
        'mb setzt hier das Verlegemaß c<sub>v</sub> = 36 mm und damit d\' = 50 mm (= 36 + 8 + 12/2). '
        'Mit diesem d\' rechnet dieses Programm.</div>'
        + _html_tabelle(["Größe", "mb", "hier", "Abweichung"], zeilen, links=(0,))
        + '<p style="font-size:0.85em;color:#555;">mb rundet K<sub>r</sub>, e<sub>2</sub> und die Momente auf 2 Stellen und wertet x im '
          '0,1-m-Raster aus (1,40 statt 1,45 m). Die Abweichungen sind rundungsbedingt.</p>',
        farbe="#ffc107")


# =============================================================================
# 9) OBERFLÄCHE (Google Colab)
# =============================================================================
if __name__ == "__main__":
    sty = {"description_width": "230px"}
    lay = widgets.Layout(width="520px")

    b_w = widgets.FloatText(value=20.0, description="Breite b (cm):", style=sty, layout=lay)
    h_w = widgets.FloatText(value=20.0, description="Höhe h (cm):", style=sty, layout=lay)
    l0_w = widgets.FloatText(value=2.90, description="Knicklänge l0 (m):", style=sty, layout=lay)
    fck_w = widgets.Dropdown(options=list(FCK_OPTIONEN), value=25,
                             description="f_ck (N/mm²):", style=sty, layout=lay)
    e0_w = widgets.FloatText(value=0.0, description="Lastausmitte e0 (cm):", style=sty, layout=lay)
    N_w = widgets.FloatText(value=645.3, description="Normalkraft N_Ed (kN):", style=sty, layout=lay)
    phi_w = widgets.FloatText(value=2.0, description="Kriechzahl φ_eff (-):", style=sty, layout=lay)
    expo_w = widgets.Dropdown(options=[MANUELL] + list(EXPO_KLASSEN), value="XC1",
                              description="Expositionsklasse:", style=sty, layout=lay)
    verf_w = widgets.Dropdown(options=list(VERFAHREN), value=VERFAHREN_ERC,
                              description="Verfahren (cmin,dur):", style=sty, layout=lay)
    erc_w = widgets.Dropdown(options=list(ERC_KLASSEN), value=3,
                             description="XRC / XRDS (Tab. 6.3/6.4):", style=sty, layout=lay)
    skl_w = widgets.Dropdown(options=list(S_KLASSEN), value="S4",
                             description="Anforderungskl. (Anhang P):", style=sty, layout=lay)
    nd_w = widgets.Dropdown(options=list(NUTZUNGSDAUER), value=50,
                            description="Nutzungsdauer (Jahre):", style=sty, layout=lay)
    dcdev_w = widgets.Dropdown(options=list(DC_DEV_FAELLE), value=DC_DEV_STANDARD,
                               description="Vorhaltemaß Δcdev (Tab. 6.7):", style=sty, layout=widgets.Layout(width="760px"))
    c_w = widgets.FloatText(value=20.0, description="Nennbetondeckung (mm, nur bei manuell):", style=sty, layout=lay)
    bue_w = widgets.Dropdown(options=[6, 8, 10, 12], value=8,
                             description="Bügel Ø (mm):", style=sty, layout=lay)
    modus_w = widgets.RadioButtons(
        options=[("Bewehrung vorgeben (Standard: 4 Ø12, je Ecke 1 Stab)", "fix"),
                 ("Bewehrung automatisch wählen (kleinste ausreichende)", "auto")],
        value="fix", description="Modus:", style=sty, layout=lay)
    dl_w = widgets.Dropdown(options=list(STAB_D), value=12,
                            description="Längsstab Ø (mm):", style=sty, layout=lay)
    n_w = widgets.Dropdown(options=list(STAB_N), value=4,
                           description="Anzahl Stäbe (min. 4):", style=sty, layout=lay)
    d1_w = widgets.FloatText(value=0.0, description="Achsabstand d1 (mm, 0 = aus c_nom; nur Modus Vorgeben):",
                             style=sty, layout=lay)

    run_btn = widgets.Button(description="Berechnen 🚀", button_style="success")
    out_area = widgets.Output()

    var_info = widgets.HTML(
        value='<div style="margin:14px 0 2px 0;font-weight:bold;">Varianten</div>'
              '<div style="font-size:0.9em;">Eine Zeile je Variante: <code>b h N_Ed [fck [e0]]</code> '
              '(cm, cm, kN, N/mm², cm). Beispiel: <code>25 25 792,9 25 2,5</code> = 25×25, N<sub>Ed</sub> = 792,9 kN, '
              'C25/30, e<sub>0</sub> = 2,5 cm. Ohne e<sub>0</sub> wird zentrisch gerechnet, ohne f<sub>ck</sub> gilt der Wert oben. Alles andere kommt aus den Feldern oben.</div>')
    var_w = widgets.Textarea(
        value="20 20 645,3\n20 20 528,3 25 2\n25 25 973,5\n25 25 792,9 25 2,5",
        placeholder="b h N_Ed [fck [e0]]",
        layout=widgets.Layout(width="520px", height="110px"), description="Eingabe:", style=sty)
    var_btn = widgets.Button(description="Varianten rechnen 📋", button_style="info")
    var_out = widgets.Output()

    mb_btn = widgets.Button(description="Vergleich mit mb-Ausdruck 📊", button_style="warning")
    mb_out = widgets.Output()

    def _c_nom():
        """c_nom [mm]: nach EC2 aus der Expositionsklasse oder von Hand."""
        d = _deck()
        return c_w.value if d is None else betondeckung(d_bue=float(bue_w.value), **d)["c_nom"]

    def _deck():
        """Parameter der EC2-Betondeckung (None: c_nom von Hand)."""
        if expo_w.value == MANUELL:
            return None
        return dict(expo=expo_w.value, verfahren=verf_w.value, erc=erc_w.value, sklasse=skl_w.value,
                    nd=nd_w.value, dc_dev_fall=dcdev_w.value)

    def _basis():
        return dict(l0_m=l0_w.value, fck=fck_w.value, e0_cm=e0_w.value,
                    phi_ef=phi_w.value, c_nom_mm=_c_nom(), d_bue_mm=float(bue_w.value),
                    deck=_deck(),
                    modus=modus_w.value, d_l=int(dl_w.value),
                    n_st=int(n_w.value), d1_mm=d1_w.value or None)

    def _fehler(ex):
        display(HTML(_box("rot", f"❌ Eingabefehler: {ex}")))

    def on_run(_):
        with out_area:
            out_area.clear_output()
            try:
                E = berechne(b_w.value, h_w.value, N_Ed_kN=N_w.value, **_basis())
                display(HTML(ausgabe(E)))
            except ValueError as ex:
                _fehler(ex)
            except Exception as ex:                   # unerwartet: nicht abstürzen
                _fehler(f"{type(ex).__name__}: {ex}")

    def on_var(_):
        with var_out:
            var_out.clear_output()
            try:
                display(HTML(varianten_html(var_w.value, _basis())))
            except Exception as ex:
                _fehler(f"{type(ex).__name__}: {ex}")

    def on_mb(_):
        with mb_out:
            mb_out.clear_output()
            try:
                display(HTML(mb_vergleich_as_html()))
                display(HTML(mb_vergleich_html(l0_m=l0_w.value, fck=fck_w.value, c_nom_mm=_c_nom(),
                                               d_bue_mm=float(bue_w.value), phi_ef=0.0)))   # mb rechnet mit φ_eff = 0
            except Exception as ex:
                _fehler(f"{type(ex).__name__}: {ex}")

    run_btn.on_click(on_run)
    var_btn.on_click(on_var)
    mb_btn.on_click(on_mb)
    display(b_w, h_w, l0_w, fck_w, e0_w, N_w, phi_w, expo_w, verf_w, erc_w, skl_w, nd_w, dcdev_w, c_w, bue_w, modus_w, dl_w, n_w, d1_w,
            run_btn, out_area, var_info, var_w, var_btn, var_out, mb_btn, mb_out)
