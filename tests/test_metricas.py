"""Pruebas de las fórmulas de metricas.py y del resampling de datos.py con casos de resultado conocido. Código generado con un agente de IA (Claude Code) con fines educativos.

Ejecuta desde la raíz del repo:

    pytest
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import datos
import metricas


def mensual(valores: list[float], inicio: str = "2020-01-31") -> pd.Series:
    """Serie con índice de fin de mes, para simular cierres mensuales."""
    return pd.Series(valores, index=pd.date_range(inicio, periods=len(valores), freq="ME"), dtype=float)


# ---------------------------------------------------------------------------
# Casos mínimos pedidos en CLAUDE.md
# ---------------------------------------------------------------------------
def test_cagr_serie_que_se_duplica_en_un_anio_es_100_por_ciento() -> None:
    """Una serie mensual que pasa de 100 a 200 en 12 meses tiene CAGR = 100 %."""
    # 13 cierres mensuales = 12 periodos = exactamente 1 año, de 100 a 200.
    precios = mensual(list(100 * 2 ** (np.arange(13) / 12)))
    assert metricas.cagr(precios, periodos_por_anio=12) == pytest.approx(1.0)


def test_cagr_anual_duplica_en_un_anio() -> None:
    """En periodicidad anual, duplicarse en un periodo (1 año) da CAGR = 100 %."""
    assert metricas.cagr(pd.Series([100.0, 200.0]), periodos_por_anio=1) == pytest.approx(1.0)


def test_volatilidad_de_rendimiento_constante_es_cero() -> None:
    """Si el rendimiento es el mismo cada mes, no hay variación: volatilidad = 0."""
    precios = mensual(list(100 * 1.01 ** np.arange(36)))  # +1 % cada mes, sin variación
    rend = metricas.rendimientos(precios)
    assert metricas.volatilidad_anualizada(rend, 12) == pytest.approx(0.0, abs=1e-12)


def test_drawdown_100_120_60_90() -> None:
    """Precios [100, 120, 60, 90]: máx. drawdown = −50 % (de 120 a 60) y todavía no se recupera."""
    precios = mensual([100, 120, 60, 90])
    info = metricas.max_drawdown(precios)
    assert info["max_drawdown"] == pytest.approx(-0.5)
    assert info["fecha_pico"] == precios.index[1]
    assert info["fecha_valle"] == precios.index[2]
    assert info["fecha_recuperacion"] is None
    assert metricas.tiempo_recuperacion(precios) is None
    assert metricas.serie_drawdown(precios).tolist() == pytest.approx([0, 0, -0.5, -0.25])


def test_beta_2x_es_2_y_correlacion_1() -> None:
    """Si el activo rinde exactamente 2 veces el benchmark, beta = 2 y correlación = 1."""
    rng = np.random.default_rng(42)
    rend_benchmark = mensual(list(rng.normal(0.01, 0.04, 60)))
    rend_activo = 2 * rend_benchmark
    assert metricas.beta(rend_activo, rend_benchmark) == pytest.approx(2.0)
    assert metricas.correlacion(rend_activo, rend_benchmark) == pytest.approx(1.0)


def test_sharpe_con_rendimiento_igual_a_tasa_libre_es_cero() -> None:
    """Si el rendimiento promedio es igual a la tasa libre de riesgo, el Sharpe ratio es ≈ 0."""
    tasa_anual = 0.065
    r_f = metricas.tasa_por_periodo(tasa_anual, 12)
    # Rendimiento promedio = r_f exactamente, con variación para que σ > 0.
    rend = mensual([r_f + 0.02, r_f - 0.02] * 18)
    assert metricas.sharpe(rend, tasa_anual, 12) == pytest.approx(0.0, abs=1e-9)


def test_sma_1_2_3_4_ventana_2() -> None:
    """SMA de [1, 2, 3, 4] con ventana 2 = [NaN, 1.5, 2.5, 3.5]."""
    resultado = metricas.sma(pd.Series([1.0, 2.0, 3.0, 4.0]), 2)
    assert math.isnan(resultado.iloc[0])
    assert resultado.iloc[1:].tolist() == pytest.approx([1.5, 2.5, 3.5])


def test_backtest_sin_leakage_no_captura_el_salto() -> None:
    """Un salto en t solo se captura si la señal usara el cierre de t (leakage)."""
    # Precio que baja de 110 a 100 (siempre bajo su SMA) y luego salta a 200.
    precios = mensual([110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 200, 200, 200])
    ventana = 3
    t_salto = precios.index[11]

    res = metricas.backtest_sma(precios, ventana, tasa_libre_anual=0.0, periodos_por_anio=12)

    # Con el cierre de t−1 (100) contra la SMA de t−1 (101) la regla está fuera.
    assert not res.senal.loc[t_salto]
    assert res.rend_regla.loc[t_salto] == pytest.approx(0.0)
    assert res.rend_buy_and_hold.loc[t_salto] == pytest.approx(1.0)
    # La regla nunca ganó nada (tasa libre 0) y buy & hold sí capturó el salto.
    assert res.curvas["regla_sma"].iloc[-1] == pytest.approx(10_000)
    assert res.curvas["buy_and_hold"].iloc[-1] > res.curvas["regla_sma"].iloc[-1]

    # Control: una regla CON leakage (usa el cierre de t) sí lo habría capturado.
    media = metricas.sma(precios, ventana)
    assert bool(precios.loc[t_salto] > media.loc[t_salto])


def test_resamplear_ohlc_mensual() -> None:
    """Diario a mensual: open = primer valor del mes, close = último, high y low = extremos, volume = suma."""
    fechas = pd.bdate_range("2024-01-01", "2024-02-29")
    n = len(fechas)
    diario = pd.DataFrame({
        "fecha": fechas,
        "ticker": "PRUEBA",
        "open": np.arange(n) + 10.0,
        "high": np.arange(n) + 20.0,
        "low": np.arange(n) + 5.0,
        "close": np.arange(n) + 15.0,
        "volume": np.ones(n, dtype=int) * 100,
    })
    diario.loc[diario["fecha"] == "2024-01-10", "high"] = 999.0  # máximo de enero a media semana
    diario.loc[diario["fecha"] == "2024-01-17", "low"] = 1.0     # mínimo de enero a media semana

    velas = datos.resamplear_ohlc(diario, "Mensual")
    enero = diario[diario["fecha"].dt.month == 1]
    v_ene = velas[velas["fecha"] == "2024-01-31"].iloc[0]

    assert len(velas) == 2
    assert v_ene["open"] == enero["open"].iloc[0]     # primer valor del mes
    assert v_ene["close"] == enero["close"].iloc[-1]  # último valor del mes
    assert v_ene["high"] == 999.0
    assert v_ene["low"] == 1.0
    assert v_ene["volume"] == 100 * len(enero)


# ---------------------------------------------------------------------------
# Pruebas adicionales
# ---------------------------------------------------------------------------
def test_resamplear_es_por_ticker() -> None:
    """El resampling se hace por ticker: los precios de dos tickers no se mezclan."""
    fechas = pd.bdate_range("2024-01-01", "2024-01-31")
    partes = [pd.DataFrame({"fecha": fechas, "ticker": t, "open": base, "high": base + 1,
                            "low": base - 1, "close": base, "volume": 1})
              for t, base in [("A", 10.0), ("B", 50.0)]]
    velas = datos.resamplear_ohlc(pd.concat(partes), "Mensual")
    assert velas.set_index("ticker")["close"].to_dict() == {"A": 10.0, "B": 50.0}


def test_periodo_en_curso_se_marca_incompleto() -> None:
    """El último mes o año se marca ``completo = False`` si sus datos no llegan a su último día hábil."""
    def diario_hasta(fin: str) -> pd.DataFrame:
        fechas = pd.bdate_range("2024-01-01", fin)
        return pd.DataFrame({"fecha": fechas, "ticker": "X", "open": 1.0, "high": 1.0,
                             "low": 1.0, "close": 1.0, "volume": 1})

    a_medio_mes = datos.resamplear_ohlc(diario_hasta("2024-02-15"), "Mensual")
    assert a_medio_mes["completo"].tolist() == [True, False]
    assert len(datos.velas_completas(a_medio_mes)) == 1

    # 2024-02-29 (jueves) es el último día hábil de febrero: periodo completo.
    fin_de_mes = datos.resamplear_ohlc(diario_hasta("2024-02-29"), "Mensual")
    assert fin_de_mes["completo"].tolist() == [True, True]

    anual = datos.resamplear_ohlc(diario_hasta("2024-02-29"), "Anual")
    assert anual["completo"].tolist() == [False]


def test_rendimientos_simple_y_log() -> None:
    """Rendimiento simple = P_t / P_{t−1} − 1 y logarítmico = ln(P_t / P_{t−1}); otro tipo da error."""
    precios = pd.Series([100.0, 110.0, 99.0])
    assert metricas.rendimientos(precios).tolist() == pytest.approx([0.10, -0.10])
    assert metricas.rendimientos(precios, "log").tolist() == pytest.approx(
        [math.log(1.1), math.log(0.9)])
    with pytest.raises(ValueError):
        metricas.rendimientos(precios, "otro")


def test_rendimiento_acumulado_multiplica_no_suma() -> None:
    """+50 % y luego −50 % deja −25 %, no 0 %: los rendimientos se multiplican."""
    assert metricas.rendimiento_acumulado(pd.Series([0.5, -0.5])).tolist() == pytest.approx([0.5, -0.25])


def test_crecimiento_capital_arranca_en_el_capital() -> None:
    """La curva de 10,000 empieza en 10,000 en la fecha inicial y crece con cada rendimiento."""
    precios = mensual([100, 110, 121])
    curva = metricas.crecimiento_capital(metricas.rendimientos(precios), 10_000, precios.index[0])
    assert curva.tolist() == pytest.approx([10_000, 11_000, 12_100])
    assert curva.index[0] == precios.index[0]


def test_tiempo_recuperacion_cuando_si_se_recupera() -> None:
    """Precios [100, 120, 60, 90, 130]: del valle (60) a superar el pico (120) pasan 2 periodos."""
    precios = mensual([100, 120, 60, 90, 130])
    assert metricas.tiempo_recuperacion(precios) == 2
    assert metricas.max_drawdown(precios)["fecha_recuperacion"] == precios.index[4]


def test_beta_alinea_fechas() -> None:
    """La beta solo usa las fechas que tienen las dos series."""
    m = mensual([0.01, -0.02, 0.03, 0.00, 0.02])
    a = 2 * m.iloc[1:]  # el activo no tiene la primera fecha
    assert metricas.beta(a, m) == pytest.approx(2.0)


def test_recta_regresion_recupera_alfa_y_beta() -> None:
    """Si r_a = 0.001 + 2·r_m, la recta de regresión da alfa = 0.001 y beta = 2."""
    m = mensual([0.01, -0.02, 0.03, 0.00, 0.02, -0.01])
    recta = metricas.recta_regresion(0.001 + 2 * m, m)
    assert recta["alfa"] == pytest.approx(0.001)
    assert recta["beta"] == pytest.approx(2.0)
    assert recta["x"] == pytest.approx([-0.02, 0.03])
    assert recta["y"] == pytest.approx([0.001 + 2 * -0.02, 0.001 + 2 * 0.03])


def test_backtest_fuera_del_mercado_rinde_tasa_libre() -> None:
    """Si la regla nunca está invertida, rinde exactamente la tasa libre de riesgo."""
    precios = mensual(list(np.linspace(200, 100, 40)))  # siempre bajando: nunca invertido
    res = metricas.backtest_sma(precios, 5, tasa_libre_anual=0.12, periodos_por_anio=12)
    r_f = metricas.tasa_por_periodo(0.12, 12)
    assert not res.senal.any()
    assert res.rend_regla.tolist() == pytest.approx([r_f] * len(res.rend_regla))
    assert res.resumen.loc["regla_sma", "pct_invertido"] == 0.0
    assert res.resumen.loc["regla_sma", "cagr"] == pytest.approx(0.12)


def test_backtest_con_pocos_periodos_regresa_advertencia() -> None:
    """Con menos periodos que la ventana de la SMA, el backtest regresa NaN y una advertencia."""
    anual = pd.Series([100.0, 110, 120, 130], index=pd.date_range("2020", periods=4, freq="YE"))
    res = metricas.backtest_sma(anual, ventana=10, tasa_libre_anual=0.05, periodos_por_anio=1)
    assert res.advertencias
    assert res.resumen.isna().all().all()


def test_resumen_metricas_con_menos_de_dos_anios() -> None:
    """Con menos de 2 años, CAGR y Sharpe ratio son NaN con advertencia, pero el drawdown sí se reporta."""
    precios = mensual(list(100 + np.arange(13)))  # 12 rendimientos = 1 año
    resumen = metricas.resumen_metricas(precios, 12, 0.065)
    assert math.isnan(resumen["cagr"])
    assert math.isnan(resumen["sharpe"])
    assert resumen["advertencias"]
    assert not math.isnan(resumen["max_drawdown"])  # el drawdown sí se reporta


def test_resumen_metricas_con_un_solo_periodo_no_inventa_drawdown() -> None:
    """Con un solo precio no hay caída que medir: el drawdown es NaN, no 0 %."""
    resumen = metricas.resumen_metricas(mensual([100.0]), 12, 0.065)
    assert math.isnan(resumen["max_drawdown"])
    assert resumen["advertencias"]


def test_resumen_metricas_completo() -> None:
    """Con 5 años de datos y un activo que rinde 1.5 veces el benchmark, el resumen sale completo y sin advertencias."""
    rng = np.random.default_rng(7)
    rend_m = rng.normal(0.008, 0.04, 60)
    benchmark = mensual(list(100 * np.cumprod(1 + np.r_[0, rend_m])))
    activo = mensual(list(100 * np.cumprod(1 + np.r_[0, 1.5 * rend_m])))
    resumen = metricas.resumen_metricas(activo, 12, 0.04, benchmark)
    assert resumen["advertencias"] == []
    assert resumen["n_periodos"] == 60
    assert resumen["n_benchmark"] == 60  # rendimientos en común para estimar la beta
    assert resumen["beta"] == pytest.approx(1.5)
    assert resumen["correlacion"] == pytest.approx(1.0)
    assert resumen["cagr"] == pytest.approx(metricas.cagr(activo, 12))


def test_tabla_tidy_para_bi() -> None:
    """La tabla para BI tiene formato largo (fecha, ticker, metrica, valor) y su CAGR coincide con la fórmula."""
    fechas = pd.date_range("2020-01-31", periods=30, freq="ME")
    velas = pd.concat([
        pd.DataFrame({"fecha": fechas, "ticker": t, "close": base * 1.01 ** np.arange(30)})
        for t, base in [("ACCION", 10.0), ("INDICE", 100.0)]
    ])
    tidy = metricas.tabla_tidy_para_bi(velas, 12, {"ACCION": 0.04}, {"ACCION": "INDICE"}, ventana_sma=3)
    assert list(tidy.columns) == ["fecha", "ticker", "metrica", "valor"]
    metricas_accion = set(tidy.loc[tidy["ticker"] == "ACCION", "metrica"])
    assert {"precio_cierre", "rendimiento", "valor_inversion", "drawdown", "sma_3",
            "cagr", "sharpe", "beta"} <= metricas_accion
    cagr_bi = tidy.query("ticker == 'ACCION' and metrica == 'cagr'")["valor"].iloc[0]
    assert cagr_bi == pytest.approx(1.01 ** 12 - 1)


def test_tabla_tidy_incluye_backtest() -> None:
    """El CSV trae las curvas y la señal del backtest, iguales a las de ``backtest_sma``."""
    fechas = pd.date_range("2020-01-31", periods=30, freq="ME")
    cierres = 100 * np.cumprod(1 + np.tile([0.05, -0.04, 0.03, -0.06, 0.02], 6))
    velas = pd.concat([
        pd.DataFrame({"fecha": fechas, "ticker": "ACCION", "close": cierres}),
        pd.DataFrame({"fecha": fechas, "ticker": "INDICE", "close": 100 * 1.01 ** np.arange(30)}),
    ])
    tidy = metricas.tabla_tidy_para_bi(velas, 12, {"ACCION": 0.04}, {"ACCION": "INDICE"},
                                       ventana_sma=3, capital=10_000)
    bt = metricas.backtest_sma(pd.Series(cierres, index=fechas), 3, 0.04, 12, 10_000)

    def serie(metrica: str) -> pd.Series:
        filas = tidy.query("ticker == 'ACCION' and metrica == @metrica")
        return pd.Series(filas["valor"].to_numpy(), index=pd.DatetimeIndex(filas["fecha"]))

    np.testing.assert_allclose(serie("valor_buy_hold"), bt.curvas["buy_and_hold"])
    np.testing.assert_allclose(serie("valor_regla_sma"), bt.curvas["regla_sma"])
    assert serie("valor_regla_sma").iloc[0] == 10_000  # arranca con el capital inicial
    senal = serie("senal_sma")
    assert set(senal.unique()) == {0.0, 1.0}  # la regla estuvo dentro y fuera
    assert (senal.index == bt.senal.index).all()
    assert (senal.to_numpy() == bt.senal.astype(float).to_numpy()).all()
    # INDICE no tiene tasa libre de riesgo: sin ella no hay backtest.
    assert not tidy.query("ticker == 'INDICE' and metrica == 'senal_sma'").shape[0]
