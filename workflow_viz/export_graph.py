"""CLI for exporting the production workflow visualization."""

from __future__ import annotations

import argparse
from pathlib import Path

from .production_graph import build_production_graph, mermaid_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the Living Tapestries workflow graph")
    parser.add_argument("--out", default="docs/production_workflow.mmd")
    parser.add_argument("--inspect", action="store_true", help="compile the optional LangGraph map")
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(mermaid_workflow(), encoding="utf-8")
    if args.inspect:
        graph = build_production_graph(use_langgraph=True)
        print(f"graph_type={type(graph).__name__}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
