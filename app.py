"""Dashboard «Acciones 101» en Streamlit (solo presentación). Código generado con un agente de IA (Claude Code) con fines educativos.

Ejecuta con:

    streamlit run app.py

Este archivo solo arma la interfaz y las gráficas. Las fórmulas viven en
``metricas.py`` y la descarga de datos en ``datos.py``.

Cómo está organizado:

1. Textos fijos y utilidades de formato.
1b. Modo claro / oscuro: template de Plotly, CSS inyectado y tablas HTML.
2. Carga y preparación de datos (con caché) y el ``Contexto`` compartido.
3. Funciones que dibujan cada gráfica (``figura_*``).
4. Barra lateral, encabezado con KPIs y una función por pestaña (``pestana_*``).
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots
from streamlit.delta_generator import DeltaGenerator

import config
import datos
import metricas

# ---------------------------------------------------------------------------
# 1. Textos fijos y utilidades
# ---------------------------------------------------------------------------
AVISO_CORTO = (
    "⚠️ Material **educativo**: análisis histórico, no recomendación de inversión. "
    "Rendimientos pasados no garantizan rendimientos futuros."
)
AVISO_PIE = (
    "**Aviso:** proyecto exclusivamente educativo. No constituye recomendación de "
    "inversión, asesoría financiera ni oferta de compra o venta de valores. "
    "Rendimientos pasados no garantizan rendimientos futuros. Datos de Yahoo Finance "
    "vía `yfinance`; pueden contener errores o retrasos.\n\n"
    "**Código generado con IA** (Claude Code, de Anthropic) y revisado por el autor."
)
NOTA_BACKTEST = (
    "Se decide con el cierre del periodo anterior; sin comisiones ni impuestos; "
    "rendimientos pasados no garantizan futuros."
)
NOTA_TASA_CONSTANTE = (
    "Cada tasa se usa **constante** para todo el periodo (el dato más reciente de su fuente). "
    "En la realidad cambiaron mucho desde 2015: es una simplificación y el Sharpe ratio es aproximado."
)
NOTA_MONEDA_LOCAL = (
    "Todo se calcula en la **moneda local** de cada activo (MXN, USD o KRW); no se convierte "
    "tipo de cambio. Cada acción se compara solo contra el benchmark de su mercado."
)
MOTIVO_POCOS_DATOS = f"se necesitan al menos {metricas.MINIMO_ANIOS:.0f} años de datos"
TICKER_EJEMPLO = "NVDA"  # acción del ejemplo de "pocas observaciones" en los expanders

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
TIPOS_LINEA = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]

st.set_page_config(page_title="Acciones 101", layout="wide")

# Modo actual ("claro" u "oscuro"). Vive en st.session_state para que sobreviva a
# cada interacción; el botón de la barra lateral lo cambia (ver ``cambiar_modo``).
if "modo" not in st.session_state:
    st.session_state.modo = config.MODO_DEFAULT
MODO: str = st.session_state.modo


def info_ticker(ticker: str) -> dict[str, str]:
    """Regresa nombre y moneda de una acción o benchmark definidos en config.py."""
    return config.TICKERS.get(ticker) or config.BENCHMARKS[ticker]


def etiqueta(ticker: str) -> str:
    """Texto para mostrar un ticker, por ejemplo ``"NVDA · NVIDIA"``."""
    return f"{ticker} · {info_ticker(ticker)['nombre']}"


def es_benchmark(ticker: str) -> bool:
    """``True`` si el ticker es un índice de referencia."""
    return ticker in config.BENCHMARKS


def etiqueta_con_tipo(ticker: str) -> str:
    """Como ``etiqueta`` pero indica si es benchmark."""
    return f"{etiqueta(ticker)} (benchmark)" if es_benchmark(ticker) else etiqueta(ticker)


def mercado_de(ticker: str) -> str:
    """Mercado de una acción o de un benchmark (el de las acciones que lo usan)."""
    if ticker in config.TICKERS:
        return config.TICKERS[ticker]["mercado"]
    return next(v["mercado"] for v in config.TICKERS.values() if v["benchmark"] == ticker)


def benchmark_de(ticker: str) -> str | None:
    """Benchmark de una acción, o ``None`` si el ticker ya es un benchmark."""
    return config.TICKERS.get(ticker, {}).get("benchmark")


def moneda_de(ticker: str) -> str:
    """Moneda local del ticker."""
    return info_ticker(ticker)["moneda"]


def es_nan(valor: object) -> bool:
    """``True`` si el valor falta (``None`` o ``NaN``)."""
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def _sin_cero_negativo(texto: str) -> str:
    """Quita el signo de ``"-0.00"`` o ``"-0.0%"``: un valor que redondea a cero no es negativo."""
    if texto.startswith("-") and float(texto.rstrip("%")) == 0:
        return texto[1:]
    return texto


def pct(valor: float, decimales: int = 1) -> str:
    """Formatea un decimal como porcentaje; ``n/d`` si falta."""
    return "n/d" if es_nan(valor) else _sin_cero_negativo(f"{valor:.{decimales}%}")


def num(valor: float, decimales: int = 2) -> str:
    """Formatea un número; ``n/d`` si falta."""
    return "n/d" if es_nan(valor) else _sin_cero_negativo(f"{valor:.{decimales}f}")


def periodos_texto(n: int, periodicidad: str) -> str:
    """``"1 mes"``, ``"5 meses"``, ``"1 año"``…"""
    p = config.PERIODICIDADES[periodicidad]
    return f"{n} {p['unidad_singular'] if n == 1 else p['unidad']}"


def rgba(hex_color: str, alfa: float) -> str:
    """Convierte ``#RRGGBB`` a ``rgba(r, g, b, alfa)`` para rellenos translúcidos."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alfa})"


def plural(n: int, singular: str, plural_: str) -> str:
    """Escribe una cantidad con el sustantivo en singular o plural.

    Args:
        n: Cantidad.
        singular: Palabra para ``n == 1`` (``"rendimiento"``).
        plural_: Palabra para cualquier otro número (``"rendimientos"``).

    Returns:
        Texto como ``"1 rendimiento"`` o ``"5 rendimientos"``.
    """
    return f"{n} {singular if n == 1 else plural_}"


def titulo_eje(texto: str, escala_log: bool) -> str:
    """Agrega «escala logarítmica» al título del eje cuando aplica, para que nadie la lea como lineal."""
    return f"{texto} · escala logarítmica" if escala_log else texto


# ---------------------------------------------------------------------------
# 1b. Modo claro / oscuro
# ---------------------------------------------------------------------------
def plantilla_plotly(modo: str) -> go.layout.Template:
    """Template de Plotly con la paleta UP del modo elegido.

    Parte de ``plotly_white`` (claro) o ``plotly_dark`` (oscuro) y reemplaza
    fondo, rejilla, textos, leyenda y globos de ayuda con los colores de
    ``config.PALETA``. Todas las gráficas lo usan (ver ``estilo_base``), así
    que cambian juntas al cambiar de modo.

    Args:
        modo: ``"claro"`` u ``"oscuro"``.

    Returns:
        Template listo para ``fig.update_layout(template=...)``.
    """
    c = config.PALETA[modo]
    plantilla = go.layout.Template(pio.templates["plotly_white" if modo == "claro" else "plotly_dark"])
    ejes = dict(gridcolor=c["rejilla"], linecolor=c["rejilla"], zerolinecolor=c["rejilla"], zeroline=False,
                automargin=True,  # deja espacio para las etiquetas de los ejes
                tickfont=dict(color=c["texto_secundario"]), title=dict(font=dict(color=c["texto_secundario"])))
    plantilla.layout.update(
        paper_bgcolor=c["fondo"], plot_bgcolor=c["fondo"],
        font=dict(color=c["texto"], size=13),
        colorway=[c["primario"], c["benchmark"], c["texto_secundario"]],  # sin rojo: solo con significado
        xaxis=ejes, yaxis=ejes,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=c["texto"])),
        hoverlabel=dict(bgcolor=c["superficie"], bordercolor=c["rejilla"], font=dict(color=c["texto"])),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=c["texto_secundario"], activecolor=c["texto_acento"]),
    )
    return plantilla


PLANTILLAS: dict[str, go.layout.Template] = {modo: plantilla_plotly(modo) for modo in config.PALETA}


