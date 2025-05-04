FROM node:18-alpine

WORKDIR /app

# Create package.json
RUN echo '{"name":"load-balancing-demo","version":"1.0.0","main":"index.js","dependencies":{"express":"^4.18.2"}}' > package.json

# Install dependencies
RUN npm install

# Copy application code
COPY index.js .

EXPOSE 3000

CMD ["node", "index.js"]