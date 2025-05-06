describe('Post Management', () => {

  // Use beforeEach to log in before each test in this file
  beforeEach(() => {
    // Use credentials for a test user (ensure this user exists in your test DB)
    cy.login('testuser', 'password');
    // Visit the page you want to test AFTER logging in
    cy.visit('/'); 
    // Wait for the feed heading to ensure the page is loaded after login
    cy.contains('h3', /Your Feed/i, { timeout: 10000 }).should('be.visible');
  });

  it('should allow a logged-in user to create a post', () => {
    // No need to visit or log in here, beforeEach handles it.
    
    // --- Now proceed with the actual test ---
    // At this point, we should be on the dashboard ('/') and logged in

    // Check for the posts list container (should exist even if empty)
    cy.get('.posts-list').should('be.visible');

    const postContent = `This is a test post created by Cypress at ${Date.now()}`;

    // <<< Add wait for the form/button to be ready before typing >>>
    cy.contains('button', 'Create Post').should('be.visible');

    // Find the textarea using its ID, wait for it to be visible, then type
    cy.get('#post-content').should('be.visible');
    cy.get('#post-content').type(postContent);

    // Find the submit button by its text and click it
    // Intercept the API call before clicking
    cy.intercept('POST', '/api/v1/posts').as('createPost');
    cy.contains('button', 'Create Post').click();

    // Wait for the API call to complete and check its status code
    cy.wait('@createPost').its('response.statusCode').should('eq', 201);

    // Wait for the post to appear in the feed (with increased timeout)
    cy.get('.posts-list').should('contain.text', postContent, { timeout: 10000 });
  });

  // Add more tests later (e.g., deleting posts, character limits?)
}); 