def css_tema(c: dict[str, str]) -> str:
    """CSS que pinta la interfaz de Streamlit con la paleta del modo elegido.

    Streamlit no permite cambiar su tema desde Python en cada sesión, así que
    el modo oscuro se logra inyectando CSS que sobrescribe fondos, superficies,
    texto y controles. Los selectores usan los atributos ``data-testid`` de
    Streamlit 1.67 (pueden cambiar en otras versiones). Los colores van en
    variables CSS (``--a101-*``) para que cada regla sirva en ambos modos.

    Args:
        c: Paleta del modo (``config.PALETA["claro"]`` o ``["oscuro"]``).

    Returns:
        Bloque ``<style>`` para ``st.markdown(..., unsafe_allow_html=True)``.
    """
    variables = "\n".join(f"  --a101-{k.replace('_', '-')}: {v};" for k, v in c.items())
    return f"""<style id="a101-tema">
:root {{
{variables}
  --a101-sobre-dorado: #1A1A1A;  /* texto sobre fondo dorado: 7.78:1 */
}}
/* El contenedor de este bloque no ocupa espacio en la página. */
[data-testid="stElementContainer"]:has(#a101-tema) {{ display: none; }}

/* 1. Fondo, superficies y texto */
body, .stApp, [data-testid="stHeader"] {{ background-color: var(--a101-fondo); color: var(--a101-texto); }}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {{ background-color: var(--a101-superficie); }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp li,
.stApp label, .stApp summary, .stApp .katex {{ color: var(--a101-texto); }}
/* Streamlit aclara los captions con opacidad 0.6; eso bajaba el gris secundario a menos de 4.5:1. */
[data-testid="stCaptionContainer"] {{ opacity: 1; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--a101-texto-secundario); }}
.stApp a {{ color: var(--a101-texto-acento); text-decoration: underline; text-decoration-color: var(--a101-primario); }}
.stApp code {{ background-color: var(--a101-rejilla); color: var(--a101-texto); }}
.stApp hr {{ border-color: var(--a101-rejilla); background-color: var(--a101-rejilla); }}
[data-testid="stHeader"] button, [data-testid="stHeader"] span,
[data-testid="stSidebarCollapseButton"] span {{ color: var(--a101-texto-secundario); }}
/* Íconos de ayuda (?), flechas de las listas y botón del calendario */
.stApp [data-testid="stTooltipIcon"] .stTooltipHoverTarget svg.icon {{ stroke: var(--a101-texto-secundario); }}
[data-testid="stTooltipContent"] {{ background-color: var(--a101-superficie); border: 1px solid var(--a101-rejilla); }}
[data-testid="stTooltipContent"] p {{ color: var(--a101-texto); }}
[data-testid="stSelectbox"] button, [data-testid="stMultiSelect"] button,
[data-testid="stDateInputCalendarButton"] {{ color: var(--a101-texto-secundario); }}
[data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg {{ fill: currentColor; }}

/* 2. Pestañas: la activa en negritas, con subrayado dorado y texto con acento */
[data-testid="stTab"] p {{ color: var(--a101-texto-secundario); }}
[data-testid="stTab"]:hover p {{ color: var(--a101-texto); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--a101-texto-acento); font-weight: 600; }}
[data-testid="stTabs"] [role="tablist"]::after {{ background-color: var(--a101-rejilla); }}

/* 3. Controles */
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
[data-testid="stDateInputField"], [data-testid="stNumberInputContainer"],
[data-testid="stNumberInputField"], [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{
  background-color: var(--a101-fondo); border-color: var(--a101-rejilla); color: var(--a101-texto); }}
.stApp input, .stApp [role="spinbutton"], [data-testid="stDateInputField"] span {{ color: var(--a101-texto); }}
.stApp [data-testid="stDateInputField"] span[data-type="literal"] {{ color: var(--a101-texto-secundario); }}
[data-testid="stMultiSelect"] [data-tag], [data-testid="stMultiSelect"] [data-tag] * {{
  background-color: var(--a101-primario); color: var(--a101-sobre-dorado); }}
[data-testid="stSliderThumbValue"] p {{ color: var(--a101-texto); font-weight: 600; }}
[data-testid="stSliderTickBar"] p {{ color: var(--a101-texto-secundario); }}
/* Radio sin elegir: círculo vacío con borde gris (el de Streamlit se pierde en modo oscuro) */
[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child {{
  background-color: var(--a101-fondo); border-color: var(--a101-texto-secundario); }}
/* Interruptor apagado: carril gris visible en ambos modos */
[data-testid="stCheckbox"] label:has(input[role="switch"]:not(:checked)) > div:nth-child(2) {{
  background-color: color-mix(in srgb, var(--a101-texto-secundario) 60%, transparent); }}

/* 3b. Menús emergentes (listas y calendario): se dibujan fuera de .stApp */
div:has(> [role="listbox"]), [data-testid="stDateInputCalendar"] {{
  background-color: var(--a101-superficie); color: var(--a101-texto); border: 1px solid var(--a101-rejilla); }}
[role="listbox"] [role="option"] {{ color: var(--a101-texto); }}
[role="listbox"] [role="option"][data-focused="true"], [role="listbox"] [role="option"][data-selected="true"] {{
  background-color: var(--a101-rejilla); }}
[data-testid="stDateInputCalendar"] th, [data-testid="stDateInputCalendar"] button,
[data-testid="stDateInputCalendar"] [role="gridcell"] > div {{ color: var(--a101-texto); }}
[data-testid="stDateInputCalendar"] [role="gridcell"] > div[data-disabled="true"],
[data-testid="stDateInputCalendar"] button[data-disabled="true"] {{ color: var(--a101-texto-secundario); opacity: 0.6; }}
[data-testid="stDateInputCalendar"] [role="gridcell"] > div[data-selection-start="true"],
[data-testid="stDateInputCalendar"] [role="gridcell"] > div[data-selection-end="true"] {{ color: var(--a101-sobre-dorado); }}

/* 4. Botones: el principal es dorado con texto oscuro (el blanco sobre dorado da 2.24:1) */
[data-testid="stBaseButton-secondary"] {{ background-color: var(--a101-fondo); border-color: var(--a101-rejilla); }}
[data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-secondary"] span {{ color: var(--a101-texto); }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: var(--a101-primario); }}
[data-testid="stBaseButton-secondary"]:hover p, [data-testid="stBaseButton-secondary"]:hover span {{ color: var(--a101-texto-acento); }}
[data-testid="stBaseButton-primary"] {{ background-color: var(--a101-primario); border-color: var(--a101-primario); }}
[data-testid="stBaseButton-primary"]:hover {{ background-color: var(--a101-dorado-fuerte); border-color: var(--a101-dorado-fuerte); }}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primary"] span {{ color: var(--a101-sobre-dorado); }}

/* 5. Tarjetas (KPIs), expanders y avisos */
[data-testid="stMetric"] {{ background-color: var(--a101-superficie); border-color: var(--a101-rejilla); }}
[data-testid="stMetricLabel"] p {{ color: var(--a101-texto-secundario); }}
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {{ color: var(--a101-texto-secundario); background-color: transparent; }}
[data-testid="stExpander"] details {{ border-color: var(--a101-rejilla); background-color: transparent; }}
[data-testid="stExpander"] summary:hover p, [data-testid="stExpander"] summary:hover span {{ color: var(--a101-texto-acento); }}
[data-testid="stAlertContainer"] {{ background-color: var(--a101-superficie); border-left: 4px solid var(--a101-texto-secundario); }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{ border-left-color: var(--a101-primario); }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ border-left-color: var(--a101-negativo); }}
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li {{ color: var(--a101-texto); }}
[data-testid="stElementToolbar"] {{ background-color: var(--a101-superficie); color: var(--a101-texto-secundario); }}

/* 6. Tablas HTML (ver tabla_html): reglas horizontales finas, números alineados a la derecha */
.a101-tabla {{ overflow: auto; border: 1px solid var(--a101-rejilla); border-radius: 0.5rem; }}
.a101-tabla table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; color: var(--a101-texto);
  font-variant-numeric: tabular-nums; }}
.a101-tabla th {{ position: sticky; top: 0; background-color: var(--a101-superficie); color: var(--a101-texto-secundario);
  font-weight: 600; text-align: left; padding: 0.45rem 0.75rem; border-bottom: 1px solid var(--a101-rejilla); white-space: nowrap; }}
.a101-tabla td {{ padding: 0.35rem 0.75rem; border-bottom: 1px solid var(--a101-rejilla); white-space: nowrap; }}
.a101-tabla tr:last-child td {{ border-bottom: none; }}
.a101-tabla tbody tr:hover td {{ background-color: var(--a101-superficie); }}
.a101-tabla .num {{ text-align: right; }}
</style>"""


def cambiar_modo() -> None:
    """Callback del botón: alterna entre modo claro y oscuro."""
    st.session_state.modo = "oscuro" if st.session_state.modo == "claro" else "claro"


# Texto que parece número: "68.0%", "-0.04", "1,234", "USD 4.03%".
_PATRON_NUMERO = re.compile(r"^([A-Z]{3} )?[-−+]?[\d,]*\.?\d+%?$")


def tabla_html(tabla: pd.DataFrame, alto_max: int | None = None) -> str:
    """Convierte una tabla de textos ya formateados en HTML que respeta el modo claro/oscuro.

    Se usa en lugar de ``st.dataframe`` porque la tabla interactiva de
    Streamlit se dibuja en un ``<canvas>`` al que el CSS del modo oscuro no
    llega. Las columnas cuyo contenido es numérico (o ``n/d``) se alinean a la
    derecha para comparar cifras de un vistazo.

    Args:
        tabla: DataFrame cuyas celdas ya son texto (``"68.0%"``, ``"1.31"``…).
        alto_max: Alto máximo en píxeles; si la tabla es más alta, se desplaza.

    Returns:
        HTML para ``st.html``.
    """
    numericas = {
        col for col in tabla.columns
        if tabla[col].astype(str).map(lambda v: v == "n/d" or bool(_PATRON_NUMERO.match(v))).all()
    }
    def celda(etiqueta_html: str, col: str, contenido: object) -> str:
        clase = ' class="num"' if col in numericas else ""
        return f"<{etiqueta_html}{clase}>{html.escape(str(contenido))}</{etiqueta_html}>"

    encabezado = "".join(celda("th", col, col) for col in tabla.columns)
    filas = "".join(
        "<tr>" + "".join(celda("td", col, v) for col, v in fila.items()) + "</tr>"
        for _, fila in tabla.iterrows()
    )
    estilo = f' style="max-height: {alto_max}px"' if alto_max else ""
    return f'<div class="a101-tabla"{estilo}><table><thead><tr>{encabezado}</tr></thead><tbody>{filas}</tbody></table></div>'


# ---------------------------------------------------------------------------
# 2. Datos
# ---------------------------------------------------------------------------
@st.cache_data(ttl=config.TTL_CACHE_SEGUNDOS, show_spinner="Descargando precios de Yahoo Finance…")
def cargar_precios(hoy: str) -> tuple[pd.DataFrame, dict]:
    """Obtiene precios diarios de todas las acciones y benchmarks (con caché de 6 h).

    Args:
        hoy: Fecha de hoy en texto; forma parte de la llave de la caché.

    Returns:
        Tupla ``(precios, metadatos)`` de ``datos.obtener_precios``.
    """
    tickers = list(config.TICKERS) + list(config.BENCHMARKS)
    return datos.obtener_precios(tickers, config.FECHA_INICIO, hoy)


