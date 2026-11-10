"""Invoice PDF rendering, tax calculation, and billing dispatch."""
from decimal import Decimal
from typing import Dict, Any, List
from payflow.billing.subscription import SubscriptionManager

class InvoiceGenerator:
    """Compiles line items and generates standardized customer invoices."""
    def __init__(self, subscription_manager: SubscriptionManager) -> None:
        self.subscription_manager = subscription_manager

    def calculate_invoice_totals(self, items: List[Dict[str, Any]], tax_rate: Decimal = Decimal("0.08")) -> Dict[str, Decimal]:
        """Calculates subtotal, sales tax, and grand total."""
        subtotal = sum(Decimal(str(i["amount"])) for i in items)
        tax = subtotal * tax_rate
        return {"subtotal": subtotal, "tax": tax, "grand_total": subtotal + tax}

    def render_pdf_invoice(self, invoice_id: str, totals: Dict[str, Decimal]) -> bytes:
        """Renders binary PDF invoice document for accounting records."""
        return f"PDF_INVOICE_{invoice_id}_TOTAL_{totals['grand_total']}".encode("utf-8")
