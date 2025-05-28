import os, sys
from app.config import HOST, PORT

if __name__ == "__main__":
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m", "uvicorn",
            "app.main:app",
            "--host", HOST,
            "--port", str(PORT),
            "--reload"         # 개발할 때만 켜세요
        ],
    )