@st.cache_data(ttl=config.TTL_CACHE_SEGUNDOS, show_spinner=False)
def preparar_velas(hoy: str, inicio: date, fin: date, periodicidad: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filtra el rango de fechas y pasa todos los tickers a la periodicidad elegida.

    Args:
        hoy: Fecha de hoy en texto (llave de la caché).
        inicio: Primer día del rango elegido en la barra lateral.
        fin: Último día del rango.
        periodicidad: ``"Mensual"`` o ``"Anual"``.

    Returns:
        Tupla ``(diario, velas)``: precios diarios del rango y velas
        (incluido el periodo incompleto, marcado en la columna ``completo``).
    """
    precios, _ = cargar_precios(hoy)
    diario = datos.filtrar_precios(precios, None, inicio, fin)
    return diario, datos.resamplear_ohlc(diario, periodicidad)


@st.cache_data(ttl=config.TTL_CACHE_SEGUNDOS, show_spinner=False)
def construir_tidy(hoy: str, inicio: date, fin: date, periodicidad: str, ventana: int,
                   tasas: tuple[tuple[str, float], ...]) -> pd.DataFrame:
    """Tabla larga para BI de todos los tickers (ver ``metricas.tabla_tidy_para_bi``).

    Args:
        hoy: Fecha de hoy en texto (llave de la caché).
        inicio: Primer día del rango.
        fin: Último día del rango.
        periodicidad: ``"Mensual"`` o ``"Anual"``.
        ventana: Ventana de la SMA en periodos.
        tasas: Pares ``(moneda, tasa anual)`` ordenados, para que la llave de
            la caché sea siempre la misma.

    Returns:
        DataFrame con columnas ``fecha, ticker, metrica, valor``.
    """
    _, velas = preparar_velas(hoy, inicio, fin, periodicidad)
    tasas_moneda = dict(tasas)
    todos = list(config.TICKERS) + list(config.BENCHMARKS)
    return metricas.tabla_tidy_para_bi(
        datos.velas_completas(velas),
        config.PERIODICIDADES[periodicidad]["periodos_por_anio"],
        {t: tasas_moneda[moneda_de(t)] for t in todos},
        {t: v["benchmark"] for t, v in config.TICKERS.items()},
        ventana,
        config.CAPITAL_INICIAL,
    )


@st.cache_data(ttl=config.TTL_CACHE_SEGUNDOS, show_spinner=False)
def ejemplo_pocas_observaciones(hoy: str, ticker: str) -> dict[str, dict]:
    """Volatilidad y beta de un ticker con todo el periodo, en Mensual y en Anual.

    Alimenta el ejemplo de "pocas observaciones" de los expanders: la misma
    acción y los mismos precios, pero con 12 veces menos rendimientos. Las
    cifras se calculan aquí (no están escritas a mano), así que se actualizan
    con los datos.

    Args:
        hoy: Fecha de hoy en texto (llave de la caché).
        ticker: Acción del ejemplo (``TICKER_EJEMPLO``).

    Returns:
        ``{"Mensual": {...}, "Anual": {...}}``; cada uno con ``n``,
        ``volatilidad``, ``beta``, ``mejor_fecha`` y ``mejor_rend`` (el
        rendimiento más alto del periodo y su fecha).
    """
    inicio, fin = date.fromisoformat(config.FECHA_INICIO), date.fromisoformat(hoy)
    salida: dict[str, dict] = {}
    for periodicidad, p in config.PERIODICIDADES.items():
        _, velas = preparar_velas(hoy, inicio, fin, periodicidad)
        completas = datos.velas_completas(velas)
        cierres = datos.serie(completas, ticker)
        r = metricas.resumen_metricas(cierres, int(p["periodos_por_anio"]),
                                      float(config.TASAS_LIBRE_RIESGO[moneda_de(ticker)]["tasa"]),
                                      datos.serie(completas, benchmark_de(ticker)))
        rend = metricas.rendimientos(cierres)
        salida[periodicidad] = {"n": r["n_periodos"], "volatilidad": r["volatilidad"], "beta": r["beta"],
                                "mejor_fecha": rend.idxmax() if not rend.empty else None,
                                "mejor_rend": float(rend.max()) if not rend.empty else math.nan}
    return salida


def texto_pocas_observaciones(hoy: date, metrica: str) -> str:
    """Párrafo del expander que explica por qué pocas observaciones dan estimaciones inestables.

    Args:
        hoy: Fecha de hoy.
        metrica: ``"volatilidad"`` o ``"beta"``.

    Returns:
        Texto en Markdown con el ejemplo de ``TICKER_EJEMPLO`` (vacío si ese
        ticker ya no está en ``config.TICKERS``).
    """
    if TICKER_EJEMPLO not in config.TICKERS:
        return ""
    ej = ejemplo_pocas_observaciones(hoy.isoformat(), TICKER_EJEMPLO)
    m, a = ej["Mensual"], ej["Anual"]
    if metrica == "beta":
        cifras = (f"la beta de {TICKER_EJEMPLO} contra {benchmark_de(TICKER_EJEMPLO)} sale **{num(m['beta'])}** "
                  f"con {m['n']} rendimientos mensuales y **{num(a['beta'])}** con solo {a['n']} anuales")
    else:
        cifras = (f"la volatilidad anualizada de {TICKER_EJEMPLO} sale **{pct(m['volatilidad'])}** con "
                  f"{m['n']} rendimientos mensuales y **{pct(a['volatilidad'])}** con solo {a['n']} anuales")
    extremo = (f" Un solo año extremo ({a['mejor_fecha']:%Y}: {a['mejor_rend']:+.0%}) pesa muchísimo en el cálculo."
               if a["mejor_fecha"] is not None else "")
    return (
        f"**Cuidado con pocas observaciones.** Cada métrica es una *estimación* hecha con N rendimientos. "
        f"Con los mismos precios, de {config.FECHA_INICIO[:4]} a hoy, {cifras}.{extremo} Por eso, con menos "
        f"de {config.MINIMO_OBSERVACIONES} rendimientos, los KPIs avisan «pocas observaciones: estimación "
        "inestable»."
    )


@dataclass
class Contexto:
    """Datos y parámetros que comparten todas las pestañas (se arma una vez por ejecución)."""

    diario: pd.DataFrame
    velas: pd.DataFrame
    completas: pd.DataFrame
    periodicidad: str
    periodos_por_anio: int
    ventana: int
    tasas: dict[str, float]
    colores: dict[str, str]
    hoy: date
    inicio: date
    fin: date
    _resumenes: dict[str, dict] = field(default_factory=dict)

    @property
    def unidad(self) -> str:
        """``"meses"`` o ``"años"``."""
        return config.PERIODICIDADES[self.periodicidad]["unidad"]

    def cierres(self, ticker: str) -> pd.Series:
        """Cierres por periodo (solo periodos completos) de un ticker."""
        return datos.serie(self.completas, ticker)

    def tasa(self, ticker: str) -> float:
        """Tasa libre de riesgo anual de la moneda del ticker."""
        return self.tasas[moneda_de(ticker)]

    def resumen(self, ticker: str) -> dict:
        """``metricas.resumen_metricas`` del ticker contra su benchmark (se guarda en memoria)."""
        if ticker not in self._resumenes:
            bench = benchmark_de(ticker)
            self._resumenes[ticker] = metricas.resumen_metricas(
                self.cierres(ticker), self.periodos_por_anio, self.tasa(ticker),
                self.cierres(bench) if bench else None,
            )
        return self._resumenes[ticker]


def motivo_nan(resumen: dict, metrica: str) -> str:
    """Explica en pocas palabras por qué una métrica quedó en ``NaN``."""
    if resumen["anios"] < metricas.MINIMO_ANIOS:
        return MOTIVO_POCOS_DATOS
    if metrica in {"beta", "correlacion"}:
        return "pocos periodos en común con el benchmark"
    if metrica == "sharpe":
        return "la volatilidad es cero"
    return "no se pudo calcular con estos datos"


def mostrar_avisos_datos(ctx: Contexto, tickers: list[str], extra: str = "", compacto: bool = False) -> None:
    """Muestra el aviso de calidad de datos (``config.AVISOS_DATOS``) de los tickers que lo tengan.

    La versión completa va en el encabezado; en las pestañas se usa la compacta,
    que también dice qué pasa y cuál es el efecto. Si en el rango elegido el
    ticker no tiene días sin volumen, el aviso no aparece.

    Args:
        ctx: Contexto con los precios diarios del rango.
        tickers: Tickers a revisar.
        extra: Texto que se agrega al final del aviso (por ejemplo, qué
            significa en la gráfica de la pestaña).
        compacto: ``True`` para la versión corta de las pestañas.
    """
    for t in tickers:
        if t not in config.AVISOS_DATOS:
            continue
        sin_volumen, dias = datos.dias_sin_volumen(ctx.diario, t)
        if sin_volumen == 0:
            continue  # en el rango elegido no hay días sin volumen: el problema no aplica
        proporcion = f" ({sin_volumen / dias:.0%})" if dias else ""
        conteo = f"En el rango elegido, {sin_volumen:,} de {dias:,} días{proporcion} no tienen volumen."
        if compacto:
            texto = (f"**Calidad de datos de {t}:** {conteo} En esos días Yahoo Finance repite el precio "
                     "anterior, lo que **baja artificialmente su volatilidad**.")
        else:
            texto = f"**Calidad de datos de {t}.** {config.AVISOS_DATOS[t]} {conteo}"
        st.warning(f"{texto} {extra}".strip(), icon="⚠️")


# ---------------------------------------------------------------------------
# 3. Gráficas
# ---------------------------------------------------------------------------
def colores_velas(colores: dict[str, str]) -> dict[str, str]:
    """Colores de velas alcistas y bajistas según ``config.VELAS_ESTILO``.

    En modo claro la vela dorada lleva borde en dorado fuerte para que se
    distinga del fondo blanco (el dorado primario tiene poco contraste).
    """
    if config.VELAS_ESTILO == "clasico":
        verde = config.VERDE_CLASICO[MODO]
        return {"sube_relleno": verde, "sube_borde": verde,
                "baja_relleno": colores["negativo"], "baja_borde": colores["negativo"]}
    return {"sube_relleno": colores["primario"], "sube_borde": colores["dorado_fuerte"],
            "baja_relleno": colores["negativo"], "baja_borde": colores["negativo"]}


def estilo_base(fig: go.Figure, alto: int = 520) -> go.Figure:
    """Aplica el template del modo actual y un estilo sobrio (sin chartjunk) a una figura.

    Los colores vienen del template (``PLANTILLAS``); aquí solo se fijan el
    alto, los márgenes, la leyenda horizontal arriba y el modo de hover.
    """
    fig.update_layout(
        template=PLANTILLAS[MODO],
        height=alto,
        margin=dict(l=80, r=20, t=40, b=50),  # espacio para las etiquetas de los ejes
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        hovermode="x unified",
    )
    return fig


def figura_velas(
    velas: pd.DataFrame,
    en_curso: pd.DataFrame,
    linea_sma: pd.Series,
    ventana: int,
    moneda: str,
    periodicidad: str,
    escala_log: bool,
    colores: dict[str, str],
    etiqueta_en_curso: str = "periodo en curso",
) -> go.Figure:
    """Gráfica de velas OHLC con la línea de la SMA (sin rangeslider).

    Las velas completas van en un trazo y el periodo incompleto en otro,
    translúcido y con una etiqueta de texto, para que no se confundan.

    Args:
        velas: Velas de periodos completos de un ticker.
        en_curso: Vela del periodo incompleto (puede venir vacía).
        linea_sma: SMA calculada solo con periodos completos.
        ventana: Ventana de la SMA, para la leyenda.
        moneda: Moneda del ticker, para el eje.
        periodicidad: ``"Mensual"`` o ``"Anual"`` (formato de fecha del hover).
        escala_log: ``True`` para el eje vertical en escala logarítmica.
        colores: Paleta del modo actual.
        etiqueta_en_curso: Texto junto a la vela incompleta.

    Returns:
        Figura de Plotly.
    """
    c = colores_velas(colores)
    formato_fecha = "%Y-%m" if periodicidad == "Mensual" else "%Y"
    estilo = dict(
        increasing=dict(fillcolor=c["sube_relleno"], line=dict(color=c["sube_borde"], width=1)),
        decreasing=dict(fillcolor=c["baja_relleno"], line=dict(color=c["baja_borde"], width=1)),
    )
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=velas["fecha"], open=velas["open"], high=velas["high"],
        low=velas["low"], close=velas["close"], name="Velas OHLC", **estilo,
    ))
    if not en_curso.empty:
        fila = en_curso.iloc[-1]
        fig.add_trace(go.Candlestick(
            x=en_curso["fecha"], open=en_curso["open"], high=en_curso["high"],
            low=en_curso["low"], close=en_curso["close"],
            name=etiqueta_en_curso.capitalize(), opacity=0.4, **estilo,
        ))
        # Etiqueta DEBAJO de la vela (arriba suele chocar con las mechas previas).
        # En un eje logarítmico, Plotly ubica las anotaciones en log10(y).
        y_texto = math.log10(fila["low"]) if escala_log else fila["low"]
        fig.add_annotation(
            x=fila["fecha"], y=y_texto, text=etiqueta_en_curso, showarrow=True,
            arrowhead=0, arrowcolor=colores["texto_secundario"], ax=0, ay=40,
            xanchor="right", font=dict(color=colores["texto_secundario"], size=12),
            bgcolor=colores["fondo"], borderpad=2,  # fondo para que se lea sobre líneas
        )
    fig.add_trace(go.Scatter(
        x=linea_sma.index, y=linea_sma.values, mode="lines", name=f"SMA {ventana}",
        line=dict(color=colores["texto"], width=2),
        hovertemplate="%{y:,.2f}<extra>SMA " + str(ventana) + "</extra>",
    ))
    estilo_base(fig)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_xaxes(hoverformat=formato_fecha)
    fig.update_yaxes(title_text=titulo_eje(f"Precio ajustado ({moneda})", escala_log), tickformat=",",
                     type="log" if escala_log else "linear")
    return fig


def estilo_linea(ticker: str, principal: str | None, colores: dict[str, str]) -> dict:
    """Estilo de línea por entidad: principal en dorado, benchmarks en azul, el resto en gris.

    El tipo de trazo de cada acción depende de su posición en config.py, así
    que no cambia cuando cambias la selección.

    Args:
        ticker: Ticker de la línea.
        principal: Acción que va en dorado, o ``None``.
        colores: Paleta del modo actual.

    Returns:
        Dict para el argumento ``line`` de ``go.Scatter``.
    """
    if ticker == principal:
        return dict(color=colores["primario"], width=3, dash="solid")
    if es_benchmark(ticker):
        return dict(color=colores["benchmark"], width=2, dash="dash")
    i = list(config.TICKERS).index(ticker)
    return dict(color=colores["texto_secundario"], width=1.8, dash=TIPOS_LINEA[i % len(TIPOS_LINEA)])


def _separar(valores: dict[str, float], separacion: float) -> dict[str, float]:
    """Reacomoda posiciones verticales de etiquetas para que no se encimen."""
    orden = sorted(valores, key=valores.get)
    salida: dict[str, float] = {}
    previo = -math.inf
    for t in orden:
        salida[t] = max(valores[t], previo + separacion)
        previo = salida[t]
    return salida


def figura_crecimiento(
    curvas: dict[str, pd.Series],
    principal: str | None,
    colores: dict[str, str],
    escala_log: bool,
    titulo_y: str,
    alto: int = 500,
) -> go.Figure:
    """Curvas de valor de una inversión, con el valor final escrito al final de cada línea.

    Args:
        curvas: Valor de la inversión por fecha, un elemento por ticker.
        principal: Ticker que se resalta en dorado, o ``None``.
        colores: Paleta del modo actual.
        escala_log: ``True`` para el eje vertical en escala logarítmica.
        titulo_y: Título del eje vertical.
        alto: Alto de la figura en píxeles.

    Returns:
        Figura de Plotly.
    """
    fig = go.Figure()
    for t, s in curvas.items():
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines", name=t, line=estilo_linea(t, principal, colores),
            hovertemplate=f"{t}: %{{y:,.0f}} {moneda_de(t)}<extra></extra>",
        ))
    estilo_base(fig, alto)

    # Rango del eje fijo para poder colocar las etiquetas finales sin choques.
    transformar = math.log10 if escala_log else (lambda v: v)
    todos = pd.concat(list(curvas.values()))
    bajo, alto_y = transformar(float(todos.min())), transformar(float(todos.max()))
    holgura = (alto_y - bajo) * 0.06 or 1.0
    fig.update_yaxes(range=[bajo - holgura, alto_y + holgura], type="log" if escala_log else "linear",
                     title_text=titulo_eje(titulo_y, escala_log), tickformat=",")
    # Rango X fijo a los datos: si no, Plotly lo alarga para que quepan las etiquetas finales.
    fig.update_xaxes(range=[min(s.index[0] for s in curvas.values()), max(s.index[-1] for s in curvas.values())])
    finales = {t: float(s.iloc[-1]) for t, s in curvas.items()}
    posiciones = _separar({t: transformar(v) for t, v in finales.items()}, (alto_y - bajo) * 0.055)
    for t, y in posiciones.items():
        fig.add_annotation(
            x=curvas[t].index[-1], y=y, xanchor="left", xshift=6, showarrow=False,
            text=f"<b>{t}</b> {finales[t]:,.0f} {moneda_de(t)}",
            font=dict(color=colores["texto"], size=12),
        )
    fig.update_layout(margin=dict(r=190))
    return fig


def _posiciones_texto(xs: list[float], ys: list[float]) -> list[str]:
    """Elige dónde va la etiqueta de cada punto (arriba, abajo, derecha o izquierda)
    buscando la posición más alejada de los demás puntos y etiquetas."""
    if not xs:
        return []
    rx = (max(xs) - min(xs)) or 1.0
    ry = (max(ys) - min(ys)) or 1.0
    puntos = [((x - min(xs)) / rx, (y - min(ys)) / ry) for x, y in zip(xs, ys)]
    candidatos = {"top center": (0.0, 0.06), "bottom center": (0.0, -0.06),
                  "middle right": (0.08, 0.0), "middle left": (-0.08, 0.0)}
    colocadas: list[tuple[float, float]] = []
    salida: list[str] = []
    for i, (px, py) in enumerate(puntos):
        otros = [p for j, p in enumerate(puntos) if j != i]

        def holgura(posicion: str) -> float:
            dx, dy = candidatos[posicion]
            cx, cy = px + dx, py + dy
            obstaculos = otros + colocadas
            if not obstaculos:
                return 1.0
            return min(((cx - ox) / 0.08) ** 2 + ((cy - oy) / 0.05) ** 2 for ox, oy in obstaculos)

        mejor = max(candidatos, key=holgura)
        salida.append(mejor)
        colocadas.append((px + candidatos[mejor][0], py + candidatos[mejor][1]))
    return salida


def figura_riesgo(tabla: pd.DataFrame, colores: dict[str, str]) -> go.Figure:
    """Dispersión riesgo (volatilidad) vs rendimiento (CAGR), color por mercado.

    Args:
        tabla: Una fila por ticker con ``ticker``, ``nombre``, ``mercado``,
            ``es_benchmark``, ``volatilidad``, ``cagr``, ``sharpe_txt`` y ``tasa_txt``.
        colores: Paleta del modo actual.

    Returns:
        Figura de Plotly; los benchmarks van con rombo y cada punto lleva su etiqueta.
    """
    colores_mercado = config.COLORES_MERCADO[MODO]
    tabla = tabla.assign(posicion=_posiciones_texto(tabla["volatilidad"].tolist(), tabla["cagr"].tolist()))
    fig = go.Figure()
    for mercado in colores_mercado:
        for bench in (False, True):
            sub = tabla[(tabla["mercado"] == mercado) & (tabla["es_benchmark"] == bench)]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["volatilidad"], y=sub["cagr"], mode="markers+text", text=sub["ticker"],
                textposition=sub["posicion"].tolist(), cliponaxis=False,
                name=f"{mercado} · {'benchmark' if bench else 'acciones'}",
                marker=dict(symbol="diamond" if bench else "circle", size=16 if bench else 12,
                            color=colores_mercado[mercado], line=dict(color=colores["texto"], width=1)),
                textfont=dict(color=colores["texto"], size=12),
                customdata=sub[["nombre", "sharpe_txt", "tasa_txt"]].to_numpy(),
                hovertemplate=("<b>%{text}</b> · %{customdata[0]}<br>CAGR: %{y:.1%}<br>"
                               "Volatilidad: %{x:.1%}<br>Sharpe ratio: %{customdata[1]} "
                               "(tasa %{customdata[2]})<extra></extra>"),
            ))
    estilo_base(fig, alto=540)
    fig.update_layout(hovermode="closest")
    fig.add_hline(y=0, line=dict(color=colores["texto_secundario"], width=1, dash="dot"))
    margen_x = (tabla["volatilidad"].max() - tabla["volatilidad"].min()) * 0.08
    margen_y = (tabla["cagr"].max() - tabla["cagr"].min()) * 0.08
    fig.update_xaxes(title_text="Volatilidad anualizada (riesgo)", tickformat=".0%",
                     range=[max(0, tabla["volatilidad"].min() - margen_x), tabla["volatilidad"].max() + margen_x])
    # Más espacio arriba para que la etiqueta del punto más alto no choque con la leyenda.
    fig.update_yaxes(title_text="CAGR (rendimiento anual compuesto)", tickformat=".0%",
                     range=[min(0, tabla["cagr"].min()) - margen_y, tabla["cagr"].max() + 2 * margen_y])
    return fig


def figura_drawdown(precios: pd.Series, dd: pd.Series, info: dict, moneda: str,
                    colores: dict[str, str], escala_log: bool) -> go.Figure:
    """Dos paneles: precio con su máximo previo (arriba) y área de drawdown (abajo).

    Args:
        precios: Cierres por periodo (solo periodos completos).
        dd: Serie de drawdown (``metricas.serie_drawdown``).
        info: Resultado de ``metricas.max_drawdown`` (valor y fechas).
        moneda: Moneda del ticker, para el eje.
        colores: Paleta del modo actual.
        escala_log: ``True`` para el panel de precio en escala logarítmica.

    Returns:
        Figura de Plotly con el máximo drawdown anotado.
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07, row_heights=[0.55, 0.45])
    fig.add_trace(go.Scatter(x=precios.index, y=precios.values, mode="lines", name="Precio ajustado",
                             line=dict(color=colores["dorado_fuerte"], width=2),
                             hovertemplate="%{y:,.2f}<extra>Precio</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=precios.index, y=precios.cummax().values, mode="lines", name="Máximo previo",
                             line=dict(color=colores["texto_secundario"], width=1.5, dash="dot"),
                             hovertemplate="%{y:,.2f}<extra>Máximo previo</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.index, y=dd.values, mode="lines", name="Drawdown", fill="tozeroy",
                             line=dict(color=colores["negativo"], width=1.5),
                             fillcolor=rgba(colores["negativo"], 0.18),
                             hovertemplate="%{y:.1%}<extra>Drawdown</extra>"), row=2, col=1)
    if info["fecha_valle"] is not None and info["max_drawdown"] < 0:
        pico, valle = info["fecha_pico"], info["fecha_valle"]
        fig.add_trace(go.Scatter(x=[pico, valle], y=[precios[pico], precios[valle]], mode="markers",
                                 name="Pico y valle", marker=dict(size=10, color=[colores["primario"], colores["negativo"]],
                                                                  line=dict(color=colores["texto"], width=1)),
                                 hoverinfo="skip"), row=1, col=1)
        # Si el valle está en el tercio derecho, la etiqueta va a su izquierda para no salirse.
        a_la_izquierda = (valle - precios.index[0]) > (precios.index[-1] - precios.index[0]) * 0.65
        fig.add_annotation(x=valle, y=info["max_drawdown"], row=2, col=1, showarrow=True, arrowhead=0,
                           ax=-50 if a_la_izquierda else 50, ay=12,
                           xanchor="right" if a_la_izquierda else "left", bgcolor=colores["fondo"],
                           arrowcolor=colores["texto_secundario"],
                           text=f"<b>Máx. drawdown {info['max_drawdown']:.1%}</b><br>valle: {valle:%Y-%m}",
                           font=dict(color=colores["texto"], size=12))
    estilo_base(fig, alto=640)
    # Rango X fijo a los datos: si no, Plotly lo alarga para que quepa la anotación.
    fig.update_xaxes(range=[precios.index[0], precios.index[-1]])
    fig.update_yaxes(title_text=titulo_eje(f"Precio ({moneda})", escala_log), tickformat=",", row=1, col=1,
                     type="log" if escala_log else "linear")
    fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
    return fig


