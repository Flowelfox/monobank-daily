import ast
import os
from pathlib import Path

from dotenv import load_dotenv

from src.logs import setup_logging

load_dotenv()

PROJECT_ROOT = Path(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")))
DATA_FOLDER = PROJECT_ROOT / "data"

TIMEZONE = "Europe/Kiev"

BOT_TOKEN = ""

DATABASE_URL = "sqlite:///data/bot.db"

REPORT_HOUR = 21
REPORT_MINUTE = 0

vars_copy = locals().copy()
local_variables = locals()
for key in vars_copy:
    if key in os.environ:
        value = os.environ[key]

        if value == "None":
            local_variables[key] = None
            continue

        if value.startswith('"') and value.endswith('"'):
            local_variables[key] = value[1:-1]
            continue

        if value.startswith("[") and value.endswith("]"):
            local_variables[key] = ast.literal_eval(value)
            continue

        if value.lower() in ("true", "false"):
            local_variables[key] = value.lower() == "true"
            continue

        try:
            local_variables[key] = int(value)
            continue
        except ValueError:
            pass

        try:
            local_variables[key] = float(value)
            continue
        except ValueError:
            pass

        local_variables[key] = value

if not DATA_FOLDER.exists():
    DATA_FOLDER.mkdir(parents=True)

setup_logging(PROJECT_ROOT)
