FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml schema.sql ./
COPY src/ src/

RUN pip install --no-cache-dir .[search]

EXPOSE 18797
CMD ["python", "-m", "streaming_catalog", "search", "--host", "0.0.0.0"]
