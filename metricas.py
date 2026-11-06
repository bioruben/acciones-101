"""Métricas financieras implementadas a mano (funciones puras, sin Streamlit). Código generado con un agente de IA (Claude Code) con fines educativos.

Todas las funciones reciben ``pd.Series`` indexadas por fecha y no dependen de
Streamlit, así que se pueden probar con ``pytest`` o usar en un notebook.

Etapa 1: solo está la media móvil simple (SMA), que usa la pestaña «Velas».
El resto de las métricas se agrega en la Etapa 2 del plan de trabajo.
"""

from __future__ import annotations

import pandas as pd


def sma(precios: pd.Series, ventana: int) -> pd.Series:
    """Media móvil simple (SMA, *simple moving average*).

    Fórmula:
        SMA_t = (P_t + P_{t-1} + ... + P_{t-n+1}) / n

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
