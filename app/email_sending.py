"""Allgemeiner E-Mail-Versand (seit 1.0.74, um Microsoft 365/OAuth 2.0 seit
1.0.79 erweitert).

Bewusst eigenständig und ohne jeden Bezug zu einem bestimmten
Geschäftsobjekt -- soll künftig für alle Vorgänge (Angebot/Auftrag/
Rechnung/Mahnung) dieselbe, einmal hinterlegte Konfiguration verwenden. Die
konkrete Zusammenstellung von Betreff/Text/Anhang bleibt Aufgabe des
jeweiligen Fachmoduls (aktuell app/reminders.py) -- hier lebt nur das
"Wie", nicht das "Was" des Versands.

Zwei grundsätzlich verschiedene Versandwege, wählbar über
SmtpSettings.send_method (Klärung: "zusätzlich als wählbare Alternative"):

- 'smtp': klassisches SMTP mit Benutzername/Passwort. Nutzt bewusst nur die
  Python-Standardbibliothek (smtplib/email), keine zusätzliche
  Versand-Bibliothek -- passend zum bisherigen Stil des Projekts (z.B.
  Passwort-Hashing über hashlib statt einer externen Bibliothek).

- 'graph_oauth2': Microsoft Graph API mit OAuth 2.0
  Client-Credentials-Flow (App-only, Application-Berechtigung Mail.Send).
  Für Microsoft 365/Exchange Online, wo SMTP AUTH zunehmend deaktiviert
  ist -- kein SMTP-Protokoll mehr, reiner REST-Aufruf über HTTPS. Bewusst
  über die Standardbibliothek (urllib) umgesetzt statt einer zusätzlichen
  HTTP-Bibliothek wie requests/httpx, da nur zwei einfache POST-Aufrufe
  nötig sind (Token holen, sendMail aufrufen).

  WICHTIG: dieser Weg konnte nicht gegen einen echten Microsoft-Mandanten
  getestet werden (dafür bräuchte es eine echte Azure-AD-App-Registrierung
  mit erteilter Berechtigung) -- nur sorgfältig gegen die
  Graph-API-Dokumentation aufgebaut. Bitte gründlicher testen als den
  SMTP-Weg.
"""

import base64
import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from sqlalchemy.orm import Session

from .crypto import decrypt_secret, encrypt_secret
from .models import SmtpSettings

ENCRYPTION_MODES = {"starttls", "ssl", "none"}
SEND_METHODS = {"smtp", "graph_oauth2"}
GRAPH_TOKEN_TIMEOUT = 15
GRAPH_SEND_TIMEOUT = 30


def get_or_create_smtp_settings(db: Session) -> SmtpSettings:
    settings = db.get(SmtpSettings, 1)
    if settings is None:
        settings = SmtpSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _missing_config_fields(s: SmtpSettings) -> list[str]:
    """Konkrete, für Menschen verständliche Liste fehlender Pflichtfelder
    der jeweils aktiven Methode -- ersetzt eine bloße "nicht vollständig
    konfiguriert"-Meldung, die im Praxistest zu unspezifisch war, um
    schnell zu erkennen, welches Feld tatsächlich fehlt."""
    if s.send_method == "graph_oauth2":
        missing = []
        if not s.graph_tenant_id: missing.append("Mandanten-ID")
        if not s.graph_client_id: missing.append("Anwendungs-ID (Client-ID)")
        if not s.graph_client_secret_encrypted: missing.append("Client-Secret")
        if not s.graph_sender_mailbox: missing.append("Absender-Postfach")
        return missing
    missing = []
    if not s.host: missing.append("SMTP-Server")
    if not s.sender_email: missing.append("Absender-E-Mail")
    if not s.username: missing.append("Benutzername")
    if not s.password_encrypted: missing.append("Passwort")
    return missing


def is_smtp_configured(db: Session) -> bool:
    """Prüft die JEWEILS aktive Methode (send_method) auf Vollständigkeit --
    der Name blieb aus demselben historischen Grund wie der Tabellenname
    'smtp_settings' erhalten, deckt inzwischen aber beide Versandwege ab."""
    s = get_or_create_smtp_settings(db)
    return not _missing_config_fields(s)


def set_send_method(db: Session, method: str) -> SmtpSettings:
    if method not in SEND_METHODS:
        raise ValueError(f"Unbekannter Versandweg: {method}")
    settings = get_or_create_smtp_settings(db)
    settings.send_method = method
    db.commit()
    db.refresh(settings)
    return settings


