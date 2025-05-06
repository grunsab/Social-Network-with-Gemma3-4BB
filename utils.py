import re
from models import User, Ampersound

def format_text_with_ampersounds(text_content, author_username):
    if not text_content or not author_username:
        return text_content

    # Regex to find &soundname patterns. Ensures name starts with a letter or number.
    # Allows alphanumeric and underscores in the name.
    ampersand_pattern = r"&([a-zA-Z0-9_][a-zA-Z0-9_-]*)"

    def replace_tag(match):
        sound_name = match.group(1)
        # Query for the ampersound belonging to the author_username
        ampersound_entry = Ampersound.query.join(User).filter(
            User.username == author_username,
            Ampersound.name == sound_name
        ).first()

        if ampersound_entry:
            # Use "ampersound-tag" class to match frontend JS and CSS
            return f'<span class="ampersound-tag" data-username="{author_username}" data-soundname="{sound_name}">&{sound_name}</span>'
        else:
            return match.group(0) # Return the original string if no ampersound found (e.g., "&sometag")

    return re.sub(ampersand_pattern, replace_tag, text_content) 