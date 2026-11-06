"""Descarga de precios con yfinance, respaldo en CSV y cambio de periodicidad. Código generado con un agente de IA (Claude Code) con fines educativos.

Flujo de datos:

1. ``descargar_precios()`` pide precios diarios ajustados a Yahoo Finance.
2. ``cargar_respaldo()`` lee ``data/respaldo_precios.csv``.
3. ``obtener_precios()`` intenta (1) y completa con (2) solo lo que falte.
4. ``resamplear_ohlc()`` pasa de datos diarios a mensuales o anuales.

Todos los DataFrames de precios usan formato *tidy* (largo): una fila por
(fecha, ticker) con las columnas ``fecha, ticker, open, high, low, close, volume``.
Este módulo no importa Streamlit: se puede usar desde un notebook o un script.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

import config

COLUMNAS: list[str] = ["fecha", "ticker", "open", "high", "low", "close", "volume"]


def _configurar_certificados_windows() -> None:
    """Evita un error de SSL de yfinance en Windows cuando la ruta tiene acentos.

    yfinance se conecta con ``curl_cffi``. En Windows, si la ruta del archivo de
    certificados de ``certifi`` tiene caracteres no ASCII (por ejemplo, una
    carpeta llamada "Visualización") y Python corre en modo UTF-8
    (``PYTHONUTF8=1``), curl no logra abrir el archivo y todas las descargas
    fallan con ``curl: (77) error adding trust anchors``. Aquí copiamos el
    archivo a una ruta sin acentos y apuntamos ``CURL_CA_BUNDLE`` a esa copia.
    En Linux, macOS y Streamlit Cloud no hace nada.
    """
    if sys.platform != "win32":
        return
    if any(os.environ.get(v) for v in ("SSL_CERT_FILE", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE")):
        return  # ya hay certificados configurados; no los tocamos
    import certifi

    origen = certifi.where()
    if origen.isascii():
        return
    for carpeta in (tempfile.gettempdir(), os.environ.get("PUBLIC", r"C:\Users\Public")):
        destino = Path(carpeta) / "acciones101_cacert.pem"
        if not str(destino).isascii():
            continue
        try:
            shutil.copyfile(origen, destino)
        except OSError:
            continue
        os.environ["CURL_CA_BUNDLE"] = str(destino)
        return


# Debe correr ANTES de importar yfinance: curl_cffi lee la ruta al importarse.
_configurar_certificados_windows()

import yfinance as yf  # noqa: E402


def _df_vacio() -> pd.DataFrame:
    """Regresa un DataFrame tidy vacío con las columnas y tipos esperados."""
    return _normalizar(pd.DataFrame(columns=COLUMNAS))


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica tipos y orden de un DataFrame tidy de precios.

    Fechas sin zona horaria, precios como ``float``, volumen como entero y
    filas ordenadas por ticker y fecha.
    """
    df = df[COLUMNAS].copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None).dt.normalize().astype("datetime64[ns]")
    df["ticker"] = df["ticker"].astype(str)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df = df.dropna(subset=["close"])
    return df.sort_values(["ticker", "fecha"]).reset_index(drop=True)


def descargar_precios(
    tickers: list[str],
    inicio: str | date,
    fin: str | date | None = None,
) -> pd.DataFrame:
    """Descarga precios diarios ajustados de Yahoo Finance en formato tidy.

    Se usa ``auto_adjust=True``: yfinance ajusta ``open``, ``high``, ``low`` y
    ``close`` por splits y dividendos. Por eso la columna ``close`` ya es el
    precio ajustado (equivale a la columna "Adj Close", que en este modo
    yfinance ya no regresa). Con precios ajustados, el rendimiento entre dos
    fechas incluye los dividendos como si se hubieran reinvertido.

    Args:
        tickers: Tickers de Yahoo Finance, por ejemplo ``["NVDA", "^GSPC"]``.
        inicio: Primera fecha, inclusive (``"AAAA-MM-DD"`` o ``date``).
        fin: Última fecha, inclusive. Si es ``None`` se usa la fecha de hoy.

    Returns:
        DataFrame con columnas ``fecha, ticker, open, high, low, close,
        volume`` y una fila por día hábil y ticker. Los tickers que Yahoo no
        regresó simplemente no aparecen (no se lanza error por ellos).

    Raises:
        Exception: Los errores de red o de Yahoo Finance se propagan;
            ``obtener_precios`` los atrapa y recurre al respaldo.

    Example:
        >>> df = descargar_precios(["AAPL"], "2024-01-01", "2024-01-31")
        >>> df.columns.tolist()
        ['fecha', 'ticker', 'open', 'high', 'low', 'close', 'volume']
    """
    if not tickers:
        return _df_vacio()
    fin = date.today() if fin is None else fin
    # yfinance NO incluye la fecha "end"; sumamos un día para que `fin` sea inclusiva.
    fin_exclusivo = pd.Timestamp(fin) + pd.Timedelta(days=1)

    crudo = yf.download(
        list(tickers),
        start=pd.Timestamp(inicio).strftime("%Y-%m-%d"),
        end=fin_exclusivo.strftime("%Y-%m-%d"),
        auto_adjust=True,
        group_by="ticker",
        multi_level_index=True,
        progress=False,
        threads=True,
    )
    if crudo is None or crudo.empty:
        return _df_vacio()

    partes: list[pd.DataFrame] = []
    tickers_recibidos = set(crudo.columns.get_level_values(0))
    for ticker in tickers:
        if ticker not in tickers_recibidos:
            continue
        bloque = crudo[ticker].rename(columns=str.lower).dropna(subset=["close"])
        if bloque.empty:
            continue
        bloque.index.name = "fecha"
        bloque = bloque.reset_index()
        bloque["ticker"] = ticker
        partes.append(bloque[COLUMNAS])

    if not partes:
        return _df_vacio()
    return _normalizar(pd.concat(partes, ignore_index=True))


