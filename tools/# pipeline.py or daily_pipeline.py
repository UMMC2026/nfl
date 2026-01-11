# pipeline.py or daily_pipeline.py

collapsed = collapse_edges(raw_edges)
scored = score_edges(collapsed)

from engine.render_gate import render_gate

validated = render_gate(scored)

write_json(
    "outputs/validated_primary_edges.json",
    validated
)
