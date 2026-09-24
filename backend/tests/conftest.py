import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La API usa una base de datos temporal en los tests, nunca la real.
os.environ["PHIBET_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
