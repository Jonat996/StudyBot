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
from api.middleware.error_handler import register_error_handlers


def create_app() -> Flask:
    settings = Settings()
    app = Flask(__name__)
    CORS(app)

    app.container = Container(settings)

    app.register_blueprint(health_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(messaging_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(bp_reminders)

    register_error_handlers(app)

    return app
