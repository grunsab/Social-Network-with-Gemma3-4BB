import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Post from './Post'; // Re-use Post component
import './Profile.css'; // Import the CSS file
import Spinner from './Spinner'; // Import Spinner

function Profile() {
  const { username } = useParams(); // Get username from URL parameter
  const { currentUser } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false); // Loading state for friend actions

  // Use useCallback for fetchProfile to prevent re-renders if passed as prop
  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`/api/v1/profiles/${username}`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch profile');
      }
      const data = await response.json();
      setProfileData(data);
    } catch (err) {
      console.error("Error fetching profile:", err);
      setError(err.message || 'Could not load profile.');
      setProfileData(null); // Clear profile data on error
    } finally {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    fetchProfile();
    // Dependency array includes username to re-fetch if URL changes
  }, [fetchProfile]);

  // --- Friendship Action Handlers ---
  const handleFriendAction = async (actionType, endpoint, method, body = null) => {
      setActionLoading(true);
      setError(''); // Clear previous errors
      try {
          const options = { 
              method: method,
              headers: body ? { 'Content-Type': 'application/json' } : {},
          };
          if (body) {
              options.body = JSON.stringify(body);
          }
          
          const response = await fetch(endpoint, options);
          const data = await response.json(); // Try to parse JSON even for errors

          if (!response.ok) {
              throw new Error(data.message || `Failed to ${actionType}`);
          }
          
          console.log(`${actionType} successful:`, data);
          // Refresh profile data to show updated status
          fetchProfile(); 
          
      } catch (err) {
          console.error(`Error ${actionType}:`, err);
          setError(err.message || `An error occurred during ${actionType}.`);
      } finally {
          setActionLoading(false);
      }
  };

  const handleSendRequest = () => {
      if (!profileData?.user?.id) return;
      handleFriendAction('send request', '/api/v1/friend-requests', 'POST', { user_id: profileData.user.id });
  };
  
  const handleCancelRequest = () => {
      if (!profileData?.pending_request_id) return;
      handleFriendAction('cancel request', `/api/v1/friend-requests/${profileData.pending_request_id}`, 'DELETE');
  };
  
  const handleAcceptRequest = () => {
       if (!profileData?.pending_request_id) return;
      handleFriendAction('accept request', `/api/v1/friend-requests/${profileData.pending_request_id}`, 'PUT', { action: 'accept' });
  };
  
  const handleRejectRequest = () => {
       if (!profileData?.pending_request_id) return;
      handleFriendAction('reject request', `/api/v1/friend-requests/${profileData.pending_request_id}`, 'PUT', { action: 'reject' });
  };
  
  const handleUnfriend = () => {
      if (!profileData?.user?.id) return;
      if (!window.confirm(`Are you sure you want to unfriend ${profileData.user.username}?`)) return;
      handleFriendAction('unfriend', `/api/v1/friendships/${profileData.user.id}`, 'DELETE');
  };

  // <<< Add handler for deleting posts from the profile view >>>
  const handlePostDeleted = (deletedPostId) => {
     console.log("Post deleted from profile, removing from list:", deletedPostId);
     setProfileData(prevData => {
         if (!prevData) return null;
         return {
             ...prevData,
             posts: prevData.posts.filter(post => post.id !== deletedPostId)
         };
     });
  };

  if (loading) return <Spinner contained={true} />; // Use spinner for initial profile load
  // Show profile error and action error separately
  const profileError = !profileData && error;
  const actionError = profileData && error;
  if (profileError) return <p className="error-message">Error: {error}</p>;
  if (!profileData) return <p>Profile not found.</p>; // Should be caught by error usually

  const { user, posts, interests, friendship_status } = profileData;

  // Helper function to render friendship buttons
  const renderFriendshipActions = () => {
    const buttonProps = { disabled: actionLoading }; // Disable buttons during action

    if (friendship_status === 'SELF') {
      return <p>(This is your profile)</p>;
    }
    if (friendship_status === 'FRIENDS') {
      return <button onClick={handleUnfriend} {...buttonProps}>Unfriend</button>;
    }
    if (friendship_status === 'PENDING_SENT') {
      return <button onClick={handleCancelRequest} {...buttonProps}>Cancel Request</button>;
    }
    if (friendship_status === 'PENDING_RECEIVED') {
      return (
        <>
          <button onClick={handleAcceptRequest} {...buttonProps}>Accept Request</button>
          <button onClick={handleRejectRequest} {...buttonProps}>Reject Request</button>
        </>
      );
    }
    // Default: status === 'NONE'
    return <button onClick={handleSendRequest} {...buttonProps}>Send Friend Request</button>;
  };

  return (
    // Apply profile-container class (could also add card if desired)
    <div className="profile-container"> 
      {/* Profile Header section */}
      <div className="profile-header">
        {user.profile_picture && 
          <img 
            src={user.profile_picture} 
            alt={`${user.username}'s profile`} 
            className="profile-picture" // Apply class
          />
        }
        <div className="profile-info"> {/* Wrapper for text info */}
            <h2 className="profile-username">{user.username}</h2>
            <div className="profile-details"> {/* Wrapper for details */}
                {/* Only show ID on own profile? Optional */} 
                {/* <p>ID: {user.id}</p> */}
                {friendship_status === 'SELF' && <p>Email: {user.email}</p>} 
                {friendship_status === 'SELF' && <p>Invites Left: {user.invites_left}</p>}
            </div>
            {/* Friendship Actions (moved inside info for better layout potentially) */}
            <div className="profile-actions"> 
               {renderFriendshipActions()}
               {actionLoading && <Spinner inline={true} />} {/* Use inline spinner for actions */} 
               {/* Use error-message class */} 
               {actionError && <p className="error-message">{actionError}</p>} 
            </div>
        </div>
      </div>

      {/* Interests Section */}
      <div className="profile-section profile-interests"> 
        <h3>Interests</h3>
        {interests.length > 0 ? (
          <ul>
            {interests.map(interest => (
              <li key={interest.category}>{interest.category} (Score: {interest.score.toFixed(2)})</li>
            ))}
          </ul>
        ) : (
          <p>No interests recorded yet.</p>
        )}
      </div>

      {/* Posts Section */}
      <div className="profile-section profile-posts"> 
        <h3>Posts</h3>
        {posts.length === 0 ? (
          <p>No posts to display.</p>
        ) : (
          posts.map(post => (
            <Post key={post.id} post={post} onDelete={handlePostDeleted} />
          ))
        )}
      </div>
    </div>
  );
}

export default Profile; 