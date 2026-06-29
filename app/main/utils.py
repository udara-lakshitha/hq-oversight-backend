import os
from jinja2 import Environment, FileSystemLoader
import resend
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def send_verification_email(student_name: str, target_email: str, otp_code: str):
    try:
        template = jinja_env.get_template("otp_email.html")
        html_content = template.render(student_name=student_name, otp_code=otp_code)
    except Exception as e:
        print(f"❌ Template Rendering failure error: {str(e)}")
        return

    if RESEND_API_KEY and RESEND_API_KEY != "re_mock_key_for_local_development":
        try:
            resend.api_key = RESEND_API_KEY
            params = {
                "from": "HQ-Oversight Engine <onboarding@resend.dev>",
                "to": [target_email],
                "subject": f"🔑 {otp_code} is your HQ-Oversight Portal Verification Passkey",
                "html": html_content
            }
            resend.Emails.send(params)
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