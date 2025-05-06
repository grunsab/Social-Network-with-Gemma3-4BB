import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom'; // To get category name from URL
import Post from './Post'; // Re-use Post component
import { useAuth } from '../context/AuthContext'; // Needed for Post component's delete checks
import Spinner from './Spinner'; // Import Spinner

function CategoryView() {
  const { categoryName } = useParams();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [initialLoad, setInitialLoad] = useState(true);

  // Fetch posts for the specific category
  const fetchCategoryPosts = useCallback(async (pageToFetch = 1, append = false) => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`/api/v1/categories/${encodeURIComponent(categoryName)}/posts?page=${pageToFetch}&per_page=10`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to fetch category posts');
      }
      const data = await response.json();

      setPosts(prevPosts => append ? [...prevPosts, ...data.posts] : data.posts);
      setCurrentPage(data.page);
      setTotalPages(data.total_pages);

    } catch (err) {
      console.error("Error fetching category posts:", err);
      setError(err.message || 'Could not load posts for this category.');
      // Optionally clear posts on error
      // if (!append) setPosts([]);
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  }, [categoryName]); // Re-create fetch function if categoryName changes

  // Initial fetch and fetch on category change
  useEffect(() => {
      setCurrentPage(1); // Reset page on category change
      setInitialLoad(true);
      fetchCategoryPosts(1, false);
  }, [fetchCategoryPosts]); // Depend on the memoized fetch function

  // Handler to remove post from state after deletion in Post component
  const handlePostDeleted = (deletedPostId) => {
     setPosts(prevPosts => prevPosts.filter(post => post.id !== deletedPostId));
  };

  const loadMorePosts = () => {
    if (currentPage < totalPages && !loading) {
        fetchCategoryPosts(currentPage + 1, true);
    }
  };
  
  if (initialLoad && loading) return <Spinner contained={true} />; // Use spinner for initial load
  if (error && !loading) return <p className="error-message">Error: {error}</p>; // Show error only if not also loading

  return (
    <div className="category-view-container">
      <h2>Posts in Category: {categoryName}</h2>
      
      {/* Posts List */} 
      <div className="posts-list" style={{ marginTop: '1.5rem' }}>
          {posts.length === 0 && !loading ? (
            <p>No posts found in this category.</p>
          ) : (
            posts.map(post => (
              // Pass onDelete handler to Post component
              <Post key={post.id} post={post} onDelete={handlePostDeleted} />
            ))
          )}
      </div>
      
      {/* Pagination / Load More Button */} 
      {loading && !initialLoad && <Spinner contained={true} />} {/* Use spinner for subsequent loads */} 
      {currentPage < totalPages && !loading && (
          <div className="text-center my-2">
              <button onClick={loadMorePosts}>
                  Load More
              </button>
          </div>
      )}
      {!loading && posts.length > 0 && currentPage >= totalPages && (
          <p className="text-center my-2" style={{ fontStyle: 'italic', opacity: 0.7 }}>End of category posts.</p>
      )}
    </div>
  );
}

export default CategoryView; 