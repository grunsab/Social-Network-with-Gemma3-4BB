import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5001', // Set the base URL for cy.visit()
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});
