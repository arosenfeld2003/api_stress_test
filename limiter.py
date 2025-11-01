from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import signal
import sys
from src.routes.warrior_routes import warrior_bp
from src.db.connection import get_connection

app = Flask(__name__)

# Rate limiting: max 100 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])
limiter.init_app(app)

# Register warrior routes blueprint
app.register_blueprint(warrior_bp)

# Initialize database schema on startup
def initialize_db():
    """Initialize database schema if needed."""
    try:
        with get_connection(read_only=False, apply_schema=True) as con:
            # Schema is automatically applied by get_connection when apply_schema=True
            pass
    except Exception as e:
        app.logger.error(f"Failed to initialize database: {e}")
        # Don't exit - allow app to start even if DB init fails
        # (DB will be initialized on first request if needed)

@app.route('/health')
def health():
    return jsonify(status='ok')

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Error: {e}")
    return jsonify(error="Internal Server Error"), 500

def handle_shutdown(signum, frame):
    print("Graceful shutdown...")
    # Cleanup resources here
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == '__main__':
    # Initialize database schema
    initialize_db()
    # Never use Flask's built-in server for production!
    app.run(host="0.0.0.0", port=5001)