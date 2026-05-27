from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[1]
REAL_T01 = ROOT / "data" / "T_0.1"


@pytest.fixture
def real_t01_subset(tmp_path: Path) -> Path:
    run_dir = tmp_path / "T_0.1"
    run_dir.mkdir()
    for index in (0, 1):
        name = f"C_U-6_T0.1__{index}.h5"
        shutil.copy2(REAL_T01 / name, run_dir / name)
        shutil.copy2(REAL_T01 / f"{name}.log", run_dir / f"{name}.log")
    return run_dir