def cargar_respaldo(ruta: str | Path = config.RUTA_RESPALDO) -> pd.DataFrame:
    """Lee el respaldo CSV de precios diarios (mismo formato tidy).

    Args:
        ruta: Ruta del CSV. Por defecto ``data/respaldo_precios.csv``.

    Returns:
        DataFrame con columnas ``fecha, ticker, open, high, low, close, volume``.

    Raises:
        FileNotFoundError: Si el archivo no existe. Se genera con
            ``python actualizar_respaldo.py``.

    Example:
        >>> respaldo = cargar_respaldo()
        >>> respaldo["ticker"].nunique() > 0
        True
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe el respaldo {ruta}. Genéralo con: python actualizar_respaldo.py"
        )
    return _normalizar(pd.read_csv(ruta))


def filtrar_precios(
    df: pd.DataFrame,
    tickers: list[str] | None = None,
    inicio: str | date | None = None,
    fin: str | date | None = None,
) -> pd.DataFrame:
    """Filtra un DataFrame tidy por tickers y por rango de fechas (inclusivo).

    Args:
        df: Precios en formato tidy.
        tickers: Tickers a conservar. ``None`` conserva todos.
        inicio: Primera fecha a conservar. ``None`` = sin límite.
        fin: Última fecha a conservar. ``None`` = sin límite.

    Returns:
        Copia filtrada del DataFrame, con el índice reiniciado.

    Example:
        >>> filtrar_precios(df, ["NVDA"], "2020-01-01", "2020-12-31")
    """
    mascara = pd.Series(True, index=df.index)
    if tickers is not None:
        mascara &= df["ticker"].isin(tickers)
    if inicio is not None:
        mascara &= df["fecha"] >= pd.Timestamp(inicio)
    if fin is not None:
        mascara &= df["fecha"] <= pd.Timestamp(fin)
    return df.loc[mascara].reset_index(drop=True)


def obtener_precios(
    tickers: list[str],
    inicio: str | date,
    fin: str | date | None = None,
    ruta_respaldo: str | Path = config.RUTA_RESPALDO,
    forzar_respaldo: bool | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Obtiene precios de Yahoo Finance y usa el respaldo CSV solo para lo que falte.

    Primero intenta ``descargar_precios``. Si la descarga falla, regresa vacía
    o le faltan tickers, completa **solo esos tickers** con el respaldo CSV.
    Así el demo de clase funciona aunque Yahoo Finance no responda (algo que
    pasa a veces en servidores en la nube).

    Para simular una falla de Yahoo, define la variable de entorno
    ``FORZAR_RESPALDO=1`` antes de correr la app.

    Args:
        tickers: Tickers a obtener.
        inicio: Primera fecha, inclusive.
        fin: Última fecha, inclusive. ``None`` = hoy.
        ruta_respaldo: Ruta del CSV de respaldo.
        forzar_respaldo: Si es ``True`` no se consulta Yahoo Finance. Si es
            ``None`` se lee la variable de entorno ``FORZAR_RESPALDO``.

    Returns:
        Tupla ``(precios, metadatos)``. ``precios`` es un DataFrame tidy.
        ``metadatos`` es un dict con:

        - ``"fuente"``: ``"yfinance"``, ``"respaldo"`` o ``"mixta"``.
        - ``"fecha_datos"``: última fecha con datos (``date``).
        - ``"tickers_respaldo"``: tickers que salieron del respaldo.
        - ``"fecha_respaldo"``: última fecha de los datos de respaldo usados
          (``None`` si no se usó el respaldo).
        - ``"tickers_sin_datos"``: tickers que no se encontraron en ninguna fuente.
        - ``"error_yfinance"``: texto del error de descarga, si lo hubo.

    Raises:
        RuntimeError: Si no se obtuvo ningún dato ni de Yahoo ni del respaldo.

    Example:
        >>> precios, meta = obtener_precios(["NVDA", "^GSPC"], "2015-01-01")
        >>> meta["fuente"] in {"yfinance", "respaldo", "mixta"}
        True
    """
    if forzar_respaldo is None:
        forzar_respaldo = os.environ.get("FORZAR_RESPALDO", "").strip() == "1"
    fin = date.today() if fin is None else fin

    descargado = _df_vacio()
    error_yfinance: str | None = None
    if forzar_respaldo:
        error_yfinance = "FORZAR_RESPALDO=1: no se consultó Yahoo Finance."
    else:
        try:
            descargado = descargar_precios(tickers, inicio, fin)
        except Exception as exc:  # noqa: BLE001 - cualquier falla de red debe caer al respaldo
            error_yfinance = f"{type(exc).__name__}: {exc}"

    recibidos = set(descargado["ticker"])
    faltantes = [t for t in tickers if t not in recibidos]

    del_respaldo = _df_vacio()
    if faltantes:
        try:
            respaldo = cargar_respaldo(ruta_respaldo)
        except FileNotFoundError as exc:
            error_yfinance = f"{error_yfinance or ''} | {exc}".strip(" |")
            respaldo = _df_vacio()
        del_respaldo = filtrar_precios(respaldo, faltantes, inicio, fin)

    precios = _normalizar(pd.concat([descargado, del_respaldo], ignore_index=True))
    if precios.empty:
        raise RuntimeError(
            "No se obtuvieron precios ni de Yahoo Finance ni del respaldo CSV. "
            f"Detalle: {error_yfinance}"
        )

    en_respaldo = set(del_respaldo["ticker"])
    tickers_respaldo = [t for t in tickers if t in en_respaldo]
    if not tickers_respaldo:
        fuente = "yfinance"
    elif descargado.empty:
        fuente = "respaldo"
    else:
        fuente = "mixta"

    metadatos = {
        "fuente": fuente,
        "fecha_datos": precios["fecha"].max().date(),
        "tickers_respaldo": tickers_respaldo,
        "fecha_respaldo": del_respaldo["fecha"].max().date() if not del_respaldo.empty else None,
        "tickers_sin_datos": [t for t in tickers if t not in set(precios["ticker"])],
        "error_yfinance": error_yfinance,
    }
    return precios, metadatos


