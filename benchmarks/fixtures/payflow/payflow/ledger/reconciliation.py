"""Bank statement reconciliation and batch settlement processor."""
from typing import List, Dict, Any
from payflow.ledger.double_entry import LedgerEngine

class ReconciliationWorker:
    """Cross-references internal journal entries against external bank statements."""
    def __init__(self, ledger: LedgerEngine) -> None:
        self.ledger = ledger

    def reconcile_daily_settlement(
        self,
        bank_records: List[Dict[str, Any]],
        ledger_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculates discrepancy delta between bank feed and ledger transactions."""
        matched = []
        discrepancies = []
        for b in bank_records:
            matching = [l for l in ledger_records if l.get("reference") == b.get("reference")]
            if matching:
                matched.append(b)
            else:
                discrepancies.append(b)
        return {
            "total_evaluated": len(bank_records),
            "matched_count": len(matched),
            "discrepancies": discrepancies,
            "is_balanced": len(discrepancies) == 0,
        }
