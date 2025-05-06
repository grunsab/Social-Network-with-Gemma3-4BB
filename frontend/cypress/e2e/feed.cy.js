/// <reference types="cypress" />

// Define users at a higher scope to be accessible by all describe blocks
const testUser = {
  username: 'testuser',
  password: 'password',
  email: 'testuser@example.com' 
};
const otherUser = {
  username: 'testuser2',
  password: 'password',
  email: 'testuser2@example.com'
};

describe('Main Feed Functionality', () => {
  // testUser and otherUser are accessible here from the higher scope
  // No need to redefine them unless shadowing is intended (which it isn't here)

  // --- Helper: Ensure users are NOT friends before a test ---
  const ensureNotFriends = (userA, userB_username) => {
    cy.login(userA.username, userA.password);
    // Get user B's ID
    cy.request(`/api/v1/profiles/${userB_username}`).then(response => {
      if (response.status === 200 && response.body.user.id) {
        const userB_id = response.body.user.id;
        // Attempt to delete friendship (ignore errors if not friends)
        cy.request({ 
          method: 'DELETE', 
          url: `/api/v1/friendships/${userB_id}`, 
          failOnStatusCode: false 
        });
        // Also attempt to delete any pending requests (sender perspective)
        // cy.request({ // This block is causing the error due to missing URL
        //   method: 'POST', 
        //   // url: `/api/v1/friend-requests/cancel_between?user_id=${userB_id}` // Hypothetical endpoint
        //   // For now, rely on the friendship deletion and test setup.
        // });
      }
    });
  };

  // --- Test Cases ---

  it('should show own public posts and include public posts of non-friends in fallback', () => {
    const ownPostContent = `My public feed post (should not see) - ${Date.now()}`;
    const otherUserPublicPostContent = `Other user public feed post (should see) - ${Date.now()}`;

    // Setup: Ensure not friends
    ensureNotFriends(testUser, otherUser.username); 
    ensureNotFriends(otherUser, testUser.username);

    cy.login(testUser.username, testUser.password);
    cy.createPost({ content: ownPostContent, privacy: 'PUBLIC' }).then(ownCreatedPost => {
      const currentOwnPostId = ownCreatedPost.id;

      cy.login(otherUser.username, otherUser.password);
      cy.createPost({ content: otherUserPublicPostContent, privacy: 'PUBLIC' }).then(otherCreatedPost => {
        const currentOtherUserPostId = otherCreatedPost.id;

        // Verification: testUser views their feed
        cy.login(testUser.username, testUser.password);
        
        cy.intercept('GET', '/api/v1/feed*').as('getFeed');
        cy.visit('/'); 

        cy.wait('@getFeed').then((interception) => {
          console.log('Feed API response (non-friends test):', interception.response.body);
          const receivedPostIds = interception.response.body.posts.map(p => p.id);
          
          expect(receivedPostIds).to.not.include(currentOwnPostId, 'Own post should not be in the feed response');
          // Assuming fallback or general public post visibility for non-friends
          expect(receivedPostIds).to.include(currentOtherUserPostId, 'Other user PUBLIC post should be in feed for non-friend'); 
        });

        cy.get('[data-cy="feed-posts-list"]').should('be.visible');

        cy.get(`[data-cy="post-${currentOwnPostId}"]`).should('not.exist');
        cy.get(`[data-cy="post-${currentOtherUserPostId}"]`).should('be.visible').and('contain.text', otherUserPublicPostContent);
      });
    });
  });

  // --- Add tests for friend visibility, friends-only posts etc. ---
  it("should not show own posts, but show friends' public and friends-only posts", () => {
    const myFeedPostContent = `My post for friend feed (should not see) - ${Date.now()}`;
    const friendPublicPostContent = `Friend public post for feed (should see) - ${Date.now()}`;
    const friendFriendsOnlyPostContent = `Friend FO post for feed (should see) - ${Date.now()}`;

    cy.login(testUser.username, testUser.password);
    cy.createPost({ content: myFeedPostContent, privacy: 'PUBLIC' }).then(myCreatedPost => {
      const currentMyFeedPostId = myCreatedPost.id;

      cy.login(otherUser.username, otherUser.password);
      cy.createPost({ content: friendPublicPostContent, privacy: 'PUBLIC' }).then(friendPublicCreatedPost => {
        const currentFriendPublicPostId = friendPublicCreatedPost.id;

        cy.createPost({ content: friendFriendsOnlyPostContent, privacy: 'FRIENDS' }).then(friendFriendsOnlyCreatedPost => {
          const currentFriendFriendsOnlyPostId = friendFriendsOnlyCreatedPost.id;

          // Setup: Make friends
          cy.login(testUser.username, testUser.password);
          cy.sendFriendRequestTo(otherUser.username).then((requestId) => {
            cy.login(otherUser.username, otherUser.password);
            cy.acceptFriendRequest(requestId);
          }).then(() => {
            // Verification (nested after friend request accepted)
            cy.login(testUser.username, testUser.password); 
            
            cy.intercept('GET', '/api/v1/feed*').as('getFriendsFeed');
            cy.visit('/');
            
            cy.wait('@getFriendsFeed').then((interception) => {
              console.log('Feed API response (friends test):', interception.response.body);
              const receivedPostIds = interception.response.body.posts.map(p => p.id);
              expect(receivedPostIds).to.not.include(currentMyFeedPostId, 'Own post should not be in friend feed response');
              expect(receivedPostIds).to.include(currentFriendPublicPostId, 'Friend PUBLIC post should be in feed');
              expect(receivedPostIds).to.include(currentFriendFriendsOnlyPostId, 'Friend FRIENDS-ONLY post should be in feed');
            });
            
            cy.get('[data-cy="feed-posts-list"]').should('be.visible');

            cy.get(`[data-cy="post-${currentMyFeedPostId}"]`).should('not.exist');
            cy.get(`[data-cy="post-${currentFriendPublicPostId}"]`).should('be.visible').and('contain.text', friendPublicPostContent);
            cy.get(`[data-cy="post-${currentFriendFriendsOnlyPostId}"]`).should('be.visible').and('contain.text', friendFriendsOnlyPostContent);
          });
        });
      });
    });
  });

  it('should NOT show friends-only posts of non-friends', () => {
    const otherFriendsOnlyPost = `Other user FO post for non-friend feed - ${Date.now()}`;

    // Setup: Create friends-only post as otherUser
    cy.login(otherUser.username, otherUser.password);
    cy.createPost({ content: otherFriendsOnlyPost, privacy: 'FRIENDS' });

    // Setup: Ensure testUser and otherUser are NOT friends
    ensureNotFriends(testUser, otherUser.username);
    ensureNotFriends(otherUser, testUser.username);

    // Verification
    cy.login(testUser.username, testUser.password); // Login as the viewing user
    cy.visit('/');

    cy.get('[data-cy="feed-posts-list"]').should('be.visible');
    cy.wait(1000);

    // Assert other user's friends-only post is NOT visible
    cy.get('[data-cy="feed-posts-list"]').should('not.contain.text', otherFriendsOnlyPost);
  });

});

