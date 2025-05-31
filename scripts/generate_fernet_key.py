from cryptography.fernet import Fernet

key = Fernet.generate_key()
print("Generated Fernet Key. KEEP THIS SECRET! Store it as an environment variable on your server.")
print("Your key is:", key.decode())

