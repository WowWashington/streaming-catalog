FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir .[search]

EXPOSE 5858
CMD ["python", "-m", "streaming_catalog", "search", "--host", "0.0.0.0"]
