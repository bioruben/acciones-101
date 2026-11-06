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
PERIODICIDAD_DEFAULT = "Mensual"        # "Mensual" o "Anual"

# Reglas de pandas para pasar de datos diarios a la periodicidad elegida.
#   "ME" = fin de mes (month end), "YE" = fin de año (year end).
# periodos_por_anio se usa para anualizar métricas (12 en mensual, 1 en anual).
# "unidad" y "adjetivo" solo se usan en los textos de la app.
PERIODICIDADES: dict[str, dict[str, str | int]] = {
    "Mensual": {"regla": "ME", "periodos_por_anio": 12, "unidad": "meses", "adjetivo": "mensuales"},
    "Anual":   {"regla": "YE", "periodos_por_anio": 1,  "unidad": "años",  "adjetivo": "anuales"},
}

# ---------------------------------------------------------------------------
# Parámetros del análisis
# ---------------------------------------------------------------------------
VENTANA_SMA_DEFAULT = 10                # en periodos de la periodicidad elegida
VENTANA_SMA_MIN = 3                     # límites del slider en la barra lateral
VENTANA_SMA_MAX = 24
CAPITAL_INICIAL = 10_000                # monto hipotético para las curvas de crecimiento

# Tasa libre de riesgo anual. Supuesto basado en CETES.
# El valor 0.07 viene de CLAUDE.md; NO se verificó contra la tasa vigente.
# Antes de clase, revisa la tasa de CETES a 28 días en Banxico, actualiza el
# valor y la fecha de abajo.
TASA_LIBRE_RIESGO_ANUAL = 0.07
FECHA_TASA_LIBRE_RIESGO = "2026-11-05"  # fecha en que se fijó el supuesto

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
# velas bajistas). Azul discreto para benchmarks. Para TEXTO sobre fondo claro
# usa "dorado_fuerte" (el dorado primario no tiene contraste suficiente).
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
    },
}

# Verde del estilo "clasico" de velas (solo se usa si VELAS_ESTILO = "clasico").
VERDE_CLASICO: dict[str, str] = {"claro": "#1E8E3E", "oscuro": "#3DBE6A"}