def resamplear_ohlc(df: pd.DataFrame, periodicidad: str) -> pd.DataFrame:
    """Convierte precios diarios a velas mensuales o anuales, por ticker.

    Reglas de agregación dentro de cada periodo:
    ``open`` = primer valor, ``high`` = máximo, ``low`` = mínimo,
    ``close`` = último valor y ``volume`` = suma.

    La fecha de cada fila es el **último día calendario** del periodo
    (por ejemplo, 2024-01-31 para enero de 2024). El periodo en curso puede
    estar incompleto: si hoy es 5 de noviembre, la vela de noviembre solo
    tiene cinco días de datos.

    Args:
        df: Precios diarios en formato tidy.
        periodicidad: ``"Mensual"`` o ``"Anual"`` (también acepta las reglas
            de pandas ``"ME"`` o ``"YE"``).

    Returns:
        DataFrame tidy con las mismas columnas, una fila por periodo y ticker.

    Raises:
        ValueError: Si la periodicidad no es válida.

    Example:
        >>> mensual = resamplear_ohlc(precios_diarios, "Mensual")
    """
    reglas_validas = {nombre: p["regla"] for nombre, p in config.PERIODICIDADES.items()}
    if periodicidad in reglas_validas:
        regla = reglas_validas[periodicidad]
    elif periodicidad in reglas_validas.values():
        regla = periodicidad
    else:
        raise ValueError(
            f"Periodicidad '{periodicidad}' no válida. Usa una de: {list(reglas_validas)}"
        )

    agregacion = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    partes: list[pd.DataFrame] = []
    for ticker, grupo in df.groupby("ticker", sort=True):
        velas = grupo.set_index("fecha")[list(agregacion)].resample(regla).agg(agregacion)
        velas = velas.dropna(subset=["close"])  # periodos sin operaciones
        velas["ticker"] = ticker
        partes.append(velas.reset_index())

    if not partes:
        return _df_vacio()
    return _normalizar(pd.concat(partes, ignore_index=True))


def serie(df: pd.DataFrame, ticker: str, columna: str = "close") -> pd.Series:
    """Extrae una columna de un ticker como serie indexada por fecha.

    Las funciones de ``metricas.py`` reciben series de este tipo.

    Args:
        df: Precios en formato tidy.
        ticker: Ticker a extraer.
        columna: Columna de precios (por defecto ``"close"``).

    Returns:
        ``pd.Series`` con índice ``fecha`` y nombre igual al ticker.

    Example:
        >>> serie(mensual, "NVDA").head(2)
    """
    datos_ticker = df.loc[df["ticker"] == ticker, ["fecha", columna]]
    return datos_ticker.set_index("fecha")[columna].rename(ticker)
