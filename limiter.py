from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import signal
import sys
import os
from src.routes.warrior_routes import warrior_bp
from src.db.connection import get_connection
from src.security import IPBlocker

app = Flask(__name__)

# Initialize IP blocker with configurable settings
ip_blocker = IPBlocker(
    window_seconds=int(os.getenv('IP_BLOCKER_WINDOW_SECONDS', '60')),
    max_requests_per_minute=int(os.getenv('IP_BLOCKER_MAX_RPM', '60000')),  # 1000 req/s
    max_failure_rate=float(os.getenv('IP_BLOCKER_MAX_FAILURE_RATE', '50.0')),
    max_rate_limit_rate=float(os.getenv('IP_BLOCKER_MAX_RATE_LIMIT_RATE', '90.0')),
    block_duration_seconds=int(os.getenv('IP_BLOCKER_DURATION_SECONDS', '300')),
    min_requests_for_abuse=int(os.getenv('IP_BLOCKER_MIN_REQUESTS', '20')),
)

# Whitelist localhost for stress testing (can be disabled)
if os.getenv('IP_BLOCKER_WHITELIST_LOCALHOST', 'true').lower() == 'true':
    ip_blocker.whitelist_ip('127.0.0.1')
    ip_blocker.whitelist_ip('::1')
    ip_blocker.whitelist_ip('localhost')
    app.logger.info("Whitelisted localhost IPs for stress testing")

# Rate limiting: configurable via FLASK_RATE_LIMIT env var (default: 60000 per minute = 1000 req/s)
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

# Get rate limit from environment variable, default to 120000 req/min (2000 req/s)
flask_rate_limit = os.getenv('FLASK_RATE_LIMIT', '120000')  # Increased for stress testing
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{flask_rate_limit} per minute"],
    storage_uri="memory://",
    default_limits_per_method=True,
    headers_enabled=False,  # Disable headers for better performance
    swallow_errors=True,  # Don't raise exceptions on storage errors
    on_breach=on_breach,  # Custom handler for rate limit breaches
    fail_on_first_breach=False  # Continue processing even after breach
)
limiter.init_app(app)

# IP blocking middleware - check before processing request
@app.before_request
def check_ip_block():
    """Check if the requesting IP is blocked."""
    ip = get_remote_address()
    
    if ip_blocker.is_blocked(ip):
        block_info = ip_blocker.get_block_info(ip)
        remaining = int(block_info['remaining_seconds']) if block_info else 0
        return jsonify(
            error="IP address blocked",
            message=f"Your IP address has been temporarily blocked due to abusive behavior. Unblock in {remaining} seconds.",
            unblock_in_seconds=remaining
        ), 403

# After request hook - record request for IP tracking
@app.after_request
def record_request_metrics(response):
    """Record request metrics for IP blocking analysis."""
    # Don't record health check requests
    if request.path == '/health':
        return response
    
    ip = get_remote_address()
    status_code = response.status_code
    
    # Record the request (this may trigger blocking if abusive)
    ip_blocker.record_request(ip, status_code)
    
    return response

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

@app.route('/admin/ip-status')
@limiter.exempt
def ip_status():
    """Admin endpoint to check IP status and metrics (for debugging)."""
    ip = request.args.get('ip') or get_remote_address()
    
    if ip_blocker.is_whitelisted(ip):
        return jsonify({
            'ip': ip,
            'status': 'whitelisted',
            'metrics': ip_blocker.get_metrics(ip)
        })
    
    block_info = ip_blocker.get_block_info(ip)
    if block_info:
        return jsonify({
            'ip': ip,
            'status': 'blocked',
            **block_info
        })
    
    return jsonify({
        'ip': ip,
        'status': 'active',
        'metrics': ip_blocker.get_metrics(ip)
    })

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
    import os
    # Initialize database schema
    initialize_db()
    
    # Get port from environment variable, default to 5001 for normal operation
    # Set PORT=9999 for stress testing
    port = int(os.getenv('PORT', 5001))
    host = os.getenv('HOST', '0.0.0.0')
    
    # For stress testing, use threaded mode for better concurrency
    # For production, use a proper WSGI server like gunicorn
    threaded = os.getenv('FLASK_THREADED', 'false').lower() == 'true'
    
    # High-performance settings for stress testing
    if threaded:
        # Enable performance optimizations for high-load testing
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    
    app.logger.info(f"Starting Flask app on {host}:{port} (threaded={threaded})")
    app.run(host=host, port=port, threaded=threaded, processes=1)