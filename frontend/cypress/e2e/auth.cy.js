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
    const timestamp = Date.now();
    const uniqueUsername = `testuser_${timestamp}`;
    const uniqueEmail = `test_${timestamp}@example.com`;
    const password = 'password123';

    // Visit the register page
    cy.visit('/register');

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

    // Submit the form
    cy.get('button[type="submit"]').contains(/register/i).click();

    // Assert success message is displayed (using the class)
    cy.get('.success-message')
      .should('be.visible')
      .and('contain.text', 'Registration successful! Redirecting to login...');

    // Assert redirection to login page (Cypress waits automatically)
    cy.url().should('eq', Cypress.config().baseUrl + '/login');
    
    // Optional: Check if the login form is now visible on the login page
    // cy.contains('h2', 'Login').should('be.visible');
  });

}); 