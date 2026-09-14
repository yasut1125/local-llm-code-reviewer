#!/bin/bash
set -e

ollama serve &

echo "Waiting for Ollama to start..."
while ! curl -s http://localhost:11434/api/tags > /dev/null; do
    sleep 1
done
echo "Ollama started successfully."

exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
