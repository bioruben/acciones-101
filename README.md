# Acciones 101

Dashboard educativo en Streamlit para analizar acciones con periodicidad mensual o anual: la bolsa no es un casino, es análisis.

> **Aviso:** Este proyecto es exclusivamente **educativo**. No constituye recomendación de inversión, asesoría financiera ni oferta de compra o venta de valores. Rendimientos pasados no garantizan rendimientos futuros. Cada persona es responsable de sus propias decisiones de inversión. Los datos provienen de Yahoo Finance a través de `yfinance` y pueden contener errores o retrasos.

> **Código generado con IA:** Todo el código de este repositorio fue escrito por un agente de IA (Claude Code, de Anthropic) a partir de las instrucciones de `CLAUDE.md`, y revisado por el autor con fines didácticos.

*README en construcción: la versión completa se escribe en la Etapa 5 del plan de trabajo (ver `CLAUDE.md`).*

## Instalación local

Requiere Python 3.12 o superior.

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
