import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from config import Settings


def send_alert(
    product_name: str,
    product_url: str,
    current_price: float,
    target_price: float,
    currency: str = "$",
    recipient: Optional[str] = None,
) -> bool:
    """
    Send a price-drop alert email via Gmail SMTP using an App Password.

    Gmail App Password setup:
      1. Go to https://myaccount.google.com/security
      2. Enable 2-Step Verification if not already on.
      3. Go to "App passwords" (search in Google Account settings).
      4. Select "Mail" and your device, then click "Generate".
      5. Copy the 16-character password into your .env file.
    """
    if not recipient:
        recipient = Settings.ALERT_RECIPIENT

    subject = f"PRICE DROP ALERT: {product_name}"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
        <div style="max-width: 560px; margin: auto; background: white; border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">
            <div style="background: linear-gradient(135deg, #22c55e, #16a34a); padding: 24px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 22px;">Price Drop Alert!</h1>
            </div>
            <div style="padding: 24px;">
                <h2 style="color: #1f2937; margin-top: 0;">{product_name}</h2>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr>
                        <td style="padding: 8px; color: #6b7280;">Current Price</td>
                        <td style="padding: 8px; font-size: 28px; font-weight: bold; color: #16a34a;">
                            {currency}{current_price:.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #6b7280;">Your Target</td>
                        <td style="padding: 8px; font-size: 18px; color: #374151;">
                            {currency}{target_price:.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #6b7280;">Savings</td>
                        <td style="padding: 8px; font-size: 18px; color: #ef4444;">
                            -{currency}{target_price - current_price:.2f}
                        </td>
                    </tr>
                </table>
                <a href="{product_url}"
                   style="display: inline-block; background: #2563eb; color: white; padding: 12px 28px;
                          text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 8px;">
                    View Product
                </a>
                <p style="color: #9ca3af; font-size: 12px; margin-top: 24px;">
                    This alert was sent by your Price Tracker bot.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = Settings.GMAIL_USER
    msg["To"] = recipient
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(Settings.GMAIL_USER, Settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        print("  SMTP Auth failed — check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        print(f"  SMTP error: {e}")
        return False