def figura_dispersion_beta(rend_a: pd.Series, rend_m: pd.Series, recta: dict, beta_valor: float,
                           ticker: str, bench: str, colores: dict[str, str]) -> go.Figure:
    """Dispersión de rendimientos del activo vs su benchmark, con la recta de regresión.

    Args:
        rend_a: Rendimientos del activo.
        rend_m: Rendimientos del benchmark.
        recta: Resultado de ``metricas.recta_regresion``.
        beta_valor: Beta que se anota junto a la recta (``NaN`` si no hay).
        ticker: Ticker del activo, para el eje vertical.
        bench: Ticker del benchmark, para el eje horizontal.
        colores: Paleta del modo actual.

    Returns:
        Figura de Plotly con un punto por periodo.
    """
    juntos = pd.concat([rend_a.rename("a"), rend_m.rename("m")], axis=1, join="inner").dropna()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=juntos["m"], y=juntos["a"], mode="markers", name="Un punto por periodo",
        marker=dict(color=rgba(colores["primario"], 0.75), size=8, line=dict(color=colores["dorado_fuerte"], width=0.8)),
        customdata=juntos.index.strftime("%Y-%m"),
        hovertemplate=f"%{{customdata}}<br>{bench}: %{{x:.1%}}<br>{ticker}: %{{y:.1%}}<extra></extra>",
    ))
    if recta["x"] and not es_nan(beta_valor):
        fig.add_trace(go.Scatter(x=recta["x"], y=recta["y"], mode="lines", name="Recta de regresión",
                                 line=dict(color=colores["texto"], width=2), hoverinfo="skip"))
        fig.add_annotation(x=recta["x"][1], y=recta["y"][1], text=f"<b>β = {beta_valor:.2f}</b>",
                           showarrow=False, xanchor="right", yanchor="bottom", yshift=6,
                           bgcolor=colores["fondo"], font=dict(color=colores["texto"], size=13))
    estilo_base(fig, alto=360)
    fig.update_layout(hovermode="closest", margin=dict(l=70, r=20, t=40, b=50))
    fig.update_xaxes(title_text=f"Rendimiento de {bench}", tickformat=".0%",
                     zeroline=True, zerolinecolor=colores["rejilla"])
    fig.update_yaxes(title_text=f"Rendimiento de {ticker}", tickformat=".0%",
                     zeroline=True, zerolinecolor=colores["rejilla"])
    return fig


