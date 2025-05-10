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

Cypress.Commands.add('login', (usernameOrEmail, password) => {
  cy.session([usernameOrEmail, password], () => {
    cy.visit('/login');
    cy.get('#identifier').type(usernameOrEmail);
    cy.get('#password').type(password);
    cy.get('button[type="submit"]').contains(/login/i).click();
    // Verify successful login - check URL lands on the root/dashboard
    // Allow for trailing slash or no trailing slash
    cy.url().should('match', new RegExp(Cypress.config().baseUrl + '/?$'));
  }, {
    // Optional: configure session validation
    validate: () => {
      // Add checks here to ensure the session is still valid if needed
      // e.g., check for a cookie or local storage item
      cy.getCookie('session').should('exist'); // Example check
    }
  });
});

// Custom command to create a post via API
Cypress.Commands.add('createPost', ({ content, privacy = 'PUBLIC' }) => {
  // Assumes the user who should create the post is already logged in via cy.login()
  // cy.request automatically uses the session cookie from cy.login()
  
  // Basic validation
  if (!content) {
    throw new Error('cy.createPost requires a content property.');
  }

  cy.request({
    method: 'POST',
    url: '/api/v1/posts',
    form: true, // Use form data as per API
    body: {
      content: content,
      privacy: privacy // PUBLIC or FRIENDS
    }
  }).then((response) => {
    // Check for successful creation (Status 201)
    expect(response.status).to.eq(201);
    // Yield the created post object to allow chaining
    cy.wrap(response.body.post);
  });
});

// Custom command to send a friend request via API
// Assumes the SENDER is currently logged in via cy.login()
Cypress.Commands.add('sendFriendRequestTo', (targetUsername) => {
  let targetUserId;

  // 1. Get Target User ID
  cy.request(`/api/v1/profiles/${targetUsername}`).then(response => {
    expect(response.status).to.eq(200);
    targetUserId = response.body.user.id;
    cy.log(`Target user ${targetUsername} has ID: ${targetUserId}`);

    // 2. Ensure not friends (delete existing friendship if any)
    // Logged in as sender, so deleting friendship with targetUserId
    return cy.request({ 
      method: 'DELETE', 
      url: `/api/v1/friendships/${targetUserId}`, 
      failOnStatusCode: false // Don't fail if they weren't friends
    });
  }).then(() => {
    // 3. Send Friend Request
    cy.log(`Sending friend request to user ID ${targetUserId}`);
    return cy.request({
      method: 'POST',
      url: '/api/v1/friend-requests',
      body: { user_id: targetUserId }
    });
  }).then(response => {
    expect(response.status).to.eq(201); // Friend request sent
    const requestId = response.body.id;
    cy.log(`Friend request sent with ID: ${requestId}`);
    // Yield the request ID for potential use later (e.g., accepting)
    cy.wrap(requestId);
  });
});

// Custom command to accept a friend request via API
// Assumes the RECEIVER is currently logged in via cy.login()
Cypress.Commands.add('acceptFriendRequest', (requestId) => {
  if (!requestId) {
    throw new Error('cy.acceptFriendRequest requires a requestId.');
  }
  cy.log(`Accepting friend request with ID: ${requestId}`);
  cy.request({
    method: 'PUT',
    url: `/api/v1/friend-requests/${requestId}`,
    body: { action: 'accept' }
  }).then(response => {
    expect(response.status).to.eq(200);
    expect(response.body.status).to.eq('ACCEPTED');
    cy.log(`Friend request ID ${requestId} accepted.`);
    cy.wrap(response.body); // Wrap the response body (updated request)
  });
});

// Custom command to logout via API
Cypress.Commands.add('logout', () => {
  // We need to ensure this runs with the user's session cookie.
  // cy.request should handle this if cy.login was used previously.
  cy.request({
    method: 'DELETE',
    url: '/api/v1/login',
    failOnStatusCode: false // Allow 401 if already logged out
  }).then((response) => {
    if (response.status === 200) {
      cy.log('Logout successful via API.');
    } else if (response.status === 401) {
      cy.log('Already logged out (API returned 401).');
    } else {
      cy.log(`Logout API failed with status: ${response.status}`);
    }
    // Clear Cypress cookies just in case session wasn't fully cleared by API
    cy.clearCookies(); 
    cy.clearLocalStorage(); // Also clear local storage if used for auth tokens
  });
});

