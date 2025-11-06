# Gunicorn configuration for high-performance stress testing

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '9999')}"
backlog = 2048

# Worker processes - use more workers for better concurrency
# Formula: (2 x $num_cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'  # sync workers work well with DuckDB
worker_connections = 1000
max_requests = 10000  # Restart workers after 10k requests to prevent memory leaks
max_requests_jitter = 1000  # Add randomness to prevent all workers restarting at once

# Timeouts
timeout = 30
keepalive = 5

# Logging
accesslog = '/tmp/gunicorn_access.log'
errorlog = '/tmp/gunicorn_error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'flask_stress_test'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Preload app to save memory
preload_app = False  # Set to False for DuckDB to avoid connection sharing issues

# Performance tuning
# worker_tmp_dir = '/dev/shm'  # Use shared memory for better performance (Linux only)
