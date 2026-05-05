from flask import Blueprint, jsonify, current_app

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    settings = current_app.container._settings
    return jsonify({
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "messaging_provider": settings.messaging_provider,
    })
