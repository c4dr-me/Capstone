"""Install runtime dependencies for the local Member 3 test server."""
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], stdout=sys.stdout, stderr=sys.stderr)
