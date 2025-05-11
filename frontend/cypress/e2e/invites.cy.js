/// <reference types="cypress" />

describe('Invite Code Management', () => {
  // const testUser = 'testUser'; // Not directly used in beforeEach login
  // const testPassword = 'password'; // Not directly used in beforeEach login

  beforeEach(function() { // Use function() to allow `this` context for mocha
    cy.request({ // Start of the chain: Reset API call
      method: 'POST',
      url: '/api/v1/test-setup/reset-user-state',
      body: {
        username: 'testuser',
        desired_state: {
          password: 'password',
          invites_left: 10, 
          user_type: 'ADMIN',
          create_default_invite: true
        }
      },
      failOnStatusCode: false 
    }).then(resetResponse => {
      expect(resetResponse.status, 'Reset User State API call').to.be.within(200, 299);
      if (resetResponse.status >= 300) {
        cy.log('Reset API Response Body:', JSON.stringify(resetResponse.body));
        throw new Error('Reset API failed, halting beforeEach'); // Halt if reset fails
      }
      // Reset was successful, now clear sessions and login
      Cypress.session.clearAllSavedSessions(); 
      return cy.login('testuser', 'password'); // Return the promise from cy.login()
    }).then(() => { // After login completes (cy.login promise resolves)
      // Fetch profile data
      return cy.request({
        method: 'GET',
        url: '/api/v1/profiles/me'
      });
    }).then(profileResponse => {
      expect(profileResponse.status).to.eq(200);
      this.initialInvitesLeft = profileResponse.body.user.invites_left;
      cy.log(`Fetched actual initial invites_left: ${this.initialInvitesLeft}`);
      // Fetch baseline invites data, add cache-busting parameter
      return cy.request({
        method: 'GET',
        url: `/api/v1/invites?timestamp=${Date.now()}`,
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' } // Ensure these are active
      });
    }).then(invitesResponse => {
      expect(invitesResponse.status).to.eq(200);
      this.baselineUnusedInvitesCount = invitesResponse.body.unused_codes ? invitesResponse.body.unused_codes.length : 0;
      this.baselineUsedInvitesCount = invitesResponse.body.used_codes ? invitesResponse.body.used_codes.length : 0;
      cy.log(`Fetched actual baseline: ${this.baselineUnusedInvitesCount} unused, ${this.baselineUsedInvitesCount} used.`);
      
      // Now that all `this.*` properties are set, set up intercepts and visit
      cy.intercept('GET', '/api/v1/profiles/me').as('getProfileDataOnPageLoad');
      cy.intercept('GET', '/api/v1/invites*').as('getInvitesDataOnPageLoad');
      cy.intercept('POST', '/api/v1/invites').as('postInviteCode');

      cy.visit('/manage-invites');

      // Wait for page load API calls and assert against the fetched baselines
      return cy.wait('@getProfileDataOnPageLoad'); // Return promise to chain
    }).then(profilePageLoadInterception => {
      const invitesLeftOnPage = profilePageLoadInterception.response.body.user.invites_left;
      cy.log(`Profile data on page load - invites_left: ${invitesLeftOnPage}`);
      expect(invitesLeftOnPage, "invites_left from page load API call").to.eq(this.initialInvitesLeft);
      return cy.wait('@getInvitesDataOnPageLoad'); // Return promise to chain
    }).then(invitesPageLoadInterception => {
      const unusedCountOnPage = invitesPageLoadInterception.response.body.unused_codes ? invitesPageLoadInterception.response.body.unused_codes.length : 0;
      const usedCountOnPage = invitesPageLoadInterception.response.body.used_codes ? invitesPageLoadInterception.response.body.used_codes.length : 0;
      cy.log(`Invites data on page load - unused: ${unusedCountOnPage}, used: ${usedCountOnPage}`);
      expect(unusedCountOnPage, "Unused invites count from page load API call").to.eq(this.baselineUnusedInvitesCount);
      expect(usedCountOnPage, "Used invites count from page load API call").to.eq(this.baselineUsedInvitesCount);
      
      // Final assertions for beforeEach completion
      cy.contains('h2', 'Manage Invite Codes').should('be.visible');
      cy.get('.invites-summary').should('contain.text', `${this.initialInvitesLeft} invites remaining`);
    });
  });

  it('should display the initial invite state correctly', function () {
    cy.get('.invites-summary').should('contain.text', `${this.initialInvitesLeft} invites remaining`);

    if (this.initialInvitesLeft > 0) {
      cy.contains('button', 'Generate New Invite Code').should('not.be.disabled');
      cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('not.exist');
    } else {
      cy.contains('button', 'Generate New Invite Code').should('be.disabled');
      cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('be.visible');
    }

    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      if (this.baselineUnusedInvitesCount === 0) {
        cy.contains('p', 'No unused invite codes.').should('be.visible');
        cy.get('ul li').should('not.exist');
      } else {
        cy.contains('p', 'No unused invite codes.').should('not.exist');
        cy.get('ul li').should('have.length', this.baselineUnusedInvitesCount);
      }
    });

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

    cy.request({
      method: 'GET',
      url: `/api/v1/invites?timestamp=${Date.now()}`, // Cache-busting
      headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
    }).then((freshInvitesResponse) => {
      expect(freshInvitesResponse.status).to.eq(200);
      expect(freshInvitesResponse.body.unused_codes.length, "Unused codes count after generation (fresh request)")
        .to.eq(expectedUnusedCountAfterGeneration);
    });
    
    cy.get('.invites-summary', { timeout: 7000 })
      .should('contain.text', `${expectedInvitesLeftAfterGeneration} invites remaining`);

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
      
      cy.request({
        method: 'GET',
        url: `/api/v1/invites?timestamp=${Date.now()}`, // Cache-busting
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
      }).then(freshInvitesResponse => {
        expect(freshInvitesResponse.status).to.eq(200);
        expect(freshInvitesResponse.body.unused_codes.length, `Unused codes count in loop (i=${i})`)
          .to.eq(expectedUnusedAfterThisGeneration);
      });

      cy.get('.invites-summary', { timeout: 7000 })
        .should('contain.text', `${expectedInvitesLeftAfterThisGeneration} invites remaining`);
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

        cy.request({
          method: 'GET',
          url: `/api/v1/invites?timestamp=${Date.now()}`, // Cache-busting
          headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
        }).then(freshInvitesResponse => {
          expect(freshInvitesResponse.status).to.eq(200);
          expect(freshInvitesResponse.body.unused_codes.length, `Unused codes count in exhaust loop (i=${i})`)
            .to.eq(expectedUnusedAfterThisGeneration);
        });
        
        cy.get('.invites-summary', { timeout: 7000 })
          .should('contain.text', `${expectedInvitesLeftAfterThisGeneration} invites remaining`);
      }
    }

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');
    cy.contains('.no-invites-message', 'No invites left', { matchCase: false }).should('be.visible');
    
    cy.intercept('POST', '/api/v1/invites').as('attemptPostWhenNoneLeftAfterDisabled');
    cy.contains('button', 'Generate New Invite Code').click({ force: true }); 
    cy.wait(250, { log: false });
    cy.get('@attemptPostWhenNoneLeftAfterDisabled.all').should('have.length', 0);

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.contains('h3', 'Unused Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', this.baselineUnusedInvitesCount + invitesToGenerateToEnd);
    });
    cy.contains('h3', 'Used Invite Codes').parent().within(() => {
      cy.get('ul li').should('have.length', this.baselineUsedInvitesCount);
    });
  });
});