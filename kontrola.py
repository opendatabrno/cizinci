"""HTML přehled kontrol zpracování – vystup/kontrola.html.

Čte vystup/kontrola_souctu.csv (jeden řádek = jeden soubor MV) a měsíční řadu, které
vytváří zpracuj_data.py, a skládá z nich jednu stránku se semafory, grafy a tabulkou.
Spouští se automaticky na konci zpracuj_data.py, samostatně:
    python kontrola.py
"""
import html
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
VYSTUP = ROOT / "vystup"

# Meziroční / meziměsíční změna počtu cizinců, nad kterou je nejspíš chyba v načtení.
MAX_ZMENA_ROK = 0.15
MAX_ZMENA_MESIC = 0.05

ZLOMY = {2021: "brexit: občané Spojeného království patří od 2021 mezi třetí země",
         2022: "válka na Ukrajině: dočasná ochrana (do 2023 součást přechodného pobytu)",
         2024: "MV uvádí dočasnou ochranu jako samostatný druh pobytu (od 10/2024)"}
# známé skoky v měsíční řadě: 12/2011 +30 tis. přechodných pobytů občanů třetích zemí (už v souboru
# MV, nejspíš změna evidence), 3/2022 příchod lidí s dočasnou ochranou, 3/2023 konec platnosti
# dočasné ochrany, kterou si lidé neprodloužili
ZLOMY_MESIC = {"2011-12-31", "2022-03-31", "2022-04-30", "2023-03-31"}
# měsíce, které ve zdroji chybí: 10/2010 je u policie jen ve formátu .doc
ZNAME_MEZERY = {"2010-10": "policie zveřejnila 10/2010 jen ve formátu .doc"}


def cislo(x):
    return "" if pd.isna(x) else f"{int(x):,}".replace(",", " ")


def esc(x):
    return html.escape("" if pd.isna(x) else str(x))


def nacti(jmeno):
    cesta = VYSTUP / jmeno
    return pd.read_csv(cesta) if cesta.exists() else pd.DataFrame()


# --- vyhodnocení -------------------------------------------------------------

def vyhodnot(k):
    """Stav každého souboru: chyba = nesedí součet MV, info = vnitřní nesoulad v souboru MV."""
    k = k.copy()
    k["nesoulad_mv"] = k.bunky_muzi_zeny_nesedi + k.radky_soucet_okresu_nesedi + k.okresy_soucet_nesedi
    k["stav"] = "ok"
    k.loc[k.nesoulad_mv > 0, "stav"] = "info"
    k.loc[k.cizinci_nesparovany_stat > 0, "stav"] = "varovani"
    k.loc[k.rozdil != 0, "stav"] = "chyba"
    return k


def vyhodnot_roky(k):
    r = k[k.mesic == 12].copy().reset_index(drop=True)
    r["zmena"] = r.cizinci_celkem.pct_change()
    skok = (r.zmena.abs() > MAX_ZMENA_ROK) & ~r.rok.isin(ZLOMY)
    r.loc[skok & (r.stav != "chyba"), "stav"] = "varovani"
    chybi = sorted(set(range(r.rok.min(), r.rok.max() + 1)) - set(r.rok)) if len(r) else []
    return r, chybi


def vyhodnot_mesice(mesicne):
    """Součet ČR po měsících z cizinci_mesicne.csv (1/2007–10/2012 starší přehledy, pak MV)."""
    m = mesicne.groupby("stav_k", as_index=False).cizinci_celkem.sum().sort_values("stav_k")
    m = m.reset_index(drop=True)
    m["zmena"] = m.cizinci_celkem.pct_change()
    m["skok"] = (m.zmena.abs() > MAX_ZMENA_MESIC) & ~m.stav_k.isin(ZLOMY_MESIC)
    obdobi = pd.period_range(pd.Period(m.stav_k.min(), "M"), pd.Period(m.stav_k.max(), "M"), freq="M")
    chybi = [str(p) for p in obdobi if str(p) not in set(m.stav_k.str[:7]) and str(p) not in ZNAME_MEZERY]
    return m, chybi


# --- grafy (inline SVG) ------------------------------------------------------

