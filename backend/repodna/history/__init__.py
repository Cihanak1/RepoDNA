"""RepoDNA Historical Architecture Snapshot & Time Machine Engine."""

from repodna.history.cache import HistoricalCache
from repodna.history.diff import EvolutionDiffEngine
from repodna.history.engine import HistoricalSnapshotEngine, ShallowCloneLimitationError
from repodna.history.evidence import HistoricalEvidenceProvider
from repodna.history.models import (
    HistoricalCouplingMetrics,
    HistoricalCycle,
    HistoricalDependencyEdge,
    HistoricalDiffResult,
    HistoricalEvidenceItem,
    HistoricalHealthMetrics,
    HistoricalLanguageSummary,
    HistoricalModuleSummary,
    HistoricalSnapshot,
    TimelineEntry,
    TimelineResult,
)
from repodna.history.timeline import TimelineEngine

__all__ = [
    "HistoricalSnapshotEngine",
    "HistoricalCache",
    "EvolutionDiffEngine",
    "TimelineEngine",
    "HistoricalEvidenceProvider",
    "ShallowCloneLimitationError",
    "HistoricalSnapshot",
    "HistoricalDiffResult",
    "TimelineResult",
    "TimelineEntry",
    "HistoricalModuleSummary",
    "HistoricalDependencyEdge",
    "HistoricalCycle",
    "HistoricalCouplingMetrics",
    "HistoricalHealthMetrics",
    "HistoricalEvidenceItem",
    "HistoricalLanguageSummary",
]
