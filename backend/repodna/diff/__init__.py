"""RepoDNA Architecture Diff Engine."""

from repodna.diff.engine import ArchitectureDiffEngine
from repodna.diff.models import (
    ArchitectureDiffResult,
    CouplingDeltaItem,
    CoverageDelta,
    CycleChanges,
    CycleDiffItem,
    DependencyChanges,
    EdgeDiffItem,
    HealthScoreDelta,
    ModuleChanges,
    RenamedModule,
    RevisionProvenance,
    RuleFindingChanges,
)
from repodna.diff.snapshot import SnapshotManager

__all__ = [
    "ArchitectureDiffEngine",
    "ArchitectureDiffResult",
    "CouplingDeltaItem",
    "CoverageDelta",
    "CycleChanges",
    "CycleDiffItem",
    "DependencyChanges",
    "EdgeDiffItem",
    "HealthScoreDelta",
    "ModuleChanges",
    "RenamedModule",
    "RevisionProvenance",
    "RuleFindingChanges",
    "SnapshotManager",
]
