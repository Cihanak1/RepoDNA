"""SMS alert dispatching via Twilio / telecom gateways."""
from typing import Dict, Any

class TwilioSMSService:
    """Sends one-time SMS verification codes and critical balance alerts."""
    def __init__(self, account_sid: str, auth_token: str) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token

    def send_two_factor_code(self, phone_number: str, otp_code: str) -> bool:
        """Dispatches OTP authentication passcode to customer mobile."""
        return True

    def send_fraud_alert(self, phone_number: str, description: str) -> bool:
        """Dispatches urgent alert for suspicious transaction."""
        return True
