"""
Shared test setup: one temporary database and upload folder for all test modules.
Importing this module must happen before app.py is imported anywhere.
"""
import atexit
import os
import shutil
import sys
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
DB_PATH = _db.name
UPLOAD_DIR = tempfile.mkdtemp(prefix="vitaplate-uploads-")

os.environ["VITAPLATE_DB"] = DB_PATH
os.environ["VITAPLATE_UPLOAD_DIR"] = UPLOAD_DIR
os.environ["SECRET_KEY"] = "test-secret-key"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as vitaplate  # noqa: E402,F401  (creates the tables and the starter recipes)


@atexit.register
def _cleanup():
    if os.path.exists(DB_PATH):
        os.unlink(DB_PATH)
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
