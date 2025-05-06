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
    cy.url().should('eq', Cypress.config().baseUrl + '/');
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
  cy.request({
    method: 'GET',
    url: '/api/v1/profiles/me',
    // failOnStatusCode: false // Let it fail if /me doesn't load, so we know earlier
  }).then(response => {
    // No need to check response.status === 200 here, as default behavior is to fail on >=400
    if (response.body.posts && response.body.posts.length > 0) {
      const posts = response.body.posts;
      cy.log(`Found ${posts.length} posts to delete for ${response.body.user.username}.`);
      // Use Cypress.Promise.all to wait for all delete requests to complete
      const deletePromises = posts.map(post => {
        return cy.request({
          method: 'DELETE',
          url: `/api/v1/posts/${post.id}`,
          // failOnStatusCode: true // Default, let it fail if a delete fails
        }).then(deleteResponse => {
          cy.log(`Deleted post ${post.id} successfully.`);
        });
      });
      // Ensure all deletions are processed before this command is considered done
      return Cypress.Promise.all(deletePromises);
    } else {
      cy.log(`No posts found for ${response.body.user.username} to delete.`);
    }
  });
});

// Custom command to ensure a user exists, registers if not.
Cypress.Commands.add('ensureUserExists', ({ username, email, password }) => {
  cy.request({
    method: 'POST',
    url: '/api/v1/register',
    body: {
      username: username,
      email: email,
      password: password
    },
    failOnStatusCode: false 
  }).then((response) => {
    if (response.status === 201) {
      cy.log(`User ${username} created successfully via ensureUserExists.`);
    } else if (response.status === 409) {
      cy.log(`User ${username} already exists (confirmed by 409).`);
    } else if (response.status === 400 && response.body.message && response.body.message.includes('Invalid or used invite code')){
      cy.log(`ensureUserExists: Registration for ${username} blocked by invite code requirement. User might not exist.`);
      // This is a specific case we might allow to pass, assuming invite codes aren't mandatory for base users.
      // Or, we could throw an error here if these users SHOULD be creatable without codes.
      // throw new Error(`ensureUserExists: Registration for ${username} failed due to mandatory invite code.`);
    } else if (response.status >= 400) {
      // Any other error from registration means the user likely wasn't ensured.
      // Throw an error to make the test failure point to ensureUserExists directly.
      throw new Error(`ensureUserExists: Failed to ensure user ${username}. API responded with ${response.status}: ${JSON.stringify(response.body)}`);
    }
  });
});