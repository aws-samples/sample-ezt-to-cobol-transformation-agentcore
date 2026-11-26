#!/bin/bash
# Invoke the agentcore dev server with a longer timeout (15 minutes)
# Usage: ./invoke.sh '{"prompt": "Process the Easytrieve file at input/ezt/pgm4.ezt"}'

TIMEOUT=${AGENTCORE_TIMEOUT:-900}
PAYLOAD="${1:-'{"prompt": "Hello"}'}"

curl -s -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  --max-time "$TIMEOUT" \
  -d "$PAYLOAD" | python3 -m json.tool
