from flask import render_template
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime
import os, db, traceback

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SEND_EMAIL = os.environ.get("SENDER_EMAIL", "flashcards@leechengzhu.com")
app_url = os.environ.get("APP_URL", "http://localhost:8080/").rstrip('/')

def send_verification_email(to_email):
    if not SENDGRID_API_KEY:
        return
    verification_code = db.set_verification_code(to_email)
    html_content = render_template('email_templates/confimation.html', verification_link=f'{app_url}/verify-email?token={verification_code}')
    msg = Mail(
        from_email=SEND_EMAIL,
        to_emails=to_email,
        subject="Email Verification",
        html_content=html_content
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(msg)

def send_password_reset_link(to_email):
    if not SENDGRID_API_KEY:
        return
    url = db.set_reset_password_link(to_email)
    html_content = render_template('email_templates/reset-password.html', reset_password_link=app_url + url)
    msg = Mail(
        from_email=SEND_EMAIL,
        to_emails=to_email,
        subject="Reset Password",
        html_content=html_content
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(msg)

def send_error_email(email, app, e):
    if not SENDGRID_API_KEY:
        return
    # Send email notification
    error_type = type(e).__name__
    error_message = str(e)
    traceback_info = traceback.format_exc()
    
    email_html = render_template('email_templates/error_notification.html',
        error_type=error_type,
        error_message=error_message,
        traceback=traceback_info,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        debug=app.debug,
        app_version='1.0.0',  # You would get this from your app config,
        email=email
    )
    msg = Mail(
        from_email=SEND_EMAIL,
        to_emails="christophelee2004@icloud.com",
        subject="Website Error",
        html_content=email_html   
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(msg)