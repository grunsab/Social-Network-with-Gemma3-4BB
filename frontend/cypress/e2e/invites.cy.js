/// <reference types="cypress" />

describe('Invite Code Management', () => {
  const testUser = {
    username: 'testuser',
    password: 'password',
    email: 'testuser@example.com'
  };
  const defaultInvites = 3;

  beforeEach(function() {
    cy.login(testUser.username, testUser.password);

    cy.request({
      method: 'GET',
      url: '/api/v1/invites',
      failOnStatusCode: false
    }).then((response) => {
      let unused = 0;
      let used = 0;
      if (response.status === 200 && response.body && response.body.invites) {
        response.body.invites.forEach(invite => {
          if (invite.used_by_user_id === null) unused++;
          else used++;
        });
      }
      this.initialUnusedInvitesCount = unused;
      this.initialUsedInvitesCount = used;
      cy.log(`Initial state from API: ${this.initialUnusedInvitesCount} unused, ${this.initialUsedInvitesCount} used invites.`);
    }).then(() => {
      return cy.request({
        method: 'PATCH',
        url: '/api/v1/profiles/me',
        body: { invites_left: defaultInvites }
      });
    }).then((patchResponse) => {
      expect(patchResponse.status).to.eq(200);
      cy.log(`Reset invites_left for ${testUser.username} to ${defaultInvites}`);

      cy.intercept('GET', '/api/v1/profiles/me').as('getProfileData');
      cy.intercept('GET', '/api/v1/invites').as('getInvitesData');

      cy.visit('/manage-invites');

      cy.wait('@getProfileData').then((interception) => {
        expect(interception.response.statusCode).to.eq(200);
        expect(interception.response.body.user.invites_left).to.eq(defaultInvites);
      });
      cy.wait('@getInvitesData');

      cy.contains('h2', 'Manage Invite Codes').should('be.visible');
      cy.get('.invites-summary').should('be.visible').and('contain.text', `${defaultInvites} invites remaining`);
    });
  });

  it('should display the initial invite state correctly', function() {
    cy.get('h2').should('contain', 'Manage Invite Codes');
    cy.get('.invites-summary').should('be.visible').and('contain.text', `${defaultInvites} invites remaining`);
    cy.get('[data-cy="invites-left-display"]').should('be.visible').and('contain.text', `Invites left: ${defaultInvites}`);

    cy.contains('h3', 'Unused Invite Codes').then($h3 => {
      const $section = $h3.parent();
      if (this.initialUnusedInvitesCount > 0) {
        $section.find('ul.invites-list .invite-list-item').should('have.length', this.initialUnusedInvitesCount);
        $section.find('p:contains("No unused invite codes found.")').should('not.exist');
      } else {
        $section.find('ul.invites-list').should('not.exist');
        $section.find('p:contains("No unused invite codes found.")').should('be.visible');
      }
    });

    cy.contains('h3', 'Used Invite Codes').then($h3 => {
      const $section = $h3.parent();
      if (this.initialUsedInvitesCount > 0) {
        $section.find('ul.invites-list .invite-list-item').should('have.length', this.initialUsedInvitesCount);
        $section.find('p:contains("No used invite codes found.")').should('not.exist');
      } else {
        $section.find('ul.invites-list').should('not.exist');
        $section.find('p:contains("No used invite codes found.")').should('be.visible');
      }
    });

    if (defaultInvites > 0) {
      cy.get('button').contains('Generate New Invite Code').should('be.visible').and('not.be.disabled');
    } else {
      cy.get('button').contains('Generate New Invite Code').should('be.disabled');
      cy.contains('.no-invites-message', 'No invites left').should('be.visible');
    }
  });

  it('should generate a new code when the button is clicked', function() {
    if (defaultInvites === 0) {
      this.skip(); return;
    }
    const expectedInvitesLeft = defaultInvites - 1;
    cy.intercept('POST', '/api/v1/invites').as('generateInvite');

    cy.contains('button', 'Generate New Invite Code').click();

    cy.wait('@generateInvite').then((postInterception) => {
      expect(postInterception.response.statusCode).to.eq(201);
      expect(postInterception.response.body).to.have.property('code');
      cy.wrap(postInterception.response.body.code).as('generatedCode');
    });

    cy.wait('@getProfileData').then((profileInterception) => {
      expect(profileInterception.response.statusCode).to.eq(200);
      expect(profileInterception.response.body.user.invites_left).to.eq(expectedInvitesLeft);
    });
    cy.wait('@getInvitesData');

    cy.get('.invites-summary').should('contain.text', `${expectedInvitesLeft} invites remaining`);
    cy.get('[data-cy="invites-left-display"]').should('contain.text', `Invites left: ${expectedInvitesLeft}`);

    cy.get('@generatedCode').then((codeValue) => {
      cy.contains('h3', 'Unused Invite Codes').parent().find('ul.invites-list')
        .should('be.visible')
        .find('.invite-list-item')
        .should('have.length', this.initialUnusedInvitesCount + 1)
        .and('contain.text', codeValue);
    });
  });

  it('should disable the generate button when no invites are left', function() {
    if (defaultInvites === 0) {
      this.skip(); return;
    }
    const invitesToGenerate = defaultInvites;
    cy.intercept('POST', '/api/v1/invites').as('generateInviteLoop');

    Cypress._.times(invitesToGenerate, (i) => {
      const expectedInvitesLeftAfterThis = defaultInvites - (i + 1);
      cy.contains('button', 'Generate New Invite Code').click();
      cy.wait('@generateInviteLoop').its('response.statusCode').should('eq', 201);
      cy.wait('@getProfileData').then((profileInterception) => {
        expect(profileInterception.response.body.user.invites_left).to.eq(expectedInvitesLeftAfterThis);
      });
      cy.wait('@getInvitesData');
      cy.get('.invites-summary').should('contain.text', `${expectedInvitesLeftAfterThis} invites remaining`);
      cy.get('[data-cy="invites-left-display"]').should('contain.text', `Invites left: ${expectedInvitesLeftAfterThis}`);
    });

    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.get('[data-cy="invites-left-display"]').should('contain.text', 'Invites left: 0');
    cy.contains('button', 'Generate New Invite Code').should('be.disabled');
    cy.contains('.no-invites-message', 'No invites left').should('be.visible');
    cy.contains('h3', 'Unused Invite Codes').parent().find('ul.invites-list .invite-list-item')
      .should('have.length', this.initialUnusedInvitesCount + invitesToGenerate);
  });

  it('should show an error or prevent generation if trying to generate when none left', function() {
    const invitesToGenerate = defaultInvites;
    cy.intercept('POST', '/api/v1/invites').as('generateInviteExhaustLoop');

    if (invitesToGenerate === 0) {
      cy.contains('button', 'Generate New Invite Code').should('be.disabled');
      cy.contains('button', 'Generate New Invite Code').click({ force: true });
      cy.wait(200, { log: false });
      cy.get('@generateInviteExhaustLoop.all').its('length').should('eq', 0);
      this.skip(); return;
    }

    Cypress._.times(invitesToGenerate, (i) => {
      const expectedInvitesLeftAfterThis = defaultInvites - (i + 1);
      cy.contains('button', 'Generate New Invite Code').click();
      cy.wait('@generateInviteExhaustLoop').its('response.statusCode').should('eq', 201);
      cy.wait('@getProfileData').then((profileInterception) => {
         expect(profileInterception.response.body.user.invites_left).to.eq(expectedInvitesLeftAfterThis);
      });
      cy.wait('@getInvitesData');
    });

    cy.contains('button', 'Generate New Invite Code').should('be.disabled');
    cy.contains('button', 'Generate New Invite Code').click({ force: true });
    cy.wait(200, { log: false });
    cy.get('@generateInviteExhaustLoop.all').its('length').should('eq', invitesToGenerate);
    cy.get('.invites-summary').should('contain.text', '0 invites remaining');
    cy.get('[data-cy="invites-left-display"]').should('contain.text', 'Invites left: 0');
    cy.contains('.no-invites-message', 'No invites left').should('be.visible');
    cy.contains('h3', 'Unused Invite Codes').parent().find('ul.invites-list .invite-list-item')
      .should('have.length', this.initialUnusedInvitesCount + invitesToGenerate);
  });
});