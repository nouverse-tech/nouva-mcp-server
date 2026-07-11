import os
import sys

sys.path.append(os.path.dirname(__file__))
from db.init_db import init_db

if __name__ == "__main__":
    init_db()
