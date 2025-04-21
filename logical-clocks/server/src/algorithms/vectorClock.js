/**
 * Vector Clock implementation
 * 
 * This implements the algorithm described by Mattern (1988) and
 * Fidge (1988) independently, extending Lamport's logical clocks
 * to track causality more precisely.
 */

class VectorClock {
    constructor(nodeId, allNodeIds) {
      this.nodeId = nodeId;
      this.clock = {};
      this.eventLog = [];
      
      // Initialize each entry in the vector clock to 0
      allNodeIds.forEach(id => {
        this.clock[id] = 0;
      });
    }
  
    // Get current vector clock value
    getTime() {
      return { ...this.clock };
    }
  
    // Increment local component for internal event
    tick() {
      this.clock[this.nodeId] += 1;
      
      const event = {
        type: 'local',
        nodeId: this.nodeId,
        clock: { ...this.clock },
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
    }
  
    // Handle sending a message
    send() {
      this.clock[this.nodeId] += 1;
      
      const event = {
        type: 'send',
        nodeId: this.nodeId,
        clock: { ...this.clock },
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
    }
  
    // Handle receiving a message
    receive(messageClock) {
      // Update each component of the vector clock
      for (const nodeId in this.clock) {
        this.clock[nodeId] = Math.max(this.clock[nodeId], messageClock[nodeId]);
      }
      
      // Increment local component
      this.clock[this.nodeId] += 1;
      
      const event = {
        type: 'receive',
        nodeId: this.nodeId,
        clock: { ...this.clock },
        receivedClock: { ...messageClock },
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
    }
  
    // Check if event a happens before event b
    static happensBefore(clockA, clockB) {
      let lessThanInOne = false;
      
      for (const nodeId in clockA) {
        if (clockA[nodeId] > clockB[nodeId]) {
          return false;
        }
        if (clockA[nodeId] < clockB[nodeId]) {
          lessThanInOne = true;
        }
      }
      
      return lessThanInOne;
    }
  
    // Check if events are concurrent
    static concurrent(clockA, clockB) {
      return !this.happensBefore(clockA, clockB) && !this.happensBefore(clockB, clockA);
    }
  
    // Get the event history
    getEventLog() {
      return this.eventLog;
    }
    
    // Clear event history (useful for testing)
    clearEventLog() {
      this.eventLog = [];
    }
  }
  
  export default VectorClock;