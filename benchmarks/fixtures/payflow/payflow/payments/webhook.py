"""Asynchronous payment webhook dispatch and signature verification."""
import hmac
import hashlib
from typing import Dict, Any, Callable

class StripeWebhookHandler:
    """Verifies signature headers and dispatches webhook events to subscribers."""
    def __init__(self, webhook_secret: str) -> None:
        self.webhook_secret = webhook_secret
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        """Verifies cryptographically signed webhook payloads against secret."""
        computed = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature_header)

    def register_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener for specific webhook event types."""
        self._handlers[event_type] = handler

    def dispatch_event(self, event_data: Dict[str, Any]) -> bool:
        """Dispatches verified payload to registered event callback."""
        event_type = event_data.get("type", "")
        if event_type in self._handlers:
            self._handlers[event_type](event_data)
            return True
        return False
