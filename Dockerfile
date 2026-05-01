FROM python:3.11-slim
WORKDIR /src
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ARG GITHUB_TOKEN
RUN if [ -n "$GITHUB_TOKEN" ]; then \
      git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi && \
    pip install . && \
    if [ -n "$GITHUB_TOKEN" ]; then \
      git config --global --remove-section "url.https://${GITHUB_TOKEN}@github.com/" 2>/dev/null || true; \
    fi
# Command to start your agent logic
CMD ["python", "src/Founder/FounderAgent.py"]