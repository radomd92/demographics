"""Build and verify the optional extension in fresh subprocesses."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent


def build_native() -> str:
    """Type-check, compile C, verify in isolation, then atomically publish binaries."""
    lock = ROOT / "build" / ".native-build-lock"
    lock.parent.mkdir(exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise RuntimeError("Another native build is running (build/.native-build-lock).") from error
    logs: list[str] = []
    try:
        with TemporaryDirectory(prefix="native-staging-", dir=ROOT / "build") as directory:
            staging = Path(directory)
            commands = [
                [sys.executable, "-m", "mypy", "demographics/kernel.py", "demographics/models.py"],
                [sys.executable, "setup_native.py", "build_ext", "--build-lib", str(staging)],
            ]
            for command in commands:
                completed = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False
                )
                logs.append(completed.stdout + completed.stderr)
                if completed.returncode:
                    raise RuntimeError("Native build failed:\n" + "\n".join(logs)[-16000:])
            artifacts = [p for p in staging.rglob("*") if p.suffix in (".so", ".pyd")]
            if not artifacts:
                raise RuntimeError("Compiler did not produce a native extension.")
            # Test the candidate before replacing any working engine. This package
            # shadows the editable checkout in the verification subprocess.
            package = staging / "demographics"
            package.mkdir(exist_ok=True)
            for source in (ROOT / "demographics").glob("*.py"):
                (package / source.name).write_bytes(source.read_bytes())
            verification = subprocess.run(
                [sys.executable, "-m", "demographics.benchmark"],
                cwd=staging,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            logs.append(verification.stdout + verification.stderr)
            if verification.returncode:
                raise RuntimeError("Compiled, but native verification failed:\n" + "\n".join(logs))
            for artifact in artifacts:
                destination = ROOT / artifact.relative_to(staging)
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Copy first, then atomically replace; never truncate a mapped extension.
                temporary = destination.with_suffix(destination.suffix + ".new")
                temporary.write_bytes(artifact.read_bytes())
                os.replace(temporary, destination)
        return "\n".join(logs)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Native build/verification timed out.\n" + "\n".join(logs)) from error
    finally:
        lock.rmdir()


def main() -> None:
    """Build, or inspect the actually importable engine from a fresh process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        from demographics.engine import is_native, load_kernel

        kernel = load_kernel()
        print(json.dumps({"native": is_native(kernel), "module": str(kernel.__file__)}))
    else:
        try:
            print(build_native())
        except RuntimeError as error:
            parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
