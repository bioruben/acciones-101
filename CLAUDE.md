# CLAUDE.md — Dashboard "Acciones 101"

Instrucciones para construir este repositorio con Claude Code. Léelas completas antes de escribir código y síguelas en el orden de la sección **Plan de trabajo**.

## 1. Contexto y objetivo

Este repo es material de clase de la **Universidad Panamericana** (curso de visualización de datos y narración de historias). Sirve como ejemplo de:

1. Un **análisis de acciones 101** con periodicidad **mensual o anual** (no trading de corto plazo).
2. Cómo construir y publicar un **dashboard en Streamlit** usando un **agente de IA** (Claude Code).

El dashboard debe explicar cada métrica a estudiantes de ciencia de datos, no solo mostrarla. La presentación de la clase se titula *"Más allá del dashboard: la bolsa no es un casino, es análisis"* y tiene slides para pegar capturas de vistas específicas (ver sección 9). Los nombres de pestañas y vistas deben coincidir exactamente.

## 2. Reglas generales

- **Idioma:** interfaz, docstrings, comentarios y README en **español**. Los términos financieros se dejan **en inglés**: CAGR, drawdown, Sharpe ratio, beta, benchmark, buy & hold, backtest, ticker, Adj Close, SMA, OHLC, market cap. Los nombres de empresas y tickers **no se traducen**.
- **Sin recomendaciones de inversión.** Nunca generes texto como "compra", "vende", "conviene invertir en…". Todo se describe en pasado y como análisis histórico.
- **Sin logos** en el dashboard.
- **Código limpio y didáctico:** type hints en todas las funciones y **docstrings en español** en todas las funciones públicas (estilo Google: descripción, `Args`, `Returns`, `Raises` si aplica, y un `Example` corto cuando ayude). Los estudiantes van a leer el código.
- **Sin información del futuro (leakage)** en cualquier cálculo que simule decisiones.
- Antes de dar algo por terminado: `pytest` pasa y `streamlit run app.py` corre sin errores ni warnings ruidosos.

## 3. Disclaimers obligatorios

Deben aparecer **en el README** (al inicio, en un bloque destacado) y **en la app** (texto breve en el pie de la barra lateral y un aviso corto debajo del título):

> **Aviso:** Este proyecto es exclusivamente **educativo**. No constituye recomendación de inversión, asesoría financiera ni oferta de compra o venta de valores. Rendimientos pasados no garantizan rendimientos futuros. Cada persona es responsable de sus propias decisiones de inversión. Los datos provienen de Yahoo Finance a través de `yfinance` y pueden contener errores o retrasos.

> **Código generado con IA:** Todo el código de este repositorio fue escrito por un agente de IA (Claude Code, de Anthropic) a partir de las instrucciones de `CLAUDE.md`, y revisado por el autor con fines didácticos.

Agrega también una línea en el encabezado (docstring de módulo) de cada archivo `.py`: `"""<propósito del módulo>. Código generado con un agente de IA (Claude Code) con fines educativos."""`

## 4. Stack

- Python 3.11+
- `streamlit`, `yfinance`, `pandas`, `numpy`, `plotly`, `pytest`.
- **Fija versiones exactas** en `requirements.txt` con las versiones que instales y verifiques (`paquete==x.y.z`). No uses rangos abiertos.
- Nada de librerías de análisis técnico (ta-lib, etc.): todas las métricas se implementan a mano en `metricas.py` para que sean didácticas.

## 5. Estructura del repositorio

```
acciones-101/
├── app.py                    # Dashboard en Streamlit (solo presentación)
├── config.py                 # Tickers, benchmarks, fechas, tasa libre de riesgo, paleta
├── datos.py                  # Descarga con yfinance, respaldo CSV y resampling
├── metricas.py               # Las métricas (funciones puras, sin Streamlit)
├── actualizar_respaldo.py    # Regenera data/respaldo_precios.csv
├── data/
│   └── respaldo_precios.csv  # Precios diarios ajustados de todos los tickers
├── tests/
│   └── test_metricas.py      # Pruebas de las fórmulas con casos conocidos
├── .streamlit/
│   └── config.toml           # Tema base y color primario
├── requirements.txt
├── .gitignore
├── CLAUDE.md
└── README.md
```

Separación estricta: `metricas.py` y `datos.py` **no importan Streamlit** (salvo que necesites algo trivial; preferible no). `app.py` no contiene fórmulas.

### .gitignore

