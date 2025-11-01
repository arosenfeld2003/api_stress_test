# PR Summary: Add Nginx Docker Container Build and macOS Compatibility

## Overview
This PR adds the ability to build and run the nginx reverse proxy container locally, with full macOS/Windows Docker Desktop compatibility. Previously, the nginx image was expected to exist in GHCR, but the build process and local development setup were missing.

## Changes Made

### New Files

- **`Dockerfile.nginx`**
  - Creates nginx Docker image based on `nginx:alpine`
  - Copies `nginx.conf.local` as default configuration
  - Creates SSL certificate directories for future use
  - Exposes ports 80 and 443

- **`nginx.conf.local`**
  - HTTP-only nginx configuration for local testing (no SSL required)
  - Includes all rate limiting (5 req/s with burst of 10)
  - Connection limits (20 concurrent per IP)
  - Security headers configured
  - Uses `host.docker.internal:5001` for macOS/Windows Docker Desktop compatibility
  - Timeout directives properly placed at server level (not location level)

- **`scripts/build_nginx_image.sh`**
  - Build script for creating the nginx Docker image
  - Supports custom image name via parameter
  - Provides platform-specific run instructions (macOS/Windows vs Linux)
  - Includes GHCR push instructions

### Modified Files

- **`README.md`**
  - Updated "Pull and Run Nginx Container" section to "Build and Run Nginx Container"
  - Added instructions for building image locally when not available in GHCR
  - Added platform-specific Docker run commands:
    - macOS/Windows: Uses port mapping only (no `--network host`)
    - Linux: Option to use `--network host`
  - Added note explaining `host.docker.internal` usage for Docker Desktop
  - Clarified networking differences between macOS/Windows and Linux

### Technical Improvements

- **macOS/Windows Docker Desktop Compatibility**
  - Changed nginx `proxy_pass` from `127.0.0.1:5001` to `host.docker.internal:5001`
  - Removed `--network host` requirement for Docker Desktop
  - Standard port mapping (`-p 80:80 -p 443:443`) works correctly

- **Nginx Configuration Fixes**
  - Moved timeout directives (`client_body_timeout`, `client_header_timeout`, etc.) from `location` block to `server` block
  - Fixed nginx syntax errors that prevented container startup
  - Maintained all rate limiting and security features

## Benefits

- ✅ **Local Development**: Developers can now build and run nginx container locally without needing GHCR access
- ✅ **macOS Support**: Full compatibility with Docker Desktop on macOS/Windows
- ✅ **Linux Support**: Still works with `--network host` on Linux systems
- ✅ **No SSL Required**: Local testing configuration works without SSL certificates
- ✅ **Production Ready**: Can still deploy production `nginx.conf` with SSL after container starts

## Testing

- ✅ Container builds successfully
- ✅ Container starts and nginx runs without errors
- ✅ Nginx successfully proxies requests to Flask app on port 5001
- ✅ Rate limiting tests pass (`test_rate_limiter.py`)
- ✅ Health endpoint accessible: `curl http://localhost:80/health`

## Migration Notes

- **For existing users on Linux**: The `--network host` option still works, but for macOS/Windows users, they should now use standard port mapping without `--network host`
- **For new users**: Build the image locally first using `./scripts/build_nginx_image.sh`, then run the container

