#!/usr/bin/env python3
"""Pure tests for the optional, ordered exchange-group failover policy."""
import ast
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "95.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
names = {"group_failover_index", "group_failover_scan_groups", "group_failover_after_scan",
         "select_capacity_leave_candidate", "same_peer_ref", "_safe_id",
         # کمکی‌های انتخابِ کاندید (انتخاب حالا خطی است، نه O(n²))
         "peer_ref_key", "_capacity_pool", "_capacity_candidates"}
selected = [node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names]
defaults_node = next(node for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "DEFAULTS"
                            for target in node.targets))
namespace = {"re": re}
exec(compile(ast.Module(body=[defaults_node], type_ignores=[]), str(SOURCE), "exec"), namespace)
exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
index = namespace["group_failover_index"]
scan_groups = namespace["group_failover_scan_groups"]
after_scan = namespace["group_failover_after_scan"]
select_candidate = namespace["select_capacity_leave_candidate"]

checks = 0
failures = []


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        failures.append(message)
        print("FAIL", message)
    else:
        print("OK", message)


groups = ["@primary", "@backup"]
exchange_defaults = namespace["DEFAULTS"]["exchange"]
check(exchange_defaults["group_failover_on"] is False,
      "new and migrated settings keep failover disabled by default")
check(exchange_defaults["group_failover_after_sec"] == 300,
      "default inactivity window is five minutes")
check(exchange_defaults["auto_leave_completed_on_limit"] is True,
      "capacity cleanup is enabled for an explicit Telegram limit error")

# Legacy/default behavior: disabled is a no-op, even with two configured groups.
legacy = {"group_failover_on": False}
check(index(legacy, groups, 1000) is None, "disabled mode does not select a failover group")
check(scan_groups(legacy, groups, 1000) == groups,
      "disabled mode continues scanning every legacy group")
check(after_scan(legacy, groups, 1000, found=False) is None,
      "disabled mode never advances the scan group")
check("_group_failover_active_index" not in legacy,
      "legacy config is not mutated when failover is disabled")

# Invalid one-group state safely behaves like the old scanner.
one_group = {"group_failover_on": True}
check(index(one_group, ["@primary"], 1000) is None,
      "a single group cannot activate failover")

# A missing timestamp initializes a full inactivity window; it does not switch at once.
active = {"group_failover_on": True, "group_failover_after_sec": 300}
check(index(active, groups, 1000) == 0, "the first ordered group is primary")
check(scan_groups(active, groups, 1000) == ["@primary"],
      "active failover scans only the primary group")
check(active["_group_failover_last_activity"] == 1000,
      "first activation starts a fresh grace window")
check(after_scan(active, groups, 1299, found=False) is None,
      "no switch occurs before the configured quiet interval")

# A fresh link resets the timer, and only a quiet interval advances to backup.
check(after_scan(active, groups, 1300, found=True) is None,
      "a newly discovered exchange link keeps the current group active")
check(active["_group_failover_last_activity"] == 1300,
      "fresh activity refreshes the inactivity timestamp")
check(after_scan(active, groups, 1599, found=False) is None,
      "the refreshed timer is respected")
check(after_scan(active, groups, 1600, found=False) == (0, 1),
      "quiet primary advances to the backup group")
check(active["_group_failover_active_index"] == 1,
      "backup becomes the active scan group")
check(scan_groups(active, groups, 1600) == ["@backup"],
      "after failover, only the backup group is scanned")
check(active["_group_failover_last_activity"] == 1600,
      "backup gets its own full quiet interval")

# Cyclic failover supports ordered additional groups; failures do not count as inactivity.
check(after_scan(active, groups, 1900, found=False, scan_error=True) is None,
      "a scan/API error cannot trigger failover")
check(after_scan(active, groups, 1900, found=False) == (1, 0),
      "a stale backup rotates to the primary on the next interval")

# Invalid stored index is corrected safely.
invalid = {"group_failover_on": True, "_group_failover_active_index": 99,
           "_group_failover_last_activity": 2000}
check(index(invalid, groups, 2000) == 0, "out-of-range active index resets to primary")
check(invalid["_group_failover_active_index"] == 0,
      "corrected primary index is persisted in settings state")

# Capacity cleanup may only use old, reciprocated exchanges outside monitoring.
records = [
    {"id": 1, "status": "joined", "direction": "out", "peer_id": 101,
     "peer_joined_at": 900, "joined_at": 100, "chat_id": 1001,
     "link": "@oldchan", "next_reminder": 0, "watching": False},
    {"id": 2, "status": "joined", "direction": "in", "peer_id": 102,
     "joined_at": 200, "chat_id": 1002, "link": "@newchan",
     "next_reminder": 0, "watching": False},
    {"id": 3, "status": "joined", "direction": "out", "peer_id": 103,
     "peer_joined_at": 950, "joined_at": 300, "chat_id": 1003,
     "link": "@stillwatched", "next_reminder": 0, "watching": True},
    {"id": 4, "status": "joined", "direction": "out", "peer_id": 104,
     "peer_joined_at": None, "joined_at": 50, "chat_id": 1004,
     "link": "@notreciprocal", "next_reminder": 0, "watching": False},
]
candidate = select_candidate(records, own_channels=["@mychannel"])
check(candidate and candidate["id"] == 1,
      "a reciprocal exchange is eligible without waiting for the 24-hour watch window")
check(select_candidate(records, exclude_id=1)["id"] == 2,
      "the currently retried exchange is excluded from cleanup")

own_channel_record = dict(records[0], id=5, link="@mychannel", chat_id=1005)
check(select_candidate([own_channel_record], own_channels=["@mychannel"]) is None,
      "cleanup never leaves one of the user's own channels")

reminder_record = dict(records[0], id=6, link="@reminderchan", chat_id=1006,
                        next_reminder=1200)
check(select_candidate([reminder_record]) is None,
      "an exchange with an active reminder is not eligible")

duplicate_record = dict(records[0], id=7, link="@oldchan", chat_id=1001)
check(select_candidate([records[0], duplicate_record]) is None,
      "duplicate records for the same joined channel are left untouched")

print(f"CHECKS {checks}")
print(f"FAILED {len(failures)}")
raise SystemExit(1 if failures else 0)
