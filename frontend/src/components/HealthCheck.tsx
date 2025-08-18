
import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

const API_BASE_URL = 'http://localhost:5000';

const HealthCheck = () => {
  const [status, setStatus] = useState<'checking' | 'healthy' | 'error'>('checking');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
          setStatus('healthy');
        } else {
          setStatus('error');
        }
      } catch (error) {
        setStatus('error');
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed top-4 right-4 z-50">
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
        status === 'healthy' ? 'bg-green-100 text-green-800' :
        status === 'error' ? 'bg-red-100 text-red-800' :
        'bg-yellow-100 text-yellow-800'
      }`}>
        {status === 'checking' && <Loader2 className="w-4 h-4 animate-spin" />}
        {status === 'healthy' && <CheckCircle className="w-4 h-4" />}
        {status === 'error' && <XCircle className="w-4 h-4" />}
        <span>
          Backend: {status === 'healthy' ? 'Connected' : status === 'error' ? 'Disconnected' : 'Checking...'}
        </span>
      </div>
    </div>
  );
};

export default HealthCheck;