def graf_roky(r):
    """Sloupce cizinců podle let; tmavší část = dočasná ochrana."""
    w, h, pad, pad_b, pad_t = 560, 230, 8, 26, 26
    n = len(r)
    sirka = (w - pad * 2) / n
    maxi = r.cizinci_celkem.max() or 1
    casti = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Cizinci podle let">',
             f'<text x="{pad}" y="16" class="g-nadpis">Cizinci k 31. 12.</text>']
    for i, x in enumerate(r.itertuples()):
        vyska = (h - pad_b - pad_t) * x.cizinci_celkem / maxi
        do = 0 if pd.isna(x.cizinci_docasna_ochrana) else (h - pad_b - pad_t) * x.cizinci_docasna_ochrana / maxi
        sx = pad + i * sirka + 3
        y = h - pad_b - vyska
        zlom = " zlom" if x.rok in ZLOMY else ""
        casti.append(f'<rect x="{sx:.1f}" y="{y:.1f}" width="{sirka - 6:.1f}" height="{vyska:.1f}" rx="2" '
                     f'class="s-cizinci{zlom}"><title>{x.rok}: {cislo(x.cizinci_celkem)}</title></rect>')
        if do:
            casti.append(f'<rect x="{sx:.1f}" y="{y:.1f}" width="{sirka - 6:.1f}" height="{do:.1f}" rx="2" '
                         f'class="s-obcane"><title>{x.rok}: dočasná ochrana {cislo(x.cizinci_docasna_ochrana)}'
                         f'</title></rect>')
        casti.append(f'<text x="{sx + (sirka - 6) / 2:.1f}" y="{h - 9}" class="g-osa">{str(x.rok)[2:]}</text>')
    casti.append("</svg>")
    return "".join(casti)


def graf_mesice(m):
    """Čára počtu cizinců po měsících; body = podezřelé skoky."""
    w, h, pad, pad_b, pad_t = 560, 230, 10, 26, 26
    hodnoty = m.cizinci_celkem.tolist()
    maxi, mini = max(hodnoty), 0
    def xy(i, v):
        x = pad + i * (w - 2 * pad) / max(len(hodnoty) - 1, 1)
        y = h - pad_b - (h - pad_b - pad_t) * (v - mini) / (maxi - mini or 1)
        return x, y
    body = " ".join(f"{x:.1f},{y:.1f}" for x, y in (xy(i, v) for i, v in enumerate(hodnoty)))
    casti = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Cizinci po měsících">',
             f'<text x="{pad}" y="16" class="g-nadpis">Cizinci po měsících</text>',
             f'<polyline points="{body}" fill="none" stroke="var(--s-ciz)" stroke-width="2"/>']
    for i, r in enumerate(m.itertuples()):
        x, y = xy(i, r.cizinci_celkem)
        if r.stav_k.endswith("-12-31") and int(r.stav_k[:4]) % 2 == 0:
            casti.append(f'<text x="{x:.1f}" y="{h - 9}" class="g-osa">{r.stav_k[2:4]}</text>')
        if r.skok:
            casti.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--err)">'
                         f'<title>{r.stav_k}: {r.zmena:+.1%}</title></circle>')
    casti.append("</svg>")
    return "".join(casti)


# --- sekce stránky -----------------------------------------------------------

STAVY = {"ok": ("V pořádku", "✓"), "info": ("Známý rozdíl", "i"),
         "varovani": ("Ověřit ručně", "!"), "chyba": ("Nesedí", "✕")}


def odznak(stav):
    text, ikona = STAVY[stav]
    return f'<span class="odznak {stav}"><b>{ikona}</b>{text}</span>'


def karta(nadpis, stav, popis):
    return (f'<div class="karta {stav}"><div class="karta-hlava">{odznak(stav)}</div>'
            f'<h3>{nadpis}</h3><p>{popis}</p></div>')


def nejhorsi(stavy):
    poradi = ["ok", "info", "varovani", "chyba"]
    return max(stavy, key=poradi.index) if len(stavy) else "ok"


def zmena(x, mez, znamy_zlom=False):
    if pd.isna(x):
        return ""
    trida = "zmena" + (" skok" if abs(x) > mez and not znamy_zlom else "")
    return f"<span class='{trida}'>{x:+.1%}</span>".replace(".", ",")


