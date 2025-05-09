import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import CreatePostForm from './CreatePostForm';
import ImageGeneratorForm from './ImageGeneratorForm'; // Import the new form
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
  const [sortBy, setSortBy] = useState('recency'); // Added sortBy state, default to recency
  const observerTarget = useRef(null);

  const fetchPosts = useCallback(async (pageToFetch = 1, append = false, sortOrder = sortBy) => {
    setLoadingPosts(true);
    setErrorPosts('');
    try {
      // Include sort_by parameter in the API call
      const response = await fetch(`/api/v1/feed?page=${pageToFetch}&per_page=10&sort_by=${sortOrder}`);
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
  }, [sortBy]); // Add sortBy to dependencies of fetchPosts

  useEffect(() => {
    if (currentUser) {
      setCurrentPage(1);
      setInitialLoad(true);
      fetchPosts(1, false, sortBy); // Pass sortBy to initial fetch
    }
  }, [currentUser, fetchPosts, sortBy]); // Add sortBy to dependencies of this effect

  const handlePostCreated = (newPost) => {
    console.log("New post created, prepending to feed:", newPost);
    // If sorting by recency, new post should appear at the top.
    // If sorting by relevance, it's complex, so for now, prepend and let next fetch re-sort.
    setPosts(prevPosts => [newPost, ...prevPosts]);
    // Optionally, could re-fetch if sortBy is 'relevance' to ensure accurate placement,
    // but that might be too disruptive. For now, prepend.
  };

  const handleImagePostCreated = async (postId, imageUrl) => {
    setLoadingPosts(true); // Show a loading indicator while we fetch the new post
    try {
      const response = await fetch(`/api/v1/posts/${postId}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to fetch newly created image post');
      }
      const newImagePost = await response.json();
      // Similar to handlePostCreated, prepend for now.
      setPosts(prevPosts => [newImagePost, ...prevPosts]);
    } catch (err) {
      console.error("Error fetching image post after creation:", err);
      setErrorPosts(err.message); // Display an error if fetching fails
    } finally {
      setLoadingPosts(false);
    }
  };

  const handlePostDeleted = (deletedPostId) => {
    console.log("Post deleted, removing from feed:", deletedPostId);
    setPosts(prevPosts => prevPosts.filter(post => post.id !== deletedPostId));
  };
  
  const loadMorePosts = useCallback(() => {
    if (currentPage < totalPages && !loadingPosts) {
        fetchPosts(currentPage + 1, true, sortBy); // Pass sortBy to loadMorePosts
    }
  }, [currentPage, totalPages, loadingPosts, fetchPosts, sortBy]); // Add sortBy to dependencies

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

  // Handler for changing sort order
  const handleSortChange = (newSortBy) => {
    setSortBy(newSortBy);
    setCurrentPage(1); // Reset to first page
    setInitialLoad(true); // Trigger loading state for new sort
    // fetchPosts will be called by the useEffect watching sortBy
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
      <ImageGeneratorForm onImagePostCreated={handleImagePostCreated} /> {/* Add the new form here */}

      {/* Sort options UI */}
      <div className="feed-sort-options" style={{ margin: '1rem 0', display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
        <label htmlFor="sort-by-select" style={{ marginRight: '0.5rem' }}>Sort by: </label>
        <select 
          id="sort-by-select"
          value={sortBy}
          onChange={(e) => handleSortChange(e.target.value)}
          style={{ padding: '0.25rem', borderRadius: '4px' }}
        >
          <option value="relevance">Relevance</option>
          <option value="recency">Recency</option>
        </select>
      </div>

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