#!/usr/bin/env python3
"""Config priority: ENV -> manager_config.json -> hardcoded."""
import os, sys, json, shutil, subprocess, tempfile

ROOT = os.path.join(tempfile.gettempdir(), "jafj_config_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INNER = """
import os, sys, json
sys.path.insert(0, os.getcwd())
import manager_82 as M
c = M.Config()

def _mask(v):
    # never print real secrets: a value counts as a placeholder only if it
    # is one of the well-known test tokens; anything else (the hardcoded
    # production fallback) is reported as its presence + a short prefix.
    s = str(v)
    if s in ("FILE_TOKEN_abc", "ENV_TOKEN_123", "FILE_HASH_xyz", "ENV_HASH_456"):
        return s
    if s.isdigit():
        return s            # api_id is not secret
    return "<set:len=%d,prefix=%r>" % (len(s), s[:3])

print("CFG api_id=%r bot_token=%s api_hash=%s"
      % (c["api_id"], _mask(c["bot_token"]), _mask(c["api_hash"])))
"""

def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)

def run(extra_env, port):
    env = dict(os.environ)
    env["JAFJ_DATA"] = DATA
    env["DATA_DIR"] = DATA
    env["PORT"] = str(port)
    # clean connection env by default
    for k in ("BOT_TOKEN", "API_ID", "API_HASH", "ADMIN_IDS", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    env.update(extra_env)
    p = subprocess.run([sys.executable, "-c", INNER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr

def scenario_file_api_wins_and_hardcode_token_wins_over_stale_file():
    print("--- 1: file api_id/hash win, hardcoded BOT_TOKEN beats stale file token ---")
    reset()
    with open(os.path.join(DATA, "manager_config.json"), "w", encoding="utf-8") as f:
        json.dump({"bot_token": "8832561144:OLD_STALE_TOKEN", "api_id": 11111, "api_hash": "FILE_HASH_xyz"}, f)
    out = run({}, 8131)
    print(out.strip().splitlines()[-3:])
    good = (
        "api_id=11111" in out
        and "FILE_HASH_xyz" in out
        and "bot_token=<set:len=46,prefix='921'>" in out
        and "28039994" not in out
    )
    print("scenario1:", "PASS" if good else "FAIL")
    if not good:
        print(out[-2000:])
    return good

def scenario_env_wins_over_file():
    print("--- 2: env wins over file and hardcoded ---")
    reset()
    with open(os.path.join(DATA, "manager_config.json"), "w", encoding="utf-8") as f:
        json.dump({"bot_token": "FILE_TOKEN_abc", "api_id": 11111, "api_hash": "FILE_HASH_xyz"}, f)
    out = run({"BOT_TOKEN": "ENV_TOKEN_123", "API_ID": "22222", "API_HASH": "ENV_HASH_456"}, 8132)
    print(out.strip().splitlines()[-3:])
    good = "api_id=22222" in out and "ENV_TOKEN_123" in out and "ENV_HASH_456" in out
    print("scenario2:", "PASS" if good else "FAIL")
    if not good:
        print(out[-2000:])
    return good

def scenario_hardcode_fallback():
    print("--- 3: hardcoded fallback (no file, no env) ---")
    reset()
    out = run({}, 8133)
    print(out.strip().splitlines()[-3:])
    good = "api_id=28039994" in out and "bot_token=<set:len=46,prefix='921'>" in out
    print("scenario3:", "PASS" if good else "FAIL")
    if not good:
        print(out[-2000:])
    return good

def scenario_retired_env_token_ignored():
    print("--- 4: retired BOT_TOKEN in env is ignored ---")
    reset()
    out = run({"BOT_TOKEN": "8832561144:AAFSRpyaD4M9GWWsiltBMXs6acbbo6W0J-M"}, 8134)
    print(out.strip().splitlines()[-3:])
    good = "bot_token=<set:len=46,prefix='921'>" in out
    print("scenario4:", "PASS" if good else "FAIL")
    if not good:
        print(out[-2000:])
    return good

if __name__ == "__main__":
    ok = (scenario_file_api_wins_and_hardcode_token_wins_over_stale_file()
          and scenario_env_wins_over_file()
          and scenario_hardcode_fallback()
          and scenario_retired_env_token_ignored())
    print("ALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
