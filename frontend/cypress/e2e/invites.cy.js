/// <reference types="cypress" />

describe('Invite Code Management', () => {
  const testUser = 'testUser';
  const testPassword = 'password';

  beforeEach(function () {
    // Clear any existing session to ensure a fresh login
    Cypress.session.clearAllSavedSessions(); // Re-added this line
    cy.login(testUser, testPassword);

    // Get the actual current invites_left for the testUser
    // Relies on the session cookie from cy.login(), removed explicit Authorization header
    cy.request({
      method: 'GET',
      url: '/api/v1/profiles/me'
    }).then(profileResponse => {
      expect(profileResponse.status).to.eq(200);
      this.initialInvitesLeft = profileResponse.body.user.invites_left;
      cy.log(`Fetched actual initial invites_left: ${this.initialInvitesLeft}`);
    });

    // Get baseline counts of existing invite codes (since they are not deleted)
    // Relies on the session cookie from cy.login(), removed explicit Authorization header
    cy.request({
      method: 'GET',
      url: '/api/v1/invites'
    }).then(invitesResponse => {
      expect(invitesResponse.status).to.eq(200);
      this.baselineUnusedInvitesCount = invitesResponse.body.unused_codes ? invitesResponse.body.unused_codes.length : 0;
      this.baselineUsedInvitesCount = invitesResponse.body.used_codes ? invitesResponse.body.used_codes.length : 0;
      cy.log(`Fetched actual baseline: ${this.baselineUnusedInvitesCount} unused, ${this.baselineUsedInvitesCount} used.`);
    });

    cy.intercept('GET', '/api/v1/profiles/me').as('getProfileDataOnPageLoad');
    cy.intercept('GET', '/api/v1/invites').as('getInvitesDataOnPageLoad');
    cy.intercept('POST', '/api/v1/invites').as('postInviteCode');

    cy.visit('/manage-invites');

    // Wait for page to load and make its own API calls
    cy.wait('@getProfileDataOnPageLoad').then(interception => {
      const invitesLeftOnPage = interception.response.body.user.invites_left;
      cy.log(`Profile data on page load - invites_left: ${invitesLeftOnPage}`);
      // Assert that the page reflects the invites_left we fetched *before* visiting
      expect(invitesLeftOnPage, "invites_left from page load API call").to.eq(this.initialInvitesLeft);
    });

    cy.wait('@getInvitesDataOnPageLoad').then(interception => {
      const unusedCountOnPage = interception.response.body.unused_codes ? interception.response.body.unused_codes.length : 0;
      const usedCountOnPage = interception.response.body.used_codes ? interception.response.body.used_codes.length : 0;
      cy.log(`Invites data on page load - unused: ${unusedCountOnPage}, used: ${usedCountOnPage}`);
      // Assert that the page reflects the invite counts we fetched *before* visiting
      expect(unusedCountOnPage, "Unused invites count from page load API call").to.eq(this.baselineUnusedInvitesCount);
      expect(usedCountOnPage, "Used invites count from page load API call").to.eq(this.baselineUsedInvitesCount);
    });

    cy.contains('h1', 'Manage Invite Codes').should('be.visible');
    // Check that the summary text on the page matches the actual initial invites left
    cy.get('.invites-summary').should('contain.text', `${this.initialInvitesLeft} invites remaining`);
  });

  it('should display the initial invite state correctly', function () {
    // Check invite summary text
    cy.get('.invites-summary').should('contain.text', `${this.initialInvitesLeft} invites remaining`);

    // Check "Generate New Invite Code" button state
    if (this.initialInvitesLeft > 0) {
      cy.contains('button', 'Generate New Invite Code').should('not.be.disabled');
      cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('not.exist');
    } else {
      cy.contains('button', 'Generate New Invite Code').should('be.disabled');
      cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('be.visible');
    }

    // Check unused codes list
    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      if (this.baselineUnusedInvitesCount === 0) {
        cy.contains('p', 'No unused invite codes.').should('be.visible');
        cy.get('ul li').should('not.exist');
      } else {
        cy.contains('p', 'No unused invite codes.').should('not.exist');
        cy.get('ul li').should('have.length', this.baselineUnusedInvitesCount);
      }
    });

    // Check used codes list
    cy.contains('h3', 'Used Invite Codes').parent().within(() => {
      if (this.baselineUsedInvitesCount === 0) {
        cy.contains('p', 'No used invite codes.').should('be.visible');
        cy.get('ul li').should('not.exist');
      } else {
        cy.contains('p', 'No used invite codes.').should('not.exist');
        cy.get('ul li').should('have.length', this.baselineUsedInvitesCount);
      }
    });
  });

  it('should generate a new code when the button is clicked', function () {
    if (this.initialInvitesLeft === 0) {
      cy.log('Skipping test: No initial invites to generate a new one.');
      this.skip(); 
      return;
    }

    const expectedInvitesLeftAfterGeneration = this.initialInvitesLeft - 1;
    const expectedUnusedCountAfterGeneration = this.baselineUnusedInvitesCount + 1;

    cy.contains('button', 'Generate New Invite Code').click();

    cy.wait('@postInviteCode').then((postInterception) => {
      expect(postInterception.response.statusCode, "POST invite code status").to.eq(201);
      expect(postInterception.response.body).to.have.property('code');
    });

    cy.get('.invites-summary', { timeout: 7000 })
      .should('contain.text', `${expectedInvitesLeftAfterGeneration} invites remaining`);

    cy.intercept('GET', '/api/v1/invites').as('getInvitesDataAfterGen'); 
    cy.wait('@getInvitesDataAfterGen').then((invitesInterception) => {
      expect(invitesInterception.response.body.unused_codes.length, "Unused codes count after generation")
        .to.eq(expectedUnusedCountAfterGeneration);
    });

    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', expectedUnusedCountAfterGeneration);
    });
  });

  it('should disable the generate button when no invites are left (i.e., invites_left becomes 0)', function () {
    const invitesToGenerate = this.initialInvitesLeft;
    if (invitesToGenerate === 0) {
      cy.log('Skipping test: Already 0 invites, button should be disabled.');
      cy.contains('button', 'Generate New Invite Code').should('be.disabled');
      this.skip();
      return;
    }

    cy.log(`Starting with ${invitesToGenerate} invites. Will generate all of them.`);

    for (let i = 0; i < invitesToGenerate; i++) {
      const expectedInvitesLeftAfterThisGeneration = this.initialInvitesLeft - (i + 1);
      const expectedUnusedAfterThisGeneration = this.baselineUnusedInvitesCount + (i + 1);
      cy.log(`Generating invite ${i + 1} of ${invitesToGenerate}. Expecting ${expectedInvitesLeftAfterThisGeneration} invites_left and ${expectedUnusedAfterThisGeneration} unused codes.`);
      
      cy.contains('button', 'Generate New Invite Code').click();
      cy.wait('@postInviteCode').its('response.statusCode').should('eq', 201);
      
      cy.get('.invites-summary', { timeout: 7000 })
        .should('contain.text', `${expectedInvitesLeftAfterThisGeneration} invites remaining`);
      
      cy.intercept('GET', '/api/v1/invites').as(`getInvitesDataLoop${i}`); 
      cy.wait(`@getInvitesDataLoop${i}`).then(invitesInterception => {
        expect(invitesInterception.response.body.unused_codes.length, `Unused codes count in loop (i=${i})`)
          .to.eq(expectedUnusedAfterThisGeneration);
      });
    }

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');
    cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('be.visible');

    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', this.baselineUnusedInvitesCount + invitesToGenerate);
    });
  });

  it('should show an error or prevent generation if trying to generate when none left', function () {
    const invitesToGenerateToEnd = this.initialInvitesLeft;
    cy.log(`Initially ${this.initialInvitesLeft} invites. Will generate ${invitesToGenerateToEnd} to exhaust them.`);

    if (invitesToGenerateToEnd > 0) {
      for (let i = 0; i < invitesToGenerateToEnd; i++) {
        const expectedInvitesLeftAfterThisGeneration = this.initialInvitesLeft - (i + 1);
        const expectedUnusedAfterThisGeneration = this.baselineUnusedInvitesCount + (i + 1);

        cy.contains('button', 'Generate New Invite Code').click();
        cy.wait('@postInviteCode').its('response.statusCode').should('eq', 201);

        cy.get('.invites-summary', { timeout: 7000 })
          .should('contain.text', `${expectedInvitesLeftAfterThisGeneration} invites remaining`);

        cy.intercept('GET', '/api/v1/invites').as(`getInvitesDataExhaustLoop${i}`); 
        cy.wait(`@getInvitesDataExhaustLoop${i}`).then(invitesInterception => {
          expect(invitesInterception.response.body.unused_codes.length, `Unused codes count in exhaust loop (i=${i})`)
            .to.eq(expectedUnusedAfterThisGeneration);
        });
      }
    }

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');
    cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('be.visible');
    
    cy.intercept('POST', '/api/v1/invites').as('attemptPostWhenNoneLeft');
    
    cy.contains('button', 'Generate New Invite Code').click({ force: true }); 

    cy.wait(250, { log: false }); 
    
    cy.get('@attemptPostWhenNoneLeft.all').should('have.length', 0);

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', this.baselineUnusedInvitesCount + invitesToGenerateToEnd);
    });
    cy.contains('h3', 'Used Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', this.baselineUsedInvitesCount);
    });
  });
});