def update_smtp_settings(
    db: Session, *, host: str, port: int, username: str, encryption: str,
    sender_email: str, sender_name: str | None, password: str | None = None,
) -> SmtpSettings:
    """password=None bedeutet "unverändert lassen" -- das bereits
    gespeicherte, verschlüsselte Passwort wird dann nicht angetastet.
    Damit muss das Passwort nie erneut eingegeben werden, nur um andere
    Felder wie z.B. den Absendernamen zu ändern, und es muss nie im
    Klartext an die Oberfläche zurückgegeben werden, um es "vorauszufüllen"."""
    if encryption not in ENCRYPTION_MODES:
        raise ValueError(f"Unbekannte Verschlüsselung: {encryption}")
    settings = get_or_create_smtp_settings(db)
    settings.host = host
    settings.port = port
    settings.username = username
    settings.encryption = encryption
    settings.sender_email = sender_email
    settings.sender_name = sender_name
    if password:
        settings.password_encrypted = encrypt_secret(password)
    db.commit()
    db.refresh(settings)
    return settings


def update_graph_settings(
    db: Session, *, tenant_id: str, client_id: str, sender_mailbox: str, client_secret: str | None = None,
) -> SmtpSettings:
    """Analog zu update_smtp_settings(): client_secret=None lässt das
    bereits gespeicherte, verschlüsselte Secret unangetastet."""
    settings = get_or_create_smtp_settings(db)
    settings.graph_tenant_id = tenant_id
    settings.graph_client_id = client_id
    settings.graph_sender_mailbox = sender_mailbox
    if client_secret:
        settings.graph_client_secret_encrypted = encrypt_secret(client_secret)
    db.commit()
    db.refresh(settings)
    return settings


def _connect_smtp(settings: SmtpSettings) -> smtplib.SMTP:
    try:
        if settings.encryption == "ssl":
            conn = smtplib.SMTP_SSL(settings.host, settings.port, timeout=15)
        else:
            conn = smtplib.SMTP(settings.host, settings.port, timeout=15)
            if settings.encryption == "starttls":
                conn.starttls()
        if settings.username and settings.password_encrypted:
            conn.login(settings.username, decrypt_secret(settings.password_encrypted))
        return conn
    except smtplib.SMTPAuthenticationError as e:
        raise ValueError("Anmeldung beim Mailserver fehlgeschlagen -- bitte Benutzername/Passwort prüfen.") from e
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        raise ValueError(f"Verbindung zum Mailserver fehlgeschlagen: {e}") from e


def _get_graph_access_token(settings: SmtpSettings) -> str:
    """Holt ein neues Zugriffstoken per OAuth 2.0 Client-Credentials-Flow
    (App-only). Bewusst ohne Zwischenspeicherung/Cache: bei den hier zu
    erwartenden Versandmengen (einzelne Dokumente, kein Massenversand)
    überwiegt die Einfachheit eines frischen Tokens pro Versand den
    geringen Zusatzaufwand einer weiteren Anfrage."""
    token_url = f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": settings.graph_client_id,
        "client_secret": decrypt_secret(settings.graph_client_secret_encrypted),
        "scope": "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=GRAPH_TOKEN_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["access_token"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"Anmeldung bei Microsoft 365 fehlgeschlagen: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ValueError(f"Verbindung zu Microsoft 365 fehlgeschlagen: {e}") from e


def check_smtp_connection(db: Session) -> None:
    """Baut nur die Verbindung auf (bzw. holt bei Microsoft 365 nur ein
    Zugriffstoken), ohne etwas zu versenden -- für einen "Verbindung
    testen"-Knopf in den Einstellungen, damit eine falsche Konfiguration
    nicht erst beim ersten echten Versand auffällt.

    Bei Microsoft 365 bestätigt das nur Mandant/App/Secret, NICHT, ob die
    Mail.Send-Berechtigung tatsächlich erteilt (und Admin-genehmigt)
    wurde -- das zeigt sich erst beim echten Versand."""
    settings = get_or_create_smtp_settings(db)
    missing = _missing_config_fields(settings)
    if missing:
        raise ValueError(f"E-Mail-Versand ist noch nicht vollständig konfiguriert. Es fehlt: {', '.join(missing)}.")
    if settings.send_method == "graph_oauth2":
        _get_graph_access_token(settings)
        return
    conn = _connect_smtp(settings)
    conn.quit()


