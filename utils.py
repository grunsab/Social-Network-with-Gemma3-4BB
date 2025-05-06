import re
from models import User, Ampersound
from sqlalchemy.orm import joinedload

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