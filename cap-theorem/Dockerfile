FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the node code
COPY distributed_node.py .

# Create logs directory
RUN mkdir -p logs

# Run the node
CMD ["python", "distributed_node.py"] 