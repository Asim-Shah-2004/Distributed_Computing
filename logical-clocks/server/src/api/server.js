import express from 'express';
import cors from 'cors';
import morgan from 'morgan';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import path from 'path';
import { fileURLToPath } from 'url';
import config from '../config.js';

// Get the directory name in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class APIServer {
  constructor(node) {
    this.node = node;
    this.app = express();
    this.port = config.port;
    this.isDashboard = config.isDashboard;
    
    // Configure middleware
    this.app.use(cors());
    this.app.use(express.json());
    this.app.use(morgan('dev'));
    
    // Set up Socket.IO for real-time updates
    this.server = http.createServer(this.app);
    this.io = new SocketIOServer(this.server, {
      cors: {
        origin: '*',
        methods: ['GET', 'POST']
      }
    });
    
    this.setupRoutes();
    
    if (this.isDashboard) {
      this.setupDashboard();
    }
  }

  setupRoutes() {
    // Get node status and clock info
    this.app.get('/status', (req, res) => {
      res.json(this.node.getClockValue());
    });
    
    // Receive messages from other nodes
    this.app.post('/message', (req, res) => {
      const result = this.node.receiveMessage(req.body);
      
      // Broadcast update to any connected clients
      this.io.emit('clock-update', this.node.getClockValue());
      this.io.emit('event', result);
      
      res.json(result);
    });
    
    // Trigger a local event
    this.app.post('/event', (req, res) => {
      const result = this.node.recordLocalEvent();
      
      // Broadcast update
      this.io.emit('clock-update', this.node.getClockValue());
      this.io.emit('event', result);
      
      res.json(result);
    });
    
    // Send a message to specific node
    this.app.post('/send', async (req, res) => {
      const { targetUrl } = req.body;
      
      if (!targetUrl) {
        return res.status(400).json({ error: 'Target URL is required' });
      }
      
      const result = await this.node.sendMessage(targetUrl);
      res.json(result);
    });
    
    // Get event logs
    this.app.get('/logs', (req, res) => {
      res.json(this.node.getEventLogs());
    });
    
    // Start automatic event generation
    this.app.post('/start', (req, res) => {
      const { interval } = req.body;
      const result = this.node.startEventGeneration(interval);
      res.json(result);
    });
    
    // Stop automatic event generation
    this.app.post('/stop', (req, res) => {
      const result = this.node.stopEventGeneration();
      res.json(result);
    });
    
    // Switch algorithm
    this.app.post('/algorithm', (req, res) => {
      const { algorithm } = req.body;
      
      if (!algorithm || (algorithm !== 'lamport' && algorithm !== 'vector')) {
        return res.status(400).json({ error: 'Algorithm must be either "lamport" or "vector"' });
      }
      
      const result = this.node.setAlgorithm(algorithm);
      
      // Broadcast algorithm change
      this.io.emit('algorithm-change', result);
      
      res.json(result);
    });
  }

  setupDashboard() {
    // Serve static files for dashboard
    const dashboardPath = path.join(__dirname, '../visualization');
    this.app.use(express.static(dashboardPath));
    
    // Dashboard specific routes
    this.app.get('/nodes', async (req, res) => {
      try {
        const nodeStatuses = await Promise.all(
          config.nodeUrls.map(async (url) => {
            try {
              const response = await fetch(`${url}/status`);
              return await response.json();
            } catch (error) {
              return { url, error: error.message, status: 'offline' };
            }
          })
        );
        
        res.json(nodeStatuses);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });
  }

  start() {
    this.server.listen(this.port, () => {
      console.log(`${this.isDashboard ? 'Dashboard' : 'Node'} server running on port ${this.port}`);
    });
    
    this.io.on('connection', (socket) => {
      console.log(`Client connected: ${socket.id}`);
      
      // Send initial state
      socket.emit('clock-update', this.node.getClockValue());
      
      socket.on('disconnect', () => {
        console.log(`Client disconnected: ${socket.id}`);
      });
    });
  }
}

export default APIServer;