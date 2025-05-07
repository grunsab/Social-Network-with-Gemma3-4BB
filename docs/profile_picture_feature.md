# Profile Picture Upload Feature

This document describes the implementation of the profile picture upload feature in the social network application.

## Overview

Users can now upload and change their profile pictures from their profile page. The feature includes:

- A file selection dialog to choose an image file
- Validation to ensure the file is an image and within size limits (5MB)
- Direct upload to S3/cloud storage
- Display of the profile picture throughout the application

## Implementation Details

### Backend

1. **Upload Endpoint**: `/api/v1/profiles/upload_picture`
   - Handles multipart form data with the image file
   - Validates the file is an image
   - Uploads to configured S3/cloud storage
   - Updates the user's profile_picture field with the URL

2. **Profile Model**:
   - The User model has a `profile_picture` field to store the URL
   - Profile picture URLs are propagated through user references

3. **API Integration**:
   - The MyProfileResource also accepts profile_picture URL updates via PATCH

### Frontend

1. **Upload Component**:
   - Implemented in the Profile component
   - Hidden file input triggered by a button click
   - Shows loading state during upload
   - Displays error messages if upload fails

2. **Display**:
   - Profile pictures appear in the profile header
   - Default fallback image when no picture is available
   - Profile pictures also display in posts, comments, friend lists, etc.

## Usage

1. Navigate to your profile page
2. Click on the "Change Photo" or "Add Photo" button below your profile picture
3. Select an image file (JPEG, PNG, etc.) to upload
4. The image will be uploaded and displayed immediately upon successful upload

## Future Improvements

- Add image cropping before upload
- Allow deletion/reversion to default profile picture
- Implement image optimization to reduce size before upload
- Add image moderation to ensure appropriate content
