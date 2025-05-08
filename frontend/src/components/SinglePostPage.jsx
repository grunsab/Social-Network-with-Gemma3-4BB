import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Spinner from './Spinner';
import Post from './Post';

function SinglePostPage() {
  const { postId } = useParams();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchPost() {
      try {
        const resp = await fetch(`/api/v1/posts/${postId}`, { credentials: 'include' });
        if (!resp.ok) {
          const data = await resp.json();
          throw new Error(data.message || 'Failed to fetch post');
        }
        const data = await resp.json();
        setPost(data);
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchPost();
  }, [postId]);

  const handleDelete = (deletedId) => navigate('/');

  if (loading) return <Spinner contained={true} />;
  if (error) return <p className="error-message">Error: {error}</p>;
  if (!post) return <p>No post found.</p>;

  return (
    <div className="single-post-page">
      <button onClick={() => navigate(-1)} className="back-button">Back</button>
      <Post post={post} onDelete={handleDelete} />
    </div>
  );
}

export default SinglePostPage;
