FROM python:3.11-slim
WORKDIR /src
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install .
# Command to start your agent logic
CMD ["python", "src/Founder/FounderAgent.py"]