// Custom command to delete all posts by the currently logged-in user
Cypress.Commands.add('deleteAllMyPosts', () => {
  cy.log('Attempting to delete all posts for current user...');
  let currentUsername = 'unknown'; // For logging

  return cy.request({ // Ensure this command returns the Cypress chain
    method: 'GET',
    url: '/api/v1/profiles/me',
    // failOnStatusCode: false // Default is true, let it fail if /me doesn't load
  }).then(profileResponse => {
    // Check if profileResponse.body and profileResponse.body.user exist
    if (profileResponse && profileResponse.body && profileResponse.body.user) {
      currentUsername = profileResponse.body.user.username;
    } else {
      cy.log('Could not retrieve username from /profiles/me response.');
      // Potentially throw an error or handle as appropriate if user info is critical
    }

    const posts = profileResponse.body.posts;
    if (posts && posts.length > 0) {
      cy.log(`User ${currentUsername} has ${posts.length} posts to delete.`);
      
      // Start a Cypress chain with a no-op command.
      // Each subsequent delete request will be chained to this.
      let deleteChain = cy.noop(); 
      
      posts.forEach(post => {
        deleteChain = deleteChain.request({
          method: 'DELETE',
          url: `/api/v1/posts/${post.id}`,
          // failOnStatusCode: true by default. If a delete fails, the command chain will fail.
        }).then(deleteResponse => {
          // This .then() is part of the chain and will execute sequentially for each post.
          cy.log(`Delete response for post ${post.id} (user: ${currentUsername}): Status ${deleteResponse.status}`);
        });
      });
      
      return deleteChain; // Return the fully constructed chain of delete operations.
    } else {
      cy.log(`No posts found for user ${currentUsername} to delete.`);
      // No need to return cy.wrap(null) explicitly if there's nothing to chain,
      // the .then() will implicitly return.
      // However, to be explicit for the command's return value:
      return cy.wrap(null, { log: false }); // Signify completion with no further actions.
    }
  });
});

// Custom command to ensure a user exists, registers if not.
Cypress.Commands.add('ensureUserExists', ({ username, email, password, inviteCode = null }) => {
  const attemptRegistration = (currentInviteCode) => {
    const registrationBody = {
      username: username,
      email: email,
      password: password
    };
    if (currentInviteCode) {
      registrationBody.invite_code = currentInviteCode;
    }

    return cy.request({
      method: 'POST',
      url: '/api/v1/register',
      body: registrationBody,
      failOnStatusCode: false
    });
  };

  attemptRegistration(inviteCode).then((response) => {
    if (response.status === 201) {
      cy.log(`User ${username} created successfully via ensureUserExists.`);
    } else if (response.status === 409) {
      cy.log(`User ${username} already exists (confirmed by 409).`);
    } else if (response.status === 400 && response.body.message && response.body.message.toLowerCase().includes('invite code is required')) {
      cy.log(`ensureUserExists: Registration for ${username} requires an invite code. Attempting to generate one.`);
      
      // Log in as a user who can generate invite codes (e.g., 'testuser')
      // IMPORTANT: Ensure 'testuser'/'password' can register without an invite or already exists.
      // This could lead to a loop if 'testuser' itself needs an invite code and doesn't exist.
      // For this scenario, we assume 'testuser' is a base user or can be created.
      cy.login('testuser', 'password'); // Hardcoded for now, consider Cypress.env()

      let generatedInviteCode = '';
      cy.request({
        method: 'POST',
        url: '/api/v1/invites', // Endpoint to generate an invite code
      }).then((inviteResponse) => {
        expect(inviteResponse.status).to.eq(201);
        if (inviteResponse.body.code) {
          generatedInviteCode = inviteResponse.body.code;
        } else if (typeof inviteResponse.body === 'string') {
          generatedInviteCode = inviteResponse.body;
        } else {
          generatedInviteCode = inviteResponse.body?.invite?.code || inviteResponse.body?.data?.code;
        }
        if (!generatedInviteCode) {
          throw new Error('ensureUserExists: Could not extract generated invite code.');
        }
        cy.log(`Generated invite code: ${generatedInviteCode}`);
        cy.logout(); // Logout the 'testuser'
      }).then(() => {
        // Retry registration with the generated invite code
        return attemptRegistration(generatedInviteCode);
      }).then((retryResponse) => {
        if (retryResponse.status === 201) {
          cy.log(`User ${username} created successfully with generated invite code.`);
        } else if (retryResponse.status === 409) {
          cy.log(`User ${username} already exists (confirmed by 409 on retry).`);
        } else {
          throw new Error(`ensureUserExists: Failed to register ${username} even with a generated invite code. API responded with ${retryResponse.status}: ${JSON.stringify(retryResponse.body)}`);
        }
      });
    } else if (response.status >= 400) {
      throw new Error(`ensureUserExists: Failed to ensure user ${username}. API responded with ${response.status}: ${JSON.stringify(response.body)}`);
    }
  });
});