def bunka_do(r):
    if pd.notna(r.cizinci_docasna_ochrana):
        return cislo(r.cizinci_docasna_ochrana)
    if r.rok >= 2022:
        return "<span class='tlumene'>v přechodném</span>"
    return '<span class="tlumene">–</span>'


def tabulka_roku(r):
    radky = []
    for x in r.itertuples():
        zlom = f'<span class="zlom-text">{esc(ZLOMY[x.rok])}</span>' if x.rok in ZLOMY else ""
        radky.append(
            f"<tr><td class='rok'>{x.rok}{zlom}</td>"
            f"<td class='c'>{cislo(x.mv_celkem)}</td>"
            f"<td class='c'>{cislo(x.cizinci_celkem)}{zmena(x.zmena, MAX_ZMENA_ROK, x.rok in ZLOMY)}</td>"
            f"<td class='c'>{cislo(x.cizinci_trvaly_pobyt)}</td>"
            f"<td class='c'>{cislo(x.cizinci_prechodny_pobyt)}</td>"
            f"<td class='c'>{bunka_do(x)}</td>"
            f"<td class='c'>{cislo(x.cizinci_eu_ehp_ch)}</td>"
            f"<td class='c'>{cislo(x.cizinci_nezjisteny_okres)}</td>"
            f"<td class='c{' zvyrazni' if x.cizinci_nesparovany_stat else ''}'>{cislo(x.cizinci_nesparovany_stat)}</td>"
            f"<td>{odznak(x.stav)}</td></tr>")
    return ("<div class='tab-obal'><table><thead><tr><th>Rok</th><th class='c'>Součet MV</th>"
            "<th class='c'>Zpracováno</th><th class='c'>Trvalý</th><th class='c'>Přechodný</th>"
            "<th class='c'>z toho dočasná ochrana</th><th class='c'>EU, EHP, CH</th>"
            "<th class='c'>Nezjištěný okres</th><th class='c'>Nespárovaný stát</th>"
            "<th>Stav</th></tr></thead><tbody>" + "".join(radky) + "</tbody></table></div>")


def tabulka(d, sloupce, popisky, prazdne):
    if d.empty:
        return f"<p class='prazdne'>{prazdne}</p>"
    ciselne = {c for c in sloupce if pd.api.types.is_numeric_dtype(d[c]) and c not in ("rok", "mesic")}
    hlava = "".join(f"<th{' class=c' if s in ciselne else ''}>{p}</th>" for s, p in zip(sloupce, popisky))
    radky = "".join(
        "<tr>" + "".join(f"<td class='c'>{cislo(getattr(r, s))}</td>" if s in ciselne else
                         f"<td>{esc(getattr(r, s))}</td>" for s in sloupce) + "</tr>"
        for r in d.itertuples())
    return f"<div class='tab-obal'><table><thead><tr>{hlava}</tr></thead><tbody>{radky}</tbody></table></div>"


