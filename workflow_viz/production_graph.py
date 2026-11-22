"""LangGraph-compatible, read-only map of the video production lifecycle."""

from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    episode: int
    source_valid: bool
    assets_ready: bool
    narration_ready: bool
    captions_ready: bool
    render_ready: bool
    audio_ready: bool
    timing_qa: bool
    visual_qa: bool
    delivery_ready: bool
    retry_count: int
    status: str


STAGES = (
    ("source", "Source JSON\\nvalidate"),
    ("assets", "Style + scene\\nassets"),
    ("narration", "Narration\\nTTS"),
    ("timeline", "Measured\\ntimeline"),
    ("captions", "Caption\\nalignment"),
    ("render", "Panorama\\nrender"),
    ("audio", "Music + SFX\\nmix"),
    ("qa", "Timing + visual\\nQA"),
    ("review", "Adversarial +\\nprocedural review"),
    ("delivery", "Drive upload +\\nverification"),
)

EDGES = (
    ("source", "assets", "valid"),
    ("assets", "narration", "ready"),
    ("narration", "timeline", "waveform master"),
    ("timeline", "captions", "word timings"),
    ("captions", "render", "caption plan"),
    ("render", "audio", "video"),
    ("audio", "qa", "muxed film"),
    ("qa", "review", "all hard gates pass"),
    ("review", "delivery", "review pass"),
    ("qa", "render", "retry: visual/timing failure"),
    ("review", "narration", "retry: wording/speech failure"),
    ("delivery", "end", "Drive verified"),
)


def _noop_node(name: str):
    def node(state: WorkflowState) -> WorkflowState:
        return {**state, "status": f"mapped:{name}"}

    node.__name__ = f"map_{name}"
    return node


def build_production_graph(use_langgraph: bool = True) -> Any:
    """Return a compiled LangGraph when installed, otherwise a static map."""
    if not use_langgraph:
        return {"stages": STAGES, "edges": EDGES}
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return {"stages": STAGES, "edges": EDGES}

    graph = StateGraph(WorkflowState)
    for key, _label in STAGES:
        graph.add_node(key, _noop_node(key))
    graph.add_edge(START, "source")
    for left, right, label in EDGES:
        if right == "end":
            graph.add_edge(left, END)
        elif not label.startswith("retry"):
            graph.add_edge(left, right)
    return graph.compile()


def mermaid_workflow() -> str:
    """Create a stable Mermaid diagram, independent of installed packages."""
    lines = ["flowchart LR"]
    for key, label in STAGES:
        lines.append(f'    {key}["{label.replace(chr(10), "<br/>" )}"]')
    lines.append("    start((START)) --> source")
    for left, right, label in EDGES:
        target = "stop" if right == "end" else right
        if right == "end":
            lines.append("    stop((DONE))")
        marker = "-.->" if label.startswith("retry") else "-->"
        lines.append(f"    {left} {marker}|{label}| {target}")
    lines.extend([
        "    classDef gate fill:#fff3cd,stroke:#b58105,color:#3d2b00",
        "    class qa,review gate",
    ])
    return "\n".join(lines) + "\n"
