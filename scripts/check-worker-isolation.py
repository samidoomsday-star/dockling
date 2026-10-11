"""Assert actual local worker container restrictions without exposing its credentials."""

import argparse
import json
import subprocess


def command(*args: str) -> str:
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--rehearsal", action="store_true")
args = parser.parse_args()
prefix = "dockling-staging-rehearsal" if args.rehearsal else "dockling-saas"
container = prefix + "-worker-1"
private_network = prefix + "_worker-private"
worker = json.loads(command("inspect", container))[0]
host = worker["HostConfig"]
assert worker["State"]["Running"]
assert worker["Config"]["User"] == "1000:1000"
assert host["ReadonlyRootfs"] and host["Memory"] == 4 * 1024**3
assert host["NanoCpus"] == 2 * 10**9 and host["PidsLimit"] == 128
assert "ALL" in host["CapDrop"] and "no-new-privileges:true" in host["SecurityOpt"]
assert set(worker["NetworkSettings"]["Networks"]) == {private_network}
network = json.loads(command("network", "inspect", private_network))[0]
assert network["Internal"]
assert host["Dns"] == ["127.0.0.1"]
assert not worker["NetworkSettings"]["Ports"]
mounts = {"/models", "/broker", "/private/ca.pem"} if args.rehearsal else {"/models", "/broker"}
assert {m["Destination"] for m in worker["Mounts"]} == mounts
assert all(not m["RW"] for m in worker["Mounts"])
probe = """
import socket
from pathlib import Path
from sqlalchemy import text
from stmtconv.config import load_worker_settings
from stmtconv.model_setup import load_manifest,verify_artifacts
from stmtconv.web.database import worker_database
cfg=load_worker_settings()
verify_artifacts(Path('/models'),load_manifest())
engine=worker_database(cfg)
with engine.connect() as db:
    assert db.scalar(text('SELECT current_user'))=='dockling_worker'
    if cfg.mode=='production':
        assert db.scalar(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')) is True
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
print(command("exec", container, "python", "-c", probe).strip())
print(
    "PASS: private network only, read-only models/root, non-root user, bounded CPU/RAM/processes, no public ports or Docker socket."
)
