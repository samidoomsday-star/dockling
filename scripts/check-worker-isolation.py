"""Assert actual local worker container restrictions without exposing its credentials."""

import json
import subprocess


def command(*args: str) -> str:
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout


worker = json.loads(command("inspect", "dockling-saas-worker-1"))[0]
host = worker["HostConfig"]
assert worker["State"]["Running"]
assert worker["Config"]["User"] == "1000:1000"
assert host["ReadonlyRootfs"] and host["Memory"] == 4 * 1024**3
assert host["NanoCpus"] == 2 * 10**9 and host["PidsLimit"] == 128
assert "ALL" in host["CapDrop"] and "no-new-privileges:true" in host["SecurityOpt"]
assert set(worker["NetworkSettings"]["Networks"]) == {"dockling-saas_worker-private"}
network = json.loads(command("network", "inspect", "dockling-saas_worker-private"))[0]
assert network["Internal"]
assert host["Dns"] == ["127.0.0.1"]
assert not worker["NetworkSettings"]["Ports"]
assert all(not m["RW"] and m["Destination"] in {"/models", "/broker"} for m in worker["Mounts"])
probe = """
import socket
from pathlib import Path
from sqlalchemy import create_engine,text
from stmtconv.config import load_worker_settings
from stmtconv.model_setup import load_manifest,verify_artifacts
cfg=load_worker_settings()
verify_artifacts(Path('/models'),load_manifest())
engine=create_engine(cfg.database_url.get_secret_value(),hide_parameters=True)
with engine.connect() as db:
    assert db.scalar(text('SELECT current_user'))=='dockling_worker'
    try: db.execute(text('SELECT * FROM web_files'))
    except Exception: pass
    else: raise AssertionError('Unscoped table read was allowed')
try: socket.getaddrinfo('example.com',443)
except socket.gaierror: pass
else: raise AssertionError('Public DNS resolution was allowed')
for address in [('1.1.1.1',443),('8.8.8.8',443)]:
    try:
        connection=socket.create_connection(address,timeout=3)
    except OSError: pass
    else:
        connection.close();raise AssertionError('Public egress was allowed')
print('PASS: CPU model hashes, restricted SQL role and public IP/DNS egress denial.')
"""
print(command("exec", "dockling-saas-worker-1", "python", "-c", probe).strip())
print(
    "PASS: private network only, read-only models/root, non-root user, bounded CPU/RAM/processes, no public ports or Docker socket."
)
