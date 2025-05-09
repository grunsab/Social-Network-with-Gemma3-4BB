function loadComments(postId, commentsSection, commentsContainer) {
    fetch(`/post/${postId}/comments`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        if (!response.ok) { throw new Error('Network response was not ok ' + response.statusText); }
        return response.json();
    })
    .then(comments => {
        let commentsHtml = '';
        const commentCountSpan = document.querySelector(`.comments-toggle[data-post-id="${postId}"] .comment-count`);

        if (comments.length === 0) {
            commentsHtml = '<div class="alert alert-light border-0 p-2 text-center">No comments yet. Be the first!</div>';
            if (commentCountSpan) commentCountSpan.textContent = ''; // Clear count
        } else {
            commentsHtml = '<div class="list-group list-group-flush">'; // Use flush for tighter spacing
            comments.forEach(comment => {
                commentsHtml += `
              <div class="list-group-item list-group-item-action flex-column align-items-start comment-item px-0 py-2" id="comment-${comment.id}">
                <div class="d-flex w-100 justify-content-between">
                  <h6 class="mb-1"><a href="/profile/${comment.author}" class="text-decoration-none">@${comment.author}</a></h6>
                  <small class="text-muted"><span class="local-timestamp" data-timestamp="${comment.timestamp}">Loading...</span></small>
                </div>
                <div class="comment-content mb-1"></div>
                <div class="comment-raw-content" style="display: none;">${escapeHtml(comment.content)}</div>
                ${comment.is_author ?
                    `<div class="text-end mt-1">
                    <button class="btn btn-sm btn-outline-danger delete-comment" data-comment-id="${comment.id}" data-post-id="${postId}">Delete</button>
                   </div>` : ''}
              </div>
            `;
            });
            commentsHtml += '</div>';
            if (commentCountSpan) commentCountSpan.textContent = `(${comments.length})`; // Update count
        }

        commentsContainer.innerHTML = commentsHtml;

        // Render markdown for newly loaded comments
        renderCommentMarkdown(commentsContainer);

        // Format timestamps for newly loaded comments (Assuming formatLocalTimestamps is global or loaded elsewhere)
        if (typeof formatLocalTimestamps === 'function') {
            formatLocalTimestamps(commentsContainer);
        } else {
            console.warn('formatLocalTimestamps function not found. Timestamps will not be formatted.');
        }


        // Add event listeners for delete buttons WITHIN the specific container
        attachDeleteListeners(commentsContainer);
    })
    .catch(error => {
        console.error('Error loading comments:', error);
        commentsContainer.innerHTML = '<div class="alert alert-danger">Error loading comments. Please try again later.</div>';
        const commentCountSpan = document.querySelector(`.comments-toggle[data-post-id="${postId}"] .comment-count`);
        if (commentCountSpan) commentCountSpan.textContent = '(Error)';
    });
}

function renderCommentMarkdown(container) {
    container.querySelectorAll('.comment-item').forEach(item => {
        const contentDiv = item.querySelector('.comment-content');
        const rawContentDiv = item.querySelector('.comment-raw-content');
        if (contentDiv && rawContentDiv && typeof marked !== 'undefined') {
             // Content already escaped when inserting into rawContentDiv
             const rawContent = rawContentDiv.textContent || '';
             try {
                // Configure marked to handle basic GFM line breaks
                marked.setOptions({ breaks: true });
                contentDiv.innerHTML = marked.parse(rawContent);
             } catch (error) {
                console.error('Error parsing comment markdown:', error, 'Raw content:', rawContent);
                contentDiv.innerHTML = '<p class="text-danger">Error rendering comment.</p>';
             }
        } else if (typeof marked === 'undefined') {
             console.warn('marked library not found. Cannot render comment markdown.');
             if (contentDiv && rawContentDiv) {
                 contentDiv.textContent = rawContentDiv.textContent || ''; // Display raw text as fallback
             }
        }
    });
}

// Simple HTML escaping function
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
 }

function formatLocalTimestamps(container) {
    container.querySelectorAll('.local-timestamp').forEach(span => {
        const isoTimestamp = span.dataset.timestamp;
        if (isoTimestamp) {
            try {
                // Use toLocaleString() for date and time in user's locale
                span.textContent = new Date(isoTimestamp).toLocaleString();
            } catch (error) {
                console.error("Error formatting timestamp:", isoTimestamp, error);
                span.textContent = 'Invalid date';
            }
        } else {
            span.textContent = ''; // Clear if no timestamp
        }
    });
}

