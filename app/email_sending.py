"""Allgemeiner E-Mail-Versand (seit 1.0.74, um Microsoft 365/OAuth 2.0 seit
1.0.79 erweitert).

Bewusst eigenständig und ohne jeden Bezug zu einem bestimmten
Geschäftsobjekt -- alle Vorgänge (Angebot/Auftrag/Rechnung/Mahnung/Aufgabe)
verwenden dieselbe, einmal hinterlegte Konfiguration. Die konkrete
Zusammenstellung von Betreff/Text/Anhang bleibt Aufgabe des jeweiligen
Fachmoduls -- hier lebt nur das "Wie", nicht das "Was" des Versands.

Seit 1.8.17 geht jeder Versand über app/email_dispatch.py (Versandprotokoll,
Ablage, Sperre gegen Doppelversand); send_message() hier ist nur noch der
Transport und hat keinen anderen Aufrufer. Die früheren Einstiege
send_email_with_attachment()/send_plain_email() sind entfallen, damit kein
Versand am Protokoll vorbeigeht.

Zwei grundsätzlich verschiedene Versandwege, wählbar über
SmtpSettings.send_method (Klärung: "zusätzlich als wählbare Alternative"):

- 'smtp': klassisches SMTP mit Benutzername/Passwort. Nutzt bewusst nur die
  Python-Standardbibliothek (smtplib/email), keine zusätzliche
  Versand-Bibliothek -- passend zum bisherigen Stil des Projekts (z.B.
  Passwort-Hashing über hashlib statt einer externen Bibliothek).

- 'graph_oauth2': Microsoft Graph API mit OAuth 2.0
  Client-Credentials-Flow (App-only). Mail.Send ist NICHT in Entra ID erteilt,
  sondern über Exchange "RBAC for Applications" auf die Gruppe ERP-Zugriff
  beschränkt -- das Absender-Postfach muss Mitglied dieser Gruppe sein.
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
# 3 MB (dezimal) Anhang: Base64 macht daraus 4,0 MB, mit Mailtext und JSON-Hülle bleibt die Anfrage
# sicher unter der 4-MiB-Grenze einer Graph-Anfrage (4.194.304 Bytes). 3 MiB wären in Base64 schon
# exakt 4 MiB -- ohne jeden Platz für den Rest der Nachricht.
MAX_ATTACHMENT_BYTES = 3_000_000


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


def get_graph_access_token(settings: SmtpSettings) -> str:
    """Holt ein neues Zugriffstoken per OAuth 2.0 Client-Credentials-Flow
    (App-only). Bewusst ohne Zwischenspeicherung/Cache: bei den hier zu
    erwartenden Versandmengen (einzelne Dokumente, kein Massenversand)
    überwiegt die Einfachheit eines frischen Tokens pro Versand den
    geringen Zusatzaufwand einer weiteren Anfrage.

    Bewusst öffentlich (kein führender Unterstrich mehr, seit Kalender-Modul Stufe 2) -- der
    Client-Credentials-Flow fordert immer den Scope "https://graph.microsoft.com/.default", die
    tatsächlich nutzbaren Berechtigungen (Mail.Send, Calendars.ReadWrite) ergeben sich
    ausschließlich aus der Exchange-RBAC-Rollenzuweisung (Scope ERP-Zugriff), nicht aus dem Token
    und nicht aus Entra ID -- ein und dasselbe Token gilt für beide Zwecke, app/outlook_calendar_sync.py ruft
    deshalb GENAU diese Funktion erneut auf, statt eine zweite Token-Beschaffung zu bauen."""
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

    Bei Microsoft 365 bestätigt das nur Mandant/App/Secret, NICHT, ob das
    Absender-Postfach in der RBAC-Gruppe ERP-Zugriff ist -- das zeigt sich
    erst beim echten Versand."""
    settings = get_or_create_smtp_settings(db)
    missing = _missing_config_fields(settings)
    if missing:
        raise ValueError(f"E-Mail-Versand ist noch nicht vollständig konfiguriert. Es fehlt: {', '.join(missing)}.")
    if settings.send_method == "graph_oauth2":
        get_graph_access_token(settings)
        return
    conn = _connect_smtp(settings)
    conn.quit()


def _send_via_smtp(settings: SmtpSettings, *, to: list[str], cc: list[str], subject: str, body_text: str,
                    attachment_bytes: bytes | None = None, attachment_filename: str | None = None,
                    headers: dict[str, str] | None = None) -> None:
    msg = MIMEMultipart()
    msg["From"] = formataddr((settings.sender_name or settings.sender_email, settings.sender_email))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    for name, value in (headers or {}).items():
        msg[name] = value
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if attachment_bytes is not None and attachment_filename is not None:
        part = MIMEApplication(attachment_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
        msg.attach(part)

    conn = _connect_smtp(settings)
    try:
        # Umschlag-Empfänger = An + CC; eine Bcc-Kopfzeile gibt es bewusst nicht.
        conn.sendmail(settings.sender_email, [*to, *cc], msg.as_string())
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
            " Häufigste Ursache: das hinterlegte Absender-Postfach ist nicht Mitglied der Gruppe "
            "ERP-Zugriff (ERP-Zugriff@dachkonzepte.gmbh) -- Mail.Send ist ausschließlich über Exchange "
            "\"RBAC for Applications\" auf die Mitglieder dieser Gruppe freigegeben, nicht über Entra ID. "
            "Postfach in die Gruppe aufnehmen; die Änderung kann einige Minuten bis zur Wirksamkeit brauchen."
        )
    if "ErrorInvalidUser" in detail or "ErrorInvalidRecipients" in detail or "does not exist" in detail:
        return " Häufigste Ursache: das hinterlegte Absender-Postfach existiert nicht oder ist falsch geschrieben."
    return ""


