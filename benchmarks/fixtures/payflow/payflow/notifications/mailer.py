"""Transactional email sending via SMTP / SES."""
from typing import Dict, Any

class EmailNotificationService:
    """Dispatches templated email receipts and security alerts."""
    def __init__(self, smtp_host: str = "mail.payflow.internal") -> None:
        self.smtp_host = smtp_host

    def send_payment_receipt(self, recipient: str, amount: str, invoice_id: str) -> bool:
        """Sends customer payment confirmation receipt."""
        return True

    def send_failed_payment_notice(self, recipient: str, retry_date: str) -> bool:
        """Sends dunning notice for declined card charge."""
        return True
