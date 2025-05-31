# Cypress E2E Tests

This directory contains end-to-end tests for the Social Network application using Cypress.

## Test Suites

### ✅ Active Tests

1. **auth.cy.js** - Authentication flow tests
   - User login
   - User registration
   - Error handling
   - Invite code validation

2. **category.cy.js** - Category view functionality
   - Display posts by category
   - Category privacy controls
   - Invalid category handling

3. **feed.cy.js** - Main feed functionality
   - Display public posts
   - Friend post visibility
   - Feed pagination with infinite scroll

4. **invites.cy.js** - Invite code management
   - Display invite state
   - Generate new codes
   - Handle invite limits

5. **posts.cy.js** - Post management
   - Create posts
   - Delete posts
   - Add/delete comments
   - Image uploads

### ⏭️ Skipped Tests

Some tests are currently skipped due to:
- **Privacy settings test**: Backend issue with privacy field
- **Large file upload test**: Complex browser file API mocking
- **Profile tests**: Missing data-cy attributes in Profile component

## Running Tests

### Local Development

```bash
# Run all tests interactively
npm run cypress:open

# Run all tests headlessly
npm run cypress:run

# Run specific test file
npx cypress run --spec "cypress/e2e/auth.cy.js"
```

### CI/CD

Tests run automatically on:
- Push to main branch
- Pull requests
- Daily schedule (2 AM UTC)
- Manual workflow dispatch

## Test Structure

### Setup

- Tests use custom commands defined in `cypress/support/commands.js`
- User data is created/cleaned up within test suites
- Backend and frontend servers must be running

### Custom Commands

- `cy.login(username, password)` - Login with session caching
- `cy.ensureUserExists(userData)` - Create user if doesn't exist
- `cy.createPost(postData)` - Create a post via API
- `cy.sendFriendRequestTo(username)` - Send friend request
- `cy.acceptFriendRequest(requestId)` - Accept friend request
- `cy.deleteAllMyPosts()` - Clean up user's posts

## Troubleshooting

### Common Issues

1. **Tests timing out**: Increase timeout in cypress.config.js
2. **Elements not found**: Check if selectors have changed
3. **API errors**: Ensure backend is running and healthy
4. **Session issues**: Clear Cypress cache

### Debug Mode

```bash
# Run with debug logs
DEBUG=cypress:* npm run cypress:run

# Increase timeout for slow CI
CYPRESS_defaultCommandTimeout=10000 npm run cypress:run
```

## Future Improvements

1. Add data-cy attributes to all components for reliable selection
2. Implement visual regression testing
3. Add performance benchmarks
4. Create more comprehensive cleanup strategies
5. Add accessibility tests