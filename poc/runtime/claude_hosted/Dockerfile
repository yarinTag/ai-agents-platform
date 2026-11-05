# Build only on explicit deployment authorization. BASE_IMAGE must be a trusted
# digest-pinned Python 3.12+ image. Run the resulting image by digest as well.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep ca-certificates && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app /workspace/repo
RUN python3 -m pip install --no-cache-dir claude-agent-sdk==0.2.177
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
USER 1000:1000
WORKDIR /tmp
