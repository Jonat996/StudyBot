import logging
import sys
from flask import Flask
from flask_cors import CORS
from config.settings import Settings
from config.container import Container
from api.routes.health import health_bp
from api.routes.plan import plan_bp
from api.routes.chat import chat_bp
from api.routes.messaging import messaging_bp
from api.routes.students import students_bp
from api.routes.reminders import bp_reminders
from api.routes.calendar import bp_calendar
from api.middleware.error_handler import register_error_handlers


def create_app() -> Flask:
    # Configure logging to stdout so Railway captures it
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = Settings()
    app = Flask(__name__)
    CORS(app)

    # Log config verification
    logger = logging.getLogger(__name__)
    import os
    raw_env = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    logger.info("TELEGRAM_BOT_TOKEN from os.environ: len=%d, first5=%s", len(raw_env), raw_env[:5] if raw_env else "EMPTY")
    logger.info("TELEGRAM_BOT_TOKEN from settings: len=%d", len(settings.telegram_bot_token))
    logger.info("GOOGLE_CLIENT_ID configured: %s", bool(settings.google_client_id))

    app.container = Container(settings)

    app.register_blueprint(health_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(messaging_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(bp_reminders)
    app.register_blueprint(bp_calendar)

    register_error_handlers(app)

    return app