Incluir al menos: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.streamlit/secrets.toml`, `.DS_Store` y **`BITACORA_AGENTE.md`**.

### Bitácora del agente (local, no se publica)

Crea y mantén `BITACORA_AGENTE.md` en la raíz (está en `.gitignore`). Registra de forma breve, en orden: qué pidió el autor, qué decidiste, qué falló y cómo se corrigió, y qué verificaste. Servirá después como material de clase.

## 6. Configuración (`config.py`)

Todo lo que un estudiante quiera cambiar debe estar aquí, con comentarios.

```python
TICKERS = {
    # ticker: {nombre, mercado, moneda, benchmark}
    "WALMEX.MX":   {"nombre": "Walmart de México", "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "AMXB.MX":     {"nombre": "América Móvil",     "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "FEMSAUBD.MX": {"nombre": "FEMSA",             "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "GMEXICOB.MX": {"nombre": "Grupo México",      "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "BIMBOA.MX":   {"nombre": "Grupo Bimbo",       "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "CEMEXCPO.MX": {"nombre": "CEMEX",             "mercado": "México", "moneda": "MXN", "benchmark": "^MXX"},
    "NVDA":        {"nombre": "NVIDIA",            "mercado": "EE.UU.", "moneda": "USD", "benchmark": "^GSPC"},
    "MU":          {"nombre": "Micron Technology", "mercado": "EE.UU.", "moneda": "USD", "benchmark": "^GSPC"},
    "AAPL":        {"nombre": "Apple",             "mercado": "EE.UU.", "moneda": "USD", "benchmark": "^GSPC"},
    "000660.KS":   {"nombre": "SK hynix",          "mercado": "Corea",  "moneda": "KRW", "benchmark": "^KS11"},
}
BENCHMARKS = {
    "^MXX":  {"nombre": "S&P/BMV IPC", "moneda": "MXN"},
    "^GSPC": {"nombre": "S&P 500",     "moneda": "USD"},
    "^KS11": {"nombre": "KOSPI",       "moneda": "KRW"},
}
FECHA_INICIO = "2015-01-01"
TICKER_DEFAULT = "NVDA"
PERIODICIDAD_DEFAULT = "Mensual"        # "Mensual" o "Anual"
VENTANA_SMA_DEFAULT = 10                # en periodos de la periodicidad elegida
CAPITAL_INICIAL = 10_000
TASA_LIBRE_RIESGO_ANUAL = 0.07          # Supuesto basado en CETES; actualizar y documentar la fecha
VELAS_ESTILO = "up"                     # "up" = dorado/rojo; "clasico" = verde/rojo
```

- **Verifica cada ticker con yfinance** al construir. Si alguno no descarga (por ejemplo `000660.KS` o alguno `.MX`), busca la variante correcta, corrígela y anótalo en la bitácora y en el README.
- Cada acción se compara **solo contra el benchmark de su mercado** y todo se calcula en **moneda local**. No mezcles monedas ni conviertas tipo de cambio en esta versión; explícalo en la app y en el README.

## 7. Datos (`datos.py`)

1. `descargar_precios(tickers, inicio, fin) -> pd.DataFrame` con yfinance, **precios ajustados** (usa `auto_adjust=True` o la columna Adj Close, y documenta cuál). Formato **tidy**: columnas `fecha, ticker, open, high, low, close, volume`, frecuencia diaria.
2. `cargar_respaldo(ruta) -> pd.DataFrame` lee `data/respaldo_precios.csv` (mismo formato tidy).
3. `obtener_precios(...) -> tuple[pd.DataFrame, dict]`: intenta yfinance; si falla, si regresa vacío o si faltan tickers, usa el respaldo **solo para lo que falte** y regresa un dict de metadatos: `{"fuente": "yfinance" | "respaldo" | "mixta", "fecha_datos": <última fecha>, "tickers_respaldo": [...]}`.
4. `resamplear_ohlc(df, periodicidad) -> pd.DataFrame`: diario → mensual (`"ME"`) o anual (`"YE"`) con `open=first, high=max, low=min, close=last, volume=sum`, **por ticker**.
5. En `app.py`, envuelve la descarga con `st.cache_data(ttl=6 * 3600)`.

### Respaldo CSV

- `actualizar_respaldo.py` descarga todos los tickers y benchmarks desde `FECHA_INICIO` hasta hoy y sobrescribe `data/respaldo_precios.csv`. Imprime un resumen: filas por ticker, fecha mínima y máxima.
- **Ejecútalo durante la construcción** para generar el CSV inicial y súbelo al repo.
- Cuando la app use el respaldo, muestra un aviso visible: "⚠️ Yahoo Finance no respondió. Mostrando datos de respaldo al <fecha>." Esto pasa a veces en servidores en la nube; el respaldo garantiza que el demo nunca falle en clase.

## 8. Métricas (`metricas.py`)

Funciones puras sobre `pd.Series` indexadas por fecha, con docstrings en español que incluyan **la fórmula** y **cómo se interpreta**. `periodos_por_anio` = 12 en mensual y 1 en anual.

| Función | Qué calcula |
|---|---|
| `rendimientos(precios, tipo="simple" \| "log")` | rₜ = Pₜ/Pₜ₋₁ − 1 o ln(Pₜ/Pₜ₋₁) |
| `rendimiento_acumulado(rend)` | Π(1 + rₜ) − 1 |
| `crecimiento_capital(rend, capital)` | Valor de una inversión inicial en el tiempo |
| `cagr(precios, periodos_por_anio)` | (P_final / P_inicial)^(1/años) − 1, con años = n_periodos / periodos_por_anio |
| `volatilidad_anualizada(rend, periodos_por_anio)` | σ(rend) × √periodos_por_anio |
| `serie_drawdown(precios)` | Pₜ / máx(P₀…Pₜ) − 1 |
| `max_drawdown(precios)` | mínimo de la serie de drawdown, con fecha del pico y del valle |
| `tiempo_recuperacion(precios)` | periodos desde el valle del máx. drawdown hasta recuperar el pico (o `None` si no se ha recuperado) |
| `beta(rend_activo, rend_benchmark)` | Cov(rₐ, rₘ) / Var(rₘ), alineando fechas |
| `correlacion(rend_activo, rend_benchmark)` | correlación de Pearson |
| `sharpe(rend, tasa_libre_anual, periodos_por_anio)` | (media(r − r_f) / σ(r)) × √periodos_por_anio, con r_f por periodo |
| `sma(precios, ventana)` | media móvil simple |
| `backtest_sma(precios, ventana, tasa_libre_anual, periodos_por_anio)` | Regla: invertido en el periodo t solo si el **cierre de t−1** > SMA de t−1; si no, rinde la tasa libre de riesgo. Regresa curva de capital de la regla y de buy & hold, la señal y un resumen (CAGR, máx. drawdown, Sharpe, % de periodos invertido) para ambas. Empieza cuando la SMA ya existe. Sin comisiones ni impuestos (documentarlo). |
| `resumen_metricas(...)` | dict o DataFrame con todas las métricas de un ticker |
| `tabla_tidy_para_bi(...)` | DataFrame largo (fecha, ticker, métrica, valor) listo para Looker Studio, Power BI o Tableau |

Validaciones: si hay menos de 2 años de datos, o en periodicidad anual hay menos periodos que la ventana de la SMA, regresa `NaN` y una advertencia clara (la app la muestra en lugar de fallar).

## 9. La app (`app.py`)

### Barra lateral
- Botón **modo claro / modo oscuro** (ver sección 10).
- Selector de ticker principal agrupado por mercado (muestra "NVDA · NVIDIA").
- Multiselección de tickers para comparar (pestañas Rendimiento y Riesgo).
- Rango de fechas (default: `FECHA_INICIO` a hoy).
- Periodicidad: Mensual / Anual.
- Ventana de la SMA (slider, 3 a 24 periodos).
- Tasa libre de riesgo anual (input, default de config, con nota "supuesto basado en CETES").
- Indicador de fuente de datos (yfinance o respaldo, con fecha).
- Disclaimer breve al pie.

### Encabezado
Título "Acciones 101", subtítulo "La bolsa no es un casino: es análisis", aviso educativo de una línea y una fila de **KPIs** del ticker principal: CAGR, Volatilidad, Máx. drawdown, Sharpe ratio, Beta vs su benchmark. Formato: porcentajes con 1 decimal; Sharpe y beta con 2.

### Pestañas (nombres exactos)
Cada pestaña incluye un `st.expander("¿Qué estoy viendo?")` con explicación breve, la fórmula (`st.latex`) y una pregunta para reflexionar.

1. **«Velas»** — velas OHLC (Plotly `Candlestick`) de la periodicidad elegida + línea SMA. Sin rangeslider.
2. **«Rendimiento»** — crecimiento de `CAPITAL_INICIAL` para los tickers seleccionados desde la misma fecha, con etiqueta del valor final de cada línea. Aviso si se mezclan monedas.
3. **«Riesgo»** — dispersión riesgo vs rendimiento (x = volatilidad anualizada, y = CAGR) de todos los tickers y benchmarks; color por mercado; benchmarks con otro marcador. Tabla con las métricas debajo.
4. **«Drawdown»** — panel superior con precio y máximo previo (línea punteada), panel inferior con área de drawdown; anotación del máximo drawdown y su fecha; tiempo de recuperación en texto.
5. **«vs Mercado»** — crecimiento del ticker vs su benchmark; dispersión de rendimientos (activo vs benchmark) con recta de regresión y beta anotada; tarjetas con beta, correlación, Sharpe del activo y del benchmark. Debe poder mostrar dos tickers lado a lado (por ejemplo WALMEX.MX y NVDA) usando dos columnas.
6. **«Backtest»** — curvas de buy & hold vs regla SMA, periodos fuera del mercado sombreados, tabla comparativa (CAGR, máx. drawdown, Sharpe, % invertido) y nota: "Se decide con el cierre del periodo anterior; sin comisiones ni impuestos; rendimientos pasados no garantizan futuros."
7. **«Datos»** — vista previa de la tabla tidy, botón para **descargar CSV** (`st.download_button`) y un texto corto sobre cómo usar ese mismo archivo en Looker Studio (vía Google Sheets), Power BI o Tableau.

### Vistas para las capturas de la presentación
Asegúrate de que estas vistas se vean bien (sin cortes, leyendas legibles):

| Slide | Vista |
|---|---|
| Velas y SMA | «Velas» · NVDA · 2015 a hoy · Mensual · SMA 10 · modo claro |
| Rendimiento acumulado | «Rendimiento» · NVDA, MU y AAPL · desde 2015 |
| Riesgo vs rendimiento | KPIs + «Riesgo» con todas las acciones y benchmarks |
| Drawdown | «Drawdown» · NVDA o 000660.KS · desde 2015 |
| Contra el mercado | «vs Mercado» · WALMEX.MX vs ^MXX y NVDA vs ^GSPC |
| Backtest | «Backtest» · ^MXX o AAPL · desde 2015 · SMA 10 (permite elegir un benchmark como activo principal en esta pestaña) |
| Modo claro / oscuro | Vista general con KPIs y «Velas», en ambos modos |

## 10. Diseño visual

Paleta basada en la UP. **Dorado como color principal**, sobre blanco (claro) o negro (oscuro). **Rojo solo con significado** (caídas, drawdown, velas bajistas, rendimientos negativos). Azul opcional y discreto para benchmarks. **Sin logo.**

| Token | Modo claro | Modo oscuro |
|---|---|---|
| Fondo | `#FFFFFF` | `#0E0E0E` |
| Superficie (tarjetas, sidebar) | `#F7F5F0` | `#1A1A1A` |
| Texto principal | `#1A1A1A` | `#F2F2F2` |
| Texto secundario | `#5C5C5C` | `#A6A6A6` |
| Primario (dorado UP) | `#C9A96E` | `#C9A96E` |
| Dorado fuerte (texto o líneas sobre claro) | `#A88B4F` | `#D9BE8A` |
| Negativo (rojo UP) | `#D0102B` | `#E5394F` |
| Benchmark (azul UP, opcional) | `#002B72` | `#6F8FD6` |
| Rejilla / bordes | `#E6E2D8` | `#2E2E2E` |

- Velas: alcista dorado, bajista rojo (`VELAS_ESTILO="up"`); opción `"clasico"` verde/rojo en config.
- Implementa el botón de modo con `st.session_state` + CSS inyectado (`st.markdown(..., unsafe_allow_html=True)`) para fondo, superficies y texto, **y** un template de Plotly por modo (`plotly_white` / `plotly_dark` personalizados con la paleta). Las gráficas deben verse bien en ambos modos.
- Verifica el **contraste** de texto en ambos modos (dorado sobre blanco solo para elementos grandes; para texto usa el dorado fuerte).
- `.streamlit/config.toml`: `primaryColor = "#C9A96E"`, `base = "light"`.
- Tipografía y espaciado limpios; nada de chartjunk (principios de Tufte).

## 11. Pruebas (`tests/test_metricas.py`)

Casos con resultado conocido, como mínimo:
- CAGR de una serie que se duplica en exactamente 1 año (12 meses) = 100%.
- Volatilidad de una serie con rendimiento constante = 0.
- Drawdown de `[100, 120, 60, 90]` → máximo drawdown = −50%; recuperación = `None`.
- Beta de un activo cuyos rendimientos son exactamente 2× los del benchmark = 2.0; correlación = 1.
- Sharpe con rendimiento igual a la tasa libre de riesgo ≈ 0.
- SMA de `[1, 2, 3, 4]` con ventana 2 = `[NaN, 1.5, 2.5, 3.5]`.
- **Backtest sin leakage:** construye una serie donde un salto en t solo sería capturado si la señal usara el cierre de t; verifica que la regla **no** lo captura.
- `resamplear_ohlc`: open = primer valor del mes, close = último, high/low correctos.

## 12. README.md

Secciones, en este orden:
1. Título y una línea de descripción + espacio para la liga de la app publicada y una captura (`docs/captura.png`, opcional).
2. **Aviso educativo** y **Código generado con IA** (textos de la sección 3, destacados).
3. Qué muestra el dashboard: las 6 métricas en una tabla (métrica, pregunta que responde, fórmula, interpretación, columna en el CSV).
4. Instalación local (venv, `pip install -r requirements.txt`, `streamlit run app.py`).
5. **Cómo agregar un ticker:** ejemplo concreto editando `TICKERS` en `config.py` (por ejemplo `"MSFT"` con benchmark `"^GSPC"`), cómo verificar que yfinance lo encuentra y cómo regenerar el respaldo.
6. **Cómo agregar una nueva métrica o variable:** ejemplo completo paso a paso con el **Sortino ratio**: función en `metricas.py` con docstring, prueba en `tests/`, inclusión en `resumen_metricas` y en `tabla_tidy_para_bi`, y KPI en `app.py`. Incluye el código del ejemplo.
7. **Cómo cambiar parámetros:** fechas, periodicidad, ventana SMA, tasa libre de riesgo, estilo de velas.
8. **Respaldo CSV:** por qué existe (Yahoo Finance a veces falla o limita las descargas desde la nube), cómo funciona el aviso en la app, cuándo y cómo actualizarlo (`python actualizar_respaldo.py` y hacer commit), y que los datos del respaldo tienen la fecha de su última actualización.
9. **Usar los datos en Looker Studio, Power BI o Tableau:** exportar desde la pestaña «Datos» y qué conviene precalcular en Python.
10. **Publicar en Streamlit Community Cloud** paso a paso (repo público en GitHub → share.streamlit.io → New app → `app.py`).
11. Estructura del repo.
12. Limitaciones: moneda local sin tipo de cambio, sesgo de supervivencia, sin costos ni impuestos, datos de Yahoo Finance, tasa libre de riesgo como supuesto.
13. Licencia MIT y créditos (datos: Yahoo Finance vía `yfinance`, uso educativo).

## 13. Plan de trabajo

Trabaja por etapas y verifica cada una antes de seguir:

1. **Esqueleto desplegable:** estructura, `config.py`, `datos.py` con descarga y respaldo, `app.py` mínima con la pestaña «Velas». Corre `actualizar_respaldo.py` para crear el CSV. Confirma que `streamlit run app.py` funciona. (Indícale al autor que conviene publicar esta versión mínima en Streamlit Cloud desde ya para detectar problemas de despliegue temprano.)
2. **Métricas + pruebas:** `metricas.py` completo y `tests/test_metricas.py`; `pytest` en verde.
3. **Pestañas y KPIs** completos.
4. **Modo claro/oscuro** y pulido visual en ambos modos.
5. **README** completo y `.gitignore`.
6. **Verificación final:**
   - `pytest` pasa.
   - La app corre sin errores en ambos modos y en Mensual y Anual.
   - Simula la falla de Yahoo (por ejemplo, con una variable de entorno `FORZAR_RESPALDO=1` que también debe documentarse) y confirma que aparece el aviso y la app funciona.
   - Contrasta a mano un número: el CAGR de AAPL desde 2015 calculado con los precios del CSV, contra el que muestra la app.
   - Revisa que no exista texto de recomendación de inversión.
7. Al terminar, entrega un **resumen**: qué se construyó, tickers que tuvieron problemas y cómo se resolvieron, resultados de las pruebas y los pasos que faltan para publicar.

## 14. Criterios de aceptación

- [ ] Las 7 pestañas con los nombres exactos y su "¿Qué estoy viendo?".
- [ ] KPIs correctos y consistentes con `metricas.py`.
- [ ] Modo claro y oscuro con botón, paleta UP, sin logo, gráficas legibles en ambos.
- [ ] Respaldo CSV funcionando, con aviso visible y fecha.
- [ ] Docstrings en español en todas las funciones públicas.
- [ ] `pytest` en verde, incluida la prueba de no-leakage del backtest.
- [ ] README con disclaimers, nota de código generado con IA, ejemplos para agregar tickers y métricas, y nota del respaldo.
- [ ] `requirements.txt` con versiones fijas; `BITACORA_AGENTE.md` existe y está en `.gitignore`.
- [ ] Ningún texto recomienda comprar o vender.
