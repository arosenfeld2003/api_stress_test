#!/bin/bash
# Update Nginx configuration for optimal PostgreSQL performance
# Target: 99.99%+ success rate

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "======================================"
echo "Updating Nginx for PostgreSQL Backend"
echo "======================================"
echo ""

# Check if nginx container is running
if ! docker ps | grep -q "api_stress_test_nginx\|warrior-nginx"; then
    echo "❌ Nginx container not found. Please start it first."
    exit 1
fi

NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "nginx" | head -1)
echo "Found Nginx container: $NGINX_CONTAINER"

# Backup current config
echo "1. Backing up current config..."
docker exec $NGINX_CONTAINER cat /etc/nginx/nginx.conf > nginx.conf.backup.$(date +%Y%m%d_%H%M%S) || true
docker exec $NGINX_CONTAINER cat /etc/nginx/conf.d/default.conf > default.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Create optimized config
echo "2. Creating optimized configuration..."
cat > /tmp/nginx_optimized.conf << 'EOF'
# Optimized Nginx Configuration for PostgreSQL Backend
# Fixes 504 Gateway Timeout errors

events {
    worker_connections 2048;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=1500r/s;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

    server {
        listen 80;
        server_name localhost;

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";

        # Increased timeouts
        client_header_timeout 30s;
        client_body_timeout 30s;
        keepalive_timeout 75s;
        send_timeout 60s;
        client_max_body_size 2M;

        location / {
            # Rate limiting with increased burst
            limit_req zone=api_limit burst=500 nodelay;
            limit_conn conn_limit 500;

            # Proxy to Flask
            proxy_pass http://host.docker.internal:5001;
            
            # Headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";

            # CRITICAL: Increased timeouts to eliminate 504 errors
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Buffering optimizations
            proxy_buffering on;
            proxy_buffer_size 8k;
            proxy_buffers 16 8k;
            proxy_busy_buffers_size 16k;
            
            # HTTP/1.1 with keepalive
            proxy_http_version 1.1;
        }

        # Status endpoint
        location /nginx_status {
            stub_status on;
            access_log off;
            allow 127.0.0.1;
            allow 172.16.0.0/12;  # Docker networks
            deny all;
        }
    }
}
EOF

# Copy config to container
echo "3. Deploying optimized configuration..."
docker cp /tmp/nginx_optimized.conf $NGINX_CONTAINER:/etc/nginx/nginx.conf

# Test configuration
echo "4. Testing configuration..."
if docker exec $NGINX_CONTAINER nginx -t; then
    echo "✅ Configuration test passed"
else
    echo "❌ Configuration test failed, restoring backup"
    docker cp nginx.conf.backup.* $NGINX_CONTAINER:/etc/nginx/nginx.conf 2>/dev/null || true
    exit 1
fi

# Reload Nginx
echo "5. Reloading Nginx..."
docker exec $NGINX_CONTAINER nginx -s reload

echo ""
echo "======================================"
echo "✅ Nginx Updated Successfully!"
echo "======================================"
echo ""
echo "Changes applied:"
echo "  • proxy_read_timeout: 30s → 60s (eliminates 504 errors)"
echo "  • proxy_connect_timeout: 10s → 60s"
echo "  • proxy_send_timeout: 20s → 60s"
echo "  • Rate limit burst: 200 → 500"
echo "  • Connection limit: 200 → 500"
echo ""
echo "Expected improvement:"
echo "  • Success rate: 99.8% → 99.99%+"
echo "  • Eliminate the 33 timeout errors"
echo ""
echo "Next: Run stress test to verify"
echo "  cd api_under_stress/stress-test && ./run-test.sh"
echo ""

