# Production workflow visualization

The repository exposes the Living Tapestries production lifecycle as a
read-only LangGraph-compatible map. The existing `batch_01.batch_runner` and
QA gates remain the execution authority.

Export Mermaid without installing anything extra:

```powershell
python -m workflow_viz.export_graph
```

This writes `docs/production_workflow.mmd`. Open it in GitHub, Mermaid Live,
or any Mermaid renderer.

For optional LangGraph compilation and graph inspection:

```powershell
python -m pip install -r requirements-workflow-viz.txt
python -m workflow_viz.export_graph --inspect
```

Solid edges are the normal production flow. Dashed edges are retry paths:
visual or timing failures return to render, while wording or speech failures
return to narration. The graph is side-effect free; it does not start TTS,
FFmpeg, image generation, or Drive uploads.