def tramos_fuera(res: metricas.ResultadoBacktest) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Agrupa periodos consecutivos fuera del mercado en tramos (inicio, fin) para sombrearlos.

    El periodo t abarca desde la fecha del periodo anterior hasta la de t.
    """
    fechas = list(res.curvas.index)  # fechas[0] es la fecha base (antes del primer periodo)
    tramos: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for i, invertido in enumerate(res.senal.tolist()):
        if invertido:
            continue
        inicio, fin = fechas[i], fechas[i + 1]
        if tramos and tramos[-1][1] == inicio:
            tramos[-1] = (tramos[-1][0], fin)
        else:
            tramos.append((inicio, fin))
    return tramos


def figura_backtest(res: metricas.ResultadoBacktest, moneda: str, colores: dict[str, str],
                    escala_log: bool) -> go.Figure:
    """Curvas de buy & hold y regla SMA, con los periodos fuera del mercado sombreados.

    Args:
        res: Resultado de ``metricas.backtest_sma``.
        moneda: Moneda del activo, para el eje.
        colores: Paleta del modo actual.
        escala_log: ``True`` para el eje vertical en escala logarítmica.

    Returns:
        Figura de Plotly.
    """
    fig = go.Figure()
    for inicio, fin in tramos_fuera(res):
        fig.add_vrect(x0=inicio, x1=fin, fillcolor=colores["rejilla"], opacity=0.7, line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=res.curvas.index, y=res.curvas["buy_and_hold"], mode="lines", name="Buy & hold",
                             line=dict(color=colores["texto_secundario"], width=2),
                             hovertemplate=f"%{{y:,.0f}} {moneda}<extra>Buy & hold</extra>"))
    fig.add_trace(go.Scatter(x=res.curvas.index, y=res.curvas["regla_sma"], mode="lines", name="Regla SMA",
                             line=dict(color=colores["primario"], width=3),
                             hovertemplate=f"%{{y:,.0f}} {moneda}<extra>Regla SMA</extra>"))
    # Trazo vacío solo para que el sombreado aparezca en la leyenda. Va al final: si fuera
    # el primero, Plotly tomaría el eje X como numérico y no dibujaría las fechas.
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Fuera del mercado (rinde la tasa libre)",
                             marker=dict(symbol="square", size=12, color=colores["rejilla"]), hoverinfo="skip"))
    estilo_base(fig, alto=500)
    fig.update_xaxes(type="date")
    fig.update_yaxes(title_text=titulo_eje(f"Valor de {config.CAPITAL_INICIAL:,} {moneda}", escala_log),
                     tickformat=",", type="log" if escala_log else "linear")
    return fig


# ---------------------------------------------------------------------------
# 4a. Pestañas
# ---------------------------------------------------------------------------
def pestana_velas(ctx: Contexto, ticker: str) -> None:
    """«Velas»: velas OHLC de la periodicidad elegida con su SMA.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción principal.
    """
    moneda = moneda_de(ticker)
    adjetivo = config.PERIODICIDADES[ctx.periodicidad]["adjetivo"]
    velas = ctx.velas[ctx.velas["ticker"] == ticker]
    diario = ctx.diario[ctx.diario["ticker"] == ticker]

    if velas.empty:
        st.warning(f"No hay datos de {ticker} en el rango elegido.")
    else:
        # La SMA (y todas las métricas) usan solo periodos completos.
        completas = datos.velas_completas(velas)
        en_curso = velas.loc[~velas["completo"]]
        linea_sma = metricas.sma(datos.serie(completas, ticker), ctx.ventana)
        # "En curso" si el periodo incompleto incluye el día de hoy; si no, lo cortó el rango de fechas.
        etiqueta_en_curso = (
            "periodo en curso"
            if not en_curso.empty and en_curso["fecha"].iloc[-1] >= pd.Timestamp(ctx.hoy)
            else "periodo incompleto"
        )
        st.markdown(
            f"**{etiqueta(ticker)}** · velas {adjetivo} y SMA de {ctx.ventana} {ctx.unidad} · "
            f"precios ajustados en {moneda}"
        )
        escala_log = st.toggle(
            "Escala logarítmica", key="log_velas",
            help="En escala logarítmica, la misma distancia vertical representa el mismo "
                 "cambio porcentual. Útil cuando el precio se multiplicó muchas veces.",
        )
        if len(completas) < ctx.ventana:
            st.info(
                f"La SMA de {ctx.ventana} {ctx.unidad} necesita al menos {ctx.ventana} periodos "
                f"completos y solo hay {len(completas)}. Reduce la ventana o amplía el rango de fechas."
            )
        fig = figura_velas(completas, en_curso, linea_sma, ctx.ventana, moneda, ctx.periodicidad,
                           escala_log, ctx.colores, etiqueta_en_curso)
        st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)
        ultimo_dia = diario["fecha"].max()
        if en_curso.empty:
            st.caption(f"Datos hasta el {ultimo_dia:%Y-%m-%d}. Todas las velas son periodos completos.")
        elif etiqueta_en_curso == "periodo en curso":
            st.caption(
                f"Datos hasta el {ultimo_dia:%Y-%m-%d}. La vela translúcida es el periodo en curso: "
                "todavía no cierra, así que no entra en la SMA ni en las métricas."
            )
        else:
            st.caption(
                f"Datos hasta el {ultimo_dia:%Y-%m-%d}. La vela translúcida es un periodo incompleto "
                "(el rango de fechas lo corta a la mitad), así que no entra en la SMA ni en las métricas."
            )

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
Cada **vela** resume un periodo (un mes o un año, según la periodicidad) con cuatro
precios (**OHLC**: *open*, *high*, *low*, *close*):

- El **cuerpo** va del precio de apertura (*open*) al de cierre (*close*).
- Las **mechas** llegan al máximo (*high*) y al mínimo (*low*) del periodo.
- **Dorada:** el periodo cerró por encima de su apertura. **Roja:** cerró por debajo.
- **Translúcida:** el periodo en curso. Todavía no cierra, así que se excluye de la SMA y
  de todas las métricas (CAGR, volatilidad, Sharpe ratio, drawdown y backtest).

La línea **SMA** (*simple moving average*) es el promedio de los últimos *n* cierres.
Suaviza el ruido y muestra la tendencia: si el precio está por encima de su SMA,
hoy vale más que su promedio reciente. Los precios están **ajustados** por splits y
dividendos, por eso los precios antiguos pueden no coincidir con los que se publicaron
en su momento.
"""
        )
        st.latex(r"\text{SMA}_t = \frac{1}{n}\sum_{i=0}^{n-1} P_{t-i}")
        st.markdown(
            "**Para reflexionar:** ¿en qué periodos el precio cruzó por debajo de su SMA y "
            "cuánto tardó en recuperarla? ¿Cambia tu lectura si pasas de *Mensual* a *Anual*?"
        )


