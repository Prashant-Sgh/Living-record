import traceback
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend package is on sys.path when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as m

client = TestClient(m.app)
print('Client created')
try:
    r = client.get('/health')
    print('GET /health', r.status_code)
    print(r.text)
except Exception as e:
    print('Exception calling /health')
    traceback.print_exc()

try:
    r = client.get('/upload')
    print('GET /upload', r.status_code)
    print(r.text)
except Exception:
    print('Exception calling /upload')
    traceback.print_exc()
