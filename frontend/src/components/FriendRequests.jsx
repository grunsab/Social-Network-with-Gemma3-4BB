import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './FriendRequests.css'; // Import the CSS file
import Spinner from './Spinner'; // Import Spinner

function FriendRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState({}); // Track loading state per request ID

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/friend-requests'); // GET endpoint
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch friend requests');
      }
      const data = await response.json();
      setRequests(data || []); // API returns a list
    } catch (err) {
      console.error("Error fetching friend requests:", err);
      setError(err.message || 'Could not load requests.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleRequestAction = async (requestId, action) => {
    setActionLoading(prev => ({ ...prev, [requestId]: true }));
    setError('');
    try {
        const response = await fetch(`/api/v1/friend-requests/${requestId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        const data = await response.json(); // Read body even on error
        if (!response.ok) {
            throw new Error(data.message || `Failed to ${action} request`);
        }
        console.log(`Request ${requestId} ${action} successful`);
        // Remove the processed request from the list
        setRequests(prev => prev.filter(req => req.id !== requestId));
        // Optionally, show a success message
    } catch (err) {
        console.error(`Error ${action}ing request:`, err);
        setError(err.message || `Could not ${action} the request.`);
    } finally {
         setActionLoading(prev => ({ ...prev, [requestId]: false }));
    }
  };

  if (loading) return <Spinner contained={true} />; // Use spinner for initial load

  return (
    <div className="friend-requests-container card">
      <h2>Pending Friend Requests</h2>
      {error && <p className="error-message">Error: {error}</p>}

      {requests.length === 0 && !loading && (
        <p>No pending friend requests.</p>
      )}

      {requests.length > 0 && (
        <ul className="friend-requests-list">
          {requests.map(req => (
            <li key={req.id} className="friend-request-item">
              <div className="friend-request-sender">
                Request from: <Link to={`/profile/${req.sender.username}`}>{req.sender.username}</Link>
              </div>
              <div className="friend-request-actions">
                <button 
                  onClick={() => handleRequestAction(req.id, 'accept')} 
                  disabled={actionLoading[req.id]}
                  className="accept-button"
                >
                  {actionLoading[req.id] ? <Spinner inline={true} /> : 'Accept'}
                </button>
                <button 
                  onClick={() => handleRequestAction(req.id, 'reject')} 
                  disabled={actionLoading[req.id]}
                  className="reject-button"
                >
                  {actionLoading[req.id] ? <Spinner inline={true} /> : 'Reject'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FriendRequests; 