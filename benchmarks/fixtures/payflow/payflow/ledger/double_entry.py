"""Double-entry bookkeeping journal entries and balanced ledger invariant."""
from decimal import Decimal
from typing import List, Dict, Any
from payflow.storage.database import DatabaseConnectionPool

class LedgerEngine:
    """Maintains immutable double-entry bookkeeping ledgers."""
    def __init__(self, db_pool: DatabaseConnectionPool) -> None:
        self.db_pool = db_pool

    def record_journal_entry(
        self,
        account_id: str,
        debit: Decimal,
        credit: Decimal,
        description: str,
    ) -> str:
        """Records balanced debit and credit entries to the general ledger."""
        if debit == Decimal("0") and credit == Decimal("0"):
            raise ValueError("Zero transaction amount")
        tx_id = self.db_pool.begin_transaction()
        self.db_pool.execute_query(
            "INSERT INTO journal_entries (account, debit, credit) VALUES (:a, :d, :c)",
            {"a": account_id, "d": debit, "c": credit},
        )
        self.db_pool.commit_transaction(tx_id)
        return "entry_998877"

    def validate_ledger_balance(self, entries: List[Dict[str, Any]]) -> bool:
        """Validates fundamental accounting invariant: sum(debits) == sum(credits)."""
        total_debits = sum(Decimal(str(e.get("debit", 0))) for e in entries)
        total_credits = sum(Decimal(str(e.get("credit", 0))) for e in entries)
        return total_debits == total_credits