CSS = """
:root{--bg:#f7f6f3;--panel:#fff;--text:#1d1f23;--muted:#6b6f76;--line:#e4e2dc;
--ok:#2f7d4f;--ok-bg:#e6f2ea;--info:#3a6ea5;--info-bg:#e7eef7;--warn:#a86a00;--warn-bg:#fbf0d9;
--err:#b3261e;--err-bg:#fbe5e3;--s-obc:#3a6ea5;--s-ciz:#c26a2e;--accent:#2f7d4f;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171a;--panel:#1d2024;--text:#e8e6e1;
--muted:#9a9ea5;--line:#30343a;--ok:#6cc08f;--ok-bg:#1c3326;--info:#86b2e0;--info-bg:#1d2a3a;--warn:#e0b04f;
--warn-bg:#3a2e14;--err:#f08a80;--err-bg:#3d1f1c;--s-obc:#6f9fd4;--s-ciz:#e0925a;--accent:#6cc08f;}}
:root[data-theme="dark"]{--bg:#15171a;--panel:#1d2024;--text:#e8e6e1;--muted:#9a9ea5;--line:#30343a;--ok:#6cc08f;
--ok-bg:#1c3326;--info:#86b2e0;--info-bg:#1d2a3a;--warn:#e0b04f;--warn-bg:#3a2e14;--err:#f08a80;--err-bg:#3d1f1c;
--s-obc:#6f9fd4;--s-ciz:#e0925a;--accent:#6cc08f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 64px}
header h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
header p{margin:0;color:var(--muted)}
h2{font-size:18px;margin:40px 0 6px}
.popis{color:var(--muted);margin:0 0 14px;max-width:780px}
.karty{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:22px}
.karta{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;border-top:3px solid var(--line)}
.karta.ok{border-top-color:var(--ok)}.karta.info{border-top-color:var(--info)}
.karta.varovani{border-top-color:var(--warn)}.karta.chyba{border-top-color:var(--err)}
.karta h3{font-size:15px;margin:10px 0 4px}.karta p{margin:0;color:var(--muted);font-size:14px}
.odznak{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:2px 9px 2px 3px;border-radius:999px;white-space:nowrap}
.odznak b{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;color:var(--panel);font-size:11px}
.odznak.ok{background:var(--ok-bg);color:var(--ok)}.odznak.ok b{background:var(--ok)}
.odznak.info{background:var(--info-bg);color:var(--info)}.odznak.info b{background:var(--info)}
.odznak.varovani{background:var(--warn-bg);color:var(--warn)}.odznak.varovani b{background:var(--warn)}
.odznak.chyba{background:var(--err-bg);color:var(--err)}.odznak.chyba b{background:var(--err)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.grafy{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.grafy svg{width:100%;height:auto;display:block}
.g-nadpis{font-size:13px;font-weight:600;fill:var(--text)}.g-osa{font-size:11px;fill:var(--muted);text-anchor:middle}
.s-obcane{fill:var(--s-obc)}.s-cizinci{fill:var(--s-ciz)}rect.zlom{opacity:.75;stroke:var(--text);stroke-dasharray:3 2;stroke-width:1}
.legenda{color:var(--muted);font-size:13px;margin-top:8px}
.tab-obal{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{font-size:12.5px;color:var(--muted);font-weight:600;background:var(--panel);position:sticky;top:0}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
.c{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.rok{font-weight:600;white-space:nowrap}.zlom-text{display:block;font-weight:400;font-size:12px;color:var(--muted);white-space:normal;max-width:220px}
.tlumene{color:var(--muted);font-size:12.5px}
.zvyrazni{color:var(--warn);font-weight:600}
.zmena{display:block;font-size:12px;color:var(--muted)}.zmena.skok{color:var(--err);font-weight:600}
.prazdne{background:var(--panel);border:1px dashed var(--line);border-radius:10px;padding:14px 16px;color:var(--muted);margin:0}
.navod{font-size:14px;color:var(--muted);margin-top:10px}
code{font-family:ui-monospace,Consolas,monospace;font-size:13px;background:var(--line);padding:1px 5px;border-radius:4px}
footer{margin-top:48px;color:var(--muted);font-size:13px}
"""


