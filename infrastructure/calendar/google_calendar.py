from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def _client_config(settings) -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def get_auth_url(settings, student_id: str) -> str:
    flow = Flow.from_client_config(_client_config(settings), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        state=student_id,
        prompt='consent',
    )
    return auth_url


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


def create_events(tokens: dict, slots_by_day: dict, settings) -> int:
    creds = Credentials(
        token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    service = build('calendar', 'v3', credentials=creds)

    day_offsets = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2,
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
    }
    priority_colors = {'Maxima': '11', 'Alta': '6', 'Media': '5', 'Baja': '2'}

    today = datetime.now()
    days_to_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_to_monday)

    events_created = 0
    for day, slots in slots_by_day.items():
        if not slots:
            continue
        offset = day_offsets.get(day, 0)
        event_date = next_monday + timedelta(days=offset)

        for slot in slots:
            hours = slot.get('hours', slot.get('predicted_hours', 1))
            start = event_date.replace(hour=18, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=float(hours))

            priority = slot.get('priority', 'Media')
            subject = slot.get('subject', slot.get('materia', 'Estudio'))

            event = {
                'summary': f'📚 {subject} ({hours}h)',
                'description': f'Prioridad: {priority}\nGenerado por StudyBot',
                'start': {'dateTime': start.isoformat(), 'timeZone': 'America/Bogota'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'America/Bogota'},
                'colorId': priority_colors.get(priority, '5'),
                'reminders': {
                    'useDefault': False,
                    'overrides': [{'method': 'popup', 'minutes': 30}],
                },
            }
            service.events().insert(calendarId='primary', body=event).execute()
            events_created += 1

    return events_created
