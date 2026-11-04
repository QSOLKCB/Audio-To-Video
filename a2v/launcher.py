"""Keep the caller's working directory for source and frozen desktop launches."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from a2v.__main__ import main
except ImportError as exc:
    print(f"Missing runtime dependency: {exc}. See docs/portable.md", file=sys.stderr)
    raise SystemExit(1)

raise SystemExit(main())
