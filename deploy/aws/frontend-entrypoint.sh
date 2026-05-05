#!/bin/sh
set -eu

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.ASCEND_RUNTIME_CONFIG = {
  apiUrl: "${ASCEND_API_URL:-http://127.0.0.1:8000}"
};
EOF
