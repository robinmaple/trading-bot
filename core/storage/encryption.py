# core/storage/encryption.py (should exist if you implemented earlier)
from cryptography.fernet import Fernet

class CredentialEncryptor:
    def __init__(self, db):
        self.db = db
        self._load_key()

    def _load_key(self):
        """Load or create encryption key"""
        result = self.db.execute(
            "SELECT key_value FROM encryption_keys WHERE key_name='brokerage_creds'"
        ).fetchone()
        
        if not result:
            # First run - generate and store key
            new_key = Fernet.generate_key().decode()
            self.db.execute(
                "INSERT INTO encryption_keys (key_name, key_value) VALUES (?, ?)",
                ('brokerage_creds', new_key)
            )
            self.key = new_key
        else:
            self.key = result[0]
        
        self.cipher = Fernet(self.key.encode())