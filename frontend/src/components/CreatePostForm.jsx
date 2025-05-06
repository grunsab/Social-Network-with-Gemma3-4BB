import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext'; // To ensure user is logged in, though ProtectedRoute handles page access
import Spinner from './Spinner'; // Implied import for Spinner component

function CreatePostForm({ onPostCreated }) { // Accept callback to refresh post list
  const { currentUser } = useAuth();
  const [content, setContent] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [privacy, setPrivacy] = useState('PUBLIC'); // Default privacy
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleImageChange = (event) => {
    if (event.target.files && event.target.files[0]) {
        // Check file size (e.g., < 10MB)
        if (event.target.files[0].size > 10 * 1024 * 1024) {
            setError('Image file is too large (max 10MB).');
            setImageFile(null);
            event.target.value = null; // Clear the input
        } else {
            setImageFile(event.target.files[0]);
            setError(''); // Clear error if size is okay
        }
    } else {
        setImageFile(null);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!content && !imageFile) {
      setError('Post must contain text or an image.');
      return;
    }
    setError('');
    setLoading(true);

    const formData = new FormData();
    formData.append('content', content);
    formData.append('privacy', privacy);
    if (imageFile) {
      formData.append('image', imageFile);
    }

    try {
      const response = await fetch('/api/v1/posts', {
        method: 'POST',
        // No 'Content-Type': 'application/json' header for FormData
        // The browser will set the correct multipart/form-data header
        body: formData,
      });

      const data = await response.json(); // Still expect JSON response

      if (!response.ok) {
        setError(data.message || 'Failed to create post.');
      } else {
        // Post created successfully
        console.log('Post created:', data.post);
        // Clear the form
        setContent('');
        setImageFile(null);
        setPrivacy('PUBLIC');
        document.getElementById('post-image-input').value = null; // Clear file input
        
        // Notify parent component (Dashboard) to refresh posts
        if (onPostCreated) {
          onPostCreated(data.post); // Pass the new post data if needed
        }
      }
    } catch (err) {
      console.error("Create post API call failed:", err);
      setError('Failed to connect to the server. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  // Ensure user is logged in to see the form (though page is protected)
  if (!currentUser) return null; 

  return (
    // Use card styling for the form container
    <div className="card" style={{ marginBottom: '2rem' }}> 
      <h4>Create New Post</h4>
      {/* Display error above the form */}
      {error && <p className="error-message">{error}</p>}
      <form onSubmit={handleSubmit}>
        {/* Remove inline style from div */}
        <div> 
          <label htmlFor="post-content">What's on your mind?</label>
          <textarea 
            id="post-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows="4" /* Slightly taller */
            placeholder={`What's up, ${currentUser.username}?`}
            // Remove inline style, inherit global style
            // style={{ width: '95%' }}
          />
        </div>
        {/* Remove inline style from div */}
        <div> 
          <label htmlFor="post-image-input">Image (Optional, Max 10MB):</label>
          {/* Input type file might need custom styling later if desired */}
          <input 
            type="file"
            id="post-image-input"
            accept="image/*"
            onChange={handleImageChange}
            className="d-block mt-small" // Use utility classes
            // style={{ display: 'block', marginTop: '0.5em' }} 
          />
        </div>
        {/* Use utility classes for layout */}
        <div className="mt-1 d-flex align-items-center gap-1"> 
          <div> {/* Wrap select and label */} 
            <label htmlFor="post-privacy" className="mb-small">Privacy:</label> {/* Use class */} 
            <select 
              id="post-privacy"
              value={privacy}
              onChange={(e) => setPrivacy(e.target.value)}
              className="w-auto" // Use class
              // style={{ width: 'auto' }} 
            >
              <option value="PUBLIC">Public</option>
              <option value="FRIENDS">Friends Only</option>
            </select>
          </div>
          {/* Use utility class for margin */}
          <button type="submit" disabled={loading} className="ms-auto"> 
            {loading ? <Spinner inline={true} /> : 'Create Post'}
          </button>
        </div>
        {/* Remove error message from here */}
        {/* {error && <p style={{ color: 'red' }}>{error}</p>} */}
        {/* Moved submit button */}
        {/* <button type="submit" disabled={loading}>
          {loading ? 'Posting...' : 'Create Post'}
        </button> */}
      </form>
    </div>
  );
}

export default CreatePostForm; 