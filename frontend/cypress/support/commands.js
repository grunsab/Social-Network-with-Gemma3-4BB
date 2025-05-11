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
    cy.log(`Login session setup: Attempting to login as ${usernameOrEmail}`);
    cy.visit('/login');
    cy.get('#identifier').type(usernameOrEmail);
    cy.get('#password').type(password);

    cy.intercept('POST', '/api/v1/login').as('loginRequest');
    cy.get('button[type="submit"]').contains(/login/i).click();

    cy.wait('@loginRequest', { timeout: 10000 }).then(interception => {
      cy.log('Login API response status:', interception.response.statusCode);
      cy.log('Login API response body:', JSON.stringify(interception.response.body));
      // Expect a successful login status code from the backend (e.g., 200)
      expect(interception.response.statusCode, 'Login API call status code').to.eq(200);
    });

    // Ensure the URL changes from /login and matches an expected post-login pattern.
    // Increased timeout for URL change, as redirection might take a moment.
    cy.url({ timeout: 10000 }).should('not.eq', Cypress.config().baseUrl + '/login', 'URL should change from /login');
    
    // Adjust this regex if your app redirects to a different default page after login (e.g., /dashboard)
    // This regex allows for baseUrl, baseUrl/, or baseUrl/feed
    const expectedPostLoginUrlPattern = new RegExp(`^${Cypress.config().baseUrl}(/feed|/)?$`);
    cy.url({ timeout: 10000 }).should('match', expectedPostLoginUrlPattern, 'URL should match post-login pattern');
    
    cy.log('Login session setup: Successfully logged in and redirected.');

  }, {
    cacheAcrossSpecs: true, // Cache session across multiple spec files
    validate: () => {
      cy.log('Validating session: Checking for session cookie.');
      cy.getCookie('session').should('exist');
      // Optional: A quick API call to a protected endpoint to further validate the session
      // cy.request({url: '/api/v1/profiles/me', failOnStatusCode: false}).its('status').should('eq', 200);
      cy.log('Validating session: Session cookie exists.');
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
  // Assuming cy.login() has been called and Cypress.env('token') is set,
  // or that cy.request automatically uses the current session's authentication.
  // The initial request to get posts:
  return cy.request({
    method: 'GET',
    url: '/api/v1/profiles/me', // CORRECTED: Use the verified endpoint for current user's profile and posts
    failOnStatusCode: false // Allow handling of cases where fetching posts might fail (e.g., no posts)
  }).then(response => {
    if (response.status !== 200) {
      cy.log(`deleteAllMyPosts: Warning - Failed to fetch profile for user. Status: ${response.status}. Body: ${JSON.stringify(response.body)}`);
      return cy.wrap(null, { log: false }); // Proceed, as there might be no posts or an issue fetching.
    }

    // The endpoint /api/v1/profiles/me returns a structure like:
    // { user: {...}, posts: [...], interests: [...], ... }
    const posts = response.body.posts; 

    if (posts && posts.length > 0) {
      cy.log(`deleteAllMyPosts: Found ${posts.length} posts to delete.`);
      let deleteChain = cy.noop(); // Start with a Cypress command that does nothing.
                                  // .then() can be called on this to start a chain.
      posts.forEach(post => {
        deleteChain = deleteChain.then(() => { // Chain the next delete operation
          return cy.request({
            method: 'DELETE',
            url: `/api/v1/posts/${post.id}`,
            failOnStatusCode: false // Handle potential errors in the next .then()
          }).then(deleteResponse => {
            if (deleteResponse.status === 200 || deleteResponse.status === 204) {
              cy.log(`deleteAllMyPosts: Successfully deleted post ${post.id}`);
            } else {
              cy.log(`deleteAllMyPosts: Warning - Failed to delete post ${post.id}. Status: ${deleteResponse.status}. Body: ${JSON.stringify(deleteResponse.body)}`);
            }
          });
        });
      });
      return deleteChain; // Return the promise chain
    } else {
      cy.log('deleteAllMyPosts: No posts found to delete for the current user.');
      return cy.wrap(null, { log: false }); // Return a resolved promise
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
        if (inviteResponse.status === 201) {
          if (inviteResponse.body.code) {
            generatedInviteCode = inviteResponse.body.code;
          } else if (typeof inviteResponse.body === 'string') {
            generatedInviteCode = inviteResponse.body;
          } else {
            generatedInviteCode = inviteResponse.body?.invite?.code || inviteResponse.body?.data?.code;
          }
          if (!generatedInviteCode) {
            // This case should ideally not happen if status is 201 and backend guarantees a code
            throw new Error('ensureUserExists: Invite generation API responded with 201 but no code was found.');
          }
        } else if (inviteResponse.status === 400 && inviteResponse.body.message && inviteResponse.body.message.toLowerCase().includes('no invites left to generate')) {
          throw new Error(`ensureUserExists: 'testuser' has no invites left to generate for user '${username}'. Backend message: ${inviteResponse.body.message}`);
        } else {
          // Handle other unexpected errors during invite generation
          throw new Error(`ensureUserExists: Failed to generate invite code using 'testuser'. API responded with ${inviteResponse.status}: ${JSON.stringify(inviteResponse.body)}`);
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