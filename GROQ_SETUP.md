# Configuración Groq (Urgencia por descripción)

Este backend ahora expone:

- `POST /api/v1/solicitudes_emergencia/tools/procesar-problema`

## Variables de entorno

Configura estas variables en Render (backend):

- `GROQ_API_KEY=colocar api key aqui`
- `GROQ_MODEL=llama-3.1-8b-instant`
- `GROQ_BASE_URL=https://api.groq.com/openai/v1`
- `GROQ_TIMEOUT_SECONDS=30`

## Nota

- Si `GROQ_API_KEY` queda como `colocar api key aqui`, el endpoint devolverá error de configuración.
- El móvil consume este endpoint y actualiza automáticamente el nivel de urgencia en el formulario de emergencia.
