"""Keep the caller's working directory and use Ubuntu's system GTK bindings."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2v.__main__ import main

raise SystemExit(main())
