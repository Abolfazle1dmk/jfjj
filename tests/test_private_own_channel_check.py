#!/usr/bin/env python3
"""Private invite refs for our own channel resolve once; preview-only stays unknown."""
import asyncio
import re
import sys
import textwrap
import time
import types
from pathlib import Path
from types import SimpleNamespace

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m95_private_check", ROOT / "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source = (ROOT / "95.py").read_text(encoding="utf-8")
a = source.index("    async def peer_in_my_channel")
b = source.index("    async def confirm_peer_membership", a)
block = textwrap.dedent(source[a:b])


class CheckChatInviteRequest:
    def __init__(self, invite_hash):
        self.invite_hash = invite_hash


# The function lazily imports precisely this Telethon request.
telethon = types.ModuleType("telethon")
tl = types.ModuleType("telethon.tl")
functions = types.ModuleType("telethon.tl.functions")
messages = types.ModuleType("telethon.tl.functions.messages")
messages.CheckChatInviteRequest = CheckChatInviteRequest
for name, module in (("telethon", telethon), ("telethon.tl", tl),
                     ("telethon.tl.functions", functions),
                     ("telethon.tl.functions.messages", messages)):
    sys.modules[name] = module


class GetParticipantRequest:
    def __init__(self, channel, user_id):
        self.channel, self.user_id = channel, user_id


class UserNotParticipantError(Exception):
    pass


class FloodWaitError(Exception):
    pass


class FakeEngine:
    def __init__(self, ref):
        self.st = SimpleNamespace(prof=lambda tier: {"channel": ref if tier == "standard" else ""})
        self.db = SimpleNamespace(log=lambda *args: None)
        self.logs = []

    def log(self, *args):
        self.logs.append(args)


class FakeClient:
    def __init__(self, entity=True):
        self.entity = SimpleNamespace(id=77, access_hash=88) if entity else None
        self.invite_calls = 0
        self.participant_calls = []

    async def __call__(self, request):
        if isinstance(request, CheckChatInviteRequest):
            self.invite_calls += 1
            return SimpleNamespace(chat=self.entity)
        self.participant_calls.append(request)
        return SimpleNamespace(participant=object())


def make_ns(ref, client):
    eng = FakeEngine(ref)
    notes, reasons = [], []
    ns = {
        "asyncio": asyncio, "time": time, "eng": eng, "client": client,
        "ex_cd": m.ExCooldown(gap_min=0, gap_max=0),
        "check_gate": m.CheckGate(base_gap=0),
        "GetParticipantRequest": GetParticipantRequest,
        "UserNotParticipantError": UserNotParticipantError,
        "FloodWaitError": FloodWaitError,
        "CHECK_DEFERRED": m.CHECK_DEFERRED,
        "_warn_check_flood": {"last": 0},
        "_note_check_why": reasons.append,
        "note": lambda text: _append(notes, text),
        "secs": m.secs,
    }
    exec(block, ns)
    return eng, ns, notes, reasons


async def _append(target, value):
    target.append(value)


# Joined private own-channel ref: resolve to entity, use it, then reuse cache.
client = FakeClient(entity=True)
eng, ns, notes, reasons = make_ns("https://t.me/+OWNPRIVATE123456", client)
assert asyncio.run(ns["peer_in_my_channel"](42)) is True
assert asyncio.run(ns["peer_in_my_channel"](43)) is True
assert client.invite_calls == 1, client.invite_calls
assert len(client.participant_calls) == 2
assert all(req.channel is client.entity for req in client.participant_calls)

# Invite preview without joined chat is not a false membership verdict and
# must never issue GetParticipantRequest against an unresolved invite string.
client = FakeClient(entity=False)
eng, ns, notes, reasons = make_ns("https://t.me/+OWNPRIVATE123456", client)
assert asyncio.run(ns["peer_in_my_channel"](42)) is None
assert client.invite_calls == 1
assert not client.participant_calls
assert reasons and "کانالِ من" in reasons[-1], reasons
print("private own-channel membership resolution: PASS")
