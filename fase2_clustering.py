"""
Fase 2 - Wikipedia pageviews -> clustering jerárquico -> 2 salidas.

Salidas (carpeta output/):
  Vía 1 (MultiStream): data.csv (semanal) + hierarchy.json
  Vía 2 (D3):          d3_data.json (diario, árbol con valores en cada nodo)

Uso: python fase2_clustering.py
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.cluster.hierarchy import linkage, fcluster

# ---------------------------------------------------------------- 1. datos
# nombre legible (único, minúsculas, sin comas) -> título en en.wikipedia
ARTICLES = {
    # festividades / estacionales
    "christmas": "Christmas", "halloween": "Halloween", "thanksgiving": "Thanksgiving",
    "valentines day": "Valentine's_Day", "easter": "Easter", "black friday": "Black_Friday_(shopping)",
    "influenza": "Influenza", "common cold": "Common_cold",
    # eventos deportivos / mediáticos
    "fifa world cup": "FIFA_World_Cup", "super bowl": "Super_Bowl", "wimbledon": "Wimbledon_Championships",
    "olympic games": "Olympic_Games", "tour de france": "Tour_de_France", "academy awards": "Academy_Awards",
    "nba finals": "NBA_Finals", "us presidential election": "United_States_presidential_election",
    "february 29": "February_29", "solar eclipse": "Solar_eclipse",
    # tecnología / tendencias
    "chatgpt": "ChatGPT", "artificial intelligence": "Artificial_intelligence", "bitcoin": "Bitcoin",
    "tiktok": "TikTok", "python language": "Python_(programming_language)", "machine learning": "Machine_learning",
    "large language model": "Large_language_model", "nvidia": "Nvidia",
    # pandemia
    "covid-19": "COVID-19", "pandemic": "Pandemic", "zoom software": "Zoom_(software)",
    "face mask": "Face_masks_during_the_COVID-19_pandemic", "remote work": "Remote_work",
}
START, END = "2016-01-01", "2025-12-31"
OUT = Path("output")
CACHE = OUT / "raw_daily.csv"   # evita volver a descargar en cada ejecución


def fetch(title):
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
           f"all-access/user/{requests.utils.quote(title, safe='')}/daily/"
           f"{START.replace('-', '')}00/{END.replace('-', '')}00")
    for wait in [0, 2, 5, 10, 20, 40]:          # Wikimedia responde 429 si vamos muy rápido
        time.sleep(wait)
        r = requests.get(url, headers={"User-Agent": "MultiStream-midterm/1.0 (student project)"}, timeout=60)
        if r.status_code != 429:
            break
    r.raise_for_status()
    print("descargado:", title)
    items = r.json()["items"]
    return pd.Series({pd.to_datetime(i["timestamp"][:8]): i["views"] for i in items})


OUT.mkdir(exist_ok=True)
if CACHE.exists():
    raw = pd.read_csv(CACHE, index_col=0, parse_dates=True)
else:
    raw = pd.DataFrame({name: fetch(t) for name, t in ARTICLES.items()})
    raw.to_csv(CACHE)

# La API omite días sin visitas (p. ej. ChatGPT antes de 2022) -> 0
raw = raw.reindex(pd.date_range(START, END, freq="D")).fillna(0)

# Índice de atención 0-100 por artículo (estilo Google Trends): así un artículo
# gigante (COVID-19) no aplasta al resto en el streamgraph apilado.
# 100 = su mejor semana (media móvil de 7 días); un día puntual puede superar 100.
daily = 100 * raw / raw.rolling(7).mean().max()
weekly = daily.resample("W-MON", label="left", closed="left").mean()  # semanas que empiezan en lunes

# ------------------------------------------------------------ 2. clustering
# Clustering por FORMA de la serie, no por volumen: log + z-score por artículo.
# Con series z-normalizadas, la distancia euclídea equivale a 1 - correlación,
# y Ward agrupa series que suben y bajan juntas.
X = np.log1p(weekly)
X = ((X - X.mean()) / X.std()).T.values          # filas = artículos
Z = linkage(X, method="ward")

# Cortes anidados del mismo dendrograma -> jerarquía de 3 niveles de grupos.
# (Los cortes de un mismo linkage son anidados por construcción.)
LEVELS = [3, 6, 12]
labels = np.array([fcluster(Z, k, criterion="maxclust") for k in LEVELS]).T  # (n_articulos, 3)
names = list(weekly.columns)
volume = raw.sum()  # para nombrar cada grupo por su artículo más visto


def build(idx, depth):
    """Hijos para los artículos idx; depth = nivel de corte actual."""
    if depth == len(LEVELS):
        return [{"name": names[i]} for i in idx]
    children = []
    for c in sorted(set(labels[idx, depth])):
        sub = [i for i in idx if labels[i, depth] == c]
        kids = build(sub, depth + 1)
        # grupo de un solo hijo -> se colapsa (ramas de distinta profundidad)
        if len(sub) == 1 or len(kids) == 1:
            children += kids
            continue
        top = max(sub, key=lambda i: volume.iloc[i])
        children.append({"name": names[top], "children": kids})  # nombre provisional
    return children


def relabel(node, path=""):
    """Grupos -> 'g1.2 chatgpt' (ruta en el árbol final + su artículo más visto). Únicos."""
    for n, c in enumerate(node["children"], 1):
        if "children" in c:
            c["name"] = f"g{path}{n} {c['name']}"
            relabel(c, f"{path}{n}.")


tree = {"name": "wikipedia attention", "children": build(list(range(len(names))), 0)}
relabel(tree)

# Colores explícitos (preprocessing.js solo inventa colores si el nodo no trae "color").
# Su escala automática va desde el blanco, así que en ramas con muchas hojas las últimas
# salen casi blancas e invisibles. Usamos los mismos tonos que la versión D3:
# un color por rama y, dentro de ella, cada nivel reparte una rampa oscuro -> pastel.
BRANCH_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]


def mix(rgb, target, t):
    return tuple(a + (b - a) * t for a, b in zip(rgb, target))


def hexcolor(rgb):
    return "#" + "".join(f"{round(c):02x}" for c in rgb)


for b, branch in enumerate(tree["children"]):
    base = tuple(int(BRANCH_COLORS[b % 3][i:i + 2], 16) for i in (1, 3, 5))
    dark, light = tuple(c * 0.7 ** 0.8 for c in base), mix(base, (255, 255, 255), 0.45)
    branch["color"] = hexcolor(base)
    level = branch.get("children", [])
    while level:                                     # recorrido por niveles dentro de la rama
        for k, node in enumerate(level):
            t = k / (len(level) - 1) if len(level) > 1 else 0.5
            node["color"] = hexcolor(mix(dark, light, t))
        level = [c for n in level for c in n.get("children", [])]

# ------------------------------------------------------------ 3. Vía 1
weekly.round(2).rename_axis("date").to_csv(OUT / "data.csv", date_format="%Y-%m-%d")
(OUT / "hierarchy.json").write_text(json.dumps({"ranges": tree}, indent=2), encoding="utf-8")

# ------------------------------------------------------------ 4. Vía 2
# Árbol con "values" en TODOS los nodos (padre = suma de hijos), alineado con "dates".
def with_values(node):
    if "children" not in node:
        return {"name": node["name"], "values": daily[node["name"]].round(2).tolist()}
    kids = [with_values(c) for c in node["children"]]
    return {"name": node["name"], "values": np.round(np.sum([k["values"] for k in kids], axis=0), 2).tolist(),
            "children": kids}


d3_data = {"dates": daily.index.strftime("%Y-%m-%d").tolist(), "tree": with_values(tree)}
(OUT / "d3_data.json").write_text(json.dumps(d3_data), encoding="utf-8")

# ------------------------------------------------------------ 5. checks
csv_cols = set(weekly.columns)
def leaves(n): return [n["name"]] if "children" not in n else sum(map(leaves, n["children"]), [])
def all_names(n): return [n["name"]] + sum((all_names(c) for c in n.get("children", [])), [])
def depth(n): return 0 if "children" not in n else 1 + max(map(depth, n["children"]))

assert set(leaves(tree)) == csv_cols, "hojas != columnas del CSV"
lower = [n.lower() for n in all_names(tree)]
assert len(lower) == len(set(lower)), "nombres repetidos (MultiStream busca por nombre)"
assert not weekly.isna().any().any(), "hay nulos"
assert depth(tree) >= 3, "jerarquía con menos de 3 niveles"


def show(n, ind=0):
    print("  " * ind + n["name"])
    for c in n.get("children", []):
        show(c, ind + 1)


show(tree)
print(f"\nOK: {len(csv_cols)} series, {len(weekly)} semanas, profundidad {depth(tree)} -> {OUT.resolve()}")
