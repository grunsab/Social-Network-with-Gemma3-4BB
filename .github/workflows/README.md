# GitHub Actions CI Workflows

This directory contains simplified GitHub Actions workflows for continuous integration.

## Workflows

### 1. `ci.yml` - Main CI Pipeline
- **Triggers**: Push to main, Pull requests, Manual dispatch
- **Jobs**:
  - `backend-tests`: Runs Python/pytest tests
  - `cypress-tests`: Runs Cypress E2E tests (parallel with backend tests)
- **Features**:
  - Single browser (Chrome) by default for speed
  - Optional multi-browser testing via workflow dispatch
  - Uploads screenshots on failure, videos always
  - Clear server startup with timeout handling

### 2. `nightly.yml` - Comprehensive Nightly Tests
- **Triggers**: Daily at 2 AM UTC, Manual dispatch
- **Purpose**: Runs full test suite across all browsers
- **Uses**: Calls main CI workflow with multi-browser option

### 3. `pr-quick-check.yml` - Fast PR Validation
- **Triggers**: PR opened/updated (only when code files change)
- **Purpose**: Quick smoke tests for faster PR feedback
- **Checks**:
  - Python linting (basic errors only)
  - Frontend linting
  - Quick backend unit tests
  - Frontend build verification

## Usage

### Running CI Manually
1. Go to Actions tab in GitHub
2. Select "CI Tests" workflow
3. Click "Run workflow"
4. Choose whether to run on multiple browsers

### Local Testing
```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm run cypress:open  # Interactive
npm run cypress:run   # Headless
```

## Configuration

### Environment Variables
The CI uses these default test values:
- `DATABASE_URL`: sqlite:///test.db
- `SECRET_KEY`: test-secret-key
- `FLASK_ENV`: test

### Cypress Configuration
- Base URL: http://localhost:5173 (frontend)
- API URL: http://localhost:5001 (backend)
- Retries: 2 in CI, 0 in interactive mode
- Videos: Always recorded
- Screenshots: Only on failure

## Improvements from Previous Setup

1. **Simplified Structure**: Single main workflow instead of two overlapping ones
2. **Parallel Execution**: Backend and Cypress tests run in parallel
3. **Flexible Browser Testing**: Single browser by default, multi-browser optional
4. **Better Error Handling**: Clearer server startup with proper timeouts
5. **Quick PR Checks**: Separate lightweight workflow for fast feedback
6. **Scheduled Tests**: Dedicated nightly workflow for comprehensive testing

## Troubleshooting

### Server Startup Issues
- Check uploaded logs in GitHub Actions artifacts
- Backend logs: `backend.log`
- Frontend logs: `frontend.log`

### Test Failures
- Screenshots and videos are uploaded as artifacts
- Named by browser for easy identification
- Retained for 7 days

### Local vs CI Differences
- CI uses SQLite test database
- Ensure all required environment variables are set
- Check for hardcoded localhost URLs in tests