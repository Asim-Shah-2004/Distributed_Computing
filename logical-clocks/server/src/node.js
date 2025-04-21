import axios from 'axios';
import LamportClock from './algorithms/lamportClock.js';
import VectorClock from './algorithms/vectorClock.js';
import config from './config.js';

class DistributedNode {
  constructor() {
    this.nodeId = config.nodeId;
    this.nodeUrls = config.nodeUrls;
    this.algorithm = config.algorithm;
    
    // Parse node IDs from URLs for vector clock initialization
    this.allNodeIds = [this.nodeId, ...this.nodeUrls.map(url => {
      const parts = url.split('/');
      return parts[parts.length - 2];
    })];
    
    // Initialize both clock types
    this.lamportClock = new LamportClock(this.nodeId);
    this.vectorClock = new VectorClock(this.nodeId, this.allNodeIds);
    
    // Current active clock based on configuration
    this.clock = this.algorithm === 'lamport' ? this.lamportClock : this.vectorClock;
    
    console.log(`Node ${this.nodeId} initialized with ${this.algorithm} clock`);
    console.log(`Connected to nodes: ${this.nodeUrls.join(', ')}`);
  }

  // Switch between clock algorithms
  setAlgorithm(algorithm) {
    if (algorithm !== 'lamport' && algorithm !== 'vector') {
      throw new Error('Algorithm must be either "lamport" or "vector"');
    }
    
    this.algorithm = algorithm;
    this.clock = algorithm === 'lamport' ? this.lamportClock : this.vectorClock;
    console.log(`Switched to ${algorithm} clock`);
    
    return { algorithm, nodeId: this.nodeId };
  }

  // Get current clock value
  getClockValue() {
    return {
      nodeId: this.nodeId,
      algorithm: this.algorithm,
      clock: this.clock.getTime(),
      lamportClock: this.lamportClock.getTime(),
      vectorClock: this.vectorClock.getTime()
    };
  }

  // Record a local event
  recordLocalEvent() {
    const event = this.clock.tick();
    console.log(`[${this.nodeId}] Local event: ${JSON.stringify(event.clock)}`);
    return event;
  }

  // Send a message to another node
  async sendMessage(targetUrl) {
    // Update local clock for send event
    const sendEvent = this.clock.send();
    const clockValue = this.clock.getTime();
    
    console.log(`[${this.nodeId}] Sending message to ${targetUrl} with clock: ${JSON.stringify(clockValue)}`);
    
    try {
      // Send the message with current clock value
      const response = await axios.post(`${targetUrl}/message`, {
        sender: this.nodeId,
        clock: clockValue,
        algorithm: this.algorithm,
        timestamp: Date.now()
      });
      
      return {
        success: true,
        event: sendEvent,
        response: response.data
      };
    } catch (error) {
      console.error(`Failed to send message to ${targetUrl}:`, error.message);
      return {
        success: false,
        event: sendEvent,
        error: error.message
      };
    }
  }

  // Receive a message from another node
  receiveMessage(message) {
    const { sender, clock: messageClock, algorithm } = message;
    
    // Ensure we're using the same algorithm as the sender
    if (algorithm !== this.algorithm) {
      this.setAlgorithm(algorithm);
    }
    
    // Update clock based on received message
    const receiveEvent = this.clock.receive(messageClock);
    
    console.log(`[${this.nodeId}] Received message from ${sender} with clock: ${JSON.stringify(messageClock)}`);
    console.log(`[${this.nodeId}] Updated clock: ${JSON.stringify(this.clock.getTime())}`);
    
    return {
      nodeId: this.nodeId,
      event: receiveEvent,
      timestamp: Date.now()
    };
  }

  // Randomly generate events (local or send)
  startEventGeneration(interval = config.eventInterval) {
    if (this.eventInterval) {
      clearInterval(this.eventInterval);
    }
    
    this.eventInterval = setInterval(async () => {
      // Random decision: local event or send message
      const sendMessage = Math.random() < config.messageProbability && this.nodeUrls.length > 0;
      
      if (sendMessage) {
        // Randomly select a target node
        const targetIndex = Math.floor(Math.random() * this.nodeUrls.length);
        const targetUrl = this.nodeUrls[targetIndex];
        
        await this.sendMessage(targetUrl);
      } else {
        this.recordLocalEvent();
      }
    }, interval);
    
    console.log(`[${this.nodeId}] Started generating events every ${interval}ms`);
    return { status: 'started', interval };
  }

  // Stop event generation
  stopEventGeneration() {
    if (this.eventInterval) {
      clearInterval(this.eventInterval);
      this.eventInterval = null;
      console.log(`[${this.nodeId}] Stopped generating events`);
      return { status: 'stopped' };
    }
    return { status: 'already stopped' };
  }

  // Get event logs for both clock types
  getEventLogs() {
    return {
      nodeId: this.nodeId,
      algorithm: this.algorithm,
      lamportEvents: this.lamportClock.getEventLog(),
      vectorEvents: this.vectorClock.getEventLog()
    };
  }
}

export default DistributedNode;