function deleteComment(commentId, postId) {
    // Consider adding CSRF token handling here if your app uses it
    fetch(`/comment/${commentId}/delete`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
            // 'X-CSRFToken': getCsrfToken() // Example for CSRF
        }
    })
    .then(response => {
         if (!response.ok) { throw new Error('Network response was not ok: ' + response.statusText); }
         // Check content type before parsing JSON
         const contentType = response.headers.get("content-type");
         if (contentType && contentType.indexOf("application/json") !== -1) {
            return response.json();
         } else {
            throw new Error('Received non-JSON response from server');
         }
    })
    .then(data => {
        if (data.success) {
            const commentElement = document.getElementById(`comment-${commentId}`);
            if (commentElement) {
                commentElement.remove();
            }
            // Reload comments in the specific post's section to update count and UI
            const commentsSection = document.getElementById(`comments-section-${postId}`);
            const commentsContainer = document.getElementById(`comments-container-${postId}`);
            if (commentsSection && commentsContainer) {
                 // Only reload if the section is currently visible
                 if (commentsSection.style.display !== 'none') {
                     loadComments(postId, commentsSection, commentsContainer);
                 } else {
                     // If section is hidden, just update the count optimistically or clear it
                      const commentCountSpan = document.querySelector(`.comments-toggle[data-post-id="${postId}"] .comment-count`);
                      if (commentCountSpan) {
                           // Decrementing might be inaccurate, safest to reload when opened or just clear
                           loadComments(postId, commentsSection, commentsContainer); // Reload anyway to get accurate count for badge
                      }
                 }
            }
        } else {
            alert('Error deleting comment: ' + (data.message || 'Unknown error'));
            console.error('Error deleting comment:', data);
        }
    })
    .catch(error => {
        alert('An error occurred while trying to delete the comment. Please try again.');
        console.error('Error during delete comment fetch:', error);
    });
}

// Function to attach delete listeners ensuring no duplicates
function attachDeleteListeners(container) {
    container.querySelectorAll('.delete-comment').forEach(button => {
        // Clone and replace to remove existing listeners before adding new ones
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);

        // Add the event listener to the new button
        newButton.addEventListener('click', function() {
            const commentId = this.getAttribute('data-comment-id');
            const postId = this.getAttribute('data-post-id');
            if (confirm('Are you sure you want to delete this comment?')) {
                deleteComment(commentId, postId);
            }
        });
    });
}

// Main initialization function to set up all event listeners
function initializeCommentHandling() {
    console.log("Initializing comment handling...");

    // Handle comments toggle
    document.querySelectorAll('.comments-toggle').forEach(button => {
        // Check if listener already attached
         if (button.dataset.listenerAttached === 'true') return;
         button.dataset.listenerAttached = 'true'; // Mark as attached

        button.addEventListener('click', function() {
            const postId = this.getAttribute('data-post-id');
            const commentsSection = document.getElementById(`comments-section-${postId}`);
            const commentsContainer = document.getElementById(`comments-container-${postId}`);

            if (!commentsSection || !commentsContainer) {
                console.error(`Could not find comments section or container for post ${postId}`);
                return;
            }

            if (commentsSection.style.display === 'none' || commentsSection.style.display === '') {
                commentsSection.style.display = 'block';
                // Show loading spinner initially
                commentsContainer.innerHTML = `<div class="text-center p-3"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div></div>`;
                // Load comments via AJAX
                loadComments(postId, commentsSection, commentsContainer);
            } else {
                commentsSection.style.display = 'none';
            }
        });
    });

    // Handle comment form submission
    document.querySelectorAll('.comment-form').forEach(form => {
         // Check if listener already attached
         if (form.dataset.listenerAttached === 'true') return;
         form.dataset.listenerAttached = 'true'; // Mark as attached

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const postId = this.getAttribute('data-post-id');
            const input = this.querySelector('.comment-input');
            const content = input.value.trim();
            const commentsSection = document.getElementById(`comments-section-${postId}`);
            const commentsContainer = document.getElementById(`comments-container-${postId}`);
            const submitButton = this.querySelector('button[type="submit"]'); // Get the submit button


            if (content && commentsSection && commentsContainer && input) {
                // Disable button to prevent double submission
                if(submitButton) submitButton.disabled = true;

                // Consider adding CSRF token handling here if needed
                fetch(`/post/${postId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                        // 'X-CSRFToken': getCsrfToken() // Example for CSRF
                    },
                    body: `content=${encodeURIComponent(content)}`
                })
                .then(response => {
                    if (!response.ok) {
                        // Try to parse error message from JSON response
                         return response.json().then(errData => {
                             throw new Error(errData.message || 'Network response was not ok: ' + response.statusText);
                         }).catch(() => {
                             // If response is not JSON or parsing fails, throw generic error
                             throw new Error('Network response was not ok: ' + response.statusText);
                         });
                     }
                    return response.json();
                })
                .then(comment => {
                    input.value = ''; // Clear input
                    // Reload comments to show the new one and update count
                    loadComments(postId, commentsSection, commentsContainer);
                })
                .catch(error => {
                     alert('Error posting comment: ' + error.message);
                     console.error('Error posting comment:', error);
                 })
                 .finally(() => {
                     // Re-enable button regardless of success or failure
                     if(submitButton) submitButton.disabled = false;
                 });
            } else if (!content) {
                 // Optionally provide feedback if comment is empty
                 input.focus(); // Focus the input field
                 // Maybe add a temporary visual indication like a red border
            }
        });
    });

     // Initial setup for existing delete buttons on page load (if any were server-rendered)
     // This shouldn't be strictly necessary if comments are always loaded via AJAX,
     // but doesn't hurt to include for robustness.
     attachDeleteListeners(document.body); // Attach to whole document initially


    console.log("Comment handling initialized.");
}

// Ensure the initialization runs after the DOM is fully loaded
// Check if DOM is already loaded (e.g., script loaded asynchronously)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCommentHandling);
} else {
    // DOMContentLoaded has already fired
    initializeCommentHandling();
}