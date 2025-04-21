import DistributedNode from './node.js';
import APIServer from './api/server.js';
import config from './config.js';

// Create the node instance
const node = new DistributedNode();

// Create and start the API server
const server = new APIServer(node);
server.start();

// If this is a regular node (not dashboard), start generating events after a delay
if (!config.isDashboard) {
  setTimeout(() => {
    node.startEventGeneration();
  }, 5000);
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('Shutting down node...');
  node.stopEventGeneration();
  process.exit(0);
});