import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from settingsconfig.utils import get_setting


logger = logging.getLogger(__name__)


def _get_gmail_credentials() -> dict[str, str]:
    return {
        'client_id': str(get_setting('GMAIL_CLIENT_ID', default='') or '').strip(),
        'client_secret': str(get_setting('GMAIL_CLIENT_SECRET', default='') or '').strip(),
        'refresh_token': str(get_setting('GMAIL_REFRESH_TOKEN', default='') or '').strip(),
        'sender_email': str(get_setting('GMAIL_SENDER_EMAIL', default='') or '').strip(),
    }


def _gmail_is_configured(credentials: dict[str, str]) -> bool:
    required = ['client_id', 'client_secret', 'refresh_token', 'sender_email']
    return all(credentials.get(key) for key in required)


def _send_via_gmail_api(subject: str, body_text: str, body_html: str | None, recipients: list[str]) -> bool:
    credentials = _get_gmail_credentials()
    if not _gmail_is_configured(credentials):
        return False

    token_response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': credentials['client_id'],
            'client_secret': credentials['client_secret'],
            'refresh_token': credentials['refresh_token'],
            'grant_type': 'refresh_token',
        },
        timeout=15,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get('access_token')
    if not access_token:
        return False

    mime = MIMEMultipart('alternative')
    mime['Subject'] = subject
    mime['From'] = credentials['sender_email']
    mime['To'] = ', '.join(recipients)
    mime.attach(MIMEText(body_text, 'plain', 'utf-8'))
    if body_html:
        mime.attach(MIMEText(body_html, 'html', 'utf-8'))

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode('utf-8')
    send_response = requests.post(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={'raw': raw},
        timeout=15,
    )
    send_response.raise_for_status()
    return True


def send_system_email(subject: str, body_text: str, recipients: list[str], body_html: str | None = None) -> bool:
    if not recipients:
        return False

    try:
        sent_via_gmail = _send_via_gmail_api(subject, body_text, body_html, recipients)
        if sent_via_gmail:
            return True
    except requests.RequestException as exc:
        logger.warning("Gmail API email send failed, falling back to Django backend: %s", exc)

    from_email = str(get_setting('GMAIL_SENDER_EMAIL', default='') or '').strip() or getattr(
        settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'
    )
    message = EmailMultiAlternatives(subject, body_text, from_email, recipients)
    if body_html:
        message.attach_alternative(body_html, "text/html")
    message.send(fail_silently=True)
    return True
