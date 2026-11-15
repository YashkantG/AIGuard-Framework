# Build from the repository root:
#   docker build -f deployment/docker/Dockerfile -t aiguard .
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install ".[postgres]"

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AIGUARD_DATABASE_URL=sqlite:////data/aiguard.db \
    AIGUARD_ARTIFACT_DIR=/data/artifacts
COPY --from=build /install /usr/local
RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin aiguard \
    && mkdir -p /data/artifacts \
    && chown -R aiguard /data
USER 10001
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["aiguard", "serve", "--host", "0.0.0.0", "--port", "8000"]