def _send_via_smtp(settings: SmtpSettings, *, to_email: str, subject: str, body_text: str,
                    attachment_bytes: bytes | None = None, attachment_filename: str | None = None) -> None:
    msg = MIMEMultipart()
    msg["From"] = formataddr((settings.sender_name or settings.sender_email, settings.sender_email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if attachment_bytes is not None and attachment_filename is not None:
        part = MIMEApplication(attachment_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
        msg.attach(part)

    conn = _connect_smtp(settings)
    try:
        conn.sendmail(settings.sender_email, [to_email], msg.as_string())
    except smtplib.SMTPException as e:
        raise ValueError(f"E-Mail-Versand fehlgeschlagen: {e}") from e
    finally:
        conn.quit()


def _graph_error_hint(detail: str) -> str:
    """Konkrete, umsetzbare Hinweise zu den häufigsten Graph-API-Fehlern
    (seit 1.0.84) -- ergänzt Microsofts eigene, oft wenig aussagekräftige
    Fehlermeldung ("Access is denied. Check credentials and try again."
    sagt z.B. nicht, WELCHE Zugangsdaten gemeint sind). Erweiterbar um
    weitere Fehlercodes, sobald sich neue Praxisfälle zeigen."""
    if "ErrorAccessDenied" in detail:
        return (
            " Häufigste Ursache: Die Anwendungsberechtigung 'Mail.Send' (nicht die gleichnamige "
            "Delegierte Berechtigung) hat keine wirksame Administratorzustimmung -- in Azure AD/Entra ID "
            "unter API-Berechtigungen prüfen, ob dort ein grüner Haken bei 'Erteilt für [Mandant]' steht, "
            "nicht nur 'Hinzugefügt'. Falls das bereits stimmt: eine Exchange-Anwendungszugriffsrichtlinie "
            "könnte den Zugriff auf dieses Postfach einschränken (per PowerShell prüfbar: "
            "Get-ApplicationAccessPolicy)."
        )
    if "ErrorInvalidUser" in detail or "ErrorInvalidRecipients" in detail or "does not exist" in detail:
        return " Häufigste Ursache: das hinterlegte Absender-Postfach existiert nicht oder ist falsch geschrieben."
    return ""


def _send_via_graph(settings: SmtpSettings, *, to_email: str, subject: str, body_text: str,
                     attachment_bytes: bytes | None = None, attachment_filename: str | None = None) -> None:
    token = _get_graph_access_token(settings)
    mailbox = urllib.parse.quote(settings.graph_sender_mailbox)
    url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/sendMail"
    message: dict = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body_text},
        "toRecipients": [{"emailAddress": {"address": to_email}}],
    }
    if attachment_bytes is not None and attachment_filename is not None:
        message["attachments"] = [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": attachment_filename,
            "contentBytes": base64.b64encode(attachment_bytes).decode("ascii"),
        }]
    payload = {"message": message, "saveToSentItems": "true"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        urllib.request.urlopen(req, timeout=GRAPH_SEND_TIMEOUT)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"E-Mail-Versand über Microsoft 365 fehlgeschlagen: {detail}{_graph_error_hint(detail)}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ValueError(f"Verbindung zu Microsoft 365 fehlgeschlagen: {e}") from e


def send_email_with_attachment(
    db: Session, *, to_email: str, subject: str, body_text: str,
    attachment_bytes: bytes, attachment_filename: str,
) -> None:
    """Versendet eine E-Mail mit genau einem PDF-Anhang über die aktuell
    gewählte Konfiguration (SmtpSettings.send_method). Wirft ValueError bei
    fehlender Konfiguration oder Versandfehler -- der Aufrufer (z.B.
    send_reminder_email() in app/reminders.py) entscheidet, wie das dem
    Menschen angezeigt wird."""
    settings = get_or_create_smtp_settings(db)
    missing = _missing_config_fields(settings)
    if missing:
        raise ValueError(f"E-Mail-Versand ist noch nicht konfiguriert. Es fehlt: {', '.join(missing)} (Einstellungen → E-Mail-Versand).")
    if settings.send_method == "graph_oauth2":
        _send_via_graph(settings, to_email=to_email, subject=subject, body_text=body_text, attachment_bytes=attachment_bytes, attachment_filename=attachment_filename)
    else:
        _send_via_smtp(settings, to_email=to_email, subject=subject, body_text=body_text, attachment_bytes=attachment_bytes, attachment_filename=attachment_filename)


def send_plain_email(db: Session, *, to_email: str, subject: str, body_text: str) -> None:
    """Wie send_email_with_attachment(), aber ohne Anhang -- für reine System-
    Benachrichtigungen (seit 1.1.3, z. B. Aufgaben-Zuweisung), die keinem Dokument
    entsprechen. Wirft ValueError bei fehlender Konfiguration oder Versandfehler,
    genau wie send_email_with_attachment()."""
    settings = get_or_create_smtp_settings(db)
    missing = _missing_config_fields(settings)
    if missing:
        raise ValueError(f"E-Mail-Versand ist noch nicht konfiguriert. Es fehlt: {', '.join(missing)} (Einstellungen → E-Mail-Versand).")
    if settings.send_method == "graph_oauth2":
        _send_via_graph(settings, to_email=to_email, subject=subject, body_text=body_text)
    else:
        _send_via_smtp(settings, to_email=to_email, subject=subject, body_text=body_text)
