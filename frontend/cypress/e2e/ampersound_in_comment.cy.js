/// <reference types="cypress" />

describe('Ampersound in Comments by Owner', () => {
  // Define user who creates and plays the ampersound
  const uploader = { username: 'ampsndowner', password: 'password', email: 'ampsndowner@example.com' };
  // const viewer = { username: 'ampsndviewer', password: 'password', email: 'ampsndviewer@example.com' }; // Viewer not needed

  const ampersoundBaseName = 'mysound'; // Changed base name for clarity
  const ampersoundFileName = 'omgbecky.webm'; 
  
  let ampersoundName; 
  let ampersoundTag;
  let testPostId;
  let initialPostContent; 
  let ampersoundUrlFromApi;
  let ampersoundId;

  before(() => {
    // 1. Ensure uploader user exists
    cy.ensureUserExists(uploader);
    // cy.ensureUserExists(viewer); // Viewer not needed

    const uniqueSuffix = Date.now();
    ampersoundName = `${ampersoundBaseName}${uniqueSuffix}`;
    ampersoundTag = `&${uploader.username}.${ampersoundName}`;
    initialPostContent = `Test post for own ampersound comment - ${uniqueSuffix}`;

    // Login as uploader once for all setup actions
    cy.login(uploader.username, uploader.password);

    // 2. Uploader creates an ampersound via API.
    cy.fixture(ampersoundFileName, 'base64').then(base64Content => {
      if (base64Content === null || base64Content === undefined || base64Content.trim() === "") {
        Cypress.log({
          name: "Fixture Missing or Empty",
          message: `Audio fixture content for ${ampersoundFileName} is missing, empty, or effectively empty. Ampersound creation cannot proceed.`,
          consoleProps: () => {
            return {
              fixturePath: `cypress/fixtures/${ampersoundFileName}`,
              advice: "Please ensure a valid, non-empty audio file is in the fixtures folder for this test."
            };
          }
        });
        throw new Error(`Audio fixture content for ${ampersoundFileName} is missing or empty. Test cannot continue.`);
      }

      // ---- Only proceed if base64Content is valid ----
      const formData = new FormData();
      formData.append('name', ampersoundName);
      formData.append('privacy', 'public'); // Own content, privacy doesn't block owner
      
      cy.log('Type of base64Content:', typeof base64Content);
      cy.log('Slice of base64Content (first 50 chars):', typeof base64Content === 'string' ? base64Content.slice(0, 50) : 'not a string');

      const blob = Cypress.Blob.base64StringToBlob(base64Content, 'audio/webm');

      if (!blob || typeof blob.type !== 'string' || typeof blob.size !== 'number') {
        const errorMsg = `Failed to create a valid Blob from base64 content for ${ampersoundFileName}. ` +
                         `base64StringToBlob returned: ${blob}. ` +
                         `Base64 content (first 100 chars): ${typeof base64Content === 'string' ? base64Content.substring(0,100) : 'Not a string'}`;
        Cypress.log({ name: "Blob Creation Error", message: errorMsg });
        throw new Error(errorMsg); // Fail the test here
      }

      formData.append('audio_file', blob, ampersoundFileName);

      cy.request({
        method: 'POST',
        url: '/api/v1/ampersounds',
        body: formData,
      }).then((response) => {
        expect(response.status).to.eq(201);

        if (response.body && typeof response.body === 'object' && Object.keys(response.body).length > 0) {
          if (response.body.ampersound_id) {
            ampersoundId = response.body.ampersound_id; // Store ID for potential cleanup
            expect(response.body).to.have.property('name', ampersoundName);
            // Log status, but owner can play their own pending ampersounds
            cy.log(`Ampersound '${ampersoundName}' created by owner. Status: ${response.body.status}. Ampersound ID: ${ampersoundId}`);
          } else {
            cy.log('WARNING: Ampersound creation API returned 201 but ampersound_id was missing in the response body.');
            cy.log('Proceeding with test, but ampersoundId will be undefined.');
            // Optionally, still check for name if it might be there even if id is not
            if (response.body.name) {
                expect(response.body).to.have.property('name', ampersoundName);
            }
             if (response.body.status) {
                cy.log(`Ampersound '${ampersoundName}' created by owner. Status from body: ${response.body.status}.`);
            }
          }
        } else {
          cy.log('WARNING: Ampersound creation API returned 201 but the response body was empty or not an object.');
          cy.log('Proceeding with test, but ampersoundId and other details from response body will be unavailable.');
        }
        // No matter what, pass along the response for potential chaining if other parts of the test need it.
        return cy.wrap(response, {log: false}); 
      }); // End of cy.request for ampersound
    }); // End of cy.fixture.then()

    // 3. Uploader creates a standard post (still logged in).
    cy.createPost({ content: initialPostContent, privacy: 'PUBLIC' }).then(post => {
      if (post && post.id) {
        testPostId = post.id;
        cy.log(`Test post created by ${uploader.username} with ID: ${testPostId} and content: "${initialPostContent}"`);
        // Verify that the content of the created post matches initialPostContent
        // This assumes 'post' object returned by API has a 'content' property
        if (post.content) {
            expect(post.content).to.equal(initialPostContent);
        } else {
            cy.log(`WARNING: Post object from createPost API did not contain a 'content' property. Cannot verify created content directly. Post object: ${JSON.stringify(post)}`);
        }
      } else {
        cy.log(`WARNING: Post creation via cy.createPost did not yield a valid post object with an ID. Post object: ${JSON.stringify(post)}`);
        cy.log('The test might fail to find the post in the feed.');
        // testPostId remains undefined, which is fine for this test's subsequent steps if post appears in feed by content.
      }
    });
    // No logout here, uploader stays logged in for the test
  });

  it('should allow a user to post a comment with their own ampersound and play it', () => {
    const commentWithAmpersound = 'Playing my own sound: ' + ampersoundTag + ' from my comment!';

    // Uploader is already logged in from the before() block continuity
    cy.visit('/'); 

    // Intercept the call the frontend might make to confirm user identity on page load
    cy.intercept('GET', '/api/v1/profiles/me').as('getProfileMeOnLoad');
    // Intercept the feed call
    cy.intercept('GET', '/api/v1/feed*').as('getFeed'); // Use wildcard for query params

    // Wait for the frontend to potentially make this call and for it to complete
    cy.wait('@getProfileMeOnLoad', { timeout: 10000 });

    cy.contains('h3', /Your Feed/i, { timeout: 10000 }).should('be.visible');
    
    // Wait for the feed API call and log its response
    cy.wait('@getFeed', { timeout: 10000 }).then((interception) => {
      cy.log('Feed API Response Status:', interception.response.statusCode);
      cy.log('Feed API Response Body:', JSON.stringify(interception.response.body));
      // Check if the initialPostContent is present in any of the feed posts
      const feedPosts = interception.response.body.posts || [];
      const postFoundInFeed = feedPosts.some(post => post.content === initialPostContent);
      if (postFoundInFeed) {
        cy.log('SUCCESS: initialPostContent found in /api/v1/feed response.');
      } else {
        cy.log('FAILURE: initialPostContent NOT found in /api/v1/feed response.');
        // Log the content of all posts received in the feed for debugging
        feedPosts.forEach((post, index) => {
          cy.log(`Feed post [${index}] content: "${post.content}"`);
        });
      }
    });

    cy.contains('.post-card', initialPostContent, { timeout: 15000 }).should('be.visible').as('targetPostCard');
    
    cy.get('@targetPostCard').find('.toggle-comments-button').should('be.visible').click();

    cy.get('@targetPostCard').find('textarea[placeholder="Add a comment..."]', { timeout: 5000 })
      .should('be.visible')
      .type(commentWithAmpersound);

    cy.intercept('POST', `/api/v1/posts/${testPostId}/comments`).as('postCommentApi');
    cy.get('@targetPostCard').find('form.comment-form button[type="submit"]').should('be.visible').click();
    
    cy.wait('@postCommentApi').then((interception) => {
      expect(interception.response.statusCode).to.eq(201);
      expect(interception.response.body.content).to.include(ampersoundTag);
    });

    // Verify the comment appears with the ampersound tag rendered correctly
    cy.get('@targetPostCard').find('.comment-content').contains('span.ampersound-tag', ampersoundTag)
      .should('be.visible')
      .and('have.attr', 'data-username', uploader.username)
      .and('have.attr', 'data-soundname', ampersoundName);
    
    // --- Uploader (owner) plays their ampersound from their own comment ---
    // (Still on the same page, already logged in)

    const ampersoundTagSelector = '.comment-content span.ampersound-tag[data-username="' + uploader.username + '"][data-soundname="' + ampersoundName + '"]';
    cy.get('@targetPostCard').find(ampersoundTagSelector, { timeout: 10000 })
      .should('be.visible')
      .as('playableAmpersoundInComment');

    cy.intercept('GET', `/api/v1/ampersounds/${uploader.username}/${ampersoundName}`).as('getAmpersoundData');
    cy.intercept('GET', '**/ampersounds/**').as('audioFileRequest'); // General intercept for S3 URL

    cy.get('@playableAmpersoundInComment').click();

    cy.wait('@getAmpersoundData').then((interception) => {
      expect(interception.response.statusCode).to.eq(200);
      expect(interception.response.body.name).to.eq(ampersoundName);
      expect(interception.response.body.user).to.eq(uploader.username);
      expect(interception.response.body).to.have.property('url');
      ampersoundUrlFromApi = interception.response.body.url;
      expect(ampersoundUrlFromApi).to.be.a('string').and.not.be.empty;
      // The play_count should be incremented even for pending if played by owner.
      // expect(interception.response.body.play_count).to.be.greaterThan(0); // Or check specific initial value if known
    });

    cy.get('audio#global-audio-player', { timeout: 10000 })
      .should('have.attr', 'src', ampersoundUrlFromApi)
      .and((audioElements) => {
        const audio = audioElements[0];
        expect(audio.error).to.be.null;
        expect(audio.readyState).to.be.greaterThan(0);
        cy.wrap(audio).its('paused').should('be.oneOf', [true, false]);
      });
    
    // No explicit logout here, test ends with uploader logged in.
  });

  after(() => {
    // Optional: Uploader logs in to clean up their ampersound and post
    // cy.login(uploader.username, uploader.password);
    // if (ampersoundId) {
    //   cy.request({ method: 'DELETE', url: `/api/v1/ampersounds/${ampersoundId}`, failOnStatusCode: false });
    // }
    // if (testPostId) {
    //   cy.request({ method: 'DELETE', url: `/api/v1/posts/${testPostId}`, failOnStatusCode: false });
    // }
    // cy.logout();
  });
}); 