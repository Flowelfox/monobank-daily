from unittest.mock import patch

from src.lib.crypto import decrypt_token, encrypt_token


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        secret_file = tmp_path / ".secret_key"

        with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
            user_id = 123456789
            original_token = "uTestToken123456789012345678901234567890"

            encrypted = encrypt_token(original_token, user_id)
            decrypted = decrypt_token(encrypted, user_id)

            assert decrypted == original_token
            assert encrypted != original_token

    def test_different_users_different_encryption(self, tmp_path):
        secret_file = tmp_path / ".secret_key"

        with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
            token = "uTestToken123456789012345678901234567890"

            encrypted_user1 = encrypt_token(token, 111111111)
            encrypted_user2 = encrypt_token(token, 222222222)

            assert encrypted_user1 != encrypted_user2

    def test_wrong_user_cannot_decrypt(self, tmp_path):
        secret_file = tmp_path / ".secret_key"

        with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
            user_id = 123456789
            wrong_user_id = 987654321
            original_token = "uTestToken123456789012345678901234567890"

            encrypted = encrypt_token(original_token, user_id)
            decrypted = decrypt_token(encrypted, wrong_user_id)

            assert decrypted is None

    def test_invalid_encrypted_data_returns_none(self, tmp_path):
        secret_file = tmp_path / ".secret_key"

        with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
            result = decrypt_token("invalid_encrypted_data", 123456789)
            assert result is None

    def test_secret_key_persists(self, tmp_path):
        secret_file = tmp_path / ".secret_key"

        with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
            token = "uTestToken123456789012345678901234567890"
            user_id = 123456789

            encrypted1 = encrypt_token(token, user_id)

            encrypted2 = encrypt_token(token, user_id)

            decrypted1 = decrypt_token(encrypted1, user_id)
            decrypted2 = decrypt_token(encrypted2, user_id)

            assert decrypted1 == token
            assert decrypted2 == token
