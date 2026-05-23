from pathlib import Path

from dqmc_tools import DQMCError, PathNotAllowedError, error_dict


def test_dqmc_error_to_dict_is_json_safe():
    err = PathNotAllowedError(
        "Path is outside configured roots.",
        details={
            "path": Path("scratch/run1"),
            "allowed_roots": [Path("scratch")],
        },
    )

    assert err.to_dict() == {
        "ok": False,
        "error_type": "path_not_allowed",
        "message": "Path is outside configured roots.",
        "details": {
            "path": "scratch\\run1" if "\\" in str(Path("scratch/run1")) else "scratch/run1",
            "allowed_roots": ["scratch"],
        },
    }


def test_error_dict_handles_known_and_unknown_exceptions():
    known = error_dict(DQMCError("Known failure.", details={"item": "x"}))
    unknown = error_dict(ValueError("Bad value."))

    assert known["error_type"] == "dqmc_error"
    assert known["details"] == {"item": "x"}
    assert unknown == {
        "ok": False,
        "error_type": "ValueError",
        "message": "Bad value.",
        "details": {},
    }
