ARG PYTHON_VERSION=3.14.3
ARG ALPINE_VERSION=3.23

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    sqlite-dev \
    cargo

RUN python -m venv "${VIRTUAL_ENV}"

COPY pyproject.toml README.md ./
COPY src ./src
COPY workspace ./workspace
COPY .streamlit ./.streamlit
COPY scripts ./scripts
COPY *.md ./

RUN pip install --upgrade pip setuptools wheel && pip install .


FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PYTHONPATH=/app/src
ENV ALA_DATABASE_URL=sqlite:////app/data/audit_manager.db
ENV ALA_OFFLINE_MODE=true
ENV ALA_SECRET_FILES_DIR=/app/data/secrets

WORKDIR /app

RUN apk add --no-cache \
    ca-certificates \
    curl \
    libffi \
    libstdc++ \
    openssl \
    sqlite-libs \
    tini \
    wget \
  && addgroup -S app \
  && adduser -S -D -H -h /app -G app -u 10001 app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

RUN chmod +x /app/scripts/docker-entrypoint.sh \
  && mkdir -p /app/data/secrets \
  && chown -R app:app /app

USER app

VOLUME ["/app/data"]

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8501/_stcore/health || exit 1

ENTRYPOINT ["/sbin/tini", "--", "/app/scripts/docker-entrypoint.sh"]
