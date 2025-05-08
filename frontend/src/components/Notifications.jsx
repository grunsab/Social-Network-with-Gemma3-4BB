import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

function Notifications() {
  const { currentUser } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchNotifications() {
      setLoading(true);
      setError('');
      try {
        const resp = await fetch('/api/v1/notifications', { credentials: 'include' });
        if (!resp.ok) {
          const data = await resp.json();
          throw new Error(data.message || 'Failed to fetch notifications');
        }
        const data = await resp.json();
        setNotifications(data);
      } catch (err) {
        console.error(err);
        setError(err.message || 'Error loading notifications');
      } finally {
        setLoading(false);
      }
    }
    if (currentUser) {
      fetchNotifications();
    }
  }, [currentUser]);

  const handleNotificationClick = async (notif) => {
    try {
      await fetch(`/api/v1/notifications/${notif.id}`, { method: 'PATCH', credentials: 'include' });
    } catch (err) {
      console.error('Failed to mark notification as read', err);
    }
    // Navigate to the specific post route
    navigate(`/posts/${notif.post_id}`);
  };

  if (loading) return <p>Loading notifications...</p>;
  if (error) return <p className="error-message">Error: {error}</p>;
  if (notifications.length === 0) return <p>No notifications.</p>;

  return (
    <div>
      <h3>Notifications</h3>
      <ul>
        {notifications.map((notif) => (
          <li
            key={notif.id}
            onClick={() => handleNotificationClick(notif)}
            style={{ cursor: 'pointer', fontWeight: notif.is_read ? 'normal' : 'bold', marginBottom: '0.5rem' }}
          >
            {notif.actor.username} {notif.notification_type === 'comment' ? 'commented on your post' : notif.notification_type}
            <span style={{ marginLeft: '0.5rem', color: '#888' }}>
              {new Date(notif.timestamp).toLocaleString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Notifications;