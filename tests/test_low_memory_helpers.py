#!/usr/bin/env python3
"""Regression tests for container-aware memory checks and streaming ZIP restore."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(tempfile.gettempdir(), "jafj_low_memory_helpers_test")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

INNER = textwrap.dedent("""
    import os, tempfile, zipfile
    import manager_82 as M

    def put(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="ascii") as f:
            f.write(text)

    # cgroup v2, nested below the mount root: report container headroom, not
    # the host's much larger /proc/meminfo value.
    root = tempfile.mkdtemp(prefix="cg-v2-")
    try:
        # Parent has more headroom; the nested tenant limit is the effective one.
        put(os.path.join(root, "memory.current"), str(100 * 1024 * 1024))
        put(os.path.join(root, "memory.max"), str(600 * 1024 * 1024))
        put(os.path.join(root, "tenant", "memory.current"), str(200 * 1024 * 1024))
        put(os.path.join(root, "tenant", "memory.max"), str(300 * 1024 * 1024))
        proc = os.path.join(root, "proc-cgroup")
        put(proc, "0::/tenant" + chr(10))
        assert M._cgroup_memory_available_mb(root, proc) == 100
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)

    # A nested leaf may be unlimited while a parent carries the effective
    # memory cap. The helper must walk all cgroup ancestors, not just the leaf.
    root = tempfile.mkdtemp(prefix="cg-v2-parent-")
    try:
        put(os.path.join(root, "memory.max"), "max")
        put(os.path.join(root, "memory.current"), str(0))
        put(os.path.join(root, "tenant", "memory.max"), str(256 * 1024 * 1024))
        put(os.path.join(root, "tenant", "memory.current"), str(176 * 1024 * 1024))
        put(os.path.join(root, "tenant", "worker", "memory.max"), "max")
        put(os.path.join(root, "tenant", "worker", "memory.current"), str(8 * 1024 * 1024))
        proc = os.path.join(root, "proc-cgroup")
        put(proc, "0::/tenant/worker" + chr(10))
        assert M._cgroup_memory_available_mb(root, proc) == 80
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # cgroup v1 path and unlimited sentinel.
    root = tempfile.mkdtemp(prefix="cg-v1-")
    try:
        put(os.path.join(root, "memory", "group-a", "memory.usage_in_bytes"),
            str(32 * 1024 * 1024))
        put(os.path.join(root, "memory", "group-a", "memory.limit_in_bytes"),
            str(128 * 1024 * 1024))
        proc = os.path.join(root, "proc-cgroup")
        put(proc, "5:cpu,memory:/group-a" + chr(10))
        assert M._cgroup_memory_available_mb(root, proc) == 96
        put(os.path.join(root, "memory", "group-a", "memory.limit_in_bytes"),
            str(1 << 62))
        assert M._cgroup_memory_available_mb(root, proc) is None
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Extraction must use ZipExtFile streaming rather than ZipFile.read, which
    # allocates a complete uncompressed database/session in memory.
    tmp = tempfile.mkdtemp(prefix="zip-stream-")
    try:
        archive = os.path.join(tmp, "backup.zip")
        dest = os.path.join(tmp, "out", "large.db")
        payload = b"z" * (3 * 1024 * 1024)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manager.db", payload)
        original_read = zipfile.ZipFile.read
        def forbidden_read(*a, **kw):
            raise AssertionError("ZipFile.read must not be used for extraction")
        zipfile.ZipFile.read = forbidden_read
        try:
            with zipfile.ZipFile(archive, "r") as z:
                copied = M._extract_zip_member_streaming(z, "manager.db", dest)
        finally:
            zipfile.ZipFile.read = original_read
        assert copied == len(payload)
        with open(dest, "rb") as f:
            assert f.read() == payload
        assert not os.path.exists(dest + ".restore_tmp")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("PASS cgroup v2 memory headroom")
    print("PASS cgroup v1 memory headroom and unlimited limit")
    print("PASS streaming ZIP extraction without ZipFile.read")
""")


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP)
    os.makedirs(DATA)
    shutil.copy2(os.path.join(REPO, "manager_82.py"), APP)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ)
    env.update(DATA_DIR=DATA, PORT=str(port), JAFJ_SKIP_GH_SYNC="1")
    p = subprocess.run([sys.executable, "-c", INNER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=30)
    print(p.stdout, end="")
    if p.returncode:
        print(p.stderr, end="", file=sys.stderr)
        raise SystemExit(p.returncode)
    if "PASS streaming ZIP extraction" not in p.stdout:
        raise SystemExit("low-memory helper test did not complete")
    shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
