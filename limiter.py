from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import signal
import sys

app = Flask(__name__)

# Rate limiting: max 100 requests per minute per IP
limiter = Limiter(app, key_func=get_remote_address, default_limits=["100 per minute"])

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
    # Never use Flask's built-in server for production!
    app.run(host="0.0.0.0", port=5000)