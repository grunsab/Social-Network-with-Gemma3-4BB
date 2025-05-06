import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext'; // To check if current user is author for delete button
import { Link } from 'react-router-dom'; // Import Link
import './Post.css'; // Import the CSS file
import Spinner from './Spinner'; // Import Spinner
import { FaTrashAlt, FaRegCommentDots } from 'react-icons/fa'; // Import Trash and Comment icons

// Basic styling for the component -- REMOVED
// const postStyle = { ... };
// const imageStyle = { ... };
// const commentSectionStyle = { ... };
// const commentStyle = { ... };

function Post({ post, onDelete }) { // Accept post object and onDelete callback
  const { currentUser } = useAuth();
  const [comments, setComments] = useState([]);
  const [loadingComments, setLoadingComments] = useState(false);
  const [errorComments, setErrorComments] = useState('');
  const [showComments, setShowComments] = useState(false);
  const [newCommentContent, setNewCommentContent] = useState('');
  const [postingComment, setPostingComment] = useState(false);

  if (!post) return null; // Don't render if no post data

  const isAuthor = currentUser && currentUser.id === post.author?.id;

  // Fetch comments function
  const fetchComments = async () => {
    if (!showComments) return; // Only fetch if section is open
    setLoadingComments(true);
    setErrorComments('');
    try {
      const response = await fetch(`/api/v1/posts/${post.id}/comments`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch comments');
      }
      const data = await response.json();
      setComments(data || []); // API returns list directly
    } catch (error) {
      console.error("Error fetching comments:", error);
      setErrorComments(error.message || 'Could not load comments.');
    } finally {
      setLoadingComments(false);
    }
  };

  // Fetch comments when showComments becomes true
  useEffect(() => {
    if (showComments) {
      fetchComments();
    }
    // Intentionally not adding fetchComments to dependency array
    // to avoid re-fetching unless showComments changes from false to true.
  }, [showComments, post.id]); 

  const handleDelete = async () => {
    if (!isAuthor) return; // Should not happen if button isn't shown
    if (!window.confirm("Are you sure you want to delete this post?")) return;

    try {
        const response = await fetch(`/api/v1/posts/${post.id}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to delete post');
        }
        console.log('Post deleted successfully');
        if (onDelete) {
            onDelete(post.id); // Notify parent to remove post from list
        }
    } catch (error) {
        console.error("Error deleting post:", error);
        alert(`Error deleting post: ${error.message}`); // Show error to user
    }
  };

  const handlePostComment = async (event) => {
      event.preventDefault();
      if (!newCommentContent.trim()) return;
      setPostingComment(true);
      setErrorComments(''); // Clear previous comment errors
      
      try {
          const response = await fetch(`/api/v1/posts/${post.id}/comments`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json'
              },
              body: JSON.stringify({ content: newCommentContent })
          });
          if (!response.ok) {
              const data = await response.json();
              throw new Error(data.message || 'Failed to post comment');
          }
          const newComment = await response.json();
          setComments(prevComments => [...prevComments, newComment]); // Add new comment to state
          setNewCommentContent(''); // Clear input field
      } catch (error) {
          console.error("Error posting comment:", error);
          setErrorComments(`Error posting comment: ${error.message}`); // Show error near comment input
      } finally {
          setPostingComment(false);
      }
  };

  const handleDeleteComment = async (commentId) => {
      if (!window.confirm("Are you sure you want to delete this comment?")) return;
      
      try {
          const response = await fetch(`/api/v1/comments/${commentId}`, {
              method: 'DELETE'
          });
          if (!response.ok) {
              const data = await response.json();
              throw new Error(data.message || 'Failed to delete comment');
          }
          setComments(prevComments => prevComments.filter(comment => comment.id !== commentId)); // Remove from state
      } catch (error) {   
          console.error("Error deleting comment:", error);
          alert(`Error deleting comment: ${error.message}`); // Show error
      }
  };

  return (
    // Apply card class and post class
    <div className="card post"> 
      {/* Post Header */}
      <div className="post-header">
          <Link to={`/profile/${post.author?.username}`} className="post-author-link">
            {post.author?.username || 'Unknown User'}
          </Link>
          <span className="post-timestamp">{new Date(post.timestamp).toLocaleString()}</span>
      </div>

      {/* Post Image */}
      {post.image_url && (
        <img src={post.image_url} alt="Post image" className="post-image" />
      )}
      
      {/* Post Content */}
      {/* Only render content paragraph if content exists */} 
      {post.content && <p className="post-content">{post.content}</p>} 

      {/* Display Categories/Classifications */}
      {typeof post.classification_scores === 'object' && 
       post.classification_scores !== null && 
       Object.keys(post.classification_scores).length > 0 && (
        <div className="post-categories"> 
          <strong>Categories: </strong>
          {Object.entries(post.classification_scores)
            .filter(([_, score]) => score >= 0.5) // Filter categories with score >= 0.5
            .map(([category, score], index, arr) => (
              <span key={category}>
                <Link to={`/category/${encodeURIComponent(category)}`}>{category}</Link>
                {` (${score.toFixed(2)})`}
                {index < arr.length - 1 ? ', ' : ''} {/* Add comma separator */}
              </span>
            ))}
        </div>
      )}
      
      {/* Post Footer/Actions */}
      <div className="post-footer"> 
        <span className="post-privacy">Privacy: {post.privacy}</span>
        {isAuthor && (
           <button onClick={handleDelete} className="post-delete-button icon-button">
             <FaTrashAlt /> {/* Add Trash Icon */} 
             <span>Delete Post</span>
           </button>
        )}
      </div>

      {/* --- Comments Section --- */}
      <div className="post-comments-section"> 
        <button onClick={() => setShowComments(!showComments)} className="toggle-comments-button">
          <FaRegCommentDots style={{ marginRight: '0.4em', verticalAlign: 'middle' }} /> {/* Comment Icon */} 
          {showComments ? 'Hide' : 'Show'} Comments ({comments.length > 0 ? comments.length : '...'}) 
        </button>

        {showComments && (
          <div>
            {loadingComments && <Spinner contained={true} />} {/* Use spinner for loading comments */} 
            {/* Use error-message class */} 
            {errorComments && !postingComment && <p className="error-message">{errorComments}</p>}
            
            {/* Comment List */}
            {!loadingComments && comments.map(comment => (
              // Apply comment class
              <div key={comment.id} className="comment"> 
                 <Link to={`/profile/${comment.author?.username}`} className="comment-author-link">
                    {comment.author?.username || 'User'}
                 </Link>
                 : {comment.content}
                 <span className="comment-timestamp">{new Date(comment.timestamp).toLocaleString()}</span>
                 {/* Comment Delete Button */} 
                 {currentUser && currentUser.id === comment.author?.id && (
                     <button 
                        onClick={() => handleDeleteComment(comment.id)} 
                        className="comment-delete-button icon-button">
                        <FaTrashAlt /> {/* Add Trash Icon */} 
                    </button>
                 )}
              </div>
            ))}
            {!loadingComments && comments.length === 0 && !errorComments && <p>No comments yet.</p>} 

            {/* Add Comment Form */}
            {/* Apply comment-form class */} 
            <form onSubmit={handlePostComment} className="comment-form"> 
              <textarea 
                value={newCommentContent}
                onChange={(e) => setNewCommentContent(e.target.value)}
                placeholder="Add a comment..."
                rows="2"
                required
              />
              <button type="submit" disabled={postingComment}>
                {postingComment ? <Spinner inline={true} /> : 'Comment'} {/* Use inline spinner */} 
              </button>
              {/* Show posting error specifically here, use error-message class */} 
              {errorComments && postingComment && <p className="error-message">{errorComments}</p>} 
            </form>
          </div>
        )}
      </div>

      {/* TODO: Add likes button/count */}
    </div>
  );
}

export default Post; 