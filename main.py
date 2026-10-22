import sys
from app.cli import run_cli
from app.server import run_server, uvicorn

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    if "--server" in sys.argv:
        run_server()
    else:
        run_cli()
