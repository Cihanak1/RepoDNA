"""API routing endpoints binding HTTP requests to underlying services."""
from typing import Dict, Any
from payflow.auth.middleware import AuthenticationMiddleware
from payflow.payments.gateway import PaymentGatewayClient
from payflow.billing.subscription import SubscriptionManager

def create_api_router(
    auth: AuthenticationMiddleware,
    payments: PaymentGatewayClient,
    billing: SubscriptionManager,
) -> Dict[str, Any]:
    """Factory creating API routes for the financial gateway."""
    return {
        "status": "ready",
        "endpoints": [
            "/api/v1/health",
            "/api/v1/auth/token",
            "/api/v1/payments/charge",
            "/api/v1/subscriptions/create",
        ],
    }

def health_check_endpoint() -> Dict[str, str]:
    """Returns service operational health status."""
    return {"status": "healthy", "service": "payflow"}
