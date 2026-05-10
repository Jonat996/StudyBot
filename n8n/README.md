# Flujo n8n — StudyBot

Este directorio contiene el flujo de n8n que orquesta los canales de mensajería.

## Cómo importar
1. n8n → Workflows → Import from file
2. Selecciona `studybot_workflow.json`

## Variables de entorno requeridas en n8n
| Variable | Valor |
|----------|-------|
| STUDYBOT_API_URL | URL de Railway (ej: https://studybot.railway.app) |
| GOOGLE_CALENDAR_ID | ID del calendario de Google |

## Credenciales requeridas en n8n
- Telegram API → token del bot creado en BotFather
- Google Calendar OAuth2 API → cuenta de Google del estudiante

## Subflows
1. **Conversación principal** — Telegram → /api/chat → Calendar + Telegram
2. **Recordatorio 7am** — Schedule → /api/reminders/today → Telegram
3. **Keep-alive 10min** — Schedule → /health → Railway despierto

## Endpoints de Flask que consume n8n
- POST /api/chat — conversación principal
- GET /api/reminders/today — recordatorios diarios
- GET /health — keep-alive
