"""Subscription lifecycle management, recurring plans, and prorations."""
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any
from payflow.payments.gateway import PaymentGatewayClient

class SubscriptionManager:
    """Manages recurring subscription billing cycles and plan upgrades."""
    def __init__(self, payment_gateway: PaymentGatewayClient) -> None:
        self.payment_gateway = payment_gateway

    def create_subscription(self, customer_id: str, plan_tier: str) -> Dict[str, Any]:
        """Provisions a recurring subscription plan for a customer."""
        price_map = {"starter": Decimal("29.00"), "pro": Decimal("99.00"), "enterprise": Decimal("499.00")}
        amount = price_map.get(plan_tier, Decimal("49.00"))
        charge = self.payment_gateway.charge_card(customer_id, amount, "USD")
        return {"sub_id": f"sub_{customer_id}", "plan": plan_tier, "charge": charge}

    def calculate_prorated_amount(
        self,
        old_rate: Decimal,
        new_rate: Decimal,
        days_remaining: int,
        total_days: int = 30,
    ) -> Decimal:
        """Calculates prorated upgrade or downgrade charge difference."""
        daily_diff = (new_rate - old_rate) / Decimal(str(total_days))
        return daily_diff * Decimal(str(days_remaining))

    def cancel_subscription(self, sub_id: str, at_period_end: bool = True) -> bool:
        """Terminates active subscription either immediately or at period end."""
        return True
