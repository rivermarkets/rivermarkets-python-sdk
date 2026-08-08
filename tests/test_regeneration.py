import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postprocess_preserves_fee_helper() -> None:
    tracked_outputs = [
        ROOT / "rivermarkets" / "client.py",
        ROOT / "rivermarkets" / "fee_calculator.py",
        ROOT / "rivermarkets" / "__init__.py",
    ]
    before = {path: path.read_text() for path in tracked_outputs}

    subprocess.run(
        ["python3", "fern/postprocess.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert {path: path.read_text() for path in tracked_outputs} == before
