/// <reference types="cypress" />

describe.skip('Profile Page Functionality', () => {
  // Define test user credentials
  const testUser = {
    username: 'testuser',
    password: 'password',
    email: 'testuser@example.com'
  };
  const otherUser = {
    username: 'testuser2',
    password: 'password', // Assuming same password for simplicity
    email: 'testuser2@example.com'
  };

  before(() => {
    // Ensure test users exist
    cy.ensureUserExists(testUser);
    cy.ensureUserExists(otherUser);
  });

  // Note: Using cy.login() defined in support/commands.js within each test.
  // cy.session within cy.login() handles caching the login state efficiently.

  it("should display the logged-in user's own profile correctly on /profile/me", () => {
    cy.login(testUser.username, testUser.password);

    // --- Setup: Create a post as testUser to generate interests ---
    const selfPostContent = `Post by ${testUser.username} to generate interests - ${Date.now()}`;
    cy.createPost({ content: selfPostContent });
    // Give a slight pause for the post creation/interest update to potentially process
    cy.wait(500); 

    // --- Visit Profile ---
    cy.visit('/profile/me');
    cy.url().should('eq', Cypress.config().baseUrl + '/profile/me');

    // --- Assertions ---
    cy.get('[data-cy="profile-username"]').should('contain.text', testUser.username);
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'SELF');
    cy.get('[data-cy="profile-posts-section"]').should('be.visible');
    // Check the post we just created is visible
    cy.get('[data-cy="profile-posts-section"]').should('contain.text', selfPostContent);
    
    // Verify interests section is visible
    cy.get('[data-cy="profile-interests-section"]').should('be.visible');
    // Add specific interest checks based on expected classification of selfPostContent
    // e.g., cy.get('[data-cy="profile-interests-section"]').should('contain.text', 'MyInterestCategory');
    
    // Verify email and invites_left for self
    cy.get('[data-cy="profile-email"]').should('contain.text', testUser.email);
    cy.get('[data-cy="profile-invites-left"]').should('be.visible'); // Just check visibility for now
    // Example to check specific number: cy.get('[data-cy="profile-invites-left"]').should('contain.text', '3');

    // Verify friendship buttons are not present
    cy.get('[data-cy="send-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="accept-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="reject-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="cancel-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="unfriend-button"]').should('not.exist');
  });

  it("should display another user's profile correctly and show 'NONE' friendship status", () => {
    cy.login(testUser.username, testUser.password);
    cy.visit(`/profile/${otherUser.username}`);
    cy.url().should('include', `/profile/${otherUser.username}`);
    cy.get('[data-cy="profile-username"]').should('contain.text', otherUser.username);
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="accept-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="reject-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="cancel-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="unfriend-button"]').should('not.exist');
    // Optional: Check posts and interests sections are visible (if public)
    cy.get('[data-cy="profile-posts-section"]').should('be.visible');
    cy.get('[data-cy="profile-interests-section"]').should('be.visible');
  });

  it('should allow sending a friend request and update status to PENDING_SENT', () => {
    cy.login(testUser.username, testUser.password);
    cy.visit(`/profile/${otherUser.username}`);
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible').click();
    cy.wait(500); // Wait for potential API call/UI update
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_SENT');
    cy.get('[data-cy="send-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="cancel-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="accept-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="reject-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="unfriend-button"]').should('not.exist');
  });

   it('should allow receiving user to accept a friend request and update status to FRIENDS', () => {
    // ---- SETUP: testuser sends request to testuser2 ----
    cy.login(testUser.username, testUser.password);
    cy.visit(`/profile/${otherUser.username}`);
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible').click();
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_SENT');
    cy.wait(200);
    // cy.session handles user switching

    // ---- Login as otherUser (testuser2) ----
    cy.login(otherUser.username, otherUser.password);

    // ---- Visit testuser's profile ----
    cy.visit(`/profile/${testUser.username}`);

    // ---- Verify PENDING_RECEIVED state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_RECEIVED');
    cy.get('[data-cy="accept-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="reject-friend-request-button"]').should('be.visible');

    // ---- Accept the request ----
    cy.get('[data-cy="accept-friend-request-button"]').click();
    cy.wait(500);

    // ---- Verify FRIENDS state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'FRIENDS');
    cy.get('[data-cy="unfriend-button"]').should('be.visible');
    cy.get('[data-cy="accept-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="reject-friend-request-button"]').should('not.exist');
  });

  it('should allow receiving user to reject a friend request and update status to NONE', () => {
    // ---- SETUP: testuser sends request to testuser2 ----
    cy.login(testUser.username, testUser.password);
    cy.visit(`/profile/${otherUser.username}`);
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible').click();
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_SENT');
    cy.wait(200);
    // cy.session handles user switching

    // ---- Login as otherUser (testuser2) ----
    cy.login(otherUser.username, otherUser.password);

    // ---- Visit testuser's profile ----
    cy.visit(`/profile/${testUser.username}`);

    // ---- Verify PENDING_RECEIVED state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_RECEIVED');
    cy.get('[data-cy="accept-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="reject-friend-request-button"]').should('be.visible');

    // ---- Reject the request ----
    cy.get('[data-cy="reject-friend-request-button"]').click();
    cy.wait(500);

    // ---- Verify NONE state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="accept-friend-request-button"]').should('not.exist');
    cy.get('[data-cy="reject-friend-request-button"]').should('not.exist');
  });

  it('should allow sender to cancel a sent friend request and update status to NONE', () => {
    cy.login(testUser.username, testUser.password);
    // ---- SETUP: testuser sends request to testuser2 ----
    cy.visit(`/profile/${otherUser.username}`);
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible').click();

    // ---- Verify PENDING_SENT state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_SENT');
    cy.get('[data-cy="cancel-friend-request-button"]').should('be.visible');
    cy.wait(200); // Ensure state is settled before cancelling

    // ---- Cancel the request ----
    cy.get('[data-cy="cancel-friend-request-button"]').click();
    cy.wait(500); // Wait for API call/UI update

    // ---- Verify NONE state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="cancel-friend-request-button"]').should('not.exist');
  });

  it('should allow a user to unfriend an existing friend', () => {
    // ---- SETUP PART 1: testuser sends request ----
    cy.login(testUser.username, testUser.password);
    cy.visit(`/profile/${otherUser.username}`);
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible').click();
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_SENT');
    cy.wait(200);
    // cy.session handles user switching

    // ---- SETUP PART 2: otherUser accepts request ----
    cy.login(otherUser.username, otherUser.password);
    cy.visit(`/profile/${testUser.username}`);
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'PENDING_RECEIVED');
    cy.get('[data-cy="accept-friend-request-button"]').should('be.visible').click();
    cy.wait(500);
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'FRIENDS'); // Verify acceptance worked
    // cy.session handles user switching

    // ---- Login again as testuser ----
    cy.login(testUser.username, testUser.password);

    // ---- Visit friend's profile (otherUser) ----
    cy.visit(`/profile/${otherUser.username}`);

    // ---- Verify FRIENDS state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'FRIENDS');
    cy.get('[data-cy="unfriend-button"]').should('be.visible');

    // ---- Unfriend the user ----
    cy.get('[data-cy="unfriend-button"]').click();
    cy.wait(500); // Wait for API call/UI update

    // ---- Verify NONE state ----
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');
    cy.get('[data-cy="send-friend-request-button"]').should('be.visible');
    cy.get('[data-cy="unfriend-button"]').should('not.exist');
  });

});

