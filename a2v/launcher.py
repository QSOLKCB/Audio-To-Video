"""Keep the caller's working directory and use Ubuntu's system GTK bindings."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from a2v.__main__ import main
except ImportError as exc:
    print(f"Missing runtime dependency: {exc}. Run ./install-deps.sh", file=sys.stderr)
    raise SystemExit(1)

raise SystemExit(main())