describe('Feed Pagination', () => {
  // testUser is redefined locally here, which is fine for this block's specific needs if different from global.
  // However, to use the global testUser for consistency or if it's the same one:
  // const testUser = testUser; // or just use testUser directly from higher scope.
  // For clarity and current structure, the local re-definition is okay if intended.
  
  // For paginationPosterUser, it's specific to this block.
  const paginationPosterUser = { 
    username: 'paginationposter',
    password: 'password',
    email: 'pagination@example.com'
  };
  const postsPerPage = 10;
  // Revert workaround: Go back to creating just enough posts for 2 pages.
  const totalPostsToCreate = postsPerPage + 2; 

  before(() => {
    // Ensure all necessary users for this describe block exist
    cy.ensureUserExists(testUser); // User viewing the feed
    cy.ensureUserExists(paginationPosterUser); // User creating posts for pagination
    cy.ensureUserExists(otherUser); // User from other tests whose posts might interfere

    // Clean up posts from users that might affect the feed count for testUser
    cy.login(otherUser.username, otherUser.password);
    cy.deleteAllMyPosts().then(() => {
      cy.log(`Finished deleteAllMyPosts for ${otherUser.username}.`);
      // Also clean up posts from paginationPosterUser to ensure a clean slate for beforeEach
      cy.login(paginationPosterUser.username, paginationPosterUser.password);
      cy.deleteAllMyPosts().then(() => {
        cy.log(`Finished deleteAllMyPosts for ${paginationPosterUser.username}.`);
        // Verify cleanup: Login as testUser and check for otherUser's posts
        cy.login(testUser.username, testUser.password);
        cy.intercept('GET', '/api/v1/feed*').as('feedAfterCleanup'); // Renamed alias
        cy.visit('/');
        cy.wait('@feedAfterCleanup').then(interception => {
          const postsInFeed = interception.response.body.posts;
          const otherUserPostsInFeed = postsInFeed.filter(p => p.author.username === otherUser.username);
          cy.log(`After cleaning ${otherUser.username}'s posts, ${testUser.username} sees ${otherUserPostsInFeed.length} posts from ${otherUser.username}. Expected 0.`);
          expect(otherUserPostsInFeed.length, `Posts from ${otherUser.username} after cleanup`).to.eq(0);
          
          const paginationPostsInFeed = postsInFeed.filter(p => p.author.username === paginationPosterUser.username);
          cy.log(`After cleaning ${paginationPosterUser.username}'s posts, ${testUser.username} sees ${paginationPostsInFeed.length} posts from ${paginationPosterUser.username}. Expected 0.`);
          expect(paginationPostsInFeed.length, `Posts from ${paginationPosterUser.username} after cleanup`).to.eq(0);

          const paginationTestContentPosts = postsInFeed.filter(p => p.content.includes('Pagination Test Post'));
          cy.log(`${testUser.username} sees ${paginationTestContentPosts.length} 'Pagination Test Post' posts before paginationPosterUser creates new ones in beforeEach. Expected 0.`);
          expect(paginationTestContentPosts.length, '"Pagination Test Post" content before creation').to.eq(0);
        });
      });
    });
  });

  beforeEach(() => {
    // paginationPosterUser creates posts needed for pagination test
    cy.login(paginationPosterUser.username, paginationPosterUser.password);
    cy.log(`Creating ${totalPostsToCreate} posts as ${paginationPosterUser.username} for pagination test...`);
    let chain = cy;
    Cypress._.times(totalPostsToCreate, (i) => {
      chain = chain.createPost({ 
        content: `Pagination Test Post ${i + 1}/${totalPostsToCreate} by ${paginationPosterUser.username} - ${Date.now()}`,
        privacy: 'PUBLIC' 
      });
    });
    chain.then(() => {
        cy.log(`${totalPostsToCreate} posts created by ${paginationPosterUser.username}.`);
    });
  });

  it('should load the first page, allow loading more, and show end message', () => {
    // testUser views the feed
    cy.login(testUser.username, testUser.password);
    cy.visit('/');

    // Intercept the initial feed call to understand what testUser sees
    cy.intercept('GET', '/api/v1/feed?page=1*').as('getInitialFeed');

    // Verify initial page load (10 posts containing "Pagination Test Post")
    cy.get('.posts-list .post:contains("Pagination Test Post")').should('have.length', postsPerPage);
    cy.wait('@getInitialFeed').then(interception => {
      cy.log('Initial Feed Total Items:', interception.response.body.total_items);
      cy.log('Initial Feed Total Pages:', interception.response.body.total_pages);
    });
    
    // Ensure the load more trigger exists and end message is not yet visible
    cy.get('[data-cy="feed-load-more-trigger"]').should('be.visible');
    cy.contains('p', 'End of feed.').should('not.exist');

    // Intercept the next page request
    cy.intercept('GET', '/api/v1/feed?page=2&per_page=10').as('loadPage2');

    // Scroll to the trigger element to load more posts
    cy.get('[data-cy="feed-load-more-trigger"]').scrollIntoView();

    // Verify API call and loading state (optional)
    // cy.get('.spinner').should('be.visible'); // Check for spinner
    // cy.wait('@loadPage2').its('response.statusCode').should('eq', 200);
    cy.wait('@loadPage2').then((interception) => {
        expect(interception.response.statusCode).to.eq(200);
        cy.log('Page 2 Feed Total Items:', interception.response.body.total_items);
        cy.log('Page 2 Feed Total Pages:', interception.response.body.total_pages);
    });

    // cy.get('.spinner').should('not.exist'); // Check spinner gone

    // Verify total posts visible (expecting 12 now)
    cy.get('.posts-list .post:contains("Pagination Test Post")').should('have.length', totalPostsToCreate);

    // Verify Load More trigger is gone (or not visible if it's removed from DOM when no more pages)
    // Depending on implementation, it might still exist but not trigger more loads, or be removed.
    // For now, let's assume it should not be visible if there are no more pages.
    cy.get('[data-cy="feed-load-more-trigger"]').should('not.exist');

    // Verify End of feed message is visible
    cy.contains('p', 'End of feed.').should('be.visible');
  });
}); 