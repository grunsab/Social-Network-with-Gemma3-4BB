import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import CreatePostForm from './CreatePostForm';
import Post from './Post';
import Spinner from './Spinner';

function Dashboard() {
  const { currentUser } = useAuth();
  const [posts, setPosts] = useState([]);
  const [loadingPosts, setLoadingPosts] = useState(false);
  const [errorPosts, setErrorPosts] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [feedMessage, setFeedMessage] = useState('');
  const [initialLoad, setInitialLoad] = useState(true);

  const fetchPosts = async (pageToFetch = 1, append = false) => {
    setLoadingPosts(true);
    setErrorPosts('');
    try {
      const response = await fetch(`/api/v1/feed?page=${pageToFetch}&per_page=10`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch feed');
      }
      const data = await response.json();
      
      setPosts(prevPosts => append ? [...prevPosts, ...data.posts] : data.posts);
      setCurrentPage(data.page);
      setTotalPages(data.total_pages);
      setFeedMessage(data.message || '');
      
    } catch (err) {
      console.error("Error fetching feed:", err);
      setErrorPosts(err.message || 'Could not load feed.');
    } finally {
      setLoadingPosts(false);
      setInitialLoad(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      setCurrentPage(1);
      setInitialLoad(true);
      fetchPosts(1, false);
    }
  }, [currentUser]);

  const handlePostCreated = (newPost) => {
    console.log("New post created, refreshing feed from page 1:", newPost);
    setCurrentPage(1);
    setInitialLoad(true);
    fetchPosts(1, false);
  };

  const handlePostDeleted = (deletedPostId) => {
    console.log("Post deleted, removing from feed:", deletedPostId);
    setPosts(prevPosts => prevPosts.filter(post => post.id !== deletedPostId));
  };
  
  const loadMorePosts = () => {
    if (currentPage < totalPages && !loadingPosts) {
        fetchPosts(currentPage + 1, true);
    }
  };

  if (!currentUser) {
    return <p>Please log in to see the dashboard.</p>;
  }

  if (initialLoad && loadingPosts) {
      return <Spinner contained={true} />;
  }

  return (
    <>
      <CreatePostForm onPostCreated={handlePostCreated} />

      <h3>{feedMessage || 'Your Feed'}</h3>
      {errorPosts && <p className="error-message">Error: {errorPosts}</p>}
      
      <div className="posts-list" style={{ marginTop: '1.5rem' }}>
          {!loadingPosts && posts.length === 0 ? (
            <p>No posts found in your feed. Create one or explore!</p>
          ) : (
            posts.map(post => (
              <Post key={post.id} post={post} onDelete={handlePostDeleted} />
            ))
          )}
      </div>
      
      {/* Loading indicator for subsequent pages */}
      {loadingPosts && !initialLoad && <Spinner contained={true} />} 
      
      {/* Load More Button */} 
      {currentPage < totalPages && !loadingPosts && (
          <div className="text-center my-2"> {/* Center the button */} 
              <button onClick={loadMorePosts}>
                  Load More
              </button>
          </div>
      )}
      
      {/* End of Feed message */}
      {!loadingPosts && posts.length > 0 && currentPage >= totalPages && (
          <p className="text-center my-2" style={{ fontStyle: 'italic', opacity: 0.7 }}>End of feed.</p> // Keep inline style for unique properties
      )}
    </>
  );
}

export default Dashboard; 