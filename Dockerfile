# ============================================================================
# Multi-Stage Dockerfile für Football Dashboard
# Stage 1: Dependencies
# Stage 2: Runtime
# ============================================================================

FROM python:3.11-slim as base

# Setze Umgebungsvariablen
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Arbeitsverzeichnis
WORKDIR /app

# ============================================================================
# Stage 1: Dependencies installieren
# ============================================================================

FROM base as dependencies

# Kopiere requirements
COPY api/requirements.txt .

# Installiere Python-Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime Image
# ============================================================================

FROM base as runtime

# Kopiere installierte Packages von dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Kopiere Application Code
COPY api/main.py /app/
COPY web /app/web

# Erstelle non-root user für Security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Wechsel zu non-root user
USER appuser

# Exponiere Port
EXPOSE 8080

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)"

# Starte Application
CMD ["python", "main.py"]
