"""
The HTTP layer. It parses requests, calls the registration service, and turns
the result into JSON — nothing else. No validation rules and no SQL live here,
so the same service could be put behind a different framework without touching
core/.

create_app takes its collaborators as arguments rather than building them,
which keeps this file free of any concrete implementation. run_web.py is the
composition root that wires the real ones in.
"""
import logging

from flask import Flask, jsonify, render_template, request

from core.models.country import CountryRegistry
from core.registration import RegistrationService

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 8 * 1024


def create_app(registration: RegistrationService, countries: CountryRegistry) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    @app.get("/")
    def form_page():
        return render_template("register.html", countries=countries.as_list())

    @app.get("/healthz")
    def healthz():
        """Liveness only — deliberately does not touch the database.

        If this reported the database's state, a brief outage there would mark
        this container unhealthy and restart it, which fixes nothing and drops
        in-flight requests. Postgres has its own healthcheck."""
        return jsonify({"status": "ok"}), 200

    @app.get("/api/countries")
    def country_list():
        """One source of truth for the dialling rules: the browser renders its
        hints from this, the server validates against the same registry."""
        return jsonify(countries.as_list())

    @app.post("/api/register")
    def register():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "errors": {"form": "درخواست نامعتبر است."}}), 400

        result = registration.register(
            first_name=str(payload.get("first_name", ""))[:200],
            last_name=str(payload.get("last_name", ""))[:200],
            phone_raw=str(payload.get("phone", ""))[:40],
            email=str(payload.get("email", ""))[:300],
            country_iso=str(payload.get("country", ""))[:4],
        )

        if not result.ok:
            return jsonify({"ok": False, "errors": result.errors}), 400

        return jsonify({"ok": True, "full_name": result.full_name}), 201

    @app.errorhandler(500)
    def server_error(error):
        logger.exception("Unhandled error on %s", request.path)
        return jsonify({"ok": False, "errors": {"form": "خطای سرور. بعداً تلاش کنید."}}), 500

    return app
