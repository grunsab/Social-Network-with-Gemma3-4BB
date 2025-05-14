import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Post from './Post'; // Re-use Post component
import './Profile.css'; // Import the CSS file
import './ProfilePicture.css'; // Import the profile picture CSS
import Spinner from './Spinner'; // Import Spinner
import AmpersoundRecorder from './AmpersoundRecorder'; // Import AmpersoundRecorder
import { FaTrashAlt, FaPlay, FaPause, FaCamera } from 'react-icons/fa'; // Import icons
import { formatToLocalDateTime, formatToLocalDate } from '../utils/dateUtils';

function Profile() {
  const { username } = useParams(); // Get username from URL parameter
  const { currentUser, refreshUserProfile } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false); // Loading state for friend actions

  // State for user's ampersounds
  const [myAmpersounds, setMyAmpersounds] = useState([]);
  const [loadingAmpersounds, setLoadingAmpersounds] = useState(false);
  const [errorAmpersounds, setErrorAmpersounds] = useState('');
  const [deleteInProgress, setDeleteInProgress] = useState(null); // Track which sound ID is being deleted

  // State for playback on profile page
  const [currentlyPlaying, setCurrentlyPlaying] = useState(null); // { id: soundId, audio: audioObject }
  const [loadingSound, setLoadingSound] = useState(null); // Track which sound is loading
  const [playbackError, setPlaybackError] = useState(''); // Specific error for playback

  // State and handlers for profile picture upload
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = React.useRef(null);

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

  // Fetch user's ampersounds if it's their own profile
  useEffect(() => {
    const fetchMyAmpersounds = async () => {
        if (profileData && profileData.friendship_status === 'SELF') {
            setLoadingAmpersounds(true);
            setErrorAmpersounds('');
            try {
                const response = await fetch('/api/v1/ampersounds/my_sounds', {
                    credentials: 'include' // For session cookie
                });
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.message || 'Failed to fetch your Ampersounds');
                }
                const data = await response.json();
                setMyAmpersounds(data || []);
            } catch (err) {
                console.error("Error fetching Ampersounds:", err);
                setErrorAmpersounds(err.message || 'Could not load your Ampersounds.');
                setMyAmpersounds([]);
            } finally {
                setLoadingAmpersounds(false);
            }
        }
    };

    if (profileData && profileData.friendship_status === 'SELF') {
        fetchMyAmpersounds();
    }
  }, [profileData]); // Rerun when profileData is loaded/changed

  // Cleanup audio on unmount or when playing state changes
  useEffect(() => {
    return () => {
        if (currentlyPlaying?.audio) {
            currentlyPlaying.audio.pause();
        }
    };
  }, [currentlyPlaying]);

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

  // Handler for deleting an Ampersound
  const handleDeleteAmpersound = async (soundId, soundName) => {
      if (!window.confirm(`Are you sure you want to delete the Ampersound "&${soundName}"? This cannot be undone.`)) {
          return;
      }
      setDeleteInProgress(soundId); // Indicate deletion is happening for this ID
      setErrorAmpersounds(''); // Clear previous errors
      try {
          const response = await fetch(`/api/v1/ampersounds/${soundId}`, {
              method: 'DELETE',
              credentials: 'include' // Include session cookie
          });
          const data = await response.json(); // Attempt to parse JSON even on error

          if (!response.ok) {
              throw new Error(data.message || 'Failed to delete Ampersound');
          }

          // Remove from state on success
          setMyAmpersounds(prevSounds => prevSounds.filter(s => s.id !== soundId));
          console.log("Ampersound deleted successfully:", soundId);

      } catch (err) {
          console.error(`Error deleting Ampersound ${soundId}:`, err);
          setErrorAmpersounds(`Error deleting "&${soundName}": ${err.message}`);
      } finally {
          setDeleteInProgress(null); // Clear deletion indicator
      }
  };

  // Playback handler for profile page list
  const handlePlayToggle = async (sound) => {
    setPlaybackError('');
    setLoadingSound(sound.id);

    if (currentlyPlaying?.id === sound.id) {
        currentlyPlaying.audio.pause();
        setCurrentlyPlaying(null);
        setLoadingSound(null);
        return;
    }

    if (currentlyPlaying?.audio) {
        currentlyPlaying.audio.pause();
        setCurrentlyPlaying(null);
    }

    try {
        // Fetch URL and increment count
        const response = await fetch(`/api/v1/ampersounds/${username}/${sound.name}`, {
             credentials: 'include'
        });
         if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.message || `Could not fetch &${sound.name}`);
        }
        const data = await response.json();

        if (data.url) {
            // Update play count in local state
            setMyAmpersounds(prevSounds => prevSounds.map(s => 
                s.id === sound.id ? { ...s, play_count: data.play_count ?? s.play_count } : s
            ));

            const audio = new Audio(data.url);
            setCurrentlyPlaying({ id: sound.id, audio: audio });
            
            audio.play().catch(playError => {
                console.error("Error playing audio:", playError);
                setPlaybackError(`Could not play &${sound.name}: ${playError.message}`);
                setCurrentlyPlaying(null);
            });

            audio.onended = () => {
                setCurrentlyPlaying(null);
            };
        } else {
             throw new Error('Audio URL not found in response.');
        }
    } catch (err) {
        console.error(`Error playing &${sound.name}:`, err);
        setPlaybackError(`Error playing &${sound.name}: ${err.message}`);
        setCurrentlyPlaying(null);
    } finally {
        setLoadingSound(null);
    }
  };

  // Handle file input change for profile picture
  const handleProfilePictureChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.type.match('image.*')) {
      setUploadError('Please select an image file (JPEG, PNG, etc.)');
      return;
    }

    // Validate file size (max 5MB)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError(`File size should be less than 5MB. Current size: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
      return;
    }

    setUploading(true);
    setUploadError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/v1/profiles/upload_picture', {
        method: 'POST',
        credentials: 'include', // Include session cookie
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to upload profile picture');
      }

      const data = await response.json();
      
      // Update profile data with new profile picture URL
      setProfileData(prevData => ({
        ...prevData,
        user: {
          ...prevData.user,
          profile_picture: data.profile_picture
        }
      }));

      // Refresh currentUser in AuthContext to update everywhere in the app
      await refreshUserProfile();

      console.log('Profile picture updated successfully');
    } catch (err) {
      console.error('Error uploading profile picture:', err);
      setUploadError(err.message || 'Failed to upload profile picture');
    } finally {
      setUploading(false);
    }
  };

  // Trigger file input click
  const handleUploadButtonClick = () => {
    fileInputRef.current.click();
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
        <div className="profile-picture-container">
          <img 
            src={user.profile_picture || '/default-profile.png'} 
            alt={`${user.username}'s profile`} 
            className="profile-picture"
          />
          {friendship_status === 'SELF' && (
            <div className="profile-picture-actions">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleProfilePictureChange}
                accept="image/*"
                className="file-input"
                style={{ display: 'none' }}
              />
              <button 
                onClick={handleUploadButtonClick} 
                disabled={uploading}
                className="upload-picture-btn"
                title="Upload new profile picture"
              >
                {uploading ? <Spinner inline={true} size="small" /> : <><FaCamera /> {user.profile_picture ? 'Change' : 'Add'} Photo</>}
              </button>
              {uploadError && <p className="error-message">{uploadError}</p>}
            </div>
          )}
        </div>
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

      {/* Profile picture upload section (newly added) */}
      {friendship_status === 'SELF' && (
        <div className="profile-section profile-picture-upload">
          <h3>Profile Picture</h3>
          <div className="profile-picture-current">
            {user.profile_picture ? (
              <img src={user.profile_picture} alt="Current profile" className="current-profile-picture" />
            ) : (
              <div className="no-profile-picture">No profile picture set</div>
            )}
          </div>
          <div className="profile-picture-actions">
            <button onClick={handleUploadButtonClick} className="upload-button">
              {uploading ? <Spinner inline={true} size="small" /> : 'Upload New Picture'}
            </button>
            <input 
              type="file" 
              accept="image/*" 
              onChange={handleProfilePictureChange} 
              style={{ display: 'none' }} 
              ref={fileInputRef}
            />
          </div>
          {uploadError && <p className="error-message">{uploadError}</p>}
        </div>
      )}

      {/* Ampersound Recorder and List for own profile */} 
      {friendship_status === 'SELF' && (
        <div className="profile-section ampersound-management-section">
          <div className="ampersound-recorder-section">
            <h3>Create New Ampersound</h3>
            <AmpersoundRecorder />
          </div>

          <div className="my-ampersounds-list-section">
            <h3>My Saved Ampersounds ({myAmpersounds.length})</h3>
            {loadingAmpersounds && <Spinner contained={true} />}
            {errorAmpersounds && <p className="error-message">{errorAmpersounds}</p>}
            {playbackError && <p className="error-message">Playback Error: {playbackError}</p>} 
            {!loadingAmpersounds && !errorAmpersounds && myAmpersounds.length === 0 && (
                <p>You haven't created any Ampersounds yet.</p>
            )}
            {!loadingAmpersounds && myAmpersounds.length > 0 && (
                <ul className="ampersound-list">
                    {myAmpersounds.map(sound => (
                        <li key={sound.id} className="ampersound-list-item">
                            <div className="ampersound-item-info">
                                <div className="ampersound-info">
                                    <span className="ampersound-name">&{sound.name}</span>
                                    <span className="ampersound-timestamp">
                                        ({formatToLocalDate(sound.timestamp)})
                                    </span>
                                    {/* Display privacy status */}
                                    <span className={`ampersound-privacy-status ${sound.privacy === 'friends' ? 'privacy-friends' : 'privacy-public'}`}>
                                        ({sound.privacy})
                                    </span>
                                </div>
                                <span className="ampersound-play-count">({sound.play_count ?? 0} plays)</span>
                            </div>
                            <div className="ampersound-item-actions">
                                {/* Play/Pause Button */} 
                                <button 
                                    onClick={() => handlePlayToggle(sound)}
                                    className={`ampersound-play-button icon-button ${currentlyPlaying?.id === sound.id ? 'playing' : ''}`}
                                    disabled={loadingSound === sound.id || deleteInProgress === sound.id}
                                    title={currentlyPlaying?.id === sound.id ? `Pause &${sound.name}` : `Play &${sound.name}`}
                                >
                                    {loadingSound === sound.id ? (
                                        <Spinner inline={true} size="small" />
                                    ) : currentlyPlaying?.id === sound.id ? (
                                        <FaPause /> 
                                    ) : (
                                        <FaPlay />
                                    )}
                                </button>
                                {/* Delete Button */}
                                <button 
                                    className="ampersound-delete-button icon-button"
                                    onClick={() => handleDeleteAmpersound(sound.id, sound.name)}
                                    disabled={deleteInProgress === sound.id}
                                    title={`Delete &${sound.name}`}
                                >
                                    {deleteInProgress === sound.id ? <Spinner inline={true} size="small" /> : <FaTrashAlt />}
                                </button>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
          </div>
        </div>
      )}

      {/* NEW: Wrapper for Interests and Posts */}
      <div className="profile-main-content">
        {/* Interests Section (will be sidebar) */}
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

        {/* Posts Section (will be main area) */}
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
      </div> {/* End of profile-main-content */}
    </div>
  );
}

export default Profile;