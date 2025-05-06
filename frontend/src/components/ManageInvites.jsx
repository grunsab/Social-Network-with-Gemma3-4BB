import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import './ManageInvites.css'; // Import the CSS file
import Spinner from './Spinner'; // Import Spinner
import { FaCopy } from 'react-icons/fa'; // Import Copy icon

function ManageInvites() {
  const { currentUser } = useAuth(); // Needed?
  const [invitesData, setInvitesData] = useState({ unused_codes: [], used_codes: [], invites_left: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);

  const fetchInvites = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/invites');
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch invite codes');
      }
      const data = await response.json();
      setInvitesData(data);
    } catch (err) {
      console.error("Error fetching invites:", err);
      setError(err.message || 'Could not load invite codes.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInvites();
  }, [fetchInvites]);

  const handleGenerateCode = async () => {
    setGenerating(true);
    setError(''); // Clear previous errors
    try {
        const response = await fetch('/api/v1/invites', { method: 'POST' });
        const data = await response.json(); // Read body even on error
        if (!response.ok) {
            throw new Error(data.message || 'Failed to generate code');
        }
        // Success - refetch the invite list to show the new code and updated count
        fetchInvites(); 
    } catch (err) {
        console.error("Error generating invite code:", err);
        setError(err.message || 'Could not generate new code.');
    } finally {
        setGenerating(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
        alert('Registration URL copied to clipboard!');
    }, (err) => {
        alert('Failed to copy URL.');
        console.error('Could not copy text: ', err);
    });
  };

  if (loading) return <Spinner contained={true} />; // Use spinner for initial load

  return (
    <div className="invites-container card">
      <h2>Manage Invite Codes</h2>
      <p className="invites-summary">You have <strong>{invitesData.invites_left}</strong> invites remaining.</p>
      
      <div className="generate-invite-section">
        <button onClick={handleGenerateCode} disabled={generating || invitesData.invites_left <= 0}>
          {generating ? <Spinner inline={true} /> : 'Generate New Invite Code'}
        </button>
        {error && <p className="error-message">Error: {error}</p>}
        {!generating && invitesData.invites_left <= 0 && <span className="no-invites-message">(No invites left)</span>}
      </div>

      <div className="invites-list-section">
        <h3>Unused Invite Codes</h3>
        {invitesData.unused_codes.length > 0 ? (
          <ul className="invites-list">
            {invitesData.unused_codes.map(code => (
              <li key={code.id} className="invite-list-item">
                <code className="invite-code">{code.code}</code>
                <div className="invite-actions">
                  {code.registration_url ? (
                    <button onClick={() => copyToClipboard(code.registration_url)} className="icon-button">
                      <FaCopy style={{ verticalAlign: 'middle', marginRight: '0.3em' }}/>
                      Copy Link
                    </button>
                  ) : (
                    <span className="invite-details">(Reg URL missing)</span>
                  )}
                </div>
                <small className="invite-details"> (Created: {new Date(code.timestamp).toLocaleDateString()})</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>No unused invite codes.</p>
        )}
      </div>

      <div className="invites-list-section">
        <h3>Used Invite Codes</h3>
        {invitesData.used_codes.length > 0 ? (
          <ul className="invites-list">
            {invitesData.used_codes.map(code => (
              <li key={code.id} className="invite-list-item">
                <code className="invite-code">{code.code}</code>
                <span>Used by: {code.used_by_username || `User ID ${code.used_by_id}`}</span>
                <small className="invite-details"> (Created: {new Date(code.timestamp).toLocaleDateString()})</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>No used invite codes.</p>
        )}
      </div>
    </div>
  );
}

export default ManageInvites; 