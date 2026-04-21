"""Run the full tracking pipeline by executing grouped step scripts in one shared runtime."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ROOT / "pipeline_steps" / "01_setup_and_dependencies.py",
    ROOT / "pipeline_steps" / "02_tracking_components.py",
    ROOT / "pipeline_steps" / "03_configuration_and_inputs.py",
    ROOT / "pipeline_steps" / "04_execute_pipeline.py",
    ROOT / "pipeline_steps" / "05_results_and_reports.py",
    ROOT / "pipeline_steps" / "06_wandering_risk_analysis.py",
]


def main() -> None:
    local_ultra_dir = ROOT / ".ultralytics"
    local_ultra_dir.mkdir(exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(local_ultra_dir)

    shared_globals = {"__name__": "__main__"}
    for step in STEPS:
        print(f"[RUN] {step.name}")
        code = step.read_text(encoding="utf-8-sig")
        shared_globals["__file__"] = str(step)
        exec(compile(code, str(step), "exec"), shared_globals)


if __name__ == "__main__":
    main()
