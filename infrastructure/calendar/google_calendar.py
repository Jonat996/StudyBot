import urllib.parse
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.events']
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _client_config(settings) -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri],
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
        }
    }


def get_auth_url(settings, student_id: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "state": student_id,
        "prompt": "consent",
    }
    return _AUTH_URI + "?" + urllib.parse.urlencode(params)


def exchange_code(settings, code: str) -> dict:
    flow = Flow.from_client_config(_client_config(settings), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": creds.expiry.isoformat() if creds.expiry else None,
    }


def create_events(tokens: dict, slots_by_day: dict, settings,
                   available_schedule: dict = None) -> int:
    """Create Google Calendar events from a study plan.

    Args:
        tokens: OAuth tokens (access_token, refresh_token)
        slots_by_day: {"monday": [{"subject": ..., "hours": ..., "priority": ...}], ...}
        settings: App settings with Google credentials
        available_schedule: Per-day availability, e.g.
            {"monday": {"start": "17:00", "end": "21:00"}, "tuesday": {"start": "14:00", "end": "20:00"}}
            Falls back to 14:00-20:00 if not provided.
    """
    from datetime import datetime as dt_cls
    expiry = None
    if tokens.get('expires_at'):
        try:
            parsed = dt_cls.fromisoformat(tokens['expires_at'])
            # google.auth needs offset-naive UTC datetime
            expiry = parsed.replace(tzinfo=None)
        except (ValueError, TypeError):
            pass

    creds = Credentials(
        token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        expiry=expiry,
    )
    service = build('calendar', 'v3', credentials=creds)

    day_offsets = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2,
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
    }
    priority_colors = {'Maxima': '11', 'Alta': '6', 'Media': '5', 'Baja': '2'}

    default_schedule = {"start": "14:00", "end": "20:00"}
    if not available_schedule:
        available_schedule = {}

    # Translate Spanish day names to English
    _es_to_en = {
        "lunes": "monday", "martes": "tuesday", "miércoles": "wednesday",
        "miercoles": "wednesday", "jueves": "thursday", "viernes": "friday",
        "sábado": "saturday", "sabado": "saturday", "domingo": "sunday",
    }
    available_schedule = {_es_to_en.get(k.lower(), k.lower()): v for k, v in available_schedule.items()}

    # Use Bogota timezone (UTC-5) for date calculations
    from datetime import timezone as tz
    bogota_tz = tz(timedelta(hours=-5))
    today = datetime.now(bogota_tz).replace(tzinfo=None)
    today_weekday = today.weekday()  # 0=Monday

    events_created = 0
    for day, slots in slots_by_day.items():
        if not slots:
            continue
        target_weekday = day_offsets.get(day, 0)
        # Calculate next occurrence of this day (including today)
        days_ahead = (target_weekday - today_weekday) % 7
        # If days_ahead is 0, it means today IS that day — use today
        event_date = today + timedelta(days=days_ahead)

        # Get this day's schedule or use default
        day_schedule = available_schedule.get(day, default_schedule)
        start_hour, start_min = (int(x) for x in day_schedule["start"].split(":"))
        end_hour, end_min = (int(x) for x in day_schedule["end"].split(":"))

        logger.info("Calendar event day=%s | event_date=%s | schedule=%s | start=%02d:%02d end=%02d:%02d",
                     day, event_date.strftime('%Y-%m-%d'), day_schedule,
                     start_hour, start_min, end_hour, end_min)

        current_start = event_date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        day_end_limit = event_date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

        for slot in slots:
            hours = float(slot.get('hours', slot.get('predicted_hours', 1)))
            end = current_start + timedelta(hours=hours)

            if end > day_end_limit:
                end = day_end_limit
                if current_start >= day_end_limit:
                    break

            priority = slot.get('priority', 'Media')
            subject = slot.get('subject', slot.get('materia', 'Estudio'))

            event = {
                'summary': f'📚 {subject} ({hours}h)',
                'description': f'Prioridad: {priority}\nGenerado por StudyBot',
                'start': {'dateTime': current_start.isoformat(), 'timeZone': 'America/Bogota'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'America/Bogota'},
                'colorId': priority_colors.get(priority, '5'),
                'reminders': {
                    'useDefault': False,
                    'overrides': [{'method': 'popup', 'minutes': 30}],
                },
            }
            service.events().insert(calendarId='primary', body=event).execute()
            events_created += 1

            # Next event starts where this one ended + 10 min break
            current_start = end + timedelta(minutes=10)

    return events_created
