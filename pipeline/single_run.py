import json
from pipeline.batch_runner import run_pipeline

with open("wp_metadata.json") as f:
    meta = json.load(f)

# Hanya proses WP_013 (Bitcoin)
results = run_pipeline(
    metadata=[m for m in meta if m["id"] == "WP_013"],
    output_dir="output_md",
    skip_db=True
)