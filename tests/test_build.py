"""A failed native candidate must not replace a previously working extension."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from demographics import build


def test_failed_verification_keeps_existing_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build, "ROOT", tmp_path)
    package = tmp_path / "demographics"
    package.mkdir()
    (package / "__init__.py").write_text("")
    binary = package / "kernel.test.so"
    binary.write_bytes(b"working engine")

    def command(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "setup_native.py" in args:
            staging = Path(args[args.index("--build-lib") + 1]) / "demographics"
            staging.mkdir(parents=True)
            (staging / binary.name).write_bytes(b"bad candidate")
        if "demographics.benchmark" in args:
            return subprocess.CompletedProcess(args, 1, "", "Results differ")
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr("demographics.build.subprocess.run", command)
    with pytest.raises(RuntimeError, match="verification failed"):
        build.build_native()
    assert binary.read_bytes() == b"working engine"
    assert not (tmp_path / "build" / ".native-build-lock").exists()


def test_concurrent_build_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "ROOT", tmp_path)
    lock = tmp_path / "build" / ".native-build-lock"
    lock.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="Another native build"):
        build.build_native()
    assert lock.exists()
