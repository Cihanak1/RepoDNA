"""Unit tests for Tree-sitter AST parsers, import resolver, and Tarjan SCC dependency graph."""

from __future__ import annotations

from repodna.graph.engine import build_dependency_graph
from repodna.parsers.resolver import ImportResolver
from repodna.parsers.treesitter_parser import parse_source_file
from repodna.schemas.models import FileNode, LanguageSupportLevel


def test_python_treesitter_and_ast_parsing() -> None:
    code = """
import os
from .utils import helper_fn
from ..domain.models import UserAccount

class OrderProcessor:
    def process(self):
        mod = __import__(dynamic_plugin)
        return helper_fn()
"""
    parsed = parse_source_file("processor.py", ".py", code)
    assert parsed.language == "Python"
    assert parsed.support_level == LanguageSupportLevel.FULL_AST
    assert parsed.lines_code >= 7

    symbol_names = {s.name for s in parsed.symbols}
    assert "OrderProcessor" in symbol_names
    assert "process" in symbol_names

    rel_imports = [imp for imp in parsed.raw_imports if imp.is_relative]
    assert len(rel_imports) == 2
    dyn_imports = [imp for imp in parsed.raw_imports if imp.is_dynamic]
    assert len(dyn_imports) == 1


def test_typescript_treesitter_parsing() -> None:
    ts_code = """
import { useState } from 'react';
import { ApiClient } from './api/client';
import type { RepoNode } from '../types/graph';

export interface GraphProps {
  title: string;
}

export function renderGraph(props: GraphProps) {
  const lazyMod = import(variablePath);
  return ApiClient.fetch();
}
"""
    parsed = parse_source_file("GraphView.tsx", ".tsx", ts_code)
    assert parsed.language == "TypeScript (TSX)"
    assert parsed.support_level == LanguageSupportLevel.FULL_AST

    specs = [imp.module_specifier for imp in parsed.raw_imports if not imp.is_dynamic]
    assert "react" in specs
    assert "./api/client" in specs
    assert "../types/graph" in specs
    assert any(imp.is_dynamic for imp in parsed.raw_imports)

    sym_names = {s.name for s in parsed.symbols}
    assert "GraphProps" in sym_names
    assert "renderGraph" in sym_names


def test_go_and_rust_treesitter_parsing() -> None:
    go_code = """
package main
import (
    "fmt"
    "github.com/acme/project/internal/store"
)
type Server struct {}
func StartServer() {}
"""
    go_parsed = parse_source_file("main.go", ".go", go_code)
    assert go_parsed.language == "Go"
    assert go_parsed.support_level == LanguageSupportLevel.FULL_AST
    assert "github.com/acme/project/internal/store" in [i.module_specifier for i in go_parsed.raw_imports]
    assert {s.name for s in go_parsed.symbols} >= {"Server", "StartServer"}

    rust_code = """
use crate::engine::graph;
mod config;
pub struct Scanner {}
pub fn run_scan() {}
"""
    rs_parsed = parse_source_file("lib.rs", ".rs", rust_code)
    assert rs_parsed.language == "Rust"
    assert rs_parsed.support_level == LanguageSupportLevel.FULL_AST
    assert any("crate::engine::graph" in i.module_specifier for i in rs_parsed.raw_imports)
    assert {s.name for s in rs_parsed.symbols} >= {"Scanner", "run_scan"}


def test_import_resolver_and_circular_dependency_detection() -> None:
    file_ids = {
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/leaf.py",
        "src/orphan.py",
    }
    resolver = ImportResolver(file_ids)
    p_a = parse_source_file("a.py", ".py", "from . import b\nfrom . import leaf\nimport requests\n")
    internal_a, ext_a, unres_a = resolver.resolve_for_file("src/a.py", "Python", p_a.raw_imports)
    assert [t for t, _ in internal_a] == ["src/b.py", "src/leaf.py"]
    assert ext_a == ["requests"]
    assert unres_a == []

    nodes = [
        FileNode(
            id=fid,
            name=fid.split("/")[-1],
            directory="src",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=200,
            lines_total=20,
            lines_code=15,
            lines_comment=2,
            lines_blank=3,
        )
        for fid in sorted(file_ids)
    ]

    # Create 3-hop cycle: src/a.py -> src/b.py -> src/c.py -> src/a.py
    raw_edges = [
        ("src/a.py", "src/b.py", ["b"], 1),
        ("src/b.py", "src/c.py", ["c"], 1),
        ("src/c.py", "src/a.py", ["a"], 1),
        ("src/a.py", "src/leaf.py", ["leaf"], 2),
    ]
    edges, cycles, metrics = build_dependency_graph(nodes, raw_edges)

    assert metrics.cycle_count == 1
    assert metrics.nodes_in_cycles == 3
    assert cycles[0].nodes == ["src/a.py", "src/b.py", "src/c.py", "src/a.py"]
    assert metrics.orphan_files_count == 1

    node_by_id = {n.id: n for n in nodes}
    assert node_by_id["src/a.py"].in_cycle is True
    assert node_by_id["src/leaf.py"].in_cycle is False
    assert node_by_id["src/leaf.py"].instability == 0.0  # fan_in=1, fan_out=0 => maximally stable
    assert node_by_id["src/orphan.py"].is_orphan is True
