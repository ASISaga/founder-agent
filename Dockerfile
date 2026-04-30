FROM python:3.11-slim
WORKDIR /src
COPY . .
RUN pip install .
# Command to start your agent logic
CMD ["python", "src/Founder/FounderAgent.py"]