import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Los tests usan siempre la liga de ejemplo, aunque haya un .env con DATA_SOURCE=live.
os.environ["DATA_SOURCE"] = "sample"
