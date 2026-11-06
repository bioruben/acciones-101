"""Dashboard «Acciones 101» en Streamlit (solo presentación). Código generado con un agente de IA (Claude Code) con fines educativos.

Ejecuta con:

    streamlit run app.py

Este archivo solo arma la interfaz y las gráficas. Las fórmulas viven en
``metricas.py`` y la descarga de datos en ``datos.py``.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import datos
import metricas

# ---------------------------------------------------------------------------
# Textos fijos
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

# Modo de color. En la Etapa 4 se agrega el botón claro/oscuro.
MODO = "claro"

st.set_page_config(page_title="Acciones 101", layout="wide")


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------
def info_ticker(ticker: str) -> dict[str, str]:
    """Regresa nombre y moneda de una acción o benchmark definidos en config.py."""
    return config.TICKERS.get(ticker) or config.BENCHMARKS[ticker]


def etiqueta(ticker: str) -> str:
    """Texto para mostrar un ticker, por ejemplo ``"NVDA · NVIDIA"``."""
    return f"{ticker} · {info_ticker(ticker)['nombre']}"


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


def estilo_base(fig: go.Figure, colores: dict[str, str], alto: int = 520) -> go.Figure:
    """Aplica la paleta del dashboard y un estilo sobrio (sin chartjunk) a una figura."""
    fig.update_layout(
        height=alto,
        paper_bgcolor=colores["fondo"],
        plot_bgcolor=colores["fondo"],
        font=dict(color=colores["texto"], size=13),
        margin=dict(l=80, r=20, t=40, b=50),  # espacio para las etiquetas de los ejes
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=colores["superficie"], font_color=colores["texto"],
                        bordercolor=colores["rejilla"]),
    )
    ejes = dict(gridcolor=colores["rejilla"], linecolor=colores["rejilla"], zeroline=False, automargin=True,
                tickfont=dict(color=colores["texto_secundario"]),
                title_font=dict(color=colores["texto_secundario"]))
    fig.update_xaxes(**ejes)
    fig.update_yaxes(**ejes)
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
    estilo_base(fig, colores)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_xaxes(hoverformat=formato_fecha)
    fig.update_yaxes(title_text=f"Precio ajustado ({moneda})", tickformat=",",
                     type="log" if escala_log else "linear")
    return fig


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
hoy = date.today()
try:
    precios, meta = cargar_precios(hoy.isoformat())
except RuntimeError as error:
    st.error(f"No fue posible cargar datos. {error}")
    st.stop()

colores = config.PALETA[MODO]
fecha_minima = date.fromisoformat(config.FECHA_INICIO)

# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Controles")

    mercados = list(dict.fromkeys(v["mercado"] for v in config.TICKERS.values()))
    mercado_default = config.TICKERS[config.TICKER_DEFAULT]["mercado"]
    mercado = st.radio("Mercado", mercados, index=mercados.index(mercado_default), horizontal=True)
    opciones = [t for t, v in config.TICKERS.items() if v["mercado"] == mercado]
    indice_default = opciones.index(config.TICKER_DEFAULT) if config.TICKER_DEFAULT in opciones else 0
    ticker = st.selectbox("Acción principal", opciones, index=indice_default, format_func=etiqueta)

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

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
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

if ticker in config.AVISOS_DATOS:
    sin_volumen, dias = datos.dias_sin_volumen(datos.filtrar_precios(precios, [ticker], inicio, fin), ticker)
    proporcion = f" ({sin_volumen / dias:.0%})" if dias else ""
    st.warning(
        f"**Calidad de datos de {ticker}.** {config.AVISOS_DATOS[ticker]} "
        f"En el rango elegido, {sin_volumen:,} de {dias:,} días{proporcion} no tienen volumen.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Pestañas (en la Etapa 3 se agregan las demás)
# ---------------------------------------------------------------------------
(tab_velas,) = st.tabs(["Velas"])

with tab_velas:
    moneda = info_ticker(ticker)["moneda"]
    adjetivo = config.PERIODICIDADES[periodicidad]["adjetivo"]
    diario = datos.filtrar_precios(precios, [ticker], inicio, fin)
    velas = datos.resamplear_ohlc(diario, periodicidad)

    if velas.empty:
        st.warning(f"No hay datos de {ticker} en el rango elegido.")
    else:
        # La SMA (y todas las métricas) usan solo periodos completos.
        completas = datos.velas_completas(velas)
        en_curso = velas.loc[~velas["completo"]]
        linea_sma = metricas.sma(datos.serie(completas, ticker), ventana)
        # "En curso" si el periodo incompleto incluye el día de hoy; si no, lo cortó el rango de fechas.
        etiqueta_en_curso = (
            "periodo en curso"
            if not en_curso.empty and en_curso["fecha"].iloc[-1] >= pd.Timestamp(hoy)
            else "periodo incompleto"
        )

        st.markdown(
            f"**{etiqueta(ticker)}** · velas {adjetivo} y SMA de {ventana} {unidad} · "
            f"precios ajustados en {moneda}"
        )
        escala_log = st.toggle(
            "Escala logarítmica",
            help="En escala logarítmica, la misma distancia vertical representa el mismo "
                 "cambio porcentual. Útil cuando el precio se multiplicó muchas veces.",
        )
        if len(completas) < ventana:
            st.info(
                f"La SMA de {ventana} {unidad} necesita al menos {ventana} periodos completos y "
                f"solo hay {len(completas)}. Reduce la ventana o amplía el rango de fechas."
            )
        fig = figura_velas(completas, en_curso, linea_sma, ventana, moneda, periodicidad,
                           escala_log, colores, etiqueta_en_curso)
        st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
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
