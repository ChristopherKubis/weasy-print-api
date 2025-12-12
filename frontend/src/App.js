import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);
  const [cpuHistory, setCpuHistory] = useState([]);
  const [memoryHistory, setMemoryHistory] = useState([]);
  const [requestHistory, setRequestHistory] = useState([]);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  const wsRef = useRef(null);

  useEffect(() => {
    // Initial data fetch
    const fetchInitialData = async () => {
      try {
        // Fetch health status
        const healthRes = await axios.get('http://localhost:8000/');
        setHealth(healthRes.data);

        // Fetch request history
        const historyRes = await axios.get('http://localhost:8000/request-history');
        setRequestHistory(historyRes.data.requests);

        setError(null);
      } catch (err) {
        setError('Failed to fetch initial data from API');
        console.error(err);
      }
    };

    fetchInitialData();

    // Setup WebSocket connection
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket Connected');
        setConnectionStatus('Connected ✓');
        setError(null);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'metrics') {
          // Update metrics
          setMetrics(message.data);
          
          // Update charts
          const timestamp = new Date().toLocaleTimeString();
          setCpuHistory(prev => [...prev.slice(-19), { 
            time: timestamp, 
            cpu: message.data.cpu.percent 
          }]);
          setMemoryHistory(prev => [...prev.slice(-19), { 
            time: timestamp, 
            memory: message.data.memory.percent 
          }]);
        } else if (message.type === 'new_request') {
          // Add new request to history
          setRequestHistory(prev => [...prev, message.data].slice(-50));
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
        setError('WebSocket connection error');
        setConnectionStatus('Error ✗');
      };

      ws.onclose = () => {
        console.log('WebSocket Disconnected');
        setConnectionStatus('Disconnected - Reconnecting...');
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
    };

    connectWebSocket();

    // Cleanup
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🖨️ WeasyPrint API Monitor</h1>
        <p>Real-time System Monitoring Dashboard</p>
        <div className="connection-status">
          <span className={`status-indicator ${connectionStatus.includes('Connected') ? 'connected' : 'disconnected'}`}>
            ⚡ {connectionStatus}
          </span>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="dashboard">
        {/* Health Status Card */}
        <div className="card status-card">
          <h2>API Status</h2>
          {health ? (
            <div className="status-info">
              <div className="status-badge success">
                <span className="status-dot"></span>
                {health.status.toUpperCase()}
              </div>
              <p className="status-message">{health.message}</p>
            </div>
          ) : (
            <p className="loading">Loading...</p>
          )}
        </div>

        {/* System Metrics Cards */}
        {metrics && (
          <>
            <div className="card metric-card">
              <h3>CPU Usage</h3>
              <div className="metric-value">
                <span className="value">{metrics.cpu.percent.toFixed(1)}%</span>
              </div>
              <div className="metric-details">
                <p>Cores: {metrics.cpu.count}</p>
              </div>
            </div>

            <div className="card metric-card">
              <h3>Memory Usage</h3>
              <div className="metric-value">
                <span className="value">{metrics.memory.percent.toFixed(1)}%</span>
              </div>
              <div className="metric-details">
                <p>Used: {formatBytes(metrics.memory.used)}</p>
                <p>Total: {formatBytes(metrics.memory.total)}</p>
              </div>
            </div>

            <div className="card metric-card">
              <h3>API Statistics</h3>
              <div className="metric-value">
                <span className="value">{metrics.api.total_requests}</span>
                <span className="label">Total Requests</span>
              </div>
              <div className="metric-details">
                <p>Successful: {metrics.api.successful_conversions}</p>
                <p>Failed: {metrics.api.failed_conversions}</p>
              </div>
            </div>
          </>
        )}

        {/* CPU Chart */}
        <div className="card chart-card">
          <h3>CPU Usage Over Time</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={cpuHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis dataKey="time" stroke="#ccc" />
              <YAxis stroke="#ccc" domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e1e2e', border: '1px solid #444' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="cpu" 
                stroke="#82ca9d" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Memory Chart */}
        <div className="card chart-card">
          <h3>Memory Usage Over Time</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={memoryHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis dataKey="time" stroke="#ccc" />
              <YAxis stroke="#ccc" domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e1e2e', border: '1px solid #444' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="memory" 
                stroke="#8884d8" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Request History Table */}
        <div className="card table-card">
          <h3>📊 Recent PDF Conversion Requests</h3>
          <div className="table-container">
            <table className="request-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Status</th>
                  <th>Duration (s)</th>
                  <th>HTML Size</th>
                  <th>PDF Size</th>
                  <th>CPU %</th>
                  <th>Memory Used</th>
                  <th>Sys Memory %</th>
                </tr>
              </thead>
              <tbody>
                {requestHistory.length > 0 ? (
                  requestHistory.slice().reverse().map((req, index) => (
                    <tr key={index} className={req.status === 'failed' ? 'failed-row' : 'success-row'}>
                      <td>{new Date(req.timestamp).toLocaleTimeString()}</td>
                      <td>
                        <span className={`status-badge ${req.status}`}>
                          {req.status === 'success' ? '✓' : '✗'} {req.status.toUpperCase()}
                        </span>
                      </td>
                      <td>{req.duration_seconds}s</td>
                      <td>{req.html_size_kb} KB</td>
                      <td>{req.pdf_size_kb} KB</td>
                      <td>{req.cpu_usage_percent}%</td>
                      <td>{req.memory_used_mb} MB</td>
                      <td>{req.system_memory_percent}%</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', color: '#999' }}>
                      No requests yet. Try converting an HTML to PDF!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
