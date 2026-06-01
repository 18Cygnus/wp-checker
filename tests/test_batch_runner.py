import importlib.util
from pathlib import Path


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "runner", "pipeline/batch_runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE_METADATA = [
    {"id": "WP_019", "nama_proyek": "Canton Network",
     "folder": "whitepapers/average/", "filename": "technical_only_Canton.pdf",
     "quality_label": "average", "profile_label": "technical_only"},
]


def test_run_single_wp_produces_step_files(tmp_path):
    runner = load_runner()
    results = runner.run_pipeline(
        metadata=SAMPLE_METADATA,
        output_dir=str(tmp_path),
        skip_db=True,
    )
    assert len(results) == 1
    r = results[0]
    assert r["status"] == "ok"
    assert (tmp_path / "WP_019_CantonNetwork" / "step1_CantonNetwork.md").exists()
    assert (tmp_path / "WP_019_CantonNetwork" / "step2_CantonNetwork.md").exists()
    assert (tmp_path / "WP_019_CantonNetwork" / "step4_CantonNetwork.md").exists()
    assert len(r["sections"]) >= 3
    assert all("predicted_label" in s for s in r["sections"])
