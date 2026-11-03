#!/usr/bin/env python3
"""Reproducible Linux source package from a committed Git tree, not the worktree."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def package(ref, output):
    commit = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
    source = git("show", commit + ":a2v/__init__.py").decode()
    version = re.search(r'__version__ = "([0-9A-Za-z.-]+)"', source).group(1)
    name = "Audio-To-Video-" + version
    entries = []
    for record in git("ls-tree", "-rz", commit).split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, sha = meta.split()
        path = raw_path.decode()
        if kind != b"blob" or not (path in ("audio2video", "install-deps.sh", "README.md", "LICENSE")
            or path.startswith(("a2v/", "tests/", "scripts/", "docs/", "LICENSES/"))):
            continue
        if mode not in (b"100644", b"100755"):
            raise ValueError("Only regular files can be packaged: " + path)
        entries.append((path, git("cat-file", "blob", sha.decode()), 0o755 if mode == b"100755" else 0o644))
    entries.append(("SOURCE_COMMIT", (commit + "\n").encode(), 0o644))
    checksums = "".join(hashlib.sha256(data).hexdigest() + "  " + path + "\n" for path, data, _ in sorted(entries))
    entries.append(("SHA256SUMS", checksums.encode(), 0o644))
    output.mkdir(parents=True, exist_ok=True)
    target = output / (name + "-linux.tar.gz")
    with target.open("wb") as file, gzip.GzipFile(fileobj=file, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path, data, mode in sorted(entries):
                info = tarfile.TarInfo(name + "/" + path)
                info.size, info.mode, info.mtime = len(data), mode, 0
                archive.addfile(info, io.BytesIO(data))
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_name(target.name + ".sha256").write_text(checksum + "  " + target.name + "\n")
    print(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    package(args.ref, args.output_dir)
