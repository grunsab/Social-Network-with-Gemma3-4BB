# Profile Picture Upload Feature for the Social Network

This PR implements a feature for users to upload profile pictures on the My Profile page.

## Frontend Changes
- Added file input and upload button in the profile header
- Added state management for file upload process
- Styled the profile picture section with upload button
- Added error handling for upload issues

## Backend Changes
- Added a new endpoint `/api/v1/profiles/upload_picture` to handle file uploads
- Integrated with S3 storage for profile pictures
- Added file type validation to ensure only images are uploaded
- Updated the user model to store profile picture URL

## Testing
- Manually tested uploading various image formats
- Verified error handling for invalid file types
- Verified proper display of profile picture across the app

## Notes
- The profile picture is stored in S3 and the URL is saved in the user model
- Image dimensions are controlled via CSS (100px × 100px)
- Default fallback image is used when profile picture is not set
