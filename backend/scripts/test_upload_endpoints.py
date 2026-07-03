from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import app.main as m

client = TestClient(m.app)

# POST a small PDF-like bytes
pdf_bytes = b"%PDF-1.4\n%EOF\n"
files = {'file': ('test.pdf', pdf_bytes, 'application/pdf')}
print('POST /upload')
r = client.post('/upload', files=files)
print(r.status_code, r.text)

if r.status_code == 201:
    item = r.json()
    uid = item['id']
    print('GET /upload/{id}')
    g = client.get(f'/upload/{uid}')
    print(g.status_code, g.text)

    print('DELETE /upload/{id}')
    d = client.delete(f'/upload/{uid}')
    print(d.status_code, d.text)
else:
    print('POST failed; skipping GET/DELETE')

print('List uploads')
print(client.get('/upload').status_code, client.get('/upload').text)
