import re
from models import User, Ampersound
from sqlalchemy.orm import joinedload

# Helper function to generate S3 file URL
# Moved from app.py and made more generic
def generate_s3_file_url(app_config, s3_key):
    if not s3_key:
        return None

    s3_client = app_config.get('S3_CLIENT') # S3_CLIENT should be in app_config
    s3_bucket = app_config.get('S3_BUCKET')
    domain_name_images = app_config.get('DOMAIN_NAME_IMAGES')
    s3_endpoint_url = app_config.get('S3_ENDPOINT_URL')
    s3_region = app_config.get('S3_REGION', 'us-east-1') # Default to us-east-1

    file_url = None
    if s3_client and s3_bucket: # Check if S3 client and bucket are configured
        try:
            if domain_name_images:
                file_url = f"{domain_name_images}/{s3_key}"
            elif s3_endpoint_url:
                # For R2 or MinIO like services, the URL is typically endpoint/bucket/key
                file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
            else: # Assuming AWS S3 default URL structure
                if s3_region == 'auto':
                    # 'auto' is specific to Cloudflare R2's SDK configuration,
                    # not for URL construction. S3_ENDPOINT_URL should be used for R2.
                    # If this is AWS S3 and region is 'auto', it's a misconfiguration.
                    print(f"WARN: Cannot construct S3 URL for {s3_key} with 'auto' region and no S3_ENDPOINT_URL. Ensure S3_ENDPOINT_URL is set for non-AWS S3 services or S3_REGION is explicit for AWS S3.")
                    return None
                file_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"
        except Exception as e:
            print(f"ERROR: Error generating S3 URL for key {s3_key}: {e}")
            return None
    else:
        # This case implies S3 is not configured (e.g. S3_CLIENT is None or S3_BUCKET is None)
        print(f"WARN: S3 client or bucket not configured in app_config. Cannot generate URL for {s3_key}.")
        return None
    return file_url

def format_text_with_ampersounds(text_content, author_username):
    # author_username is the author of the post/comment containing the text,
    # used potentially for context later, but not directly for resolving tags now.
    if not text_content:
        return text_content

    # Regex to find patterns: 
    # 1. &username.soundname (Groups 1 and 2)
    # 2. &soundname (Group 3)
    # Ensures names start with alphanumeric/underscore, allows hyphens within.
    ampersand_pattern = r"&([a-zA-Z0-9_][a-zA-Z0-9_-]*)\.([a-zA-Z0-9_][a-zA-Z0-9_-]+)|&([a-zA-Z0-9_][a-zA-Z0-9_-]+)"

    def replace_tag(match):
        target_username = match.group(1) # Username if &user.sound format
        sound_name_for_user = match.group(2) # Soundname if &user.sound format
        single_sound_name = match.group(3) # Soundname if &sound format

        ampersound_entry = None
        owner_username = None
        resolved_sound_name = None

        if target_username and sound_name_for_user:
            # Case 1: &username.soundname specified
            ampersound_entry = Ampersound.query.join(User).filter(
                User.username == target_username,
                Ampersound.name == sound_name_for_user
            ).first()
            if ampersound_entry:
                owner_username = target_username # Username specified is the owner
                resolved_sound_name = sound_name_for_user
        
        elif single_sound_name:
            # Case 2: &soundname specified, check for uniqueness
            query = Ampersound.query.filter(Ampersound.name == single_sound_name)
            count = query.count()

            if count == 1:
                # Globally unique sound name found
                ampersound_entry = query.options(joinedload(Ampersound.user)).first() # Eager load owner
                if ampersound_entry and ampersound_entry.user:
                     owner_username = ampersound_entry.user.username
                     resolved_sound_name = single_sound_name
            # else: (count is 0 or > 1) - Ambiguous or not found, leave as text

        # If we found a valid, resolvable ampersound entry
        if ampersound_entry and owner_username and resolved_sound_name:
            return f'<span class="ampersound-tag" data-username="{owner_username}" data-soundname="{resolved_sound_name}">{match.group(0)}</span>' # Display original tag text
        else:
            # Not found, ambiguous, or invalid format - return the original matched text
            return match.group(0) 

    return re.sub(ampersand_pattern, replace_tag, text_content)