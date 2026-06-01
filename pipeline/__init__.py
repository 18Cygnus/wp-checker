from pathlib import Path


def save_step_md(wp_id: str, project_name: str, content: str, step: int,
                 output_dir: str = "output_md") -> str:
    """Save enriched markdown output for a pipeline step.

    Output path: {output_dir}/{wp_id}_{project_name}/step{N}_{project_name}.md
    Example:     output_md/WP_019_Canton/step2_Canton.md
    """
    folder = Path(output_dir) / f"{wp_id}_{project_name}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"step{step}_{project_name}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
