# Acciones 101

Dashboard educativo en Streamlit para analizar acciones con periodicidad mensual o anual: la bolsa no es un casino, es análisis.

> **Aviso:** Este proyecto es exclusivamente **educativo**. No constituye recomendación de inversión, asesoría financiera ni oferta de compra o venta de valores. Rendimientos pasados no garantizan rendimientos futuros. Cada persona es responsable de sus propias decisiones de inversión. Los datos provienen de Yahoo Finance a través de `yfinance` y pueden contener errores o retrasos.

> **Código generado con IA:** Todo el código de este repositorio fue escrito por un agente de IA (Claude Code, de Anthropic) a partir de las instrucciones de `CLAUDE.md`, y revisado por el autor con fines didácticos.

*README en construcción: la versión completa se escribe en la Etapa 5 del plan de trabajo (ver `CLAUDE.md`).*

## Calidad de datos: AMXB.MX (América Móvil)

> ⚠️ En los datos de Yahoo Finance, de 2015 a agosto de 2023 la serie B de América Móvil (`AMXB.MX`) tiene muchos días **sin volumen** (nadie la operó) y en casi todos ellos **se repite el precio del día anterior**: 829 de 2,978 días en el respaldo al 2026-11-05, y en 824 de ellos el cierre es idéntico al del día previo. Hasta el 16 de marzo de 2023 la serie más operada era la L, que ese día se convirtió en serie B. Los precios repetidos hacen que la acción parezca más estable de lo que fue: **bajan artificialmente la volatilidad** (y tienden a bajar también la beta y la correlación con el IPC). Se conserva en el dashboard como ejemplo de por qué hay que revisar la calidad de los datos; la app muestra este aviso al seleccionarla.

## Limitación: tasa libre de riesgo constante

El Sharpe ratio y el backtest usan **una tasa libre de riesgo por moneda, constante para todo el periodo** (el dato más reciente de cada fuente, ver `config.py`): CETES 28 días para MXN (Banxico), T-bill a 3 meses para USD (FRED, serie DTB3) y la tasa base del Bank of Korea para KRW. En la realidad esas tasas cambiaron mucho desde 2015, así que el Sharpe ratio es una aproximación. No se usa el promedio histórico porque descargar las series de Banxico y del Bank of Korea requiere registrarse y usar una clave de API.

## Instalación local

Requiere Python 3.12+.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Para simular que Yahoo Finance no responde y probar el respaldo CSV:

```bash
# Windows (PowerShell):  $env:FORZAR_RESPALDO = "1"; streamlit run app.py
# macOS/Linux:           FORZAR_RESPALDO=1 streamlit run app.py
```

Para regenerar el respaldo `data/respaldo_precios.csv`:

```bash
python actualizar_respaldo.py
```
