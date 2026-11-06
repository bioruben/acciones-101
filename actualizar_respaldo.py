"""Regenera data/respaldo_precios.csv con los precios diarios de todos los tickers y benchmarks. Código generado con un agente de IA (Claude Code) con fines educativos.

Uso (desde la raíz del repo, con el entorno virtual activo):

    python actualizar_respaldo.py

Descarga desde ``config.FECHA_INICIO`` hasta hoy todos los tickers de
``config.TICKERS`` y ``config.BENCHMARKS``. Si Yahoo Finance no regresa alguno,
el script se detiene **sin sobrescribir** el respaldo anterior, para no
perder datos buenos. Después de actualizarlo, haz commit del CSV.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import config
import datos


def main() -> int:
    """Descarga todos los tickers, sobrescribe el CSV de respaldo e imprime un resumen.

    Returns:
        Código de salida: ``0`` si se actualizó el respaldo, ``1`` si faltó
        algún ticker y el archivo no se tocó.
    """
    tickers = list(config.TICKERS) + list(config.BENCHMARKS)
    hoy = date.today()
    print(f"Descargando {len(tickers)} tickers de Yahoo Finance ({config.FECHA_INICIO} a {hoy})...")

    precios = datos.descargar_precios(tickers, config.FECHA_INICIO, hoy)

    faltantes = [t for t in tickers if t not in set(precios["ticker"])]
    if faltantes:
        print(f"ERROR: Yahoo Finance no regresó datos para: {', '.join(faltantes)}")
        print("El respaldo NO se sobrescribió. Revisa los tickers en config.py e intenta de nuevo.")
        return 1

    ruta = config.RUTA_RESPALDO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    precios.to_csv(temporal, index=False, float_format="%.6f", date_format="%Y-%m-%d")
    os.replace(temporal, ruta)  # reemplazo atómico: nunca queda un CSV a medias

    resumen = (
        precios.groupby("ticker", sort=False)
        .agg(filas=("fecha", "size"), fecha_min=("fecha", "min"), fecha_max=("fecha", "max"))
        .reindex(tickers)
    )
    resumen["fecha_min"] = resumen["fecha_min"].dt.date
    resumen["fecha_max"] = resumen["fecha_max"].dt.date
    print()
    print(resumen.to_string())
    print()
    print(f"Total de filas: {len(precios):,}")
    print(f"Archivo: {ruta} ({ruta.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
