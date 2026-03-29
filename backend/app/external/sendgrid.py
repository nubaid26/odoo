# backend/app/external/sendgrid.py
"""
SendGrid email client — renders Jinja2 templates and sends via SendGrid SDK.
Called only from the Celery notification worker — never inline in a request thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import settings

logger = logging.getLogger("trustflow.external.sendgrid")

# Set up Jinja2 template loader
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


def send_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    """
    Render a Jinja2 email template and send via SendGrid.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        template_name: Name of the template file in templates/ directory.
        context: Template context variables for Jinja2 rendering.

    Returns:
        True if email sent successfully, False otherwise.

    Raises:
        Exception: On SendGrid API failure (for Celery retry to catch).
    """
    try:
        # Render the HTML template
        template = _jinja_env.get_template(template_name)
        html_content = template.render(**context)

        # Build the message
        message = Mail(
            from_email=(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        # Send via SendGrid
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)

        logger.info(
            "Email sent to %s (subject: '%s', status: %d)",
            to_email, subject, response.status_code,
        )
        return True

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        raise
