from pathlib import Path

from dqmc_tools.errors import DQMCError, PathNotAllowedError, error_dict


def test_dqmc_error_to_dict_is_json_safe():
    err = PathNotAllowedError(
        "Path is outside roots.",
        details={"path": Path("scratch/run1"), "roots": [Path("scratch")]},
    )

    assert err.to_dict() == {
        "ok": False,
        "error_type": "path_not_allowed",
        "message": "Path is outside roots.",
        "details": {
            "path": "scratch\\run1" if "\\" in str(Path("scratch/run1")) else "scratch/run1",
            "roots": ["scratch"],
        },
    }


def test_error_dict_handles_known_and_unknown_exceptions():
    assert error_dict(DQMCError("Known.", details={"x": 1})) == {
        "ok": False,
        "error_type": "dqmc_error",
        "message": "Known.",
        "details": {"x": 1},
    }
    assert error_dict(ValueError("Bad value.")) == {
        "ok": False,
        "error_type": "ValueError",
        "message": "Bad value.",
        "details": {},
    }