def main():
    k = nacti("kontrola_souctu.csv")
    if k.empty:
        print("Chybí vystup/kontrola_souctu.csv – nejdřív spusť zpracuj_data.py")
        return 1
    k = vyhodnot(k)
    r, chybi_roky = vyhodnot_roky(k)
    m, chybi_mesice = vyhodnot_mesice(nacti("cizinci_mesicne.csv"))
    nesp = nacti("staty_nesparovane.csv")

    # 1) součty proti MV – všechny soubory
    chyby = k[k.stav == "chyba"].stav_k.tolist()
    stav_soucty = "chyba" if chyby else "ok"
    popis_soucty = (f"Nesedí součet proti MV: {', '.join(chyby)}." if chyby else
                    f"Všech {len(k)} souborů: součet okresů a států = součet MV, zvlášť za trvalý, "
                    "přechodný pobyt a dočasnou ochranu.")
    # 2) roční řada
    skoky = r[(r.stav == "varovani") & (r.cizinci_nesparovany_stat == 0)].rok.tolist()
    stav_roky = "chyba" if chybi_roky else "varovani" if skoky else "ok"
    popis_roky = (f"Chybí roky {', '.join(map(str, chybi_roky))}." if chybi_roky else
                  f"Skok o víc než {MAX_ZMENA_ROK:.0%} mimo známé zlomy: {', '.join(map(str, skoky))}."
                  if skoky else f"{r.rok.min()}–{r.rok.max()} bez mezer a bez podezřelých skoků.")
    # 3) státy
    stav_staty = "varovani" if not nesp.empty else "ok"
    popis_staty = (f"{nesp.nazev_mv.nunique()} názvů není v <code>ciselniky/staty.csv</code> "
                   f"({cislo(nesp.cizinci_celkem.sum())} osob)." if not nesp.empty else
                   "Všechny názvy států jsou v číselníku.")
    # 4) měsíční řada
    mskoky = m[m.skok].stav_k.tolist()
    stav_mesice = "varovani" if (chybi_mesice or mskoky) else "ok"
    popis_mesice = "; ".join(filter(None, [
        f"chybí měsíce {', '.join(chybi_mesice)}" if chybi_mesice else "",
        f"skok o víc než {MAX_ZMENA_MESIC:.0%}: {', '.join(mskoky)}" if mskoky else ""])).capitalize() + "." \
        if stav_mesice != "ok" else (
            f"{m.stav_k.min()[:7]} – {m.stav_k.max()[:7]}: {len(m)} měsíců bez neznámých skoků; "
            + "; ".join(f"chybí {k} ({v})" for k, v in ZNAME_MEZERY.items()) + ".")
    # 5) tabulka ČR × stát od 2007
    ks = nacti("kontrola_staty.csv")
    if ks.empty:
        stav_hist, popis_hist = "chyba", "Chybí vystup/kontrola_staty.csv."
    else:
        ks = ks.sort_values("rok").reset_index(drop=True)
        ks["zmena"] = ks.cizinci_celkem.pct_change()
        mv = r.set_index("rok").cizinci_celkem
        nesedi = [x.rok for x in ks.itertuples() if x.rok in mv.index and x.cizinci_celkem != mv[x.rok]]
        mezery = sorted(set(range(ks.rok.min(), ks.rok.max() + 1)) - set(ks.rok))
        skoky_h = ks[(ks.zmena.abs() > MAX_ZMENA_ROK) & ~ks.rok.isin(ZLOMY)].rok.tolist()
        stav_hist = "chyba" if nesedi or mezery else "varovani" if skoky_h else "ok"
        popis_hist = (f"Nesedí na okresní data: {nesedi}." if nesedi else
                      f"Chybí roky {mezery}." if mezery else
                      f"Skok o víc než {MAX_ZMENA_ROK:.0%}: {skoky_h}." if skoky_h else
                      f"{ks.rok.min()}–{ks.rok.max()}: roky 2007–2011 sedí na „Celkový součet“ ve zdroji, "
                      "od 2012 na součet okresů.")
    # 6) vnitřní nesoulad v souborech MV
    nesoulad = k[k.nesoulad_mv > 0]
    stav_mv = "info" if len(nesoulad) else "ok"
    popis_mv = (f"V {len(nesoulad)} souborech MV nesedí muži + ženy nebo součet okresů: "
                f"{', '.join(nesoulad.stav_k)}. Je to už ve zdroji, data se přebírají, jak jsou."
                if len(nesoulad) else "Muži + ženy = celkem a součet okresů = celkový součet ve všech souborech.")

    stranka = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kontrola zpracování</title><style>{CSS}</style></head><body><main>
<header><h1>Kontrola zpracování dat MV</h1>
<p>Cizinci s povoleným pobytem, okresy {r.rok.min()}–{r.rok.max()}, ČR po měsících
{m.stav_k.min()[:7]} – {m.stav_k.max()} ·
vygenerováno {datetime.now():%d. %m. %Y %H:%M}</p></header>

<section class="karty">
{karta("Součty proti MV", stav_soucty, popis_soucty)}
{karta("Roční řada", stav_roky, popis_roky)}
{karta("Názvy států", stav_staty, popis_staty)}
{karta("Měsíční řada", stav_mesice, popis_mesice)}
{karta("ČR podle států od 2007", stav_hist, popis_hist)}
{karta("Nesoulad v souborech MV", stav_mv, popis_mv)}
</section>

