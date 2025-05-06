// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })

Cypress.Commands.add('login', (identifier, password) => {
    cy.session([identifier, password], () => {
      cy.visit('/login');
      cy.get('#identifier').type(identifier);
      cy.get('#password').type(password);
      cy.get('button[type="submit"]').contains(/login/i).click();
      // Wait for login to complete by checking for an element on the dashboard
      // or waiting for the URL to change and the profile call to likely succeed.
      // Using URL check + a small wait for API call as a proxy.
      cy.url({ timeout: 10000 }).should('eq', Cypress.config().baseUrl + '/');
      // Verify an element that relies on successful login / profile fetch
      cy.contains('h3', /Your Feed/i, { timeout: 10000 }).should('be.visible'); 
    }, {
      cacheAcrossSpecs: true // Optional: speeds up tests if login is needed across multiple spec files
    });
  });