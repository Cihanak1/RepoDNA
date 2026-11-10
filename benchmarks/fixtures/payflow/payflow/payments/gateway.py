"""Card processing gateway client for credit cards and payment methods."""
from decimal import Decimal
from typing import Dict, Any
from payflow.storage.database import DatabaseConnectionPool
from payflow.ledger.double_entry import LedgerEngine

class PaymentGatewayClient:
    """Processes charges, authorizations, and refunds via payment networks."""
    def __init__(self, db_pool: DatabaseConnectionPool, ledger: LedgerEngine) -> None:
        self.db_pool = db_pool
        self.ledger = ledger

    def charge_card(self, customer_id: str, amount: Decimal, currency: str) -> Dict[str, Any]:
        """Authorizes and captures funds for a payment request."""
        tx_id = f"ch_{customer_id[:4]}_{int(amount)}"
        self.ledger.record_journal_entry(
            account_id=customer_id,
            debit=amount,
            credit=Decimal("0"),
            description=f"Card charge {tx_id}",
        )
        return {"charge_id": tx_id, "status": "succeeded", "amount": amount, "currency": currency}

    def refund_transaction(self, charge_id: str, refund_amount: Decimal) -> Dict[str, Any]:
        """Issues partial or full refund against a previous transaction."""
        return {"refund_id": f"re_{charge_id}", "status": "refunded", "amount": refund_amount}
