FROM python:3.11-slim
WORKDIR /src
COPY . .
RUN pip install -r requirements.txt
# Command to start your agent logic
CMD ["python", "FounderAgent.py"]