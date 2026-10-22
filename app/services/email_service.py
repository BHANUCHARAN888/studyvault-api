import resend

from app.core.config import settings


def send_verification_email(email: str, token: str) -> None:
    resend.api_key = settings.resend_api_key

    verification_url = (
        f"{settings.frontend_base_url}/verify-email.html"
        f"?token={token}"
    )

    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": [email],
            "subject": "Verify your StudyVault email",
            "html": f"""
                <div>
                    <h2>Verify your StudyVault email</h2>
                    <p>Thanks for registering for StudyVault.</p>
                    <p>Click the link below to verify your email address.
                    This link expires in
                    {settings.verification_token_expire_minutes} minutes.</p>
                    <p>
                        <a href="{verification_url}">
                            Verify my email
                        </a>
                    </p>
                    <p>If you did not create this account, you can
                    safely ignore this email.</p>
                </div>
            """,
        }
    )