def pestana_rendimiento(ctx: Contexto, ticker: str, seleccion: list[str]) -> None:
    """«Rendimiento»: crecimiento de CAPITAL_INICIAL para los tickers seleccionados.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción principal (su línea va en dorado).
        seleccion: Tickers elegidos en «Comparar» (barra lateral).
    """
    if not seleccion:
        st.info("Elige al menos un ticker en **Comparar** (barra lateral).")
        return
    series = {t: ctx.cierres(t) for t in seleccion}
    series = {t: s for t, s in series.items() if len(s) >= 2}
    if not series:
        st.warning("No hay suficientes periodos completos en el rango elegido.")
        return
    # Misma fecha de inicio para todos: la más tardía entre los primeros datos.
    inicio_comun = max(s.index[0] for s in series.values())
    curvas = {}
    for t, s in series.items():
        s = s.loc[inicio_comun:]
        curvas[t] = metricas.crecimiento_capital(metricas.rendimientos(s), config.CAPITAL_INICIAL, s.index[0])

    monedas = sorted({moneda_de(t) for t in curvas})
    st.markdown(
        f"**Valor de {config.CAPITAL_INICIAL:,} invertidos el {inicio_comun:%Y-%m-%d}** "
        f"(cierre {ctx.periodicidad.lower()}), reinvirtiendo dividendos"
    )
    if len(monedas) > 1:
        st.warning(
            f"Estás comparando activos en distintas monedas ({', '.join(monedas)}). Cada línea está en "
            "su moneda local y no se convierte tipo de cambio: compara la **forma** y el rendimiento "
            "porcentual de las curvas, no los montos entre monedas distintas."
        )
    mostrar_avisos_datos(ctx, list(curvas), compacto=True)
    # Abre en escala logarítmica: en lineal, una acción que se multiplicó cientos de veces aplasta a las demás.
    escala_log = st.toggle("Escala logarítmica", value=True, key="log_rendimiento",
                           help="Con escala logarítmica, pendientes iguales = misma tasa de crecimiento.")
    titulo_y = f"Valor de la inversión ({monedas[0]})" if len(monedas) == 1 else "Valor de la inversión (moneda local)"
    fig = figura_crecimiento(curvas, ticker if ticker in curvas else None, ctx.colores, escala_log, titulo_y)
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption("Dorado: acción principal. Azul: benchmarks. Gris: demás acciones. El valor final está escrito al final de cada línea.")

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            f"""
Cada línea responde: *si hubiera invertido {config.CAPITAL_INICIAL:,} el mismo día en cada activo,
¿cuánto valdría después?* Los rendimientos se **multiplican** periodo a periodo (interés
compuesto) y, como los precios están ajustados, incluyen dividendos reinvertidos.

**¿Por qué escala logarítmica?** En log, pendientes iguales = misma tasa de crecimiento: dos
líneas igual de inclinadas crecieron al mismo % por periodo, aunque una valga mucho más que la otra.
"""
        )
        st.latex(r"V_t = C \times \prod_{i=1}^{t}(1 + r_i) \qquad r_i = \frac{P_i}{P_{i-1}} - 1")
        st.markdown(
            "**Para reflexionar:** la curva que termina más arriba, ¿fue también la más cómoda de "
            "sostener? Revisa sus caídas en «Drawdown» antes de concluir."
        )


def pestana_riesgo(ctx: Contexto, seleccion: list[str]) -> None:
    """«Riesgo»: dispersión volatilidad vs CAGR y tabla de métricas.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        seleccion: Tickers elegidos en «Comparar»; se usan si se elige
            "Solo la selección de la barra lateral".
    """
    alcance = st.radio(
        "Qué mostrar", ["Todas las acciones y benchmarks", "Solo la selección de la barra lateral (y sus benchmarks)"],
        horizontal=True, key="alcance_riesgo",
    )
    if alcance.startswith("Todas"):
        tickers = list(config.TICKERS) + list(config.BENCHMARKS)
    else:
        bench = [benchmark_de(t) for t in seleccion if benchmark_de(t)]
        tickers = list(dict.fromkeys(seleccion + bench))
    if not tickers:
        st.info("Elige al menos un ticker en **Comparar** (barra lateral).")
        return

    filas = []
    for t in tickers:
        r = ctx.resumen(t)
        moneda = moneda_de(t)
        filas.append({
            "ticker": t, "nombre": info_ticker(t)["nombre"], "mercado": mercado_de(t), "moneda": moneda,
            "es_benchmark": es_benchmark(t), "cagr": r["cagr"], "volatilidad": r["volatilidad"],
            "max_drawdown": r["max_drawdown"], "sharpe": r["sharpe"], "tasa": ctx.tasa(t),
            "beta": r["beta"], "correlacion": r["correlacion"], "benchmark": benchmark_de(t) or "es benchmark",
            "sharpe_txt": num(r["sharpe"]), "tasa_txt": f"{moneda} {ctx.tasa(t):.2%}",
        })
    tabla = pd.DataFrame(filas)
    graficables = tabla.dropna(subset=["cagr", "volatilidad"])

    mostrar_avisos_datos(ctx, tickers, compacto=True,
                         extra="En la gráfica, su punto aparece más a la **izquierda** (menos volátil) "
                               "de lo que debería.")
    if len(set(tabla["moneda"])) > 1:
        st.caption(NOTA_MONEDA_LOCAL)
    if graficables.empty:
        st.warning(f"No hay métricas que graficar: {MOTIVO_POCOS_DATOS}.")
    else:
        st.plotly_chart(figura_riesgo(graficables, ctx.colores), width="stretch", theme=None, config=PLOTLY_CONFIG)
        faltan = sorted(set(tabla["ticker"]) - set(graficables["ticker"]))
        if faltan:
            st.caption(f"Sin punto en la gráfica ({MOTIVO_POCOS_DATOS}): {', '.join(faltan)}.")

    vista = pd.DataFrame({
        "Ticker": tabla["ticker"],
        "Nombre": tabla["nombre"],
        "Mercado": tabla["mercado"],
        "CAGR": tabla["cagr"].map(pct),
        "Volatilidad": tabla["volatilidad"].map(pct),
        "Máx. drawdown": tabla["max_drawdown"].map(pct),
        "Sharpe ratio": tabla["sharpe"].map(num),
        "Tasa libre usada": tabla["tasa_txt"],
        "Beta": tabla["beta"].map(num),
        "Correlación": tabla["correlacion"].map(num),
        "Benchmark": tabla["benchmark"],
    })
    st.html(tabla_html(vista))
    st.caption(f"n/d = no disponible ({MOTIVO_POCOS_DATOS}, o es un benchmark y no tiene beta contra sí mismo). "
               "Cada Sharpe ratio usa la tasa libre de riesgo de la moneda del activo.")

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
Cada punto es un activo: a la **derecha**, más volatilidad (riesgo); **arriba**, más
rendimiento anual compuesto (CAGR). Los rombos son benchmarks. Un activo "eficiente" está
arriba y a la izquierda. El **Sharpe ratio** resume esa relación: rendimiento por encima
de la tasa libre de riesgo por cada unidad de volatilidad.
"""
        )
        st.latex(r"\text{CAGR} = \left(\frac{P_{final}}{P_{inicial}}\right)^{1/\text{años}} - 1"
                 r"\qquad \sigma_{anual} = \sigma(r)\sqrt{k}")
        st.latex(r"\text{Sharpe} = \frac{\overline{r - r_f}}{\sigma(r)}\sqrt{k}"
                 r"\qquad k = \text{periodos por año}")
        st.markdown(f"**Simplificación:** {NOTA_TASA_CONSTANTE}")
        st.markdown(texto_pocas_observaciones(ctx.hoy, "volatilidad"))
        st.markdown(
            "**Para reflexionar:** ¿algún activo tuvo más rendimiento con *menos* riesgo que su "
            "benchmark? ¿Qué tanto depende la respuesta del periodo elegido?"
        )


def pestana_drawdown(ctx: Contexto, ticker: str) -> None:
    """«Drawdown»: precio con máximo previo, área de drawdown y tiempo de recuperación.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción principal.
    """
    precios = ctx.cierres(ticker)
    if len(precios) < 2:
        st.warning("No hay suficientes periodos completos en el rango elegido.")
        return
    dd = metricas.serie_drawdown(precios)
    info = metricas.max_drawdown(precios)
    recuperacion = metricas.tiempo_recuperacion(precios)
    moneda = moneda_de(ticker)

    st.markdown(f"**{etiqueta(ticker)}** · caídas desde el máximo previo, con cierres {config.PERIODICIDADES[ctx.periodicidad]['adjetivo']}")
    escala_log = st.toggle("Escala logarítmica (panel de precio)", key="log_drawdown")
    st.plotly_chart(figura_drawdown(precios, dd, info, moneda, ctx.colores, escala_log),
                    width="stretch", theme=None, config=PLOTLY_CONFIG)

    pico, valle = info["fecha_pico"], info["fecha_valle"]
    if info["max_drawdown"] == 0:
        st.markdown("En este rango el precio nunca cayó por debajo de su máximo previo.")
    elif recuperacion is None:
        transcurrido = len(precios.loc[valle:]) - 1
        if transcurrido == 0:
            despues = ("El valle es el último periodo completo: la caída podría seguir, y todavía no hay "
                       "datos para medir la recuperación.")
        else:
            despues = (f"Desde el valle han pasado {periodos_texto(transcurrido, ctx.periodicidad)} "
                       "sin volver al nivel del pico.")
        st.markdown(
            f"**Todavía no se recupera.** La peor caída fue de **{info['max_drawdown']:.1%}**, del pico de "
            f"{pico:%Y-%m} al valle de {valle:%Y-%m}. {despues}"
        )
    else:
        total = len(precios.loc[pico:info["fecha_recuperacion"]]) - 1
        st.markdown(
            f"**Tiempo de recuperación: {periodos_texto(recuperacion, ctx.periodicidad)}.** La peor caída fue "
            f"de **{info['max_drawdown']:.1%}** (pico {pico:%Y-%m}, valle {valle:%Y-%m}) y recuperó el "
            f"nivel del pico en {info['fecha_recuperacion']:%Y-%m}: "
            f"{periodos_texto(total, ctx.periodicidad)} desde el pico."
        )

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
Arriba, el precio y su **máximo previo** (línea punteada). Abajo, el **drawdown**: qué tan
lejos está el precio de ese máximo. 0 % significa que está en máximo histórico. El
**máximo drawdown** es la peor caída del periodo: lo que habría perdido alguien que compró
en el pico. Recuperarse cuesta más que caer: tras −50 % se necesita +100 %.
"""
        )
        st.latex(r"DD_t = \frac{P_t}{\max(P_0, \dots, P_t)} - 1 \qquad \text{MDD} = \min_t DD_t")
        st.markdown(
            "**Para reflexionar:** si hubieras vivido el peor drawdown, ¿habrías mantenido la "
            "inversión hasta la recuperación? ¿Cuánto tiempo estarías dispuesto a esperar?"
        )


