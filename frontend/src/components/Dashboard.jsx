import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  const observerTarget = useRef(null);

  const fetchPosts = useCallback(async (pageToFetch = 1, append = false) => {
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
  }, []);

  useEffect(() => {
    if (currentUser) {
      setCurrentPage(1);
      setInitialLoad(true);
      fetchPosts(1, false);
    }
  }, [currentUser, fetchPosts]);

  const handlePostCreated = (newPost) => {
    console.log("New post created, prepending to feed:", newPost);
    // Prepend the new post to the existing posts list
    setPosts(prevPosts => [newPost, ...prevPosts]);
    // No need to trigger a full refresh or set loading/initialLoad here
    // The feed will naturally update on next full load or page change if needed.
    // setCurrentPage(1);
    // setInitialLoad(true);
    // fetchPosts(1, false);
  };

  const handlePostDeleted = (deletedPostId) => {
    console.log("Post deleted, removing from feed:", deletedPostId);
    setPosts(prevPosts => prevPosts.filter(post => post.id !== deletedPostId));
  };
  
  const loadMorePosts = useCallback(() => {
    if (currentPage < totalPages && !loadingPosts) {
        fetchPosts(currentPage + 1, true);
    }
  }, [currentPage, totalPages, loadingPosts, fetchPosts]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting) {
          loadMorePosts();
        }
      },
      { threshold: 1.0 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [loadMorePosts]);

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
      
      <div className="posts-list" data-cy="feed-posts-list" style={{ marginTop: '1.5rem' }}>
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
      
      {/* Observer Target for Infinite Scrolling */}
      {currentPage < totalPages && !loadingPosts && (
        <div ref={observerTarget} style={{ height: '20px', margin: '20px' }} data-cy="feed-load-more-trigger">
          {/* This div is the trigger for loading more posts. It can be styled as needed or remain invisible. */}
        </div>
      )}
      
      {/* End of Feed message */}
      {!loadingPosts && posts.length > 0 && currentPage >= totalPages && (
          <p className="text-center my-2" style={{ fontStyle: 'italic', opacity: 0.7 }}>End of feed.</p>
      )}
    </>
  );
}

export default Dashboard; 