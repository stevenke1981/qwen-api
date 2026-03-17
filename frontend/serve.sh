#!/bin/bash
PORT="${1:-3000}"
echo "Frontend: http://localhost:$PORT"
python3 -m http.server "$PORT" --directory "$(dirname "$0")"