def panel_vs_mercado(ctx: Contexto, ticker: str, clave: str) -> None:
    """Un panel de «vs Mercado»: crecimiento, dispersión con beta y tarjetas.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción del panel; se compara contra su benchmark.
        clave: Sufijo para que los widgets de cada panel no choquen
            (``"izq"``, ``"der"`` o ``"unico"``).
    """
    bench = benchmark_de(ticker)
    a, m = ctx.cierres(ticker), ctx.cierres(bench)
    st.markdown(f"#### {etiqueta(ticker)}\nvs **{etiqueta(bench)}** · en {moneda_de(ticker)}")
    mostrar_avisos_datos(ctx, [ticker], compacto=True)
    if len(a) < 2 or len(m) < 2:
        st.warning("No hay suficientes periodos completos en el rango elegido.")
        return

    inicio_comun = max(a.index[0], m.index[0])
    curvas = {t: metricas.crecimiento_capital(metricas.rendimientos(s.loc[inicio_comun:]), config.CAPITAL_INICIAL,
                                              inicio_comun)
              for t, s in [(ticker, a), (bench, m)]}
    escala_log = st.toggle("Escala logarítmica", key=f"log_vs_{clave}")
    fig = figura_crecimiento(curvas, ticker, ctx.colores, escala_log,
                             f"Valor de {config.CAPITAL_INICIAL:,} ({moneda_de(ticker)})", alto=360)
    fig.update_layout(margin=dict(l=70, r=170, t=40, b=40))
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG, key=f"crec_{clave}")

    r = ctx.resumen(ticker)
    rb = ctx.resumen(bench)
    rend_a, rend_m = metricas.rendimientos(a), metricas.rendimientos(m)
    recta = metricas.recta_regresion(rend_a, rend_m)
    st.plotly_chart(figura_dispersion_beta(rend_a, rend_m, recta, r["beta"], ticker, bench, ctx.colores),
                    width="stretch", theme=None, config=PLOTLY_CONFIG, key=f"disp_{clave}")

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    tasa_txt = f"{moneda_de(ticker)} {ctx.tasa(ticker):.2%}"
    tarjeta(c1, "Beta", r["beta"], num(r["beta"]), motivo_nan(r, "beta"),
            "Cuánto se movió en promedio cuando el benchmark se movió 1 %. Es la pendiente de la recta.")
    tarjeta(c2, "Correlación", r["correlacion"], num(r["correlacion"]), motivo_nan(r, "correlacion"),
            "Qué tan juntos se movieron (−1 a 1). Si es baja, la beta explica poco.")
    tarjeta(c3, f"Sharpe ratio · {ticker}", r["sharpe"], num(r["sharpe"]), motivo_nan(r, "sharpe"),
            f"Con tasa libre de riesgo {tasa_txt}, constante (simplificación).")
    tarjeta(c4, f"Sharpe ratio · {bench}", rb["sharpe"], num(rb["sharpe"]), motivo_nan(rb, "sharpe"),
            f"Con tasa libre de riesgo {tasa_txt}, constante (simplificación).")


def tarjeta(columna: DeltaGenerator, titulo: str, valor: float, texto: str,
            motivo: str, ayuda: str) -> None:
    """Un ``st.metric`` que, si el valor falta, explica por qué en lugar de mostrar un guion.

    Args:
        columna: Columna de Streamlit donde va la tarjeta.
        titulo: Nombre de la métrica.
        valor: Valor numérico (puede ser ``NaN``).
        texto: Valor ya formateado (``"68.0%"``).
        motivo: Por qué falta el valor, si es ``NaN``.
        ayuda: Texto del ícono de ayuda.
    """
    if es_nan(valor):
        columna.metric(titulo, "n/d", delta=motivo, delta_color="gray", delta_arrow="off", help=ayuda, border=True)
    else:
        columna.metric(titulo, texto, help=ayuda, border=True)


def pestana_vs_mercado(ctx: Contexto, ticker: str) -> None:
    """«vs Mercado»: una o dos acciones contra su benchmark, lado a lado.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción de la izquierda (o la única, si se apaga "Dos acciones lado a lado").
    """
    lado_a_lado = st.toggle("Dos acciones lado a lado", value=True, key="vs_doble")
    opciones = list(config.TICKERS)
    if lado_a_lado:
        segundo = config.VS_MERCADO_SEGUNDO_DEFAULT
        if segundo == ticker:
            segundo = next(t for t in opciones if t != ticker)
        izquierda, derecha = st.columns(2, gap="large")
        t1 = izquierda.selectbox("Acción de la izquierda", opciones, index=opciones.index(ticker), format_func=etiqueta)
        t2 = derecha.selectbox("Acción de la derecha", opciones, index=opciones.index(segundo), format_func=etiqueta)
        with izquierda:
            panel_vs_mercado(ctx, t1, "izq")
        with derecha:
            panel_vs_mercado(ctx, t2, "der")
    else:
        panel_vs_mercado(ctx, ticker, "unico")
    if lado_a_lado and moneda_de(t1) != moneda_de(t2):
        st.caption(NOTA_MONEDA_LOCAL)

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
Arriba, cuánto habría crecido la misma inversión en la acción y en su benchmark. Abajo,
cada punto es un periodo: en el eje horizontal el rendimiento del mercado y en el vertical
el de la acción. La **pendiente** de la recta es la **beta**: β > 1 amplifica los movimientos
del mercado; β < 1 los amortigua. La **correlación** dice qué tan bien se ajustan los puntos
a la recta.
"""
        )
        st.latex(r"\beta = \frac{\operatorname{Cov}(r_a, r_m)}{\operatorname{Var}(r_m)}"
                 r"\qquad \rho = \frac{\operatorname{Cov}(r_a, r_m)}{\sigma_a\,\sigma_m}")
        st.markdown(f"**Simplificación del Sharpe ratio:** {NOTA_TASA_CONSTANTE}")
        st.markdown(texto_pocas_observaciones(ctx.hoy, "beta"))
        st.markdown(
            "**Para reflexionar:** una acción con beta alta, ¿es necesariamente más arriesgada que "
            "una con beta baja? Compara su volatilidad en «Riesgo»."
        )


def pestana_backtest(ctx: Contexto, ticker: str) -> None:
    """«Backtest»: regla SMA contra buy & hold, sin información del futuro.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Activo con el que abre el selector de la pestaña.
    """
    opciones = list(config.TICKERS) + list(config.BENCHMARKS)
    # El selector tiene key, así que Streamlit recuerda la elección. Si cambia la acción
    # principal en la barra lateral, el backtest la sigue; si no, se respeta lo que elegiste aquí.
    if st.session_state.get("_backtest_sigue_a") != ticker:
        st.session_state["activo_backtest"] = ticker
        st.session_state["_backtest_sigue_a"] = ticker
    activo = st.selectbox("Activo para el backtest (también puedes elegir un benchmark)", opciones,
                          format_func=etiqueta_con_tipo, key="activo_backtest")
    moneda = moneda_de(activo)
    mostrar_avisos_datos(ctx, [activo], compacto=True)
    res = metricas.backtest_sma(ctx.cierres(activo), ctx.ventana, ctx.tasa(activo),
                                ctx.periodos_por_anio, config.CAPITAL_INICIAL)
    st.markdown(
        f"**{etiqueta_con_tipo(activo)}** · regla: invertido solo si el cierre del periodo anterior "
        f"estaba por encima de su SMA de {ctx.ventana} {ctx.unidad}; si no, rinde la tasa libre de riesgo "
        f"({moneda} {ctx.tasa(activo):.2%} anual)."
    )
    for advertencia in res.advertencias:
        st.warning(advertencia)
    if not res.curvas.empty:
        escala_log = st.toggle("Escala logarítmica", key="log_backtest")
        st.plotly_chart(figura_backtest(res, moneda, ctx.colores, escala_log),
                        width="stretch", theme=None, config=PLOTLY_CONFIG)
        st.caption(f"Desde {res.curvas.index[0]:%Y-%m-%d} (cuando la SMA ya existe), con {config.CAPITAL_INICIAL:,} {moneda}.")

    tabla = res.resumen.rename(index={"regla_sma": "Regla SMA", "buy_and_hold": "Buy & hold"})
    st.html(tabla_html(pd.DataFrame({
        "Estrategia": tabla.index,
        "CAGR": tabla["cagr"].map(pct),
        "Máx. drawdown": tabla["max_drawdown"].map(pct),
        "Sharpe ratio": tabla["sharpe"].map(num),
        "% del tiempo invertido": tabla["pct_invertido"].map(lambda v: pct(v, 0)),
    })))
    if tabla[["cagr", "sharpe"]].isna().any().any():
        st.caption(f"n/d = no disponible ({MOTIVO_POCOS_DATOS} después de formar la SMA).")
    st.info(NOTA_BACKTEST)

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
Un **backtest** simula qué habría pasado si se hubiera seguido una regla. Aquí, la regla
está invertida en el periodo *t* solo si en el cierre del periodo **anterior** el precio
estaba por encima de su SMA; si no, el dinero rinde la tasa libre de riesgo. Decidir con el
cierre de *t* para invertir en *t* sería **leakage**: usar información que todavía no
existía. Las bandas sombreadas son los periodos fuera del mercado.
"""
        )
        st.latex(r"\text{señal}_t = \mathbb{1}\left[P_{t-1} > \text{SMA}_{t-1}\right]"
                 r"\qquad r^{regla}_t = \text{señal}_t\, r_t + (1 - \text{señal}_t)\, r_f")
        st.markdown(f"**Simplificación del Sharpe ratio:** {NOTA_TASA_CONSTANTE}")
        st.markdown(
            "**Para reflexionar:** si la regla tuvo menor drawdown pero también menor CAGR, ¿qué "
            "preferirías? ¿Qué pasaría con el resultado si cambias la ventana de la SMA o el periodo?"
        )


