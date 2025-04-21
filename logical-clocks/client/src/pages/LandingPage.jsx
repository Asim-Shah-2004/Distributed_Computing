import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Send, Activity, Play, Square, RefreshCw, Server } from 'lucide-react';
import io from 'socket.io-client';

const NodeDashboard = () => {
  const [clockValue, setClockValue] = useState({});
  const [logs, setLogs] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [algorithm, setAlgorithm] = useState('lamport');
  const [targetUrl, setTargetUrl] = useState('');
  const [eventInterval, setEventInterval] = useState(5000);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState('status');
  const [socket, setSocket] = useState(null);
  const [notification, setNotification] = useState(null);

  // Connect to Socket.IO
  useEffect(() => {
    const newSocket = io(window.location.origin);
    setSocket(newSocket);

    newSocket.on('clock-update', (data) => {
      setClockValue(data);
    });

    newSocket.on('event', (data) => {
      showNotification(`New event: ${data.type}`);
      fetchLogs();
    });

    newSocket.on('algorithm-change', (data) => {
      setAlgorithm(data.algorithm);
      showNotification(`Algorithm changed to ${data.algorithm}`);
    });

    return () => newSocket.disconnect();
  }, []);

  // Initial data fetch
  useEffect(() => {
    fetchStatus();
    fetchLogs();
    fetchNodes();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/status');
      const data = await response.json();
      setClockValue(data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const fetchLogs = async () => {
    try {
      const response = await fetch('/logs');
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  const fetchNodes = async () => {
    try {
      const response = await fetch('/nodes');
      const data = await response.json();
      setNodes(data);
    } catch (error) {
      console.error('Error fetching nodes:', error);
    }
  };

  const triggerEvent = async () => {
    try {
      await fetch('/event', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      showNotification('Local event triggered');
    } catch (error) {
      console.error('Error triggering event:', error);
    }
  };

  const sendMessage = async () => {
    if (!targetUrl) {
      showNotification('Please enter a target URL', true);
      return;
    }
    
    try {
      await fetch('/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ targetUrl }),
      });
      showNotification(`Message sent to ${targetUrl}`);
    } catch (error) {
      console.error('Error sending message:', error);
      showNotification('Failed to send message', true);
    }
  };

  const toggleEventGeneration = async () => {
    try {
      if (isGenerating) {
        await fetch('/stop', {
          method: 'POST',
        });
        setIsGenerating(false);
        showNotification('Event generation stopped');
      } else {
        await fetch('/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ interval: eventInterval }),
        });
        setIsGenerating(true);
        showNotification(`Event generation started (${eventInterval}ms)`);
      }
    } catch (error) {
      console.error('Error toggling event generation:', error);
    }
  };

  const switchAlgorithm = async (newAlgorithm) => {
    try {
      await fetch('/algorithm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ algorithm: newAlgorithm }),
      });
      setAlgorithm(newAlgorithm);
      showNotification(`Switched to ${newAlgorithm} algorithm`);
    } catch (error) {
      console.error('Error switching algorithm:', error);
    }
  };

  const showNotification = (message, isError = false) => {
    setNotification({ message, isError });
    setTimeout(() => setNotification(null), 3000);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Navigation header */}
      <header className="bg-gray-800 p-4 shadow-lg">
        <div className="container mx-auto flex justify-between items-center">
          <motion.h1 
            className="text-2xl font-bold flex items-center gap-2"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Server className="text-blue-400" /> 
            Distributed System Dashboard
          </motion.h1>
          
          <motion.div 
            className="flex items-center gap-4"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <button
              className={`px-3 py-2 rounded ${algorithm === 'lamport' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'}`}
              onClick={() => switchAlgorithm('lamport')}
            >
              Lamport Clock
            </button>
            <button
              className={`px-3 py-2 rounded ${algorithm === 'vector' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'}`}
              onClick={() => switchAlgorithm('vector')}
            >
              Vector Clock
            </button>
          </motion.div>
        </div>
      </header>

      {/* Main content */}
      <div className="container mx-auto p-4">
        {/* Tab navigation */}
        <motion.div 
          className="flex mb-6 bg-gray-800 rounded-lg overflow-hidden"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          {['status', 'events', 'network', 'control'].map(tab => (
            <button
              key={tab}
              className={`flex-1 py-3 px-4 capitalize flex items-center justify-center gap-2 transition-colors ${
                activeTab === tab ? 'bg-blue-600' : 'hover:bg-gray-700'
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'status' && <Clock size={18} />}
              {tab === 'events' && <Activity size={18} />}
              {tab === 'network' && <Server size={18} />}
              {tab === 'control' && <RefreshCw size={18} />}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </motion.div>

        {/* Content based on active tab */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            {/* Status Tab */}
            {activeTab === 'status' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <motion.div 
                  className="bg-gray-800 p-6 rounded-lg shadow-lg"
                  whileHover={{ scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                    <Clock className="text-blue-400" /> Clock Status
                  </h2>
                  
                  <div className="overflow-auto max-h-96">
                    {algorithm === 'lamport' ? (
                      <div className="flex flex-col items-center">
                        <motion.div 
                          className="text-6xl font-bold text-blue-400"
                          key={clockValue.timestamp}
                          initial={{ scale: 1.2, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={{ type: "spring", stiffness: 200 }}
                        >
                          {clockValue.timestamp || 0}
                        </motion.div>
                        <p className="text-gray-400 mt-2">Lamport Timestamp</p>
                      </div>
                    ) : (
                      <div>
                        <h3 className="text-lg font-medium mb-2">Vector Clock</h3>
                        <div className="grid grid-cols-2 gap-4">
                          {clockValue.vector && Object.entries(clockValue.vector).map(([nodeId, time]) => (
                            <motion.div 
                              key={nodeId}
                              className="bg-gray-700 p-3 rounded-lg"
                              initial={{ scale: 0.9, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              transition={{ type: "spring", stiffness: 300 }}
                            >
                              <div className="text-sm text-gray-400">Node {nodeId}</div>
                              <div className="text-2xl font-bold text-blue-400">{time}</div>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>

                <motion.div 
                  className="bg-gray-800 p-6 rounded-lg shadow-lg"
                  whileHover={{ scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <h2 className="text-xl font-semibold mb-4">System Info</h2>
                  <div className="space-y-4">
                    <div>
                      <p className="text-gray-400">Current Algorithm</p>
                      <p className="text-lg font-medium capitalize">{algorithm}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Event Generation</p>
                      <p className="text-lg font-medium">{isGenerating ? `Active (${eventInterval}ms)` : 'Inactive'}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Connected Nodes</p>
                      <p className="text-lg font-medium">{nodes.length}</p>
                    </div>
                  </div>
                </motion.div>
              </div>
            )}

            {/* Events Tab */}
            {activeTab === 'events' && (
              <motion.div 
                className="bg-gray-800 p-6 rounded-lg shadow-lg"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5 }}
              >
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <Activity className="text-blue-400" /> Event Logs
                </h2>
                
                <div className="overflow-auto max-h-96">
                  <div className="space-y-2">
                    {logs.map((log, index) => (
                      <motion.div 
                        key={index}
                        className={`p-3 rounded-lg flex justify-between ${
                          log.type === 'send' ? 'bg-blue-900/30 border-l-4 border-blue-500' : 
                          log.type === 'receive' ? 'bg-green-900/30 border-l-4 border-green-500' : 
                          'bg-purple-900/30 border-l-4 border-purple-500'
                        }`}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: index * 0.05, duration: 0.3 }}
                      >
                        <div>
                          <span className="text-sm text-gray-400">
                            {log.timestamp} • {log.type.toUpperCase()}
                          </span>
                          <div className="mt-1">
                            {log.message || `${log.type} event`}
                          </div>
                        </div>
                        <div>
                          {algorithm === 'lamport' ? (
                            <span className="text-xl font-bold text-blue-400">{log.clock}</span>
                          ) : (
                            <div className="text-sm text-gray-400">
                              Vector: {JSON.stringify(log.clock)}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    ))}
                    
                    {logs.length === 0 && (
                      <div className="text-center py-10 text-gray-500">
                        No events recorded yet
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {/* Network Tab */}
            {activeTab === 'network' && (
              <motion.div 
                className="bg-gray-800 p-6 rounded-lg shadow-lg"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5 }}
              >
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <Server className="text-blue-400" /> Network Nodes
                </h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {nodes.map((node, index) => (
                    <motion.div 
                      key={index}
                      className={`p-4 rounded-lg border ${node.status === 'offline' ? 'border-red-500 bg-red-900/20' : 'border-green-500 bg-green-900/20'}`}
                      initial={{ scale: 0.9, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ delay: index * 0.1, duration: 0.3 }}
                      whileHover={{ scale: 1.03 }}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-medium truncate" title={node.url}>
                            {node.url?.replace('http://', '')}
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`inline-block w-2 h-2 rounded-full ${node.status === 'offline' ? 'bg-red-500' : 'bg-green-500'}`}></span>
                            <span className="text-sm text-gray-400 capitalize">{node.status || 'online'}</span>
                          </div>
                        </div>
                        
                        {node.status !== 'offline' && algorithm === 'vector' && (
                          <div className="text-sm bg-gray-700 px-2 py-1 rounded">
                            ID: {node.id || index}
                          </div>
                        )}
                      </div>
                      
                      <div className="mt-3">
                        {node.status !== 'offline' && (
                          algorithm === 'lamport' ? (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-400">Clock Value:</span>
                              <span className="text-blue-400 font-bold">{node.timestamp || '0'}</span>
                            </div>
                          ) : (
                            <div>
                              <div className="text-sm text-gray-400 mb-1">Vector Clock:</div>
                              <div className="text-xs bg-gray-900 p-2 rounded overflow-x-auto">
                                {JSON.stringify(node.vector || {})}
                              </div>
                            </div>
                          )
                        )}
                        
                        {node.status === 'offline' && (
                          <div className="text-sm text-red-400 mt-1">{node.error || 'Connection error'}</div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                  
                  {nodes.length === 0 && (
                    <div className="col-span-full text-center py-10 text-gray-500">
                      No nodes available
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* Control Tab */}
            {activeTab === 'control' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <motion.div 
                  className="bg-gray-800 p-6 rounded-lg shadow-lg"
                  whileHover={{ scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <h2 className="text-xl font-semibold mb-4">Message Control</h2>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Target Node URL</label>
                      <input
                        type="text"
                        className="w-full bg-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="http://localhost:3001"
                        value={targetUrl}
                        onChange={(e) => setTargetUrl(e.target.value)}
                      />
                    </div>
                    
                    <div className="flex gap-3">
                      <motion.button
                        className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded flex items-center justify-center gap-2"
                        onClick={sendMessage}
                        whileTap={{ scale: 0.95 }}
                      >
                        <Send size={16} /> Send Message
                      </motion.button>
                      
                      <motion.button
                        className="flex-1 bg-purple-600 hover:bg-purple-700 text-white py-2 px-4 rounded flex items-center justify-center gap-2"
                        onClick={triggerEvent}
                        whileTap={{ scale: 0.95 }}
                      >
                        <Activity size={16} /> Trigger Event
                      </motion.button>
                    </div>
                  </div>
                </motion.div>
                
                <motion.div 
                  className="bg-gray-800 p-6 rounded-lg shadow-lg"
                  whileHover={{ scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <h2 className="text-xl font-semibold mb-4">Auto-generation</h2>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Event Interval (ms)</label>
                      <input
                        type="number"
                        className="w-full bg-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        min="100"
                        step="100"
                        value={eventInterval}
                        onChange={(e) => setEventInterval(parseInt(e.target.value))}
                        disabled={isGenerating}
                      />
                    </div>
                    
                    <motion.button
                      className={`w-full py-2 px-4 rounded flex items-center justify-center gap-2 ${
                        isGenerating ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'
                      } text-white`}
                      onClick={toggleEventGeneration}
                      whileTap={{ scale: 0.95 }}
                    >
                      {isGenerating ? (
                        <>
                          <Square size={16} /> Stop Generation
                        </>
                      ) : (
                        <>
                          <Play size={16} /> Start Generation
                        </>
                      )}
                    </motion.button>
                  </div>
                </motion.div>
                
                <motion.div 
                  className="bg-gray-800 p-6 rounded-lg shadow-lg md:col-span-2"
                  whileHover={{ scale: 1.01 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <h2 className="text-xl font-semibold mb-4">Data Refresh</h2>
                  
                  <div className="flex gap-3">
                    <motion.button
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 px-4 rounded flex items-center justify-center gap-2"
                      onClick={fetchStatus}
                      whileTap={{ scale: 0.95 }}
                    >
                      <RefreshCw size={16} /> Refresh Status
                    </motion.button>
                    
                    <motion.button
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 px-4 rounded flex items-center justify-center gap-2"
                      onClick={fetchLogs}
                      whileTap={{ scale: 0.95 }}
                    >
                      <RefreshCw size={16} /> Refresh Logs
                    </motion.button>
                    
                    <motion.button
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 px-4 rounded flex items-center justify-center gap-2"
                      onClick={fetchNodes}
                      whileTap={{ scale: 0.95 }}
                    >
                      <RefreshCw size={16} /> Refresh Nodes
                    </motion.button>
                  </div>
                </motion.div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
        
        {/* Notification */}
        <AnimatePresence>
          {notification && (
            <motion.div
              className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg ${
                notification.isError ? 'bg-red-600' : 'bg-blue-600'
              }`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              transition={{ duration: 0.3 }}
            >
              {notification.message}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default NodeDashboard;