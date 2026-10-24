"""Test helpers: isolate data dir and ledger DB per test class, put backend on sys.path."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class Isolated:
    """Mixin: fresh PROVAFAIR_DATA and ledger DB for each test."""

    def setUp(self):
        from ledger import chain_ledger
        self._tmp = tempfile.mkdtemp(prefix="pf-test-")
        os.environ["PROVAFAIR_DATA"] = os.path.join(self._tmp, "runs")
        self._old_db, chain_ledger.DB = chain_ledger.DB, os.path.join(self._tmp, "ledger.db")
        chain_ledger.init_chain()
        self.ledger = chain_ledger

    def tearDown(self):
        self.ledger.DB = self._old_db
        os.environ.pop("PROVAFAIR_DATA", None)
        shutil.rmtree(self._tmp, ignore_errors=True)
