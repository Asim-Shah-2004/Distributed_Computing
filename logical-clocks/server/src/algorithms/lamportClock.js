/**
 * Lamport's Logical Clock implementation
 * 
 * This implements the algorithm described by Leslie Lamport in
 * "Time, Clocks, and the Ordering of Events in a Distributed System"
 */

class LamportClock {
    constructor(nodeId) {
      this.nodeId = nodeId;
      this.clock = 0;
      this.eventLog = [];
    }
  
    // Get current clock value
    getTime() {
      return this.clock;
    }
  
    // Increment clock for internal event
    tick() {
      this.clock += 1;
      
      const event = {
        type: 'local',
        nodeId: this.nodeId,
        clock: this.clock,
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
    }
  
    // Handle sending a message
    send() {
      this.clock += 1;
      
      const event = {
        type: 'send',
        nodeId: this.nodeId,
        clock: this.clock,
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
    }
  
    // Handle receiving a message
    receive(messageClock) {
      // Update clock to be greater than both local clock and message clock
      this.clock = Math.max(this.clock, messageClock) + 1;
      
      const event = {
        type: 'receive',
        nodeId: this.nodeId,
        clock: this.clock,
        receivedClock: messageClock,
        timestamp: Date.now()
      };
      
      this.eventLog.push(event);
      return event;
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
  
  export default LamportClock;