# Atención pública en Wikipedia: series temporales jerárquicas con MultiStream

Proyecto del midterm de visualización de datos basado en el paper
[MultiStream: A Multiresolution Streamgraph Approach to Explore Hierarchical Time Series](https://github.com/erickedu85/multistream)
(Cuenca et al., IEEE TVCG 2018). El enunciado está en [`enunciado.md`](enunciado.md).

**Pregunta analítica:** ¿qué temas comparten la misma dinámica de atención pública, y se distinguen
grupos estacionales, por evento y de tendencia?

## Datos

- **Fuente:** [Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/), visitas diarias a
  31 artículos de Wikipedia en inglés (2016-01-01 a 2025-12-31).
- **Temas:** festividades (*Christmas*, *Halloween*…), deportes y eventos (*FIFA World Cup*,
  *Super Bowl*…), tecnología (*ChatGPT*, *Bitcoin*…) y pandemia (*COVID-19*, *Zoom*…).
- **Índice de atención 0–100:** cada artículo se escala respecto a su mejor semana (estilo
  Google Trends), para que un artículo enorme no aplaste al resto en el streamgraph apilado.

## Jerarquía (clustering)

Clustering jerárquico aglomerativo (Ward) sobre la *forma* de las series: logaritmo + z-score por
artículo, de modo que la distancia equivale a 1 − correlación. El dendrograma se corta en 3, 6 y 12
grupos (cortes anidados) y los grupos de un solo hijo se colapsan, lo que da una jerarquía de
**4 niveles con ramas de distinta profundidad**:

```
wikipedia attention
├─ g1  tendencias      (ChatGPT, IA, TikTok, COVID-19, Zoom…)
├─ g2  estacionales    (Christmas, Thanksgiving, Black Friday, Halloween…)
└─ g3  eventos         (FIFA World Cup, Olympics, Influenza, Super Bowl, Oscars…)
```

## Estructura

| Ruta | Contenido |
|---|---|
| `fase2_clustering.py` | Descarga, normalización, clustering y exportación (las dos vías) |
| `output/data.csv`, `output/hierarchy.json` | Vía 1: entradas del `preprocessing.js` de MultiStream (semanal) |
| `output/multistream_wikipedia.json` | **JSON final para MultiStream** (probado en la web) |
| `output/muti_output.json` | El mismo JSON generado con la herramienta web (mismos datos, `t_granularity: "days"`) |
| `output/d3_data.json` | Vía 2: datos diarios + árbol, para la visualización en D3 |
| `output/raw_daily.csv` | Caché de la descarga (evita volver a llamar a la API) |
| `d3/index.html` | Visualización propia en D3.js |

## Cómo reproducirlo

```powershell
# 1. Entorno y datos
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python fase2_clustering.py

# 2. JSON para MultiStream (preprocessing.js del repo oficial)
git clone https://github.com/erickedu85/multistream
cd multistream\generate_supported_file
npm install
node preprocessing.js --raw=..\..\output\data.csv --hierarchy=..\..\output\hierarchy.json `
  --output=..\..\output\multistream_wikipedia.json --granularity=weeks --step=1 `
  --datatype="attention index (0-100)"
```

## Visualización en D3

```powershell
python -m http.server 8000      # desde la carpeta del proyecto
```

Abrir <http://localhost:8000/d3/>. Funcionalidades:

- **Streamgraph** de los hijos del nodo actual; clic en una capa para bajar a esa rama y en la
  ruta superior para subir.
- **Niveles (1–4):** cuántos niveles bajo el nodo actual se muestran a la vez.
- **Granularidad:** día / semana / mes (promedio del índice en cada periodo).
- **Línea de tiempo con deslizadores** para acotar el periodo (overview + detalle).
- **Árbol de la jerarquía** (minimizable): clic en nodos de cualquier nivel para seleccionarlos y
  compararlos; otro clic los quita.
