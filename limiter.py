from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import signal
import sys
from src.routes.warrior_routes import warrior_bp
from src.db.connection import get_connection

app = Flask(__name__)

# Rate limiting: max 100 requests per minute per IP
# Explicitly use memory storage to avoid warning (for development/single-process use)
def on_breach(request_limit):
    """Custom handler when rate limit is breached - return 429 response."""
    from flask import jsonify
    response = jsonify(
        error="Rate limit exceeded",
        message=f"Limit of {request_limit.limit} exceeded"
    )
    response.status_code = 429
    return response

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],
    storage_uri="memory://",
    default_limits_per_method=True,
    headers_enabled=True,
    swallow_errors=True,  # Don't raise exceptions on storage errors
    on_breach=on_breach,  # Custom handler for rate limit breaches
    fail_on_first_breach=False  # Continue processing even after breach
)
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
@limiter.exempt  # Exclude health endpoint from rate limiting
def health():
    """Health check endpoint - exempt from rate limiting for monitoring."""
    return jsonify(status='ok')

# Handle rate limit exceptions properly (before general exception handler)
@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    """Handle rate limit exceptions - return 429 instead of 500."""
    try:
        message = str(e.description) if hasattr(e, 'description') else "Rate limit exceeded"
    except:
        message = "Rate limit exceeded"
    response = jsonify(error="Rate limit exceeded", message=message)
    response.status_code = 429
    return response

# Flask-Limiter also uses HTTPException, so we need to handle that too
from werkzeug.exceptions import HTTPException

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle HTTP exceptions including rate limit errors."""
    if hasattr(e, 'code') and e.code == 429:
        return handle_rate_limit_exceeded(e)
    # For other HTTP exceptions, let Flask handle them normally
    return e

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions."""
    # Check if it's a rate limit exception
    if isinstance(e, RateLimitExceeded):
        return handle_rate_limit_exceeded(e)
    # Check if it's an HTTP exception with 429 code
    if isinstance(e, HTTPException) and e.code == 429:
        return handle_rate_limit_exceeded(e)
    
    # Log the actual exception for debugging
    import traceback
    error_details = traceback.format_exc()
    app.logger.error(f"Unhandled exception: {type(e).__name__}: {e}\n{error_details}")
    
    # If the error message suggests rate limiting, return 429
    error_str = str(e).lower()
    if 'rate limit' in error_str or '429' in error_str or 'too many requests' in error_str:
        return handle_rate_limit_exceeded(e)
    
    return jsonify(error="Internal Server Error", details=str(e) if app.debug else None), 500

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