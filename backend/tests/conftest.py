import os
import sys

# Make backend modules importable when pytest runs from within tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
