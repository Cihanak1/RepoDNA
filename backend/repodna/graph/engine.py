"""Dependency graph engine: Tarjan SCC, elementary cycle finder, fan-in/out, instability & topology metrics."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from repodna.schemas.models import (
    CycleGroup,
    DependencyEdge,
    FileNode,
    GraphMetrics,
    LanguageSupportLevel,
    SeverityLevel,
)

ENTRYPOINT_FILENAMES = {
    "main.py",
    "app.py",
    "cli.py",
    "__init__.py",
    "__main__.py",
    "manage.py",
    "conftest.py",
    "setup.py",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "main.ts",
    "main.tsx",
    "main.js",
    "main.go",
    "main.rs",
    "lib.rs",
    "vite.config.ts",
    "playwright.config.ts",
}


def build_dependency_graph(
    files: list[FileNode],
    raw_edges: list[tuple[str, str, list[str], int]],
) -> tuple[list[DependencyEdge], list[CycleGroup], GraphMetrics]:
    """
    Compute directed dependency graph, node topological metrics, and circular dependencies.

    Args:
        files: List of FileNode objects (mutated in-place with fan_in, fan_out, instability, cycle flags).
        raw_edges: List of (source_id, target_id, imported_names, line_number).
    """
    node_map: dict[str, FileNode] = {f.id: f for f in files}

    # Deduplicate edges between the same (source, target) pair while aggregating imported symbol names
    edge_agg: dict[tuple[str, str], tuple[set[str], int]] = {}
    for src, dst, names, line in raw_edges:
        if src not in node_map or dst not in node_map or src == dst:
            continue
        key = (src, dst)
        if key not in edge_agg:
            edge_agg[key] = (set(names), line)
        else:
            existing_names, existing_line = edge_agg[key]
            existing_names.update(names)
            edge_agg[key] = (existing_names, min(existing_line, line))

    adj: dict[str, list[str]] = defaultdict(list)
    rev_adj: dict[str, list[str]] = defaultdict(list)

    for (src, dst), _ in sorted(edge_agg.items()):
        adj[src].append(dst)
        rev_adj[dst].append(src)

    # Find Strongly Connected Components via Tarjan's algorithm
    sccs = _tarjan_scc(sorted(node_map.keys()), adj)
    cyclic_sccs = [comp for comp in sccs if len(comp) > 1]

    # Extract deterministic elementary cycles within each non-trivial SCC
    # with explicit max_total_cycles, per-SCC max_cycles, operation budget, and timeout
    max_total_cycles = 100
    max_cycles_per_scc = 25
    max_ops_per_scc = 25000
    max_time_per_scc_sec = 0.75

    cycles: list[CycleGroup] = []
    edge_in_cycle: set[tuple[str, str]] = set()
    node_to_cycles: dict[str, list[str]] = defaultdict(list)
    truncation_reasons: list[str] = []

    cycle_counter = 1
    for scc in cyclic_sccs:
        scc_set = set(scc)
        remaining_cap = max(0, max_total_cycles - len(cycles))
        if remaining_cap == 0:
            truncation_reasons.append(f"Reached global cycle reporting cap ({max_total_cycles} cycles).")
            found_cycles: list[list[str]] = []
        else:
            found_cycles, scc_trunc_reason = _extract_cycles_in_scc(
                sorted(scc),
                scc_set,
                adj,
                max_cycles=min(max_cycles_per_scc, remaining_cap),
                max_ops=max_ops_per_scc,
                timeout_sec=max_time_per_scc_sec,
            )
            if scc_trunc_reason:
                truncation_reasons.append(scc_trunc_reason)

        for cyc_nodes in found_cycles:
            cid = f"CYCLE-{cycle_counter:03d}"
            cycle_counter += 1
            length = len(cyc_nodes) - 1
            severity = SeverityLevel.CRITICAL if length >= 3 else SeverityLevel.WARNING
            chain_str = " → ".join(cyc_nodes)
            cycles.append(
                CycleGroup(
                    id=cid,
                    nodes=cyc_nodes,
                    length=length,
                    severity=severity,
                    description=f"Circular dependency chain of {length} modules: {chain_str}",
                )
            )
            for i in range(length):
                u, v = cyc_nodes[i], cyc_nodes[i + 1]
                edge_in_cycle.add((u, v))
                if cid not in node_to_cycles[u]:
                    node_to_cycles[u].append(cid)

        # Ensure every node in a cyclic SCC is marked even if cycle cap or budget was hit
        fallback_cid = f"CYCLE-SCC-{cycle_counter:03d}"
        for u in scc:
            for v in adj.get(u, []):
                if v in scc_set:
                    edge_in_cycle.add((u, v))
            if not node_to_cycles[u]:
                node_to_cycles[u].append(fallback_cid)

    edges: list[DependencyEdge] = []
    for (src, dst), (names_set, line_no) in sorted(edge_agg.items()):
        edges.append(
            DependencyEdge(
                id=f"{src}->{dst}",
                source=src,
                target=dst,
                import_names=sorted(names_set)[:15],
                line=line_no,
                in_cycle=(src, dst) in edge_in_cycle,
            )
        )

    # Populate FileNode metrics
    max_fan_in = 0
    max_fan_out = 0
    instability_sum = 0.0
    instability_count = 0
    orphan_count = 0
    hub_count = 0

    for f in files:
        imports_out = sorted(adj.get(f.id, []))
        imports_in = sorted(rev_adj.get(f.id, []))
        f.imports_internal = imports_out
        f.imported_by = imports_in
        f.fan_out = len(imports_out)
        f.fan_in = len(imports_in)
        max_fan_in = max(max_fan_in, f.fan_in)
        max_fan_out = max(max_fan_out, f.fan_out)

        total_deg = f.fan_in + f.fan_out
        if total_deg > 0:
            f.instability = round(f.fan_out / total_deg, 3)
            instability_sum += f.instability
            instability_count += 1
        else:
            f.instability = 0.0

        f.cycle_ids = node_to_cycles.get(f.id, [])
        f.in_cycle = len(f.cycle_ids) > 0

        # Hub threshold: high total coupling (fan_in + fan_out >= 6 or fan_in >= 4)
        f.is_hub = (f.fan_in >= 4) or (total_deg >= 6)
        if f.is_hub:
            hub_count += 1

        # Orphan: supported code file with 0 internal edges and not a known entrypoint/test
        is_test = "test" in f.id.lower() or "spec" in f.id.lower()
        is_entry = f.name.lower() in ENTRYPOINT_FILENAMES
        if (
            f.support_level != LanguageSupportLevel.UNSUPPORTED
            and total_deg == 0
            and not is_test
            and not is_entry
        ):
            f.is_orphan = True
            orphan_count += 1
        else:
            f.is_orphan = False

    # Connected components (weakly connected among all nodes)
    components = _count_weak_components(sorted(node_map.keys()), adj, rev_adj)
    n_nodes = len(files)
    n_edges = len(edges)
    density = round(n_edges / (n_nodes * (n_nodes - 1)), 4) if n_nodes > 1 else 0.0
    avg_instability = round(instability_sum / instability_count, 3) if instability_count > 0 else 0.0

    unique_trunc = list(dict.fromkeys(truncation_reasons))
    metrics = GraphMetrics(
        total_nodes=n_nodes,
        total_edges=n_edges,
        connected_components=components,
        scc_count=len(cyclic_sccs),
        cycle_count=len(cycles),
        nodes_in_cycles=sum(1 for f in files if f.in_cycle),
        cycles_truncated=len(unique_trunc) > 0,
        cycle_truncation_reason="; ".join(unique_trunc) if unique_trunc else None,
        orphan_files_count=orphan_count,
        hub_files_count=hub_count,
        max_fan_in=max_fan_in,
        max_fan_out=max_fan_out,
        average_instability=avg_instability,
        graph_density=density,
    )
    return edges, cycles, metrics


def _tarjan_scc(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []

    for start_node in nodes:
        if start_node in indices:
            continue

        # Iterative Tarjan to prevent RecursionError on deep dependency graphs
        call_stack: list[tuple[str, int]] = [(start_node, 0)]
        indices[start_node] = lowlink[start_node] = index
        index += 1
        stack.append(start_node)
        on_stack.add(start_node)

        while call_stack:
            u, neighbor_idx = call_stack[-1]
            neighbors = adj.get(u, [])
            if neighbor_idx < len(neighbors):
                v = neighbors[neighbor_idx]
                call_stack[-1] = (u, neighbor_idx + 1)
                if v not in indices:
                    indices[v] = lowlink[v] = index
                    index += 1
                    stack.append(v)
                    on_stack.add(v)
                    call_stack.append((v, 0))
                elif v in on_stack:
                    lowlink[u] = min(lowlink[u], indices[v])
            else:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[u])

                if lowlink[u] == indices[u]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.remove(w)
                        comp.append(w)
                        if w == u:
                            break
                    sccs.append(sorted(comp))

    return sccs


def _extract_cycles_in_scc(
    scc_nodes: list[str],
    scc_set: set[str],
    adj: dict[str, list[str]],
    max_cycles: int = 25,
    max_ops: int = 25000,
    timeout_sec: float = 0.75,
) -> tuple[list[list[str]], str | None]:
    """
    Find canonical elementary cycles within an SCC using Johnson's blocked-set algorithm,
    bounded by `max_cycles`, `max_ops` operation budget, and `timeout_sec` wall-clock budget.
    """
    seen_canonical: set[tuple[str, ...]] = set()
    results: list[list[str]] = []
    node_order = {n: idx for idx, n in enumerate(scc_nodes)}
    ops_used = 0
    truncation_reason: str | None = None
    deadline = time.monotonic() + timeout_sec

    for start in scc_nodes:
        if len(results) >= max_cycles or truncation_reason is not None:
            break
        start_rank = node_order[start]
        path: list[str] = [start]
        blocked: set[str] = {start}
        blocked_map: dict[str, set[str]] = defaultdict(set)

        def unblock(
            u: str,
            _blocked: set[str] = blocked,
            _blocked_map: dict[str, set[str]] = blocked_map,
        ) -> None:
            nonlocal ops_used
            stack = [u]
            while stack:
                ops_used += 1
                curr = stack.pop()
                if curr in _blocked:
                    _blocked.remove(curr)
                    for w in list(_blocked_map[curr]):
                        _blocked_map[curr].discard(w)
                        if w in _blocked:
                            stack.append(w)

        def circuit(
            curr: str,
            _start: str = start,
            _start_rank: int = start_rank,
            _path: list[str] = path,
            _blocked: set[str] = blocked,
            _blocked_map: dict[str, set[str]] = blocked_map,
        ) -> bool:
            nonlocal ops_used, truncation_reason
            found_cycle = False
            ops_used += 1

            if len(results) >= max_cycles:
                truncation_reason = f"Reached per-SCC cycle cap ({max_cycles} cycles)."
                return True
            if ops_used >= max_ops:
                truncation_reason = f"Reached Johnson cycle enumeration operation budget ({max_ops} ops)."
                return True
            if (ops_used & 63) == 0 and time.monotonic() > deadline:
                truncation_reason = f"Reached Johnson cycle enumeration timeout ({timeout_sec:.2f}s)."
                return True

            for nxt in adj.get(curr, []):
                if nxt not in scc_set or node_order[nxt] < _start_rank:
                    continue
                if nxt == _start and len(_path) >= 2:
                    canon = _canonicalize_cycle(_path)
                    if canon not in seen_canonical:
                        seen_canonical.add(canon)
                        results.append([*list(canon), canon[0]])
                    found_cycle = True
                    if len(results) >= max_cycles:
                        truncation_reason = f"Reached per-SCC cycle cap ({max_cycles} cycles)."
                        break
                elif nxt not in _blocked and len(_path) < 16:
                    _blocked.add(nxt)
                    _path.append(nxt)
                    if circuit(nxt, _start, _start_rank, _path, _blocked, _blocked_map):
                        found_cycle = True
                    _path.pop()
                    if truncation_reason is not None:
                        break

            if found_cycle:
                unblock(curr)
            else:
                for nxt in adj.get(curr, []):
                    if nxt in scc_set and node_order[nxt] >= _start_rank:
                        _blocked_map[nxt].add(curr)
            return found_cycle

        circuit(start)

    return results, truncation_reason


def _canonicalize_cycle(cycle_nodes: list[str]) -> tuple[str, ...]:
    if not cycle_nodes:
        return ()
    min_idx = min(range(len(cycle_nodes)), key=lambda i: cycle_nodes[i])
    rotated = cycle_nodes[min_idx:] + cycle_nodes[:min_idx]
    return tuple(rotated)


def _count_weak_components(
    nodes: list[str],
    adj: dict[str, list[str]],
    rev_adj: dict[str, list[str]],
) -> int:
    visited: set[str] = set()
    count = 0
    for n in nodes:
        if n in visited:
            continue
        count += 1
        queue: deque[str] = deque([n])
        visited.add(n)
        while queue:
            curr = queue.popleft()
            for nxt in adj.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
            for prv in rev_adj.get(curr, []):
                if prv not in visited:
                    visited.add(prv)
                    queue.append(prv)
    return count
