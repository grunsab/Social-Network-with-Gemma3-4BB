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

  after(() => {
    cy.log('[Main Feed Cleanup] Starting cleanup for Main Feed Functionality...');

    const friendUser = { username: 'frienduser', password: 'password', email: 'friend@example.com' }; // Ensure definition is accessible
    const nonFriendUser = { username: 'nonfrienduser', password: 'password', email: 'nonfriend@example.com' }; // Ensure definition is accessible

    const usersToClean = [
      { name: 'testUser', userObj: testUser },
      { name: 'otherUser', userObj: otherUser },
      { name: 'friendUser', userObj: friendUser },
      { name: 'nonFriendUser', userObj: nonFriendUser }
    ];

    let cleanupChain = cy.wrap(null, { log: false });

    usersToClean.forEach(userInfo => {
      cleanupChain = cleanupChain.then(() => {
        cy.log(`[Main Feed Cleanup] Ensuring user ${userInfo.userObj.username} exists.`);
        return cy.ensureUserExists(userInfo.userObj);
      }).then(() => {
        cy.log(`[Main Feed Cleanup] Logging in as ${userInfo.userObj.username} for post deletion.`);
        return cy.login(userInfo.userObj.username, userInfo.userObj.password);
      }).then(() => {
        cy.log(`[Main Feed Cleanup] Deleting posts for ${userInfo.userObj.username}.`);
        return cy.deleteAllMyPosts();
      }).then(() => {
        cy.log(`[Main Feed Cleanup] deleteAllMyPosts for ${userInfo.userObj.username} completed. Verifying...`);
        return cy.request({ method: 'GET', url: '/api/v1/profiles/me', failOnStatusCode: false });
      }).then((profileResponse) => {
        if (profileResponse.status === 200) {
          const postsRemaining = profileResponse.body.posts ? profileResponse.body.posts.length : 0;
          cy.log(`[Main Feed Cleanup] ${userInfo.userObj.username} has ${postsRemaining} posts on own profile after their cleanup.`);
          expect(postsRemaining, `Posts for ${userInfo.userObj.username} on own profile after Main Feed cleanup`).to.equal(0);
        } else {
          cy.log(`[Main Feed Cleanup] Warn: Profile fetch for ${userInfo.userObj.username} during cleanup verification failed. Status: ${profileResponse.status}. Body: ${JSON.stringify(profileResponse.body)}`);
        }
        cy.log(`[Main Feed Cleanup] Logging out ${userInfo.userObj.username}.`);
        return cy.logout();
      }).then(() => {
        return cy.wait(200, { log: false }); // Brief pause after logout and before next user
      });
    });

    return cleanupChain.then(() => {
      cy.log('[Main Feed Cleanup] Finished cleanup for Main Feed Functionality.');
    });
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
  const totalPostsToCreate = postsPerPage + 2; 

  before(() => { // HOOK 2: Cleanup and verification
    cy.log('[Cleanup Hook] Starting cleanup...');

    // 1. Cleanup paginationPosterUser
    cy.login(paginationPosterUser.username, paginationPosterUser.password)
      .then(() => {
        cy.log(`[Cleanup Hook] Logged in as ${paginationPosterUser.username} for cleanup.`);
        return cy.deleteAllMyPosts();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] deleteAllMyPosts for ${paginationPosterUser.username} completed.`);
        return cy.request({
          method: 'GET',
          url: '/api/v1/profiles/me',
          failOnStatusCode: false
        });
      })
      .then((profileResponse) => {
        if (profileResponse.status === 200) {
          const postsRemaining = profileResponse.body.posts ? profileResponse.body.posts.length : 0;
          cy.log(`[Cleanup Hook] After deleteAllMyPosts, ${paginationPosterUser.username} has ${postsRemaining} posts according to their own profile.`);
          expect(postsRemaining, `Posts for ${paginationPosterUser.username} on their own profile after cleanup`).to.equal(0);
        } else {
          cy.log(`[Cleanup Hook] Warning: Could not fetch ${paginationPosterUser.username}'s profile after deletion. Status: ${profileResponse.status}`);
        }
        cy.wait(500);
        return cy.logout();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] Logged out ${paginationPosterUser.username}.`);
        // Intermediate check: What does testUser see?
        cy.login(testUser.username, testUser.password);
        cy.visit('/');
        cy.intercept('GET', '/api/v1/feed?page=1*').as('getFeedAfterPaginationUserCleanup');
        return cy.wait('@getFeedAfterPaginationUserCleanup');
      })
      .then((interception) => {
        const feedResponse = interception.response.body;
        const postsInFeed = feedResponse.posts;
        const paginationUserPostsInTestUserFeed = postsInFeed.filter(p => p.author.username === paginationPosterUser.username);
        cy.log(`[Cleanup Hook] After ${paginationPosterUser.username} cleanup, ${testUser.username} sees ${paginationUserPostsInTestUserFeed.length} posts from ${paginationPosterUser.username}. Total items in ${testUser.username}'s feed: ${feedResponse.total_items}`);
        expect(paginationUserPostsInTestUserFeed.length, `Posts from ${paginationPosterUser.username} in ${testUser.username}'s feed`).to.equal(0);
        return cy.logout();
      })
      .then(() => {
        // 2. Cleanup testUser
        return cy.login(testUser.username, testUser.password);
      })
      .then(() => {
        cy.log(`[Cleanup Hook] Logged in as ${testUser.username} for cleanup.`);
        return cy.deleteAllMyPosts();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] deleteAllMyPosts for ${testUser.username} completed.`);
        return cy.request({
          method: 'GET',
          url: '/api/v1/profiles/me',
          failOnStatusCode: false
        });
      })
      .then((profileResponse) => {
        if (profileResponse.status === 200) {
          const postsRemaining = profileResponse.body.posts ? profileResponse.body.posts.length : 0;
          cy.log(`[Cleanup Hook] After deleteAllMyPosts, ${testUser.username} has ${postsRemaining} posts according to their own profile.`);
          expect(postsRemaining, `Posts for ${testUser.username} on their own profile after cleanup`).to.equal(0);
        } else {
          cy.log(`[Cleanup Hook] Warning: Could not fetch ${testUser.username}'s profile after deletion. Status: ${profileResponse.status}`);
        }
        cy.wait(500);
        return cy.logout();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] Logged out ${testUser.username}.`);
        // 3. Cleanup otherUser
        return cy.login(otherUser.username, otherUser.password);
      })
      .then(() => {
        cy.log(`[Cleanup Hook] Logged in as ${otherUser.username} for cleanup.`);
        return cy.deleteAllMyPosts();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] deleteAllMyPosts for ${otherUser.username} completed.`);
        return cy.request({
          method: 'GET',
          url: '/api/v1/profiles/me',
          failOnStatusCode: false
        });
      })
      .then((profileResponse) => {
        if (profileResponse.status === 200) {
          const postsRemaining = profileResponse.body.posts ? profileResponse.body.posts.length : 0;
          cy.log(`[Cleanup Hook] After deleteAllMyPosts, ${otherUser.username} has ${postsRemaining} posts according to their own profile.`);
          expect(postsRemaining, `Posts for ${otherUser.username} on their own profile after cleanup`).to.equal(0);
        } else {
          cy.log(`[Cleanup Hook] Warning: Could not fetch ${otherUser.username}'s profile after deletion. Status: ${profileResponse.status}`);
        }
        cy.wait(500);
        return cy.logout();
      })
      .then(() => {
        cy.log(`[Cleanup Hook] Logged out ${otherUser.username}.`);
        // 4. Final Verification: testUser's feed should be empty of any posts from these three users.
        cy.log('[Cleanup Hook] Performing final verification of testUser feed.');
        cy.login(testUser.username, testUser.password);
        cy.visit('/');
        cy.intercept('GET', '/api/v1/feed?page=1*').as('getTestUserFeedAfterAllCleanups');
        return cy.wait('@getTestUserFeedAfterAllCleanups');
      })
      .then(interception => {
        const responseBody = interception.response.body;
        const totalItems = responseBody.total_items;
        const postsInFeed = responseBody.posts;

        cy.log(`[Cleanup Hook] Final check: Total items in feed for ${testUser.username}: ${totalItems}`);
        if (postsInFeed && postsInFeed.length > 0) {
          postsInFeed.forEach(post => {
            cy.log(`[Cleanup Hook] Feed item: Post ID ${post.id}, Author: ${post.author.username}, Privacy: ${post.privacy}`);
          });
        } else if (totalItems > 0) {
          cy.log('[Cleanup Hook] Warning: total_items > 0 but postsInFeed array is empty. This might indicate pagination issue or all unexpected posts are on other pages.');
        }

        const postsFromPaginationUser = postsInFeed.filter(p => p.author.username === paginationPosterUser.username).length;
        const postsFromOtherUser = postsInFeed.filter(p => p.author.username === otherUser.username).length;
        const postsFromFriendUser = postsInFeed.filter(p => p.author.username === 'frienduser').length;
        const postsFromNonFriendUser = postsInFeed.filter(p => p.author.username === 'nonfrienduser').length;

        cy.log(`[Cleanup Hook] Posts from ${paginationPosterUser.username} in final feed: ${postsFromPaginationUser}`);
        cy.log(`[Cleanup Hook] Posts from ${otherUser.username} in final feed: ${postsFromOtherUser}`);
        cy.log(`[Cleanup Hook] Posts from frienduser in final feed: ${postsFromFriendUser}`);
        cy.log(`[Cleanup Hook] Posts from nonfrienduser in final feed: ${postsFromNonFriendUser}`);

        expect(postsFromPaginationUser, `Posts from ${paginationPosterUser.username} in final feed`).to.equal(0);
        expect(postsFromOtherUser, `Posts from ${otherUser.username} in final feed`).to.equal(0);
        expect(postsFromFriendUser, `Posts from frienduser in ${testUser.username}'s final feed`).to.equal(0);
        expect(postsFromNonFriendUser, `Posts from nonfrienduser in ${testUser.username}'s final feed`).to.equal(0);
        
        expect(totalItems, 'Total items in feed after all cleanups should be 0').to.equal(0);
      });
  });

  beforeEach(() => {
    // paginationPosterUser creates posts needed for pagination test
    cy.login(paginationPosterUser.username, paginationPosterUser.password);
    cy.log(`Creating ${totalPostsToCreate} posts as ${paginationPosterUser.username} for pagination test...`);
    
    // Ensure posts are created sequentially and beforeEach completes after all are done.
    let postCreationChain = cy.noop(); // Start with a no-operation command
    Cypress._.times(totalPostsToCreate, (i) => {
      postCreationChain = postCreationChain.then(() => { // Chain the next createPost
        return cy.createPost({ 
          content: `Pagination Test Post ${i + 1}/${totalPostsToCreate} by ${paginationPosterUser.username} - ${Date.now()}`,
          privacy: 'PUBLIC' 
        });
      });
    });

    postCreationChain.then(() => {
      cy.log(`All ${totalPostsToCreate} posts created by ${paginationPosterUser.username}.`);
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
      cy.log('Initial Feed API Response:', interception.response.body);
      const expectedTotalItems = totalPostsToCreate;
      const expectedTotalPages = Math.ceil(totalPostsToCreate / postsPerPage);
      expect(interception.response.body.total_items, 'Total items in initial feed').to.eq(expectedTotalItems);
      expect(interception.response.body.total_pages, 'Total pages in initial feed').to.eq(expectedTotalPages);
    });
    
    // Ensure the load more trigger exists and end message is not yet visible
    cy.get('[data-cy="feed-load-more-trigger"]').should('be.visible');
    cy.contains('p', 'End of feed.').should('not.exist');

    // Intercept the next page request
    cy.intercept('GET', '/api/v1/feed?page=2&per_page=10*').as('loadPage2');

    // Scroll to the trigger element to load more posts
    cy.get('[data-cy="feed-load-more-trigger"]').scrollIntoView();

    // Verify API call and loading state (optional)
    // cy.get('.spinner').should('be.visible'); // Check for spinner
    // cy.wait('@loadPage2').its('response.statusCode').should('eq', 200);
    cy.wait('@loadPage2').then((interception) => {
        expect(interception.response.statusCode).to.eq(200);
        cy.log('Page 2 Feed API Response:', interception.response.body);
        const expectedTotalItems = totalPostsToCreate;
        const expectedTotalPages = Math.ceil(totalPostsToCreate / postsPerPage);
        expect(interception.response.body.total_items, 'Total items in page 2 feed response').to.eq(expectedTotalItems);
        expect(interception.response.body.total_pages, 'Total pages in page 2 feed response').to.eq(expectedTotalPages);
        expect(interception.response.body.page, 'Current page in page 2 feed response').to.eq(2);
    });

    // cy.get('.spinner').should('not.exist'); // Check spinner gone

    // Verify total posts visible (expecting 12 now)
    cy.get('.posts-list .post:contains("Pagination Test Post")').should('have.length', totalPostsToCreate);

    // Add a small wait to ensure DOM updates are processed after all posts are loaded.
    cy.wait(500); 

    // Verify End of feed message is visible first
    cy.contains('p', 'End of feed.').should('be.visible');

    // Verify Load More trigger is gone (or not visible if it's removed from DOM when no more pages)
    cy.get('[data-cy="feed-load-more-trigger"]').should('not.exist');
  });
});