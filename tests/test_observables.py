from pathlib import Path

import pytest

from dqmc_tools.errors import ObservableAmbiguousError, ObservableNotFoundError
from dqmc_tools.observables import (
    DEFAULT_REGISTRY_PATH,
    list_observables,
    load_observable_registry,
    resolve_observable,
)


def test_load_default_registry():
    registry = load_observable_registry()

    assert DEFAULT_REGISTRY_PATH.exists()
    assert "repo_variables" in registry
    assert any(item["repo_id"] == "EqLt.density" for item in registry["repo_variables"])


def test_list_observables_returns_copies():
    observables = list_observables()
    first_repo_id = observables[0]["repo_id"]

    observables[0]["repo_id"] = "mutated"

    assert list_observables()[0]["repo_id"] == first_repo_id


def test_resolve_observable_by_repo_id_h5_path_and_tail():
    by_repo_id = resolve_observable("EqLt.density")
    by_abs_h5 = resolve_observable("/meas_eqlt/density")
    by_rel_h5 = resolve_observable("meas_eqlt/density")
    by_tail = resolve_observable("density")

    assert by_repo_id["h5_path"] == "/meas_eqlt/density"
    assert by_repo_id["error_method"] == "jackknife_or_binning"
    assert by_abs_h5["repo_id"] == "EqLt.density"
    assert by_rel_h5["repo_id"] == "EqLt.density"
    assert by_tail["repo_id"] == "EqLt.density"


def test_resolve_observable_missing_name():
    with pytest.raises(ObservableNotFoundError) as exc:
        resolve_observable("not_a_registered_observable")

    assert exc.value.details == {"name": "not_a_registered_observable"}


def test_resolve_observable_ambiguous_tail(tmp_path: Path):
    registry_path = tmp_path / "observables.yaml"
    registry_path.write_text(
        """
repo_variables:
  - repo_id: EqLt.foo
    h5_path: /meas_eqlt/shared
    kind: first
  - repo_id: Uneqlt.foo
    h5_path: /meas_uneqlt/shared
    kind: second
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ObservableAmbiguousError) as exc:
        resolve_observable("foo", registry_path)

    candidates = exc.value.details["candidates"]
    assert [item["repo_id"] for item in candidates] == ["EqLt.foo", "Uneqlt.foo"]
