/// <reference types="cypress" />

describe('Category View Functionality', () => {
  // Define test user credentials
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

  // Assumed predictable categories based on content
  const techCategory = 'Technology';
  const travelCategory = 'Travel';
  const techPostContent = `Test post about programming and software - ${Date.now()}`;
  const travelPostContent = `Test post about travel and vacation - ${Date.now()}`;

  before(() => {
    // Ensure test users exist
    cy.ensureUserExists(testUser);
    cy.ensureUserExists(otherUser);

    // Create posts with specific content once before tests
    cy.login(testUser.username, testUser.password);
    cy.createPost({ content: techPostContent, privacy: 'PUBLIC' });

    cy.login(otherUser.username, otherUser.password);
    cy.createPost({ content: travelPostContent, privacy: 'PUBLIC' });
  });

  it('should display only posts relevant to the selected category', () => {
    cy.login(testUser.username, testUser.password);

    // Visit Technology category page
    cy.visit(`/category/${techCategory}`);

    // Verify Technology post is visible
    cy.contains('h2', `Posts in Category: ${techCategory}`).should('be.visible');
    cy.get('.posts-list').should('contain.text', techPostContent);

    // Verify Travel post is NOT visible
    cy.get('.posts-list').should('not.contain.text', travelPostContent);

    // Visit Travel category page
    cy.visit(`/category/${travelCategory}`);

    // Verify Travel post is visible
    cy.contains('h2', `Posts in Category: ${travelCategory}`).should('be.visible');
    cy.get('.posts-list').should('contain.text', travelPostContent);

    // Verify Technology post is NOT visible
    cy.get('.posts-list').should('not.contain.text', techPostContent);
  });

  describe('Category View Privacy', () => {
    // Use different content to avoid conflicts with the previous describe block's before hook
    const techCategory = 'Technology'; // Assuming still relevant
    const privacyTechPostContent = `Private tech post - ${Date.now()}`;
    
    // Helper to ensure users are NOT friends (copied from feed.cy.js, consider moving to commands.js)
    const ensureNotFriends = (userA, userB_username) => {
      cy.login(userA.username, userA.password);
      cy.request(`/api/v1/profiles/${userB_username}`).then(response => {
        if (response.status === 200 && response.body.user.id) {
          const userB_id = response.body.user.id;
          cy.request({ method: 'DELETE', url: `/api/v1/friendships/${userB_id}`, failOnStatusCode: false });
        }
      });
    };

    beforeEach(() => {
      // Create a friends-only tech post as otherUser before each privacy test
      cy.login(otherUser.username, otherUser.password);
      cy.createPost({ content: privacyTechPostContent, privacy: 'FRIENDS' });
    });

    it('should NOT display friends-only posts in a category if users are not friends', () => {
      // Ensure not friends
      ensureNotFriends(testUser, otherUser.username);
      ensureNotFriends(otherUser, testUser.username);

      cy.login(testUser.username, testUser.password);
      cy.visit(`/category/${techCategory}`);

      // Verify the friends-only post is NOT visible
      cy.contains('h2', `Posts in Category: ${techCategory}`).should('be.visible');
      cy.get('.posts-list').should('not.contain.text', privacyTechPostContent);
    });

    it('should display friends-only posts in a category IF users are friends', () => {
      // Make friends
      cy.login(testUser.username, testUser.password);
      cy.sendFriendRequestTo(otherUser.username).then((requestId) => {
        cy.login(otherUser.username, otherUser.password);
        cy.acceptFriendRequest(requestId);
      });

      // Verification
      cy.login(testUser.username, testUser.password);
      cy.visit(`/category/${techCategory}`);

      // Verify the friends-only post IS visible
      cy.contains('h2', `Posts in Category: ${techCategory}`).should('be.visible');
      cy.get('.posts-list').should('contain.text', privacyTechPostContent);
    });

  });

  it('should show an error message when visiting an invalid category URL', () => {
    const invalidCategory = 'InvalidCategoryABC123';

    cy.login(testUser.username, testUser.password);

    // Intercept the API call for the invalid category
    cy.intercept('GET', `/api/v1/categories/${invalidCategory}/posts*`).as('getInvalidCategory');

    // Visit the invalid category page
    // We expect this visit itself not to fail, but the component to show an error
    cy.visit(`/category/${invalidCategory}`, { failOnStatusCode: false }); // Allow non-2xx status codes from the page load/initial fetch

    // Wait for the API call to happen and verify it returns 404
    cy.wait('@getInvalidCategory').its('response.statusCode').should('eq', 404);

    // Verify an error message is displayed in the component
    // CategoryView.jsx shows: <p className="error-message">Error: {error}</p>
    cy.get('.error-message')
      .should('be.visible')
      // Check for part of the expected message from the backend abort(404, ...)
      .and('contain.text', `Category '${invalidCategory}' not found or is blocked.`); 
  });

  // --- Add tests for privacy within categories, invalid categories etc. ---

}); 