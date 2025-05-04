FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip

# Create app directory with proper permissions
RUN mkdir -p /app && chmod 777 /app

# Create a non-root user with UID 1000
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g 1000 -s /bin/bash -m appuser && \
    chown -R appuser:appuser /app

# Keep container running
CMD ["tail", "-f", "/dev/null"]