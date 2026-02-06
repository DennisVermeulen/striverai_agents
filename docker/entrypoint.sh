#!/bin/bash
set -e

# Default env vars for supervisord Xvfb resolution
export BROWSER_WIDTH="${BROWSER_WIDTH:-1280}"
export BROWSER_HEIGHT="${BROWSER_HEIGHT:-800}"
export DISPLAY_NUM="${DISPLAY_NUM:-99}"

echo "Starting Local Agent..."
echo "  Display: :${DISPLAY_NUM} (${BROWSER_WIDTH}x${BROWSER_HEIGHT})"
echo "  API: http://0.0.0.0:${API_PORT:-8000}"
echo "  VNC: :5900"
echo "  noVNC: http://0.0.0.0:6080"

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
