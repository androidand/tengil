FROM debian:bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    zfsutils-linux \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy project files
COPY pyproject.toml poetry.lock* ./
COPY tengil/ ./tengil/

# Install Python dependencies
RUN python3 -m venv .venv && \
    .venv/bin/pip install poetry && \
    .venv/bin/poetry install

# Run in mock mode by default
ENV TG_MOCK=1

ENTRYPOINT [".venv/bin/poetry", "run", "tg"]
CMD ["--help"]
