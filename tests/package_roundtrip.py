"""Verify the committed package, executable bits and CLI from another directory."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile

from fixtures import audio, decoded_frames

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts/package.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

with tempfile.TemporaryDirectory(prefix="a2v package roundtrip ") as directory:
    root = Path(directory)
    first = builder.package("HEAD", root / "one")
    second = builder.package("HEAD", root / "two")
    assert first.read_bytes() == second.read_bytes(), "Package is not reproducible"
    extracted = root / "extracted package"
    with tarfile.open(first) as archive:
        archive.extractall(extracted, filter="data")
    app = next(extracted.iterdir())
    for line in (app / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split("  ", 1)
        assert hashlib.sha256((app / path).read_bytes()).hexdigest() == digest, path
    assert (app / "audio2video").stat().st_mode & 0o111
    assert (app / "install-deps.sh").stat().st_mode & 0o111
    assert not list(app.rglob("__pycache__"))
    source = audio(root / "relative audio.wav", .237)
    subprocess.run([str(app / "audio2video"), "--version"], check=True, cwd=root)
    subprocess.run([str(app / "audio2video"), "render", source.name, "result.mp4", "--visualizer",
                    "--resolution", "720p", "--style", "gluball-knot", "--title", "Package — local export"], check=True, cwd=root)
    assert len(decoded_frames(root / "result.mp4")) == 8
    print("Package roundtrip passed: checksums, reproducibility, executable launcher, relative paths, real MP4")
