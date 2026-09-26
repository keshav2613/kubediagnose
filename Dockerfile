FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create a dedicated non-root runtime user with a numeric UID/GID.
RUN groupadd --system --gid 10001 kubediagnose \
    && useradd \
        --system \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        kubediagnose

# Copy dependency metadata first for Docker layer caching.
COPY pyproject.toml README.md ./

# Copy application source.
COPY kubediagnose ./kubediagnose

# Install KubeDiagnose.
RUN pip install --no-cache-dir .

# Run as an unprivileged user.
USER 10001:10001

ENTRYPOINT ["kubediagnose"]
CMD ["--help"]