import os
import sys
import tempfile
from pathlib import Path

os.environ["SHORTS_OFIS_VERI"] = tempfile.mkdtemp(prefix="ofis_test_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
