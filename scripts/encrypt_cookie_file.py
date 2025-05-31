from cryptography.fernet import Fernet
import os

def encrypt_file(key_string, input_filename="cookies_yt.txt", output_filename="cookies_yt.txt.encrypted"):
    """Encrypts a file using a Fernet key."""
    if not key_string:
        print("Error: Encryption key is missing.")
        return

    key = key_string.encode() # Key needs to be bytes
    fernet_obj = Fernet(key)

    try:
        with open(input_filename, "rb") as file:
            original_data = file.read()
    except FileNotFoundError:
        print(f"Error: Input file '{input_filename}' not found. Make sure it exists.")
        return
    except Exception as e:
        print(f"Error reading file '{input_filename}': {e}")
        return

    encrypted_data = fernet_obj.encrypt(original_data)

    try:
        with open(output_filename, "wb") as encrypted_file:
            encrypted_file.write(encrypted_data)
        print(f"File '{input_filename}' encrypted successfully to '{output_filename}'.")
        print(f"Make sure to commit '{output_filename}' and add '{input_filename}' to .gitignore.")
    except Exception as e:
        print(f"Error writing encrypted file '{output_filename}': {e}")

if __name__ == "__main__":
    # Load the key from an environment variable if available, otherwise prompt.
    # For local encryption, prompting or reading from a (gitignored) key file is common.
    encryption_key = os.environ.get("COOKIE_ENCRYPTION_KEY_LOCAL") # You can set this locally for convenience
    if not encryption_key:
        encryption_key = input(f"Enter the Fernet encryption key (the one you generated and saved): ")

    if encryption_key:
        # Assuming your plain cookies file is named cookies_yt.txt in the same directory
        encrypt_file(encryption_key, "cookies_yt.txt", "cookies_yt.txt.encrypted")
    else:
        print("No encryption key provided. Exiting.")

