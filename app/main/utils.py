import os
import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_verification_email(student_name: str, target_email: str, otp_code: str):
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HQ-Oversight Passcode Verification</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
            <tr>
                <td style="padding: 32px 24px; background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); text-align: center;">
                    <span style="background-color: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #ffffff; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; padding: 4px 12px; border-radius: 9999px;">🚀 Next-Gen Evaluation Engine</span>
                    <h1 style="color: #ffffff; margin: 12px 0 0 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">HQ-Oversight Portal</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 32px; color: #334155;">
                    <p style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #0f172a;">Ayubowan {student_name},</p>
                    <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                        You initiated a secure access request to sign into your account space. Use the temporary cryptographic passcode grid below to complete your system compilation check:
                    </p>
                    <table align="center" border="0" cellpadding="0" cellspacing="0" style="margin: 28px auto;">
                        <tr>
                            <td style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 16px 40px; text-align: center;">
                                <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 900; color: #1e40af; letter-spacing: 6px;">{otp_code}</span>
                            </td>
                        </tr>
                    </table>
                    <p style="margin: 24px 0 0 0; font-size: 12px; line-height: 1.5; color: #64748b; font-style: italic; text-align: center;">
                        ⚠️ This security verification passkey is unique to your session and will automatically self-destruct / expire in exactly 5 minutes.
                    </p>
                </td>
            </tr>
            <tr>
                <td style="padding: 24px 32px; background-color: #f8fafc; border-top: 1px solid #f1f5f9; text-align: center; color: #94a3b8; font-size: 11px; font-weight: 500;">
                    © 2026 HQ-Oversight Engine. Rebuilt Ecosystem for Advanced Level Combined Mathematics.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    if RESEND_API_KEY and RESEND_API_KEY != "re_mock_key_for_local_development":
        try:
            resend.api_key = RESEND_API_KEY
            params = {
                "from": "HQ-Oversight Engine <onboarding@resend.dev>",
                "to": [target_email],
                "subject": f"🔑 {otp_code} is your HQ-Oversight Portal Verification Passkey",
                "html": html_content
            }
            email_response = resend.Emails.send(params)
            print(f"📧 Production Email successfully routed through Resend API to {target_email}!")
            return
        except Exception as e:
            print(f"❌ Resend transmission ERROR encountered: {str(e)}")

    print("\n" + "📨 " + "="*65)
    print("📢 PRODUCTION EMAIL SIMULATOR (HTML DESIGN CAPTURED)")
    print(f"TARGET EMAIL : {target_email}")
    print(f"SUBJECT      : 🔑 {otp_code} is your HQ-Oversight Portal Passkey")
    print("-" * 69)
    print(f" Ayubowan {student_name}!")
    print(f" Your Combined Math panel security access code is: [ {otp_code} ]")
    print(" This passcode will expire in 5 minutes.")
    print("="*69 + "\n")