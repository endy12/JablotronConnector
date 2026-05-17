FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jablotron_gate_monitor.py .

CMD ["python", "-u", "jablotron_gate_monitor.py"]
