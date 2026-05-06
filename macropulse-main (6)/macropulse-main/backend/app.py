# Author: Kevin Ngo, 4/21/26
# Main Flask application setup including configuration, security, and route registration.

import os
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from routes.search import search_bp
from routes.stock import stock_bp
from routes.signals import signals_bp

# Kevin Ngo, 4/21/26
# Load environment variables from a .env file so sensitive config is not hardcoded.
load_dotenv()

# Kevin Ngo, 4/21/26
# Define the path to the frontend directory for serving static files.
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def create_app():
    # Kevin Ngo, 4/21/26
    # Create the Flask application instance.
    app = Flask(__name__)

    # Kevin Ngo, 4/21/26
    # Configure CORS to only allow requests from approved frontend origins.
    # This prevents unauthorized domains from accessing the API.
    allowed_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5000").split(",")
    CORS(app, origins=[o.strip() for o in allowed_origins if o.strip()])

    # Kevin Ngo, 4/21/26
    # Set up rate limiting to prevent abuse (e.g., too many requests from one IP).
    # Default limit is controlled via environment variable.
    rate_limit = os.environ.get("RATE_LIMIT", "60 per minute")
    limiter = Limiter(
        get_remote_address,   # Identifies users by IP address
        app=app,
        default_limits=[rate_limit],
        storage_uri="memory://",  # In-memory storage (suitable for development)
    )

    # Kevin Ngo, 4/21/26
    # Register API route blueprints under the /api prefix.
    # This keeps routes modular and organized.
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(stock_bp, url_prefix="/api")
    app.register_blueprint(signals_bp, url_prefix="/api")

    # Kevin Ngo, 4/21/26
    # Health check endpoint used by monitoring tools to verify server status.
    # Exempt from rate limiting so it is always accessible.
    @app.route("/health")
    @limiter.exempt
    def health():
        return jsonify({"status": "ok"}), 200

    # Kevin Ngo, 4/21/26
    # Serve the main frontend HTML file when the root URL is accessed.
    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    # Kevin Ngo, 4/21/26
    # Serve all other static frontend files (JS, CSS, etc.).
    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    # Kevin Ngo, 4/21/26
    # Initialize the app using the factory function.
    app = create_app()

    # Kevin Ngo, 4/21/26
    # Enable or disable debug mode based on environment variable.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Kevin Ngo, 4/21/26
    # Set the port dynamically for flexibility across environments.
    port = int(os.environ.get("FLASK_PORT", 5000))

    # Kevin Ngo, 4/21/26
    # Run the Flask development server.
    app.run(debug=debug_mode, port=port)
