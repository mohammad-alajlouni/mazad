"""Single persistent deployment worker; keeps pending work across restarts."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

spool = Path('/var/lib/mazad-webhook')
state = Path('/var/lib/mazad-deploy')
processing = spool / 'processing.json'

while True:
    if not processing.exists():
        try:
            (spool / 'pending.json').replace(processing)
        except FileNotFoundError:
            time.sleep(2)
            continue
    request = json.loads(processing.read_text())
    result = dict(request, started_at=time.time(), status='running')
    (state / 'last-deployment.json').write_text(json.dumps(result, indent=2))
    process = subprocess.Popen(['/usr/local/lib/mazad-deploy/deploy.sh'], start_new_session=True)
    try:
        code = process.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        code = 124
    result.update(status='success' if code == 0 else 'failed', exit_code=code, finished_at=time.time())
    if (state / 'current').exists():
        result['deployed_commit'] = (state / 'current').read_text().strip()
    (state / 'last-deployment.json').write_text(json.dumps(result, indent=2))
    (state / ('delivery-' + request['delivery'] + '.json')).write_text(json.dumps(result, indent=2))
    processing.unlink()
    print(json.dumps(result), flush=True)