// --- New Describe Block for Post Visibility --- 
describe.skip('Profile Post Visibility', () => {
  const testUser = {
    username: 'testuser',
    password: 'password',
  };
  const otherUser = {
    username: 'testuser2',
    password: 'password',
  };

  // Define unique content for test posts
  const publicPostContent = `Public post by testuser2 - ${Date.now()}`;
  const friendsPostContent = `Friends post by testuser2 - ${Date.now()}`;

  before(() => {
    // Ensure testuser2 creates posts *once* before this suite runs
    cy.login(otherUser.username, otherUser.password); // Login as the post author
    
    // Create Public Post using custom command
    cy.createPost({ content: publicPostContent, privacy: 'PUBLIC' });

    // Create Friends-Only Post using custom command
    cy.createPost({ content: friendsPostContent, privacy: 'FRIENDS' });

    // Note: Session context will be switched by cy.login() in subsequent tests.
  });

  it('should show only public posts of a non-friend user', () => {
    cy.login(testUser.username, testUser.password); // Login as the viewing user

    // TODO: Add step here to ENSURE testUser and otherUser are NOT friends
    // This might involve a cy.request() to DELETE a friendship or friend request if one exists
    // For now, assuming they start as non-friends for this test.

    cy.visit(`/profile/${otherUser.username}`);

    // Check profile username is correct (sanity check)
    cy.get('[data-cy="profile-username"]').should('contain.text', otherUser.username);

    // Verify public post is visible
    // Assuming posts are rendered within [data-cy="profile-posts-section"] 
    // and contain their content text directly or within a child element.
    cy.get('[data-cy="profile-posts-section"]')
      .should('contain.text', publicPostContent);

    // Verify friends-only post is NOT visible
    cy.get('[data-cy="profile-posts-section"]')
      .should('not.contain.text', friendsPostContent);
      
    // Also check the overall friendship status is NONE
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'NONE');

    // Verify interests are displayed (assuming posts generate some interests)
    cy.get('[data-cy="profile-interests-section"]').should('be.visible');
    // Add more specific checks if classification results are predictable
    // e.g., cy.get('[data-cy="profile-interests-section"]').should('contain.text', 'Technology'); 
    // e.g., cy.get('[data-cy="profile-interests-section"]').should('contain.text', 'Testing'); 

    // Verify email and invites are NOT visible for other user
    cy.get('[data-cy="profile-email"]').should('not.exist');
    cy.get('[data-cy="profile-invites-left"]').should('not.exist');
  });

  // --- Add test for friend visibility next ---
  it('should show both public and friends-only posts for a friend user', () => {
    // let testUserId, otherUserId, requestId;

    // --- SETUP: Establish Friendship via custom commands ---
    cy.login(testUser.username, testUser.password); // Login as sender
    cy.sendFriendRequestTo(otherUser.username).then((requestId) => {
        // request ID is yielded from the send command
        cy.login(otherUser.username, otherUser.password); // Login as receiver
        cy.acceptFriendRequest(requestId); // Accept using the request ID
    });
    // // --- Old API Setup --- 
    // // 1. Get User IDs
    // cy.login(testUser.username, testUser.password); // Login as testUser first to fetch its own data easily
    // cy.request('/api/v1/profiles/me').then(response => {
    //   expect(response.status).to.eq(200);
    //   testUserId = response.body.user.id;
    //   // Fetch other user's profile while logged in as testUser
    //   return cy.request(`/api/v1/profiles/${otherUser.username}`); 
    // }).then(response => {
    //   expect(response.status).to.eq(200);
    //   otherUserId = response.body.user.id;
    //   // We now have both IDs
    //   cy.log(`TestUser ID: ${testUserId}, OtherUser ID: ${otherUserId}`);
    //
    //   // 2. Ensure not friends (delete existing friendship if any - ignore errors)
    //   cy.request({ 
    //     method: 'DELETE', 
    //     url: `/api/v1/friendships/${otherUserId}`, 
    //     failOnStatusCode: false // Don't fail if they weren't friends
    //   });
    //
    //   // 3. Send Friend Request (testUser -> otherUser)
    //   return cy.request({
    //     method: 'POST',
    //     url: '/api/v1/friend-requests',
    //     body: { user_id: otherUserId }
    //   });
    // }).then(response => {
    //   expect(response.status).to.eq(201); // Friend request sent
    //   requestId = response.body.id; // Capture the request ID
    //   cy.log(`Sent Request ID: ${requestId}`);
    //
    //   // 4. Accept Friend Request (as otherUser)
    //   cy.login(otherUser.username, otherUser.password); // Login as the receiver
    //   return cy.request({
    //     method: 'PUT',
    //     url: `/api/v1/friend-requests/${requestId}`,
    //     body: { action: 'accept' }
    //   });
    // }).then(response => {
    //   expect(response.status).to.eq(200); // Friend request accepted
    //   expect(response.body.status).to.eq('ACCEPTED');
    //   cy.log('Friend request accepted');
    // });
    // // --- End SETUP ---

    // --- Verification --- 
    cy.login(testUser.username, testUser.password); // Login back as the viewing user
    cy.visit(`/profile/${otherUser.username}`);

    // Verify friendship status is FRIENDS
    cy.get('[data-cy="friendship-status"]').should('contain.text', 'FRIENDS');

    // Verify public post is visible
    cy.get('[data-cy="profile-posts-section"]')
      .should('contain.text', publicPostContent);

    // Verify friends-only post is ALSO visible
    cy.get('[data-cy="profile-posts-section"]')
      .should('contain.text', friendsPostContent);
      
    // Verify interests are displayed (should be the same interests as when non-friend)
    cy.get('[data-cy="profile-interests-section"]').should('be.visible');
    // Add same specific checks as in the non-friend test
    // e.g., cy.get('[data-cy="profile-interests-section"]').should('contain.text', 'Technology');
    // e.g., cy.get('[data-cy="profile-interests-section"]').should('contain.text', 'Testing');

    // Verify email and invites are NOT visible even for friend
    cy.get('[data-cy="profile-email"]').should('not.exist');
    cy.get('[data-cy="profile-invites-left"]').should('not.exist');
  });

});