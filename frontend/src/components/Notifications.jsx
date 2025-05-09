import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { formatToLocalDateTime, formatToLocalDate } from '../utils/dateUtils';

function Notifications() {
  const { currentUser, setUnreadCount } = useAuth(); // Assuming setUnreadCount is available from AuthContext
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
        // After fetching, update the unread count based on the fresh data
        const currentUnread = data.filter(n => !n.is_read).length;
        setUnreadCount(currentUnread);
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
  }, [currentUser, setUnreadCount]); // Add setUnreadCount to dependency array

  const handleNotificationClick = async (notif) => {
    // Optimistically mark as read on the frontend and update count
    // This provides a faster UI update
    if (!notif.is_read) {
      setNotifications(prevNotifications =>
        prevNotifications.map(n =>
          n.id === notif.id ? { ...n, is_read: true } : n
        )
      );
      setUnreadCount(prevCount => Math.max(0, prevCount - 1));
    }

    try {
      // Mark as read on the backend
      await fetch(`/api/v1/notifications/${notif.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, // Important: Flask expects JSON for PATCH
        body: JSON.stringify({ is_read: true }) // Send the update in the body
      });
      // No need to re-fetch, optimistic update handled it.
      // If backend failed, we might want to revert the optimistic update,
      // but for now, we'll keep it simple.
    } catch (err) {
      console.error('Failed to mark notification as read', err);
      // Optionally revert optimistic update here if backend call fails
      // For now, log the error.
    }
    // Navigate to the specific post route
    navigate(`/posts/${notif.post_id}`);
  };

  if (loading) return <p>Loading notifications...</p>;
  if (error) return <p className="error-message">Error: {error}</p>;

  const unreadNotifications = notifications.filter(notif => !notif.is_read);

  if (unreadNotifications.length === 0) return <p>No unread notifications.</p>;

  return (
    <div className="card">
      <h3>Notifications</h3>
      <ul className="notifications-list">
        {unreadNotifications.map((notif) => (
          <li
            key={notif.id}
            onClick={() => handleNotificationClick(notif)}
            className="notification-item"
            // No need for fontWeight style as we are only showing unread
          >
            {notif.actor.username} {notif.notification_type === 'comment' ? 'commented on your post' : notif.notification_type}
            <span className="notification-timestamp">
              {formatToLocalDateTime(notif.timestamp)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Notifications;