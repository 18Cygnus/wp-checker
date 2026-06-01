import importlib.util
from pathlib import Path


def load_init():
    spec = importlib.util.spec_from_file_location(
        "pipeline", "pipeline/__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_save_step_md_creates_correct_filename(tmp_path):
    pipeline = load_init()
    content = "## Abstract\n\nHello world."
    path = pipeline.save_step_md("WP_001", "FastToken", content, step=1,
                                  output_dir=str(tmp_path))
    assert Path(path).parent.name == "WP_001_FastToken"
    assert Path(path).name == "step1_FastToken.md"
    assert Path(path).read_text(encoding="utf-8") == content


def test_save_step_md_creates_output_dir_if_missing(tmp_path):
    pipeline = load_init()
    new_dir = tmp_path / "nested" / "output"
    pipeline.save_step_md("WP_002", "Bitcoin", "text", step=2,
                           output_dir=str(new_dir))
    assert (new_dir / "WP_002_Bitcoin" / "step2_Bitcoin.md").exists()
