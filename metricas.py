"""Métricas financieras implementadas a mano (funciones puras, sin Streamlit). Código generado con un agente de IA (Claude Code) con fines educativos.

Convenciones del módulo:

- Las funciones reciben ``pd.Series`` indexadas por fecha, con **una fila por
  periodo** (mes o año). ``periodos_por_anio`` = 12 en mensual y 1 en anual.
- Se usan solo **periodos completos**: el mes o año en curso se quita antes de
  llamar a estas funciones (ver ``datos.velas_completas``).
- Las fórmulas son "puras": calculan lo que se les pide. Las validaciones de
  suficiencia de datos (al menos 2 años, ventana de la SMA) viven en
  ``resumen_metricas`` y ``backtest_sma``, que regresan ``NaN`` y una
  advertencia en texto en lugar de fallar.
- No se usa ninguna librería de análisis técnico: todo está escrito con pandas
  y numpy para que se pueda leer y comprobar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MINIMO_ANIOS: float = 2.0
"""Años mínimos de datos para reportar métricas anualizadas o estimadas."""

_EPSILON = 1e-12  # por debajo de esto, una desviación estándar se trata como cero


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------
def _limpiar(serie: pd.Series) -> pd.Series:
    """Quita valores faltantes y ordena por fecha."""
    return serie.dropna().sort_index()


def _alinear(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    """Une dos series por fecha y conserva solo las fechas presentes en ambas."""
    return pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()


def tasa_por_periodo(tasa_anual: float, periodos_por_anio: int) -> float:
    """Convierte una tasa anual en la tasa equivalente de un periodo.

    Fórmula (tasa compuesta equivalente):
        r_periodo = (1 + r_anual)^(1 / periodos_por_anio) − 1

    Interpretación:
        Es la tasa que, reinvertida ``periodos_por_anio`` veces, da la tasa
        anual. Por ejemplo, 6.5 % anual equivale a ≈ 0.526 % mensual.

    Args:
        tasa_anual: Tasa anual en decimal (0.065 = 6.5 %).
        periodos_por_anio: 12 en mensual, 1 en anual.

    Returns:
        Tasa por periodo en decimal.

    Example:
        >>> round(tasa_por_periodo(0.12, 12), 6)
        0.009489
    """
    return (1 + tasa_anual) ** (1 / periodos_por_anio) - 1


# ---------------------------------------------------------------------------
# Rendimientos
# ---------------------------------------------------------------------------
def rendimientos(precios: pd.Series, tipo: str = "simple") -> pd.Series:
    """Rendimiento de cada periodo.

    Fórmulas:
        simple: r_t = P_t / P_{t−1} − 1
        log:    r_t = ln(P_t / P_{t−1})

    Interpretación:
        El rendimiento simple es el cambio porcentual del precio en el periodo
        (0.05 = subió 5 %). El logarítmico es casi igual para cambios pequeños
        y tiene la ventaja de que se puede sumar a lo largo del tiempo.
        Con precios ajustados, el rendimiento incluye dividendos.

    Args:
        precios: Precios indexados por fecha.
        tipo: ``"simple"`` o ``"log"``.

    Returns:
        Serie de rendimientos. Tiene un dato menos que ``precios`` (el primer
        periodo no tiene periodo anterior).

    Raises:
        ValueError: Si ``tipo`` no es ``"simple"`` ni ``"log"``.

    Example:
        >>> rendimientos(pd.Series([100.0, 110.0, 99.0])).round(2).tolist()
        [0.1, -0.1]
    """
    precios = _limpiar(precios)
    cociente = precios / precios.shift(1)
    if tipo == "simple":
        rend = cociente - 1
    elif tipo == "log":
        rend = np.log(cociente)
    else:
        raise ValueError(f"tipo debe ser 'simple' o 'log' (se recibió '{tipo}').")
    return rend.dropna().rename(precios.name)


def rendimiento_acumulado(rend: pd.Series) -> pd.Series:
    """Rendimiento acumulado hasta cada fecha.

    Fórmula:
        R_t = (1 + r_1) × (1 + r_2) × … × (1 + r_t) − 1 = Π(1 + r_i) − 1

    Interpretación:
        Cuánto ganó (o perdió) en total una inversión desde el inicio hasta la
        fecha t, reinvirtiendo todo. El último valor es el rendimiento total
        del periodo analizado. Ojo: los rendimientos se **multiplican**, no se
        suman: +50 % y luego −50 % deja −25 %, no 0 %.

    Args:
        rend: Rendimientos simples por periodo.

    Returns:
        Serie con el rendimiento acumulado en cada fecha.

    Example:
        >>> rendimiento_acumulado(pd.Series([0.5, -0.5])).tolist()
        [0.5, -0.25]
    """
    return (1 + _limpiar(rend)).cumprod() - 1


def crecimiento_capital(
    rend: pd.Series,
    capital: float,
    fecha_inicial: pd.Timestamp | str | None = None,
) -> pd.Series:
    """Valor en el tiempo de una inversión inicial.

    Fórmula:
        V_t = capital × Π(1 + r_i),  i = 1…t

    Interpretación:
        "Si hubiera invertido ``capital`` al inicio, ¿cuánto valdría en cada
        fecha?". Es la forma más intuitiva de comparar acciones: todas parten
        del mismo monto el mismo día.

    Args:
        rend: Rendimientos simples por periodo.
        capital: Monto inicial (en la moneda del activo).
        fecha_inicial: Si se da, agrega al inicio el punto ``(fecha_inicial,
            capital)`` para que la curva arranque exactamente en ``capital``.
            Normalmente es la fecha del primer precio.

    Returns:
        Serie con el valor de la inversión en cada fecha.

    Example:
        >>> crecimiento_capital(pd.Series([0.1, 0.1]), 100).round(2).tolist()
        [110.0, 121.0]
    """
    valores = capital * (1 + _limpiar(rend)).cumprod()
    if fecha_inicial is not None:
        inicio = pd.Series([float(capital)], index=[pd.Timestamp(fecha_inicial)], name=valores.name)
        valores = pd.concat([inicio, valores])
    return valores


def cagr(precios: pd.Series, periodos_por_anio: int) -> float:
    """CAGR: tasa de crecimiento anual compuesta (*compound annual growth rate*).

    Fórmula:
        CAGR = (P_final / P_inicial)^(1 / años) − 1
        años = n_periodos / periodos_por_anio

    donde ``n_periodos`` es el número de rendimientos, es decir, el número de
    precios menos uno (de diciembre a diciembre hay 12 periodos mensuales).

    Interpretación:
        La tasa anual constante que habría llevado del precio inicial al final.
        Un CAGR de 20 % no significa que cada año se ganó 20 %: es un promedio
        geométrico que "suaviza" años buenos y malos.

    Args:
        precios: Precios (o valores de una cartera) indexados por fecha.
        periodos_por_anio: 12 en mensual, 1 en anual.

    Returns:
        CAGR en decimal (0.2 = 20 %). ``NaN`` si hay menos de 2 precios o algún
        precio no es positivo.

    Example:
        >>> cagr(pd.Series([100.0, 200.0]), 1)  # se duplica en 1 año
        1.0
    """
    precios = _limpiar(precios)
    n_periodos = len(precios) - 1
    if n_periodos < 1:
        return math.nan
    p_inicial, p_final = float(precios.iloc[0]), float(precios.iloc[-1])
    if p_inicial <= 0 or p_final <= 0:
        return math.nan
    anios = n_periodos / periodos_por_anio
    return (p_final / p_inicial) ** (1 / anios) - 1


# ---------------------------------------------------------------------------
# Riesgo
# ---------------------------------------------------------------------------
def volatilidad_anualizada(rend: pd.Series, periodos_por_anio: int) -> float:
    """Volatilidad anualizada: desviación estándar de los rendimientos, en escala anual.

    Fórmula:
        σ_anual = σ(r) × √periodos_por_anio

    con σ(r) la desviación estándar muestral (``ddof = 1``). Se multiplica por
    la raíz porque, si los rendimientos son independientes, la varianza crece
    proporcional al tiempo.

    Interpretación:
        Qué tanto se alejan los rendimientos de su promedio. Una volatilidad de
        30 % indica que en un año "típico" el rendimiento pudo quedar unos 30
        puntos arriba o abajo del promedio. Más volatilidad = más incertidumbre,
        no necesariamente más pérdida.

    Args:
        rend: Rendimientos por periodo.
        periodos_por_anio: 12 en mensual, 1 en anual.

    Returns:
        Volatilidad anualizada en decimal. ``NaN`` si hay menos de 2 rendimientos.

    Example:
        >>> volatilidad_anualizada(pd.Series([0.01] * 24), 12)
        0.0
    """
    rend = _limpiar(rend)
    if len(rend) < 2:
        return math.nan
    sigma = float(rend.std(ddof=1))
    if sigma < _EPSILON:
        sigma = 0.0  # evita residuos de punto flotante (1e-18) en series constantes
    return sigma * math.sqrt(periodos_por_anio)


def serie_drawdown(precios: pd.Series) -> pd.Series:
    """Drawdown en cada fecha: caída desde el máximo previo.

    Fórmula:
        DD_t = P_t / máx(P_0, …, P_t) − 1

    Interpretación:
        Qué tan lejos está el precio de su mejor nivel hasta ese momento.
        0 % = está en máximo histórico; −30 % = vale 30 % menos que en su pico.
        Mide el dolor que vivió quien compró en el peor momento.

    Args:
        precios: Precios indexados por fecha.

    Returns:
        Serie de drawdowns (valores ≤ 0).

    Example:
        >>> serie_drawdown(pd.Series([100.0, 120.0, 60.0, 90.0])).tolist()
        [0.0, 0.0, -0.5, -0.25]
    """
    precios = _limpiar(precios)
    return precios / precios.cummax() - 1


def max_drawdown(precios: pd.Series) -> dict[str, float | pd.Timestamp | None]:
    """Máximo drawdown: la peor caída desde un pico, con sus fechas.

    Fórmula:
        MDD = mín_t(DD_t)

    El **pico** es la fecha del máximo previo al valle; el **valle** es la fecha
    del drawdown mínimo; la **recuperación** es la primera fecha posterior al
    valle en que el precio vuelve a alcanzar el nivel del pico.

    Interpretación:
        La peor pérdida que habría sufrido alguien que compró en el pico y vendió
        en el valle. Un MDD de −50 % requiere +100 % para recuperarse.

    Args:
        precios: Precios indexados por fecha.

    Returns:
        Dict con ``max_drawdown`` (decimal ≤ 0), ``fecha_pico``,
        ``fecha_valle`` y ``fecha_recuperacion`` (``None`` si no se ha
        recuperado). Si la serie está vacía, todo es ``NaN``/``None``.

    Example:
        >>> max_drawdown(pd.Series([100.0, 120.0, 60.0, 90.0]))["max_drawdown"]
        -0.5
    """
    precios = _limpiar(precios)
    if precios.empty:
        return {"max_drawdown": math.nan, "fecha_pico": None, "fecha_valle": None,
                "fecha_recuperacion": None}
    dd = serie_drawdown(precios)
    fecha_valle = dd.idxmin()
    fecha_pico = precios.loc[:fecha_valle].idxmax()
    nivel_pico = precios.loc[fecha_pico]
    despues = precios.loc[fecha_valle:]
    recuperado = despues[despues >= nivel_pico]
    return {
        "max_drawdown": float(dd.min()),
        "fecha_pico": fecha_pico,
        "fecha_valle": fecha_valle,
        "fecha_recuperacion": recuperado.index[0] if not recuperado.empty else None,
    }


def tiempo_recuperacion(precios: pd.Series) -> int | None:
    """Periodos que tardó el precio en recuperar su pico tras el máximo drawdown.

    Fórmula:
        periodos = posición(fecha_recuperacion) − posición(fecha_valle)

    Interpretación:
        Cuánto tiempo (en meses o años) pasó desde el peor punto hasta volver
        al máximo anterior. ``None`` significa que **todavía no se recupera**.

    Args:
        precios: Precios indexados por fecha.

    Returns:
        Número de periodos, o ``None`` si no se ha recuperado.

    Example:
        >>> tiempo_recuperacion(pd.Series([100.0, 120.0, 60.0, 90.0])) is None
        True
    """
    precios = _limpiar(precios)
    info = max_drawdown(precios)
    if info["fecha_recuperacion"] is None:
        return None
    posicion = precios.index.get_loc
    return int(posicion(info["fecha_recuperacion"]) - posicion(info["fecha_valle"]))


# ---------------------------------------------------------------------------
# Relación con el mercado
# ---------------------------------------------------------------------------
def beta(rend_activo: pd.Series, rend_benchmark: pd.Series) -> float:
    """Beta del activo contra su benchmark.

    Fórmula:
        β = Cov(r_a, r_m) / Var(r_m)

    Se usan solo las fechas presentes en ambas series.

    Interpretación:
        Cuánto se mueve el activo, en promedio, cuando el mercado se mueve 1 %.
        β = 1: igual que el mercado; β = 2: el doble; β = 0.5: la mitad.
        Es la pendiente de la recta de regresión de r_a contra r_m.

    Args:
        rend_activo: Rendimientos del activo.
        rend_benchmark: Rendimientos del benchmark, misma periodicidad.

    Returns:
        Beta. ``NaN`` si hay menos de 2 fechas en común o el benchmark no varía.

    Example:
        >>> m = pd.Series([0.01, -0.02, 0.03])
        >>> round(beta(2 * m, m), 6)
        2.0
    """
    datos = _alinear(rend_activo, rend_benchmark)
    if len(datos) < 2:
        return math.nan
    var_m = float(datos["b"].var(ddof=1))
    if var_m < _EPSILON**2:
        return math.nan
    return float(datos["a"].cov(datos["b"], ddof=1)) / var_m


def correlacion(rend_activo: pd.Series, rend_benchmark: pd.Series) -> float:
    """Correlación de Pearson entre los rendimientos del activo y del benchmark.

    Fórmula:
        ρ = Cov(r_a, r_m) / (σ_a × σ_m)

    Interpretación:
        Qué tan juntos se mueven, de −1 a 1. ρ = 1: siempre en la misma
        dirección y proporción; ρ = 0: sin relación lineal. Una correlación
        baja significa que la beta explica poco del movimiento del activo.

    Args:
        rend_activo: Rendimientos del activo.
        rend_benchmark: Rendimientos del benchmark.

    Returns:
        Correlación. ``NaN`` si hay menos de 2 fechas en común o alguna serie
        no varía.

    Example:
        >>> m = pd.Series([0.01, -0.02, 0.03])
        >>> round(correlacion(2 * m, m), 6)
        1.0
    """
    datos = _alinear(rend_activo, rend_benchmark)
    if len(datos) < 2:
        return math.nan
    return float(datos["a"].corr(datos["b"]))


def sharpe(rend: pd.Series, tasa_libre_anual: float, periodos_por_anio: int) -> float:
    """Sharpe ratio anualizado: rendimiento extra por unidad de riesgo.

    Fórmula:
        Sharpe = [media(r_t − r_f) / σ(r_t)] × √periodos_por_anio
        r_f = (1 + tasa_libre_anual)^(1 / periodos_por_anio) − 1

    Interpretación:
        Cuánto rendimiento por encima de la tasa libre de riesgo se obtuvo por
        cada unidad de volatilidad. Sharpe > 1 suele considerarse bueno;
        Sharpe ≈ 0 significa que no se ganó más que la tasa libre de riesgo.
        **Simplificación:** se usa una tasa libre de riesgo constante para todo
        el periodo, aunque en la realidad cambió con el tiempo.

    Args:
        rend: Rendimientos simples por periodo.
        tasa_libre_anual: Tasa libre de riesgo anual en decimal, en la misma
            moneda que el activo.
        periodos_por_anio: 12 en mensual, 1 en anual.

    Returns:
        Sharpe ratio anualizado. ``NaN`` si hay menos de 2 rendimientos o la
        volatilidad es cero.

    Example:
        >>> rf = tasa_por_periodo(0.12, 12)
        >>> round(sharpe(pd.Series([rf + 0.01, rf - 0.01] * 6), 0.12, 12), 6)
        0.0
    """
    rend = _limpiar(rend)
    if len(rend) < 2:
        return math.nan
    sigma = float(rend.std(ddof=1))
    if sigma < _EPSILON:
        return math.nan
    r_f = tasa_por_periodo(tasa_libre_anual, periodos_por_anio)
    return float((rend - r_f).mean()) / sigma * math.sqrt(periodos_por_anio)


# ---------------------------------------------------------------------------
# Media móvil y backtest
# ---------------------------------------------------------------------------
def sma(precios: pd.Series, ventana: int) -> pd.Series:
    """Media móvil simple (SMA, *simple moving average*).

    Fórmula:
        SMA_t = (P_t + P_{t−1} + … + P_{t−n+1}) / n

    donde ``n`` es la ventana en periodos (meses o años, según la
    periodicidad elegida).

    Interpretación:
        Es el precio promedio de los últimos ``n`` periodos. Suaviza el ruido y
        deja ver la tendencia: cuando el precio está por encima de su SMA, el
        precio actual es mayor que su promedio reciente. Los primeros ``n − 1``
        valores son ``NaN`` porque todavía no hay ``n`` datos para promediar.

    Args:
        precios: Serie de precios indexada por fecha.
        ventana: Número de periodos a promediar (``n``). Debe ser ≥ 1.

    Returns:
        Serie con la SMA, mismo índice que ``precios``.

    Raises:
        ValueError: Si ``ventana`` es menor que 1.

    Example:
        >>> sma(pd.Series([1.0, 2.0, 3.0, 4.0]), 2).tolist()
        [nan, 1.5, 2.5, 3.5]
    """
    if ventana < 1:
        raise ValueError(f"La ventana de la SMA debe ser ≥ 1 (se recibió {ventana}).")
    return precios.rolling(window=ventana, min_periods=ventana).mean()


@dataclass
class ResultadoBacktest:
    """Resultado de ``backtest_sma``.

    Attributes:
        curvas: Valor de la inversión en cada fecha, columnas ``regla_sma`` y
            ``buy_and_hold``. La primera fila es el capital inicial.
        senal: ``True`` si la regla estuvo invertida en ese periodo.
        rend_regla: Rendimientos por periodo de la regla SMA.
        rend_buy_and_hold: Rendimientos por periodo de buy & hold.
        resumen: Tabla con filas ``regla_sma`` y ``buy_and_hold`` y columnas
            ``cagr``, ``max_drawdown``, ``sharpe`` y ``pct_invertido``.
        advertencias: Mensajes para mostrar si faltan datos.
    """

    curvas: pd.DataFrame
    senal: pd.Series
    rend_regla: pd.Series
    rend_buy_and_hold: pd.Series
    resumen: pd.DataFrame
    advertencias: list[str] = field(default_factory=list)


def _resumen_vacio() -> pd.DataFrame:
    """Tabla de resumen del backtest llena de ``NaN``."""
    return pd.DataFrame(
        math.nan,
        index=pd.Index(["regla_sma", "buy_and_hold"], name="estrategia"),
        columns=["cagr", "max_drawdown", "sharpe", "pct_invertido"],
    )


def backtest_sma(
    precios: pd.Series,
    ventana: int,
    tasa_libre_anual: float,
    periodos_por_anio: int,
    capital: float = 10_000,
) -> ResultadoBacktest:
    """Backtest de una regla de media móvil contra buy & hold, sin información del futuro.

    Regla:
        En el periodo t la regla está **invertida** solo si el cierre de t−1
        fue mayor que la SMA de t−1. Si no, el dinero rinde la tasa libre de
        riesgo de ese periodo:

        señal_t       = P_{t−1} > SMA_{t−1}
        r_regla,t     = r_t     si señal_t
                        r_f     si no

    La decisión se toma con información disponible al **cierre del periodo
    anterior**; usar el cierre de t para decidir si se está invertido en t
    sería *leakage* (usar el futuro). El backtest empieza en el primer periodo
    cuya decisión ya tiene SMA, y buy & hold se mide sobre el mismo tramo.

    Supuestos: sin comisiones, sin impuestos, sin deslizamiento de precios y
    con una tasa libre de riesgo constante. Rendimientos pasados no garantizan
    rendimientos futuros.

    Args:
        precios: Precios de cierre por periodo (solo periodos completos).
        ventana: Ventana de la SMA en periodos.
        tasa_libre_anual: Tasa libre de riesgo anual en decimal.
        periodos_por_anio: 12 en mensual, 1 en anual.
        capital: Capital inicial de ambas estrategias.

    Returns:
        ``ResultadoBacktest`` con curvas, señal, rendimientos, resumen y
        advertencias. Si no hay periodos suficientes, las tablas vienen
        vacías o con ``NaN`` y ``advertencias`` explica por qué.

    Example:
        >>> res = backtest_sma(precios_mensuales, 10, 0.065, 12)
        >>> res.resumen.loc["regla_sma", "pct_invertido"]
    """
    precios = _limpiar(precios)
    advertencias: list[str] = []
    n = len(precios)
    if n <= ventana:
        advertencias.append(
            f"No se puede correr el backtest: hay {n} periodos completos y la SMA de "
            f"{ventana} periodos necesita al menos {ventana + 1} (la ventana más un "
            "periodo para decidir). Reduce la ventana o amplía el rango de fechas."
        )
        vacia = pd.Series(dtype=float)
        return ResultadoBacktest(
            curvas=pd.DataFrame(columns=["regla_sma", "buy_and_hold"], dtype=float),
            senal=pd.Series(dtype=bool), rend_regla=vacia, rend_buy_and_hold=vacia,
            resumen=_resumen_vacio(), advertencias=advertencias,
        )

    media = sma(precios, ventana)
    rend = rendimientos(precios)

    # Señal del periodo t con datos de t−1: shift(1) "mueve" el cierre y la SMA un periodo adelante.
    senal = (precios.shift(1) > media.shift(1)).astype(bool)

    # La primera decisión posible es en la posición `ventana` (la SMA existe desde `ventana − 1`).
    fecha_base = precios.index[ventana - 1]
    inicio = precios.index[ventana]
    senal = senal.loc[inicio:].rename("invertido")
    rend_bh = rend.loc[inicio:].rename("buy_and_hold")
    r_f = tasa_por_periodo(tasa_libre_anual, periodos_por_anio)
    rend_regla = rend_bh.where(senal, r_f).rename("regla_sma")

    curvas = pd.DataFrame({
        "regla_sma": crecimiento_capital(rend_regla, capital, fecha_base),
        "buy_and_hold": crecimiento_capital(rend_bh, capital, fecha_base),
    })
    curvas.index.name = "fecha"

    resumen = _resumen_vacio()
    resumen.loc["regla_sma", "pct_invertido"] = float(senal.mean())
    resumen.loc["buy_and_hold", "pct_invertido"] = 1.0
    resumen.loc["regla_sma", "max_drawdown"] = max_drawdown(curvas["regla_sma"])["max_drawdown"]
    resumen.loc["buy_and_hold", "max_drawdown"] = max_drawdown(curvas["buy_and_hold"])["max_drawdown"]

    anios = len(rend_bh) / periodos_por_anio
    if anios < MINIMO_ANIOS:
        advertencias.append(
            f"El backtest cubre solo {len(rend_bh)} periodos ({anios:.1f} años) después de "
            f"formar la SMA. Se necesitan al menos {MINIMO_ANIOS:.0f} años para reportar "
            "CAGR y Sharpe ratio; se muestran como NaN."
        )
    else:
        for nombre, r in [("regla_sma", rend_regla), ("buy_and_hold", rend_bh)]:
            resumen.loc[nombre, "cagr"] = cagr(curvas[nombre], periodos_por_anio)
            resumen.loc[nombre, "sharpe"] = sharpe(r, tasa_libre_anual, periodos_por_anio)

    return ResultadoBacktest(curvas, senal, rend_regla, rend_bh, resumen, advertencias)


# ---------------------------------------------------------------------------
# Resúmenes
# ---------------------------------------------------------------------------
def resumen_metricas(
    precios: pd.Series,
    periodos_por_anio: int,
    tasa_libre_anual: float,
    precios_benchmark: pd.Series | None = None,
) -> dict:
    """Todas las métricas de un ticker en un dict (lo que usan los KPIs).

    Valida que haya al menos ``MINIMO_ANIOS`` años de rendimientos. Si no,
    CAGR, volatilidad, Sharpe ratio, beta y correlación quedan en ``NaN`` y se
    agrega una advertencia (el drawdown y el rendimiento total sí se reportan,
    porque describen lo que pasó y no son estimaciones).

    Args:
        precios: Cierres por periodo del ticker (solo periodos completos).
        periodos_por_anio: 12 en mensual, 1 en anual.
        tasa_libre_anual: Tasa libre de riesgo anual de la moneda del ticker.
        precios_benchmark: Cierres por periodo del benchmark (opcional, para
            beta y correlación).

    Returns:
        Dict con las llaves ``fecha_inicio``, ``fecha_fin``, ``n_periodos``,
        ``anios``, ``rendimiento_total``, ``cagr``, ``volatilidad``,
        ``sharpe``, ``beta``, ``correlacion``, ``max_drawdown``,
        ``fecha_pico``, ``fecha_valle``, ``fecha_recuperacion``,
        ``tiempo_recuperacion`` y ``advertencias`` (lista de textos).

    Example:
        >>> r = resumen_metricas(cierres_nvda, 12, 0.0403, cierres_sp500)
        >>> f"{r['cagr']:.1%}"
    """
    precios = _limpiar(precios)
    rend = rendimientos(precios)
    n = len(rend)
    anios = n / periodos_por_anio
    dd = max_drawdown(precios)
    advertencias: list[str] = []

    resultado: dict = {
        "fecha_inicio": precios.index[0] if not precios.empty else None,
        "fecha_fin": precios.index[-1] if not precios.empty else None,
        "n_periodos": n,
        "anios": anios,
        "rendimiento_total": (float(precios.iloc[-1] / precios.iloc[0] - 1)
                              if len(precios) >= 2 else math.nan),
        "cagr": math.nan,
        "volatilidad": math.nan,
        "sharpe": math.nan,
        "beta": math.nan,
        "correlacion": math.nan,
        "max_drawdown": dd["max_drawdown"],
        "fecha_pico": dd["fecha_pico"],
        "fecha_valle": dd["fecha_valle"],
        "fecha_recuperacion": dd["fecha_recuperacion"],
        "tiempo_recuperacion": tiempo_recuperacion(precios),
        "advertencias": advertencias,
    }

    if anios < MINIMO_ANIOS:
        advertencias.append(
            f"Solo hay {n} periodos completos ({anios:.1f} años). Se necesitan al menos "
            f"{MINIMO_ANIOS:.0f} años para reportar CAGR, volatilidad, Sharpe ratio y beta; "
            "se muestran como NaN."
        )
        return resultado

    resultado["cagr"] = cagr(precios, periodos_por_anio)
    resultado["volatilidad"] = volatilidad_anualizada(rend, periodos_por_anio)
    resultado["sharpe"] = sharpe(rend, tasa_libre_anual, periodos_por_anio)

    if precios_benchmark is not None:
        rend_b = rendimientos(precios_benchmark)
        comunes = len(_alinear(rend, rend_b))
        if comunes / periodos_por_anio < MINIMO_ANIOS:
            advertencias.append(
                f"Solo hay {comunes} periodos en común con el benchmark; beta y "
                "correlación se muestran como NaN."
            )
        else:
            resultado["beta"] = beta(rend, rend_b)
            resultado["correlacion"] = correlacion(rend, rend_b)
    return resultado


def tabla_tidy_para_bi(
    velas: pd.DataFrame,
    periodos_por_anio: int,
    tasas_por_ticker: dict[str, float] | None = None,
    benchmark_por_ticker: dict[str, str] | None = None,
    ventana_sma: int | None = None,
    capital: float = 10_000,
) -> pd.DataFrame:
    """Tabla larga (fecha, ticker, metrica, valor) lista para Looker Studio, Power BI o Tableau.

    Formato *tidy* o "largo": una fila por combinación de fecha, ticker y
    métrica. Es el formato que mejor aceptan las herramientas de BI, porque
    "metrica" se vuelve un filtro y "valor" la medida.

    Métricas por fecha (series de tiempo):
        ``precio_cierre``, ``rendimiento``, ``rendimiento_acumulado``,
        ``valor_inversion``, ``drawdown`` y ``sma_<ventana>`` (si se da
        ``ventana_sma``).

    Métricas resumen (una fila por ticker, con la última fecha del periodo):
        ``cagr``, ``volatilidad_anualizada``, ``max_drawdown``, ``sharpe``,
        ``beta`` y ``correlacion`` (las dos últimas solo si el benchmark está
        en ``velas``).

    Args:
        velas: Velas tidy de ``resamplear_ohlc`` **solo con periodos completos**.
        periodos_por_anio: 12 en mensual, 1 en anual.
        tasas_por_ticker: Tasa libre de riesgo anual de cada ticker. Sin ella,
            el Sharpe ratio queda en ``NaN``.
        benchmark_por_ticker: Benchmark de cada ticker (``{"NVDA": "^GSPC"}``).
        ventana_sma: Ventana de la SMA a incluir, o ``None`` para omitirla.
        capital: Capital inicial para ``valor_inversion``.

    Returns:
        DataFrame con columnas ``fecha, ticker, metrica, valor``.

    Example:
        >>> tidy = tabla_tidy_para_bi(completas, 12, {"NVDA": 0.0403}, {"NVDA": "^GSPC"}, 10)
        >>> tidy["metrica"].unique()
    """
    tasas_por_ticker = tasas_por_ticker or {}
    benchmark_por_ticker = benchmark_por_ticker or {}
    cierres = {t: g.set_index("fecha")["close"].sort_index() for t, g in velas.groupby("ticker")}
    filas: list[pd.DataFrame] = []

    def agregar(serie: pd.Series, ticker: str, metrica: str) -> None:
        if serie.empty:
            return
        filas.append(pd.DataFrame({"fecha": serie.index, "ticker": ticker,
                                   "metrica": metrica, "valor": serie.to_numpy(dtype=float)}))

    for ticker, precios in cierres.items():
        rend = rendimientos(precios)
        agregar(precios, ticker, "precio_cierre")
        agregar(rend, ticker, "rendimiento")
        agregar(rendimiento_acumulado(rend), ticker, "rendimiento_acumulado")
        agregar(crecimiento_capital(rend, capital, precios.index[0]), ticker, "valor_inversion")
        agregar(serie_drawdown(precios), ticker, "drawdown")
        if ventana_sma:
            agregar(sma(precios, ventana_sma).dropna(), ticker, f"sma_{ventana_sma}")

        benchmark = benchmark_por_ticker.get(ticker)
        resumen = resumen_metricas(
            precios, periodos_por_anio, tasas_por_ticker.get(ticker, math.nan),
            cierres.get(benchmark) if benchmark and benchmark != ticker else None,
        )
        resumen_series = pd.Series({
            "cagr": resumen["cagr"],
            "volatilidad_anualizada": resumen["volatilidad"],
            "max_drawdown": resumen["max_drawdown"],
            "sharpe": resumen["sharpe"],
            "beta": resumen["beta"],
            "correlacion": resumen["correlacion"],
        })
        filas.append(pd.DataFrame({"fecha": precios.index[-1], "ticker": ticker,
                                   "metrica": resumen_series.index,
                                   "valor": resumen_series.to_numpy(dtype=float)}))

    if not filas:
        return pd.DataFrame(columns=["fecha", "ticker", "metrica", "valor"])
    tidy = pd.concat(filas, ignore_index=True)
    return tidy.sort_values(["ticker", "metrica", "fecha"]).reset_index(drop=True)