def pestana_datos(ctx: Contexto, ticker: str) -> None:
    """«Datos»: vista previa de la tabla tidy para BI y descarga en CSV.

    Args:
        ctx: Datos y parámetros compartidos por todas las pestañas.
        ticker: Acción de la vista previa.
    """
    tidy = construir_tidy(ctx.hoy.isoformat(), ctx.inicio, ctx.fin, ctx.periodicidad, ctx.ventana,
                          tuple(sorted(ctx.tasas.items())))
    st.markdown(
        f"Tabla en formato **tidy** (largo): **{len(tidy):,} filas**, una por fecha, ticker y métrica, "
        f"con periodos {config.PERIODICIDADES[ctx.periodicidad]['adjetivo']} completos."
    )
    # Vista previa: las filas más recientes de la acción principal, para ver varias métricas por fecha.
    vista = (tidy[tidy["ticker"] == ticker]
             .sort_values(["fecha", "metrica"], ascending=[False, True])
             .head(60))
    if vista.empty:
        st.info(f"No hay filas de {ticker} en el rango elegido.")
    else:
        st.html(tabla_html(vista.assign(
            fecha=vista["fecha"].dt.strftime("%Y-%m-%d"),
            valor=vista["valor"].map(lambda v: "n/d" if es_nan(v) else f"{v:,.4f}"),
        ), alto_max=380))
        st.caption(f"Vista previa: las {len(vista)} filas más recientes de {ticker} (n/d = celda vacía en el CSV). "
                   f"El CSV trae las {len(tidy):,} filas de todos los tickers.")
    nombre =f"acciones101_{ctx.periodicidad.lower()}_{ctx.inicio:%Y%m%d}_{ctx.fin:%Y%m%d}.csv"
    st.download_button("Descargar CSV", data=tidy.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
                       file_name=nombre, mime="text/csv", type="primary", icon=":material/download:")
    st.markdown(
        """
**Úsalo en otras herramientas.** El mismo archivo funciona en:

- **Looker Studio:** súbelo a Google Sheets y conéctalo como fuente de datos.
- **Power BI:** *Obtener datos → Texto/CSV*.
- **Tableau:** *Conectar → Archivo de texto*.

Usa `metrica` como filtro o dimensión y `valor` como medida. Las métricas de resumen
(`cagr`, `sharpe`, `beta`…) aparecen una vez por ticker, en la última fecha del periodo.
"""
    )

    with st.expander("¿Qué estoy viendo?"):
        st.markdown(
            """
En formato **tidy** cada fila es una observación y cada columna una variable. En lugar de
una columna por métrica (formato "ancho"), hay una columna `metrica` y una `valor`. Así,
agregar una métrica nueva no cambia la estructura del archivo. Los cálculos ya vienen hechos
en Python (con las mismas funciones de `metricas.py`), para que la herramienta de BI solo
tenga que graficar.
"""
        )
        st.latex(r"\text{valor\_inversion}_t = C \times \prod_{i=1}^{t}(1 + r_i)")
        st.markdown(
            "**Para reflexionar:** ¿qué métricas conviene calcular en Python y cuáles se pueden "
            "calcular dentro de la herramienta de BI sin riesgo de errores?"
        )


# ---------------------------------------------------------------------------
# 4b. Armado de la página
# ---------------------------------------------------------------------------
# Primero el CSS del modo, para que la página se pinte bien desde el inicio.
colores = config.PALETA[MODO]
st.markdown(css_tema(colores), unsafe_allow_html=True)

hoy = date.today()
try:
    precios, meta = cargar_precios(hoy.isoformat())
except RuntimeError as error:
    st.error(f"No fue posible cargar datos. {error}")
    st.stop()

fecha_minima = date.fromisoformat(config.FECHA_INICIO)
todos_los_tickers = list(config.TICKERS) + list(config.BENCHMARKS)

with st.sidebar:
    oscuro = MODO == "oscuro"
    st.button("Modo claro" if oscuro else "Modo oscuro", key="boton_modo", on_click=cambiar_modo,
              icon=":material/light_mode:" if oscuro else ":material/dark_mode:", width="stretch",
              help="Cambia los colores de la página y de las gráficas.")
    st.header("Controles")

    mercados = list(dict.fromkeys(v["mercado"] for v in config.TICKERS.values()))
    mercado_default = config.TICKERS[config.TICKER_DEFAULT]["mercado"]
    mercado = st.radio("Mercado", mercados, index=mercados.index(mercado_default), horizontal=True)
    opciones = [t for t, v in config.TICKERS.items() if v["mercado"] == mercado]
    indice_default = opciones.index(config.TICKER_DEFAULT) if config.TICKER_DEFAULT in opciones else 0
    ticker = st.selectbox("Acción principal", opciones, index=indice_default, format_func=etiqueta)

    seleccion = st.multiselect(
        "Comparar (pestañas Rendimiento y Riesgo)", todos_los_tickers,
        default=config.TICKERS_COMPARAR_DEFAULT, format_func=etiqueta_con_tipo,
    )

    rango = st.date_input(
        "Rango de fechas", value=(fecha_minima, hoy),
        min_value=fecha_minima, max_value=hoy, format="YYYY-MM-DD",
    )
    if isinstance(rango, (tuple, list)) and len(rango) == 2:
        inicio, fin = rango
    else:
        inicio, fin = fecha_minima, hoy
        st.caption("Elige la fecha inicial y la final. Mientras tanto se usa todo el periodo.")

    nombres_periodicidad = list(config.PERIODICIDADES)
    periodicidad = st.radio(
        "Periodicidad", nombres_periodicidad,
        index=nombres_periodicidad.index(config.PERIODICIDAD_DEFAULT), horizontal=True,
    )
    unidad = config.PERIODICIDADES[periodicidad]["unidad"]
    ventana = st.slider(
        f"Ventana de la SMA ({unidad})", min_value=config.VENTANA_SMA_MIN,
        max_value=config.VENTANA_SMA_MAX, value=config.VENTANA_SMA_DEFAULT,
    )

    with st.expander("Tasas libres de riesgo (anuales)"):
        tasas: dict[str, float] = {}
        for moneda, info in config.TASAS_LIBRE_RIESGO.items():
            valor = st.number_input(f"{moneda} (%)", min_value=-5.0, max_value=50.0,
                                    value=float(info["tasa"]) * 100, step=0.05, format="%.2f",
                                    key=f"tasa_{moneda}")
            fecha_sin_corte = str(info["fecha"]).replace("-", "‑")  # guion que no parte la línea
            st.caption(f"{info['instrumento']} · [{info['fuente']}]({info['url']}) · dato al {fecha_sin_corte}")
            tasas[moneda] = valor / 100
        st.caption(NOTA_TASA_CONSTANTE)

    st.divider()
    if meta["fuente"] == "yfinance":
        st.caption(f"**Fuente de datos:** Yahoo Finance (`yfinance`) · datos al {meta['fecha_datos']}")
    elif meta["fuente"] == "respaldo":
        st.caption(f"**Fuente de datos:** respaldo CSV · datos al {meta['fecha_respaldo']}")
    else:
        st.caption(
            f"**Fuente de datos:** Yahoo Finance + respaldo CSV para "
            f"{', '.join(meta['tickers_respaldo'])} (respaldo al {meta['fecha_respaldo']})"
        )

    st.divider()
    st.caption(AVISO_PIE)

diario, velas = preparar_velas(hoy.isoformat(), inicio, fin, periodicidad)
ctx = Contexto(
    diario=diario, velas=velas, completas=datos.velas_completas(velas), periodicidad=periodicidad,
    periodos_por_anio=int(config.PERIODICIDADES[periodicidad]["periodos_por_anio"]), ventana=ventana,
    tasas=tasas, colores=colores, hoy=hoy, inicio=inicio, fin=fin,
)

# Encabezado
st.title("Acciones 101")
st.markdown("##### La bolsa no es un casino: es análisis")
st.caption(AVISO_CORTO)

if meta["fuente"] == "respaldo":
    st.warning(f"⚠️ Yahoo Finance no respondió. Mostrando datos de respaldo al {meta['fecha_respaldo']}.")
elif meta["fuente"] == "mixta":
    st.warning(
        f"⚠️ Yahoo Finance no respondió para {', '.join(meta['tickers_respaldo'])}. "
        f"Mostrando datos de respaldo al {meta['fecha_respaldo']} para esos tickers."
    )
if meta["tickers_sin_datos"]:
    st.error(f"Sin datos en ninguna fuente para: {', '.join(meta['tickers_sin_datos'])}.")
mostrar_avisos_datos(ctx, [ticker])

# KPIs del ticker principal
resumen = ctx.resumen(ticker)
bench_principal = benchmark_de(ticker)
tasa_info = config.TASAS_LIBRE_RIESGO[moneda_de(ticker)]
k1, k2, k3, k4, k5 = st.columns(5)
tarjeta(k1, "CAGR", resumen["cagr"], pct(resumen["cagr"]), motivo_nan(resumen, "cagr"),
        "Tasa de crecimiento anual compuesta del precio ajustado (incluye dividendos).")
tarjeta(k2, "Volatilidad", resumen["volatilidad"], pct(resumen["volatilidad"]), motivo_nan(resumen, "volatilidad"),
        "Desviación estándar de los rendimientos, anualizada.")
tarjeta(k3, "Máx. drawdown", resumen["max_drawdown"], pct(resumen["max_drawdown"]),
        motivo_nan(resumen, "max_drawdown"), "La peor caída desde un máximo previo.")
tarjeta(k4, "Sharpe ratio", resumen["sharpe"], num(resumen["sharpe"]), motivo_nan(resumen, "sharpe"),
        f"Con tasa libre de riesgo {moneda_de(ticker)} {ctx.tasa(ticker):.2%} "
        f"({tasa_info['instrumento']}), constante: es una simplificación.")
tarjeta(k5, f"Beta vs {bench_principal}", resumen["beta"], num(resumen["beta"]), motivo_nan(resumen, "beta"),
        f"Sensibilidad frente a {etiqueta(bench_principal)}.")
n_rend = resumen["n_periodos"]
adjetivo = config.PERIODICIDADES[periodicidad]["adjetivo_singular" if n_rend == 1 else "adjetivo"]
texto_n = (f"KPIs de **{etiqueta(ticker)}** basados en **{plural(n_rend, 'rendimiento', 'rendimientos')} "
           f"{adjetivo}** completos ({resumen['anios']:.1f} años), en {moneda_de(ticker)}.")
if resumen["n_benchmark"] and resumen["n_benchmark"] != n_rend:
    texto_n += f" La beta usa {resumen['n_benchmark']} periodos en común con {bench_principal}."
st.caption(texto_n)
if 0 < n_rend < config.MINIMO_OBSERVACIONES:
    st.warning(
        f"**Pocas observaciones: estimación inestable.** Con solo {n_rend} datos, un periodo extremo "
        "cambia mucho la volatilidad, el Sharpe ratio y la beta (ver «Riesgo» → ¿Qué estoy viendo?).",
        icon="⚠️",
    )

tabs = st.tabs(["Velas", "Rendimiento", "Riesgo", "Drawdown", "vs Mercado", "Backtest", "Datos"])
with tabs[0]:
    pestana_velas(ctx, ticker)
with tabs[1]:
    pestana_rendimiento(ctx, ticker, seleccion)
with tabs[2]:
    pestana_riesgo(ctx, seleccion)
with tabs[3]:
    pestana_drawdown(ctx, ticker)
with tabs[4]:
    pestana_vs_mercado(ctx, ticker)
with tabs[5]:
    pestana_backtest(ctx, ticker)
with tabs[6]:
    pestana_datos(ctx, ticker)
