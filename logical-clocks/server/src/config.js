const config = {
    nodeId: process.env.NODE_ID || 'local-node',
    port: parseInt(process.env.PORT) || 3000,
    isDashboard: process.env.IS_DASHBOARD === 'true',
    
    
    nodeUrls: process.env.NODE_URLS ? 
      process.env.NODE_URLS.split(',') : 
      [],
    
    
    eventInterval: 5000,
    
    
    messageProbability: 0.4,
    
    
    algorithm: 'lamport',
    
    
    maxSimulationTime: 0
  };
  
  export default config;