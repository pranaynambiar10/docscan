#!/bin/bash
# ==============================================================================
# DocScan — 1-Step Unified Launcher
# Usage: ./start or ./start.sh
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/start-server.sh" "$@"

