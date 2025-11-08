# Gunicorn configuration optimized for DuckDB write contention
# Quick fix: Reduce workers to minimize concurrent write conflicts

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '9999')}"
backlog = 2048

# REDUCED worker count to minimize DuckDB write contention
# DuckDB can only handle 1-2 concurrent writers effectively
# More workers = more contention = more timeouts = more 503s
workers = 4  # Down from (CPU * 2 + 1) which was ~29 workers
worker_class = 'sync'
worker_connections = 1000
max_requests = 10000
max_requests_jitter = 1000

# INCREASED timeouts to handle slow database operations
timeout = 60  # Up from 30 seconds
keepalive = 5

# Logging
accesslog = '/tmp/gunicorn_access.log'
errorlog = '/tmp/gunicorn_error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'flask_stress_test_reduced'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# CRITICAL: Set to False for DuckDB to avoid connection sharing issues
preload_app = False

# Performance tuning
# worker_tmp_dir = '/dev/shm'  # Use shared memory for better performance (Linux only)

print("=" * 80)
print("GUNICORN CONFIGURATION (DuckDB Optimized)")
print("=" * 80)
print(f"Workers: {workers} (reduced to minimize write contention)")
print(f"Timeout: {timeout}s (increased to handle slow operations)")
print(f"Connection pool will be created per worker")
print("=" * 80)

