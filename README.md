# StudyBot

Chatbot academico que conversa con estudiantes via WhatsApp, predice tiempos de estudio con ML y genera cronogramas semanales optimizados.

## Arquitectura

```
studybot/
├── api/              ← Controllers Flask (sin logica de negocio)
├── core/             ← Logica pura: entities, use cases, interfaces (ABC)
├── infrastructure/   ← Implementaciones: Gemini, Twilio, Supabase, sklearn
└── config/           ← Settings (pydantic) + DI Container
```

### Flujo de datos

```
WhatsApp → POST /api/webhook/whatsapp
           → TwilioProvider.parse_incoming()
           → ManageProfile.get_or_create_student()
           → ProcessMessage.execute()
               → MessageRepository.get_recent()
               → LLMProvider.chat()
               → [si LLM detecta entidades] → GeneratePlan.execute()
                   → MLPredictor.predict_time()
                   → Greedy scheduler
               → MessageRepository.save()
           → TwilioProvider.build_response()
           → TwiML al cliente
```

## Instalacion local

```bash
git clone <repo-url>
cd studybot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales
python run.py
```

## Schema Supabase

Ejecutar el contenido de `schema.sql` en el SQL Editor de tu proyecto Supabase.

## Swappear LLM

Editar `.env`:
```
LLM_PROVIDER=gemini    # gemini | openai | groq
```

Los providers `openai` y `groq` son stubs — implementar en:
- `infrastructure/llm/openai_provider.py`
- `infrastructure/llm/groq_provider.py`

No se modifica ningun otro archivo (principio Open/Closed).

## Swappear canal de mensajeria

Editar `.env`:
```
MESSAGING_PROVIDER=twilio    # twilio | telegram
```

El provider `telegram` es stub — implementar en:
- `infrastructure/messaging/telegram_provider.py`

## Deploy en Railway

1. Crear proyecto en [Railway](https://railway.app)
2. Conectar repositorio GitHub
3. Agregar variables de entorno (mismas que `.env`)
4. Railway detecta automaticamente el `Procfile` y `railway.toml`
5. El healthcheck apunta a `GET /health`

## Endpoints

### GET /health
```bash
curl https://tu-app.railway.app/health
```
```json
{"status": "ok", "llm_provider": "gemini", "messaging_provider": "twilio"}
```

### POST /api/students
```bash
curl -X POST https://tu-app.railway.app/api/students \
  -H "Content-Type: application/json" \
  -d '{"phone": "+573001234567", "name": "Ana", "channel": "whatsapp"}'
```
```json
{"id": "uuid", "name": "Ana", "phone": "+573001234567", "channel": "whatsapp", "personal_factor": 1.0}
```

### POST /api/plan
```bash
curl -X POST https://tu-app.railway.app/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "uuid-opcional",
    "week": 1,
    "tasks": [
      {"subject": "Algebra Lineal", "difficulty": 4, "estimated_hours": 3.0, "days_available": 2},
      {"subject": "Calculo", "difficulty": 3, "estimated_hours": 2.0, "days_available": 5}
    ]
  }'
```
```json
{
  "tasks": [{"subject": "Algebra Lineal", "predicted_hours": 3.4, "priority": "Maxima", "compliance_probability": 0.72, ...}],
  "schedule": {"monday": [{"subject": "Algebra Lineal", "hours": 3.4, "priority": "Maxima"}], ...},
  "max_day_load_pct": 42.5,
  "model_metrics": {"MAE": 0.567, "RMSE": 0.807, "R2": 0.852, "F1": 0.900, "Accuracy": 0.825}
}
```

### POST /api/chat
```bash
curl -X POST https://tu-app.railway.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"student_id": "uuid", "message": "tengo calculo el viernes, es muy dificil"}'
```
```json
{"reply": "Entendido. ¿Cuántas horas crees que necesitas para estudiar cálculo?"}
```

### GET /api/students/{id}/history
```bash
curl https://tu-app.railway.app/api/students/uuid/history
```
```json
{"student_id": "uuid", "tasks": [...], "schedules": [...]}
```

### POST /api/webhook/whatsapp
Recibe payload de Twilio automaticamente. Configurar la URL en el sandbox de Twilio:
```
https://tu-app.railway.app/api/webhook/whatsapp
```

## Metricas del modelo ML

| Metrica  | Valor |
|----------|-------|
| MAE      | 0.567 |
| RMSE     | 0.807 |
| R²       | 0.852 |
| F1       | 0.900 |
| Accuracy | 0.825 |

## Tests

```bash
pytest tests/unit/ -v
```