def _send_via_graph(settings: SmtpSettings, *, to: list[str], cc: list[str], subject: str, body_text: str,
                     attachment_bytes: bytes | None = None, attachment_filename: str | None = None,
                     headers: dict[str, str] | None = None) -> None:
    """sendMail mit Anhang inline (fileAttachment) -- der einzige Weg, der mit Mail.Send allein
    auskommt (Regel 17). Größere Anhänge bräuchten eine Upload-Sitzung an einem Entwurf, also
    Mail.ReadWrite; deshalb die Größengrenze in check_attachment_size(). Eigene Kopfzeilen gehen
    über internetMessageHeaders (Graph verlangt das Präfix "X-"). Antwort bei Erfolg: 202 ohne
    Inhalt -- es gibt nichts zu lesen außer dem leeren Körper."""
    token = get_graph_access_token(settings)
    mailbox = urllib.parse.quote(settings.graph_sender_mailbox)
    url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/sendMail"
    message: dict = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body_text},
        "toRecipients": [{"emailAddress": {"address": address}} for address in to],
    }
    if cc:
        message["ccRecipients"] = [{"emailAddress": {"address": address}} for address in cc]
    if headers:
        message["internetMessageHeaders"] = [{"name": name, "value": value} for name, value in headers.items()]
    if attachment_bytes is not None and attachment_filename is not None:
        message["attachments"] = [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": attachment_filename,
            "contentType": "application/pdf",
            "contentBytes": base64.b64encode(attachment_bytes).decode("ascii"),
        }]
    payload = {"message": message, "saveToSentItems": "true"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=GRAPH_SEND_TIMEOUT) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"E-Mail-Versand über Microsoft 365 fehlgeschlagen: {detail}{_graph_error_hint(detail)}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ValueError(f"Verbindung zu Microsoft 365 fehlgeschlagen: {e}") from e


def check_attachment_size(attachment_bytes: bytes | None, attachment_filename: str | None) -> None:
    """Vor dem Senden: höchstens MAX_ATTACHMENT_BYTES (3 MB). Microsoft Graph nimmt mit sendMail
    höchstens 4 MB je Anfrage an und antwortet darüber mit 413; größere Anhänge bräuchten eine
    Upload-Sitzung und damit Mail.ReadWrite (Regel 17: nur Mail.Send). Gilt bewusst für BEIDE
    Versandwege, damit ein Dokument nicht je nach eingestelltem Weg mal hinausgeht und mal nicht."""
    if attachment_bytes is None or len(attachment_bytes) <= MAX_ATTACHMENT_BYTES:
        return
    size_mb = f"{len(attachment_bytes) / 1_000_000:.1f}".replace(".", ",")
    raise ValueError(
        f"Der Anhang „{attachment_filename}“ ist {size_mb} MB groß -- per E-Mail gehen höchstens 3 MB. "
        "Grund ist die Grenze von Microsoft 365 für den Versand mit Anhang; sie gilt hier für beide "
        "Versandwege. Es wurde nichts versendet. Bitte das PDF verkleinern (z. B. weniger oder "
        "kleinere Fotos, kleineres Briefpapier) oder das Dokument auf anderem Weg zustellen."
    )


def send_message(
    settings: SmtpSettings, *, to: list[str], cc: list[str], subject: str, body_text: str,
    attachment_bytes: bytes | None = None, attachment_filename: str | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Der eigentliche Versand über den eingestellten Weg (SmtpSettings.send_method). NUR aus
    app/email_dispatch.py aufrufen -- jeder Versand geht durch Protokoll und Ablage
    (tests/test_v321_email_dispatch.py prüft per AST, dass es keinen zweiten Aufrufer gibt).
    Wirft ValueError bei Versandfehlern; Konfiguration und Größe prüft der Aufrufer vorher."""
    kwargs = dict(
        to=to, cc=cc, subject=subject, body_text=body_text, attachment_bytes=attachment_bytes,
        attachment_filename=attachment_filename, headers=headers,
    )
    if settings.send_method == "graph_oauth2":
        _send_via_graph(settings, **kwargs)
    else:
        _send_via_smtp(settings, **kwargs)


def ensure_configured(settings: SmtpSettings) -> None:
    missing = _missing_config_fields(settings)
    if missing:
        raise ValueError(f"E-Mail-Versand ist noch nicht konfiguriert. Es fehlt: {', '.join(missing)} (Einstellungen → E-Mail-Versand).")
