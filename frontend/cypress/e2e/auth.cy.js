describe('Authentication Flow', () => {
  beforeEach(() => {
    // Optional: Clear session/cookies before each test if needed
    // cy.clearCookies();
    // cy.clearLocalStorage();
  });

  it('should allow a user to log in successfully', () => {
    // Visit the login page
    cy.visit('/login');

    // Check if the login form elements are visible
    cy.contains('h2', 'Login').should('be.visible');
    cy.get('label[for="identifier"]').should('be.visible');
    cy.get('#identifier').should('be.visible');
    cy.get('label[for="password"]').should('be.visible');
    cy.get('#password').should('be.visible');
    cy.get('button[type="submit"]').contains(/login/i).should('be.visible');

    // Enter credentials (assuming user 'testuser'/'password' exists)
    cy.get('#identifier').type('testuser');
    cy.get('#password').type('password');

    // Submit the form
    cy.get('button[type="submit"]').contains(/login/i).click();

    // Assert successful login - Check for redirection to the dashboard
    // or presence of dashboard elements. The URL check is simplest for now.
    cy.url().should('eq', Cypress.config().baseUrl + '/'); // Assumes successful login redirects to '/'
    
    // Optional: Check for an element specific to the logged-in state (e.g., logout button)
    // cy.contains('button', /logout/i).should('be.visible');
  });

  // Add more tests: failed login, navigation to register, etc.
  it('should display an error on failed login', () => {
    cy.visit('/login');

    cy.get('#identifier').type('testuser');
    cy.get('#password').type('wrongpassword');
    cy.get('button[type="submit"]').contains(/login/i).click();

    // Assert error message is displayed
    // The selector might depend on how errors are rendered (e.g., a specific class)
    cy.get('.error-message').should('contain.text', 'Invalid credentials'); // Directly check text

    // Assert we are still on the login page
    cy.url().should('include', '/login');
  });

  it('should allow a new user to register successfully', () => {
    // This test now assumes that for a standard registration,
    // an invite code might be required by the backend.
    // It will first log in as 'testuser', generate an invite code,
    // then log out and attempt to register a new user with that code.

    let inviteCode = '';

    // 1. Login as 'testuser' to generate an invite code
    cy.login('testuser', 'password');
    cy.request({
      method: 'POST',
      url: '/api/v1/invites',
    }).then((inviteResponse) => {
      expect(inviteResponse.status).to.eq(201);
      if (inviteResponse.body.code) {
        inviteCode = inviteResponse.body.code;
      } else if (typeof inviteResponse.body === 'string') {
        inviteCode = inviteResponse.body;
      } else {
        inviteCode = inviteResponse.body?.invite?.code || inviteResponse.body?.data?.code;
      }
      if (!inviteCode) {
        throw new Error('Failed to extract invite code for registration test.');
      }
      cy.log(`Generated invite code for registration test: ${inviteCode}`);
      cy.logout(); // Logout 'testuser'
    });

    cy.then(() => {
      expect(inviteCode).to.not.be.empty;

      const timestamp = Date.now();
      const uniqueUsername = `testuser_${timestamp}`;
      const uniqueEmail = `test_${timestamp}@example.com`;
      const password = 'password123';

      cy.visit(`/register?invite_code=${inviteCode}`);

      // Check form elements are visible
      cy.contains('h2', 'Register').should('be.visible');
      cy.get('#username').should('be.visible');
      cy.get('#email').should('be.visible');
      cy.get('#password').should('be.visible');
      cy.get('button[type="submit"]').contains(/register/i).should('be.visible');

      // Fill the form
      cy.get('#username').type(uniqueUsername);
      cy.get('#email').type(uniqueEmail);
      cy.get('#password').type(password);

      // Intercept the registration API call
      cy.intercept('POST', '/api/v1/register').as('registerRequest');

      // Submit the form
      cy.get('button[type="submit"]').contains(/register/i).click();

      // Wait for the API call to complete and log details
      cy.wait('@registerRequest').then((interception) => {
        cy.log('Registration request body: ' + JSON.stringify(interception.request.body));
        cy.log('Registration response status: ' + interception.response.statusCode);
        cy.log('Registration response body: ' + JSON.stringify(interception.response.body));
        expect(interception.response.statusCode).to.eq(201);
        expect(interception.request.body).to.have.property('invite_code', inviteCode);
      });

      // Assert success message is displayed
      cy.get('.success-message', { timeout: 5000 })
        .should('be.visible')
        .and('contain.text', 'Registration successful! Redirecting to login...');

      // Assert redirection to login page
      cy.url({ timeout: 5000 }).should('eq', Cypress.config().baseUrl + '/login');
    });
  });

  it('should allow registration using a valid invite code', () => {
    let inviteCode = '';

    // 1. Generate an invite code as an existing user
    cy.login('testuser', 'password'); // Assuming testuser can generate codes
    cy.request({
      method: 'POST',
      url: '/api/v1/invites',
    }).then((response) => {
      expect(response.status).to.eq(201); 
      // Check if response.body itself is the code, or if it's nested
      if (response.body.code) {
          inviteCode = response.body.code;
      } else if (typeof response.body === 'string') {
          // If the API directly returns the code string
          inviteCode = response.body; 
      } else {
           // Attempt to find code if nested differently, e.g. response.body.invite.code
          inviteCode = response.body?.invite?.code || response.body?.data?.code;
          if (!inviteCode) throw new Error('Could not extract invite code from response');
      }
      cy.log(`Generated invite code for registration: ${inviteCode}`);
      
      // Logout before visiting register page
      cy.logout(); 
    });

    // Ensure the API calls are done before proceeding
    cy.then(() => {
      // Make sure inviteCode was set
      expect(inviteCode).to.not.be.empty;

      // 2. Visit the registration page with the invite code (NOW LOGGED OUT)
      cy.visit(`/register?invite_code=${inviteCode}`);

      // Verify the page shows the code being used (if applicable)
      // This relies on the <p> tag added in Register.jsx
      cy.contains(`Registering with invite code: ${inviteCode}`).should('be.visible');

      // 3. Fill out registration form for a NEW user
      const timestamp = Date.now();
      const uniqueUsername = `inviteduser_${timestamp}`;
      const uniqueEmail = `invited_${timestamp}@example.com`;
      const password = 'password123';

      cy.get('#username').type(uniqueUsername);
      cy.get('#email').type(uniqueEmail);
      cy.get('#password').type(password);

      // 4. Intercept the registration API call
      cy.intercept('POST', '/api/v1/register').as('registerWithInvite');

      // 5. Submit the form
      cy.contains('button', /register/i).click();

      // 6. Verify the API call
      cy.wait('@registerWithInvite').then((interception) => {
        expect(interception.response.statusCode).to.eq(201);
        expect(interception.request.body).to.have.property('invite_code', inviteCode);
      });

      // 7. Verify success message and redirection to login
      cy.get('.success-message')
        .should('be.visible')
        .and('contain.text', 'Registration successful! Redirecting to login...');
      cy.url().should('eq', Cypress.config().baseUrl + '/login');
    });
  });

  it('should show an error when attempting to register with an invalid invite code', () => {
    const invalidCode = 'invalid-code-string-123';

    // 1. Visit the registration page with the invalid code
    cy.visit(`/register?invite_code=${invalidCode}`);

    // Verify the page shows an error immediately OR when trying to submit
    // Let's try filling the form and submitting
    const timestamp = Date.now();
    const uniqueUsername = `invalidinvite_${timestamp}`;
    const uniqueEmail = `invalid_${timestamp}@example.com`;
    const password = 'password123';

    cy.get('#username').type(uniqueUsername);
    cy.get('#email').type(uniqueEmail);
    cy.get('#password').type(password);

    // Intercept the registration API call
    cy.intercept('POST', '/api/v1/register').as('registerWithInvalidInvite');

    // Submit the form
    cy.contains('button', /register/i).click();

    // Verify the API call failed (e.g., 400 Bad Request)
    cy.wait('@registerWithInvalidInvite').then((interception) => {
      cy.log('Registration request body: ' + JSON.stringify(interception.request.body));
      cy.log('Registration response status: ' + interception.response.statusCode);
      cy.log('Registration response body: ' + JSON.stringify(interception.response.body));
      expect(interception.response.statusCode).to.be.oneOf([400, 404]); // 400 Bad Request or 404 Not Found are likely
      // Verify the error message from the API response is displayed
      cy.get('.error-message')
        .should('be.visible')
        .and('contain.text', interception.response.body.message); // Display API error message
        // Example check for specific text if API message is predictable:
        // .and('contain.text', 'Invalid or used invite code');
    });

    // Verify we are still on the register page (or redirected appropriately)
    cy.url().should('include', '/register'); 
  });

});