<h2>Vývoj v čase</h2>
<p class="popis">Skok, který neodpovídá známým zlomům, obvykle znamená chybu v načtení souboru. Modře je
v ročním grafu dočasná ochrana (2022–2023 ji MV samostatně neuvádí), čárkovaně roky se zlomem.
V měsíčním grafu jsou červeně skoky o víc než {MAX_ZMENA_MESIC:.0%} mimo známé (3–4/2022, 3/2023).</p>
<div class="panel"><div class="grafy">{graf_roky(r)}{graf_mesice(m)}</div>
<p class="legenda">{' · '.join(f'{rok}: {esc(t)}' for rok, t in ZLOMY.items())}</p></div>

<h2>Roční přehled (stav k 31. 12.)</h2>
<p class="popis">Zpracováno = součet všech okresů a států. Musí se rovnat součtu MV. Přechodný pobyt
zahrnuje i dočasnou ochranu.</p>
{tabulka_roku(r)}

<h2>Celá ČR podle států od roku 2007</h2>
<p class="popis">Tabulka <code>cizinci_staty.csv</code>: 2007–2010 z PDF Služby cizinecké policie, 2011 ze souboru MV
bez okresů, od 2012 součet okresů. Muži a ženy za rok 2007 ve zdroji nejsou.</p>
{tabulka(ks, ["rok", "zdroj", "cizinci_celkem", "cizinci_muzi", "cizinci_zeny", "cizinci_trvaly_pobyt",
              "cizinci_prechodny_pobyt"], ["Rok", "Zdroj", "Celkem", "Muži", "Ženy", "Trvalý", "Přechodný"],
         "Chybí vystup/kontrola_staty.csv.") if not ks.empty else ""}

<h2>Názvy států mimo číselník</h2>
{tabulka(nesp, ["stav_k", "nazev_mv", "cizinci_celkem"], ["Stav k", "Název podle MV", "Osob"],
         "Nic, všechny názvy se spárovaly.")}
<p class="navod">Nový název přidej do <code>ciselniky/staty.csv</code> (název podle MV, sjednocený název,
kód ISO 3166-1 alpha-3) a spusť <code>python zpracuj_data.py</code>.</p>

<h2>Soubory s nesouladem uvnitř souboru MV</h2>
{tabulka(nesoulad, ["stav_k", "bunky_muzi_zeny_nesedi", "radky_soucet_okresu_nesedi", "okresy_soucet_nesedi"],
         ["Stav k", "Buňky muži + ženy ≠ celkem", "Řádky součet okresů ≠ celkem", "Okresy ≠ řádek CELKEM"],
         "Žádné.")}

<footer>Zdroj: soubory v <code>vystup/</code> vytvořené <code>zpracuj_data.py</code>. Podrobnosti v README.</footer>
</main></body></html>"""
    cil = VYSTUP / "kontrola.html"
    cil.write_text(stranka, encoding="utf-8")

    # souhrn pro pull request z GitHub Actions + celkový stav do samostatného souboru
    karty = [("Součty proti MV", stav_soucty, popis_soucty), ("Roční řada", stav_roky, popis_roky),
             ("Názvy států", stav_staty, popis_staty), ("Měsíční řada", stav_mesice, popis_mesice),
             ("ČR podle států od 2007", stav_hist, popis_hist),
             ("Nesoulad v souborech MV", stav_mv, popis_mv)]
    celkem = nejhorsi([s for _, s, _ in karty])
    ikony = {"ok": "✅", "info": "ℹ️", "varovani": "⚠️", "chyba": "❌"}
    posledni = r.iloc[-1]
    souhrn = [f"## Kontrola zpracování: {ikony[celkem]} {STAVY[celkem][0]}", "",
              f"Poslední rok **{posledni.rok}**: cizinci {cislo(posledni.cizinci_celkem)}, "
              f"poslední měsíc **{m.stav_k.max()}**: {cislo(m.cizinci_celkem.iloc[-1])}.", "",
              "| Kontrola | Stav | Detail |", "|---|---|---|"]
    for nazev, stav, popis in karty:
        souhrn.append(f"| {nazev} | {ikony[stav]} {STAVY[stav][0]} | {re.sub(r'</?code>', '`', popis)} |")
    (VYSTUP / "kontrola_souhrn.md").write_text("\n".join(souhrn) + "\n", encoding="utf-8")
    (VYSTUP / "kontrola_stav.txt").write_text(celkem, encoding="utf-8")
    print(f"Kontrola: {STAVY[celkem][0]} -> {cil}")


if __name__ == "__main__":
    sys.exit(main())
