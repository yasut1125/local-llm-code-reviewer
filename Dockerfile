FROM ollama/ollama:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt-get/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY main.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ARG OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
ENV OLLAMA_MODEL=${OLLAMA_MODEL}

RUN ollama serve & \
    sleep 5 && \
    ollama pull ${OLLAMA_MODEL}

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
