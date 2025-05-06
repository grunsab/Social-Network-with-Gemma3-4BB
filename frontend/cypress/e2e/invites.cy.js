/// <reference types="cypress" />

describe('Invite Code Management', () => {
  // Define test user credentials
  const testUser = {
    username: 'testuser',
    password: 'password',
    email: 'testuser@example.com' 
  };
  const defaultInvites = 3; // Define the expected default

  beforeEach(() => {
    // Reset invites_left to default via API before each test
    cy.login(testUser.username, testUser.password);
    cy.request({
      method: 'PATCH',
      url: '/api/v1/profiles/me',
      body: {
        invites_left: defaultInvites
      }
    }).then((response) => {
      expect(response.status).to.eq(200); // Check API call success
      cy.log(`Reset invites for ${testUser.username} to ${defaultInvites}`);
      
      // Intercept the component's GET request before visiting
      cy.intercept('GET', '/api/v1/invites').as('getInvitesData');
      
      // Now visit the page after ensuring the state is reset
      cy.visit('/manage-invites');
      
      // Wait for the component's API call to finish
      cy.wait('@getInvitesData');
      
      // Wait for static elements to render confirms page is interactive
      cy.contains('h2', 'Manage Invite Codes').should('be.visible');
      
      // Now assert the content after data should have loaded
      cy.get('.invites-summary').should('contain.text', `${defaultInvites} invites remaining`);
    });
  });

  it('should display the initial invite state correctly', () => {
    // Verify initial invites left count (which should now be reset by beforeEach)
    cy.get('.invites-summary').should('contain.text', `${defaultInvites} invites remaining`);

    // Verify Generate button is enabled (assuming default > 0)
    cy.contains('button', 'Generate New Invite Code').should('be.enabled');

    // Verify Unused codes list exists and is initially empty (or contains expected seeded codes)
    // Assuming it starts empty for a fresh user
    cy.contains('h3', 'Unused Invite Codes').next('p').should('contain.text', 'No unused invite codes.');
    
    // Verify Used codes list exists and is initially empty
    cy.contains('h3', 'Used Invite Codes').next('p').should('contain.text', 'No used invite codes.');
  });

  it('should generate a new code when the button is clicked', () => {
    // Intercept the POST request for generating a code
    cy.intercept('POST', '/api/v1/invites').as('generateInvite');

    // Click the generate button
    cy.contains('button', 'Generate New Invite Code').click();

    // Wait for the API call and verify success
    cy.wait('@generateInvite').then((interception) => {
      expect(interception.response.statusCode).to.eq(201);
      // Verify the response body contains the code structure
      expect(interception.response.body).to.have.property('code');
      expect(interception.response.body).to.have.property('id');
      expect(interception.response.body.is_used).to.eq(false);
      // Store the generated code for later assertion
      const generatedCode = interception.response.body.code;
      cy.wrap(generatedCode).as('generatedCode'); 
    });

    // After generating, the component refetches data. Wait for the summary update.
    cy.get('.invites-summary').should('contain.text', `${defaultInvites - 1} invites remaining`);

    // Verify the generated code appears in the Unused list
    cy.get('@generatedCode').then((codeValue) => { // Retrieve the stored code value
      cy.contains('h3', 'Unused Invite Codes').parent()
        .find('.invites-list .invite-list-item')
        .should('have.length', 1) // Expect only one code
        .and('contain.text', codeValue); // Expect the list item to contain the code
    });

    // Verify Used codes list is still empty
    cy.contains('h3', 'Used Invite Codes').next('p').should('contain.text', 'No used invite codes.');
  });

  it('should disable the generate button when no invites are left', () => {
    // Initial state should be 3 invites (verified in previous test/beforeEach)
    const initialInvites = 3;

    // Intercept the POST request
    cy.intercept('POST', '/api/v1/invites').as('generateInviteLoop');

    // Click generate button until invites run out
    Cypress._.times(initialInvites, (i) => {
      cy.log(`Generating invite ${i + 1} of ${initialInvites}`);
      cy.contains('button', 'Generate New Invite Code').click();
      cy.wait('@generateInviteLoop').its('response.statusCode').should('eq', 201);
      // Wait for UI update showing decreased count (optional but safer)
      cy.get('.invites-summary').should('contain.text', `${initialInvites - (i + 1)} invites remaining`);
    });

    // Verify invites left is 0
    cy.get('.invites-summary').should('contain.text', '0 invites remaining');

    // Verify Generate button is now disabled
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');

    // Verify the helper text is shown
    cy.contains('.no-invites-message', 'No invites left').should('be.visible');

    // Verify the correct number of codes are in the Unused list
    cy.contains('h3', 'Unused Invite Codes').parent()
      .find('.invites-list .invite-list-item')
      .should('have.length', initialInvites);
  });

  it('should show an error or prevent generation if trying to generate when none left', () => {
    // Setup: Generate until 0 invites left (similar to previous test, could be refactored)
    const initialInvites = 3;
    cy.intercept('POST', '/api/v1/invites').as('generateInviteEmpty');
    Cypress._.times(initialInvites, () => {
      cy.contains('button', 'Generate New Invite Code').click();
      cy.wait('@generateInviteEmpty');
    });
    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');

    // Attempt to generate one more time
    // The button is disabled, so a simple click might not work. 
    // We could try { force: true } if needed, but the ideal scenario is the button is truly disabled.
    // Let's assume clicking a disabled button does nothing.
    cy.contains('button', 'Generate New Invite Code').click({ force: true }); // Try forcing it just in case

    // Assert that the API call was NOT made again (or failed with 400)
    // Using the same technique as empty comment validation
    cy.wait(100, { log: false }).then(() => {
        // Check if the intercept was called AGAIN after it was already disabled
        const calls = cy.state('requests').filter(req => req.alias === 'generateInviteEmpty');
        // Expect the number of calls to still be initialInvites (3)
        expect(calls.length).to.eq(initialInvites, 'API call should not be made when invites are 0');
    });

    // Alternatively, if the API *was* called, check for 400 status
    // cy.wait('@generateInviteEmpty').its('response.statusCode').should('eq', 400);
    // cy.get('.error-message').should('contain.text', 'You have no invites left');
    
    // Ensure count remains 0
    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
  });

  // --- Add tests for generating codes etc. ---

}); 