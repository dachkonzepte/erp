"""Verschlüsselung für sensible Zugangsdaten (seit 1.0.74, E-Mail-Versand).

Baut auf dem bereits bestehenden secret_key() aus app/auth.py auf (dort für
Session-Signaturen genutzt) -- bewusst kein zweiter, separat zu verwaltender
Schlüssel. secret_key() liest ERP_SECRET_KEY aus der Umgebungsvariable, mit
lokalem Datei-Fallback für die Entwicklung -- damit bereits jetzt bereit für
einen späteren Cloud-Betrieb, bei dem der Schlüssel über die
Umgebungsvariable der Hosting-Plattform gesetzt würde, ohne Codeänderung.

Nur für Zugangsdaten gedacht, die das System selbst zum Versenden braucht
(aktuell: SMTP-Passwort) -- NICHT für Benutzerpasswörter, die weiterhin
ausschließlich als Einweg-Hash abgelegt werden (siehe hash_password() in
app/auth.py). Der Unterschied ist bewusst: ein SMTP-Passwort muss im
Klartext wiederherstellbar sein, um sich beim Mailserver anzumelden, ein
Benutzerpasswort dagegen nie.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .auth import secret_key


def _fernet() -> Fernet:
    derived = hashlib.sha256(secret_key()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plaintext: str) -> str:
    """Verschlüsselt einen Klartext-Wert für die Ablage in der Datenbank."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Entschlüsselt einen zuvor mit encrypt_secret() gespeicherten Wert.

    Löst ValueError aus (statt der internen InvalidToken), falls der Wert
    beschädigt ist oder mit einem anderen Schlüssel verschlüsselt wurde --
    z.B. nach einem versehentlichen Wechsel von ERP_SECRET_KEY."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Gespeicherter Wert kann nicht entschlüsselt werden (falscher oder geänderter Schlüssel?).") from e
