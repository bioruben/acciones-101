"""Configuración central del dashboard «Acciones 101». Código generado con un agente de IA (Claude Code) con fines educativos.

Todo lo que un estudiante quiera cambiar (tickers, fechas, ventana de la SMA,
tasa libre de riesgo, colores) vive en este archivo. El resto del código lee
estos valores; no hace falta tocar ``app.py`` para experimentar.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Universo de acciones
# ---------------------------------------------------------------------------
# Cada ticker se compara SOLO contra el benchmark de su propio mercado y todo
# se calcula en moneda local (no se convierte tipo de cambio en esta versión).
# Los tickers siguen la nomenclatura de Yahoo Finance:
#   - ".MX" = Bolsa Mexicana de Valores
#   - ".KS" = Bolsa de Corea (KOSPI)
#   - sin sufijo = EE.UU.
TICKERS: dict[str, dict[str, str]] = {
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

# Avisos de calidad de datos que la app muestra cuando se elige el ticker.
# Para agregar uno: ticker -> texto. Se revisó con los datos del respaldo CSV.
AVISOS_DATOS: dict[str, str] = {
    "AMXB.MX": (
        "En los datos de Yahoo Finance, de 2015 a agosto de 2023 la serie B de "
        "América Móvil tiene muchos días sin volumen (nadie la operó) y en casi "
        "todos ellos se repite el precio del día anterior. Hasta el 16 de marzo "
        "de 2023 la serie más operada era la L, que ese día se convirtió en "
        "serie B. Los precios repetidos hacen que la acción parezca más estable "
        "de lo que fue: **bajan artificialmente la volatilidad** (y tienden a "
        "bajar también la beta y la correlación con el IPC)."
    ),
}

# Índices de referencia (benchmarks), uno por mercado.
BENCHMARKS: dict[str, dict[str, str]] = {
    "^MXX":  {"nombre": "S&P/BMV IPC", "moneda": "MXN"},
    "^GSPC": {"nombre": "S&P 500",     "moneda": "USD"},
    "^KS11": {"nombre": "KOSPI",       "moneda": "KRW"},
}

# ---------------------------------------------------------------------------
# Periodo y periodicidad
# ---------------------------------------------------------------------------
FECHA_INICIO = "2015-01-01"             # Primer día que se descarga (formato AAAA-MM-DD)
TICKER_DEFAULT = "NVDA"                 # Acción que aparece seleccionada al abrir la app
TICKERS_COMPARAR_DEFAULT = ["NVDA", "MU", "AAPL"]  # Selección inicial de «Rendimiento» y «Riesgo»
VS_MERCADO_SEGUNDO_DEFAULT = "WALMEX.MX"           # Acción de la derecha en «vs Mercado»
PERIODICIDAD_DEFAULT = "Mensual"        # "Mensual" o "Anual"

# Reglas de pandas para pasar de datos diarios a la periodicidad elegida.
#   "ME" = fin de mes (month end), "YE" = fin de año (year end).
# periodos_por_anio se usa para anualizar métricas (12 en mensual, 1 en anual).
# "unidad" y "adjetivo" solo se usan en los textos de la app.
PERIODICIDADES: dict[str, dict[str, str | int]] = {
    "Mensual": {"regla": "ME", "periodos_por_anio": 12, "unidad": "meses", "unidad_singular": "mes",
                "adjetivo": "mensuales", "adjetivo_singular": "mensual"},
    "Anual":   {"regla": "YE", "periodos_por_anio": 1,  "unidad": "años",  "unidad_singular": "año",
                "adjetivo": "anuales", "adjetivo_singular": "anual"},
}

# ---------------------------------------------------------------------------
# Parámetros del análisis
# ---------------------------------------------------------------------------
VENTANA_SMA_DEFAULT = 10                # en periodos de la periodicidad elegida
VENTANA_SMA_MIN = 3                     # límites del slider en la barra lateral
VENTANA_SMA_MAX = 24
CAPITAL_INICIAL = 10_000                # monto hipotético para las curvas de crecimiento

# Con menos de este número de rendimientos, los KPIs muestran el aviso
# "pocas observaciones: estimación inestable". 24 = dos años de datos mensuales.
# En periodicidad Anual casi siempre aplica (de 2015 a hoy hay unos 10 rendimientos anuales).
MINIMO_OBSERVACIONES = 24

# Tasas libres de riesgo ANUALES, una por moneda. Cada acción usa la tasa de
# su moneda para el Sharpe ratio y para el backtest (rendimiento fuera del mercado).
# Supuesto importante: se usa una tasa CONSTANTE para todo el periodo, aunque en
# la realidad cambió mucho desde 2015. Es una simplificación didáctica.
# Para actualizar: consulta la fuente, cambia "tasa" y "fecha" y haz commit.
TASAS_LIBRE_RIESGO: dict[str, dict[str, float | str]] = {
    "MXN": {
        "tasa": 0.0650,
        "instrumento": "CETES 28 días (resultado de la subasta primaria)",
        "fuente": "Banco de México, Sistema de Información Económica (SIE)",
        "url": "https://www.banxico.org.mx/tipcamb/llenarTasasInteresAction.do?idioma=sp",
        "fecha": "2026-11-03",   # fecha de la subasta
    },
    "USD": {
        "tasa": 0.0403,
        "instrumento": "T-bill a 3 meses, mercado secundario (serie DTB3, tasa de descuento)",
        "fuente": "FRED, Federal Reserve Bank of St. Louis",
        "url": "https://fred.stlouisfed.org/series/DTB3",
        "fecha": "2026-11-04",   # último dato diario publicado al consultar
    },
    "KRW": {
        "tasa": 0.0300,
        "instrumento": "Tasa base (Base Rate)",
        "fuente": "Bank of Korea, decisión de política monetaria",
        "url": "https://www.bok.or.kr/eng/bbs/E0000634/view.do?nttId=11065825&menuNo=400423",
        "fecha": "2026-10-22",   # fecha de la decisión
    },
}
FECHA_CONSULTA_TASAS = "2026-11-05"     # día en que se consultaron las tres fuentes

# Estilo de las velas: "up" = alcista dorado / bajista rojo; "clasico" = verde / rojo.
VELAS_ESTILO = "up"

# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
RUTA_RESPALDO = Path(__file__).parent / "data" / "respaldo_precios.csv"
TTL_CACHE_SEGUNDOS = 6 * 3600           # la app vuelve a consultar Yahoo Finance cada 6 horas

# ---------------------------------------------------------------------------
# Paleta (basada en la Universidad Panamericana)
# ---------------------------------------------------------------------------
# Dorado = color principal. Rojo solo con significado (caídas, drawdown,
# velas bajistas). Azul discreto para benchmarks.
#
# Contraste medido (WCAG; texto normal necesita 4.5:1, texto grande 3:1):
#   - Modo claro: dorado primario sobre blanco = 2.24:1 y dorado fuerte = 3.25:1.
#     Ninguno alcanza para texto chico, así que el dorado se usa en líneas,
#     subrayados y fondos de botón (con texto oscuro encima: 7.78:1).
#   - Modo oscuro: dorado primario sobre negro = 8.63:1 y dorado fuerte = 10.74:1.
# "texto_acento" es el color del texto destacado (pestaña activa, ligas): texto
# principal en claro y dorado fuerte en oscuro.
PALETA: dict[str, dict[str, str]] = {
    "claro": {
        "fondo": "#FFFFFF",
        "superficie": "#F7F5F0",
        "texto": "#1A1A1A",
        "texto_secundario": "#5C5C5C",
        "primario": "#C9A96E",
        "dorado_fuerte": "#A88B4F",
        "negativo": "#D0102B",
        "benchmark": "#002B72",
        "rejilla": "#E6E2D8",
        "texto_acento": "#1A1A1A",
    },
    "oscuro": {
        "fondo": "#0E0E0E",
        "superficie": "#1A1A1A",
        "texto": "#F2F2F2",
        "texto_secundario": "#A6A6A6",
        "primario": "#C9A96E",
        "dorado_fuerte": "#D9BE8A",
        "negativo": "#E5394F",
        "benchmark": "#6F8FD6",
        "rejilla": "#2E2E2E",
        "texto_acento": "#D9BE8A",
    },
}
MODO_DEFAULT = "claro"                  # modo con el que abre la app: "claro" u "oscuro"

# Color por mercado en la gráfica de «Riesgo». El rojo está reservado para caídas
# y el azul para benchmarks, así que se usan dorado, carbón y gris. Se validó que
# se distinguen con daltonismo; además cada punto lleva su etiqueta de texto.
COLORES_MERCADO: dict[str, dict[str, str]] = {
    "claro":  {"México": "#A88B4F", "EE.UU.": "#1F1F1F", "Corea": "#BFBFBF"},
    "oscuro": {"México": "#D9BE8A", "EE.UU.": "#F2F2F2", "Corea": "#8A8A8A"},
}

# Verde del estilo "clasico" de velas (solo se usa si VELAS_ESTILO = "clasico").
VERDE_CLASICO: dict[str, str] = {"claro": "#1E8E3E", "oscuro": "#3DBE6A"}
