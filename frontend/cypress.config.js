import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5173', // Set the base URL for cy.visit()
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    // Viewport settings
    viewportWidth: 1280,
    viewportHeight: 720,
    // Recording settings
    video: true,
    screenshotOnRunFailure: true,
    // Timeouts
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,
    // Retry configuration for CI
    retries: {
      runMode: 2, // Retry failed tests twice in CI
      openMode: 0, // No retries in interactive mode
    },
    // Test isolation
    testIsolation: true,
  },
});
