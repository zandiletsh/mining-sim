FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# install dependencies first so Docker can cache this step
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# only the code the service needs
COPY topology.py models.py disruptions.py simulation.py ./
COPY opsbrain ./opsbrain
COPY api ./api

# do not run as root
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
