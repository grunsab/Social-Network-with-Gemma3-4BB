#!/bin/bash
# Script to run the Flask app with the correct configuration
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Use development config
export FLASK_CONFIG=development

# Run the Flask app
python app.py
