// app/index.js - Our server application
const express = require('express');
const os = require('os');
const app = express();
const port = 3000;

// Server name from environment variable or hostname
const serverName = process.env.SERVER_NAME || os.hostname();

// Simple in-memory metrics to demonstrate load
let requestCount = 0;
let activeConnections = 0;

// Middleware to track active connections
app.use((req, res, next) => {
  activeConnections++;
  requestCount++;
  
  // When request is finished, decrement active connections
  res.on('finish', () => {
    activeConnections--;
  });
  
  next();
});

// Main route
app.get('/', (req, res) => {
  // Simulate varying processing times
  const processingTime = Math.floor(Math.random() * 200) + 50;
  
  setTimeout(() => {
    res.send(`
      <html>
      <head>
        <title>Load Balancing Demo</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
          }
          .server-info {
            background-color: #f0f0f0;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
          }
          .metrics {
            display: flex;
            gap: 20px;
          }
          .metric {
            flex: 1;
            background-color: #e6f7ff;
            padding: 10px;
            border-radius: 5px;
          }
          h1 {
            color: #333;
          }
        </style>
      </head>
      <body>
        <h1>NGINX Load Balancing Demo</h1>
        
        <div class="server-info">
          <h2>Request served by: ${serverName}</h2>
          <p>Hostname: ${os.hostname()}</p>
          <p>Processing time: ${processingTime}ms</p>
        </div>
        
        <div class="metrics">
          <div class="metric">
            <h3>Total Requests</h3>
            <p>${requestCount}</p>
          </div>
          <div class="metric">
            <h3>Active Connections</h3>
            <p>${activeConnections}</p>
          </div>
          <div class="metric">
            <h3>Server Uptime</h3>
            <p>${Math.floor(process.uptime())} seconds</p>
          </div>
        </div>
        
        <h3>Request Headers:</h3>
        <pre>${JSON.stringify(req.headers, null, 2)}</pre>
      </body>
      </html>
    `);
  }, processingTime);
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    serverName: serverName,
    activeConnections: activeConnections,
    totalRequests: requestCount
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Server ${serverName} listening at http://localhost:${port}`);
});