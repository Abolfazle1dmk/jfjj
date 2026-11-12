#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«اصلا چیزی تعیین نکردم… ولی تبادل سریع می‌گه از قبل آماده است»

باگِ گزارش‌شده دو تکه داشت و هر دو با رفتارِ واقعیِ ۹۵.py (تلگرامِ قلابی)
اینجا سنجیده می‌شوند:

  A) جای‌نگهدارهای راهنما
     - `کانال @channel` و `افزودن گروه @group` (همان «دستورات آماده»)
       نباید ذخیره شوند؛ قبلاً می‌شدند و کاربری که «هیچ چیزی تعیین
       نکرده بود» یک‌دفعه تبادلِ «آماده» می‌دید.
     - `@mychannel` / `@mygroup` که خودِ ربات در پنل نمونه می‌دهد
       هنوز معتبرند (این‌ها آیدیِ واقعیِ کاربرند).

  B) ویرایشِ تنظیمِ آماده
     - `تبادل سریع` روی تنظیمِ آماده دیگر «قفل» نمی‌کند؛ خلاصه + `ویرایش`.
     - «ویرایش کانال» فقط کانال را عوض می‌کند: گروه، پشتیبان و
       وضعیتِ روشن/خاموش دست‌نخورده می‌مانند.
     - «ویرایش گروه» / «ویرایش پشتیبان» هم فقط همان فیلد را می‌نویسند.
     - هیچ ویرایشی تبادلِ خاموش را بی‌اجازه روشن نمی‌کند.
     - فرمانِ عادی وسطِ ویرایش (مثل `پنل`) بلعیده نمی‌شود.

اجرا:  python3 tests/test_quick_exchange_edit.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(tempfile.gettempdir(), "jafj_qe_edit_run")

DRIVER = textwrap.dedent('''
    import asyncio, importlib.util, os, sys, types

    REPO = os.environ["REPO"]
    os.chdir(os.environ["DATA"])

    sent = []
    deleted = []
    CLIENTS = []
    FAILS = []
    CHECKS = [0]

    def check(cond, name):
        CHECKS[0] += 1
        print(("OK " if cond else "FAIL ") + name)
        if not cond:
            FAILS.append(name)

    class FakeMsg:
        def __init__(self, mid, text=""):
            self.id = mid
            self.raw_text = text

    class FakeClient:
        def __init__(self, *a, **k):
            self.handlers = []
            self._id = 10000
            self._done = asyncio.Event()
            CLIENTS.append(self)
        def on(self, builder):
            def deco(fn):
                self.handlers.append((builder, fn))
                return fn
            return deco
        async def start(self, phone=None, **k):
            return self
        async def get_me(self):
            return types.SimpleNamespace(first_name="Test", username="tester", id=555)
        async def send_message(self, peer, text=None, **k):
            self._id += 1
            msg = FakeMsg(self._id, text or "")
            if str(peer) in ("me", "555"):
                sent.append(msg)
            return msg
        async def delete_messages(self, peer, ids):
            deleted.append(list(ids))
            return len(list(ids))
        async def run_until_disconnected(self):
            await self._done.wait()
        async def get_entity(self, x):
            return types.SimpleNamespace(id=9001, access_hash=1234, title="Chan")
        async def iter_messages(self, group, limit=None, **k):
            if False:
                yield None
        def __call__(self, req):
            async def _done():
                return types.SimpleNamespace(
                    chats=[types.SimpleNamespace(id=9001, access_hash=1234,
                                                 title="Chan")])
            return _done()
        def __getattr__(self, name):
            async def _stub(*a, **k):
                return None
            return _stub

    class NewMsgBuilder:
        def __init__(self, *a, **k):
            self.args, self.kwargs = a, k

    tl = types.ModuleType("telethon")
    tl.TelegramClient = FakeClient
    tl.events = types.SimpleNamespace(NewMessage=NewMsgBuilder)
    tl.errors = types.SimpleNamespace(**{
        n: type(n, (Exception,), {}) for n in (
            "FloodWaitError", "SlowModeWaitError", "ChatWriteForbiddenError",
            "ChannelPrivateError", "UsernameNotOccupiedError", "RPCError",
            "UserNotParticipantError", "UserAlreadyParticipantError",
            "InviteHashExpiredError", "InviteHashInvalidError",
            "ChannelsTooMuchError", "InviteRequestSentError")})
    tlchan = types.ModuleType("telethon.tl.functions.channels")
    tlmsg = types.ModuleType("telethon.tl.functions.messages")
    def _req_class(name):
        class _R:
            def __init__(self, *a, **k):
                self.args, self.kwargs = a, k
        _R.__name__ = name
        return _R
    for n in ("JoinChannelRequest", "LeaveChannelRequest", "GetParticipantRequest"):
        setattr(tlchan, n, _req_class(n))
    tlmsg.ImportChatInviteRequest = _req_class("ImportChatInviteRequest")
    tlf = types.ModuleType("telethon.tl.functions")
    tlf.channels, tlf.messages = tlchan, tlmsg
    tltl = types.ModuleType("telethon.tl")
    tltl.functions = tlf
    tl.tl = tltl
    for name, mod in (("telethon", tl), ("telethon.events", tl.events),
                      ("telethon.errors", tl.errors), ("telethon.tl", tltl),
                      ("telethon.tl.functions", tlf),
                      ("telethon.tl.functions.channels", tlchan),
                      ("telethon.tl.functions.messages", tlmsg)):
        sys.modules[name] = mod

    spec = importlib.util.spec_from_file_location(
        "selfbot95", os.path.join(REPO, "95.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DRY_RUN = False

    eng = mod.Engine()
    creds = {"api_id": 1, "api_hash": "h", "phone": "+989120000000"}
    CLIENT = [None]

    class Ev:
        def __init__(self, text, mid):
            self.raw_text = text
            self.out = True
            self.sender_id = 555
            self.message = types.SimpleNamespace(id=mid)
            self.chat_id = 555
            self.id = mid
        async def get_reply_message(self):
            return None
        async def get_chat(self):
            return types.SimpleNamespace(id=555)
        async def reply(self, t):
            return await CLIENT[0].send_message("me", t)

    def reset(channel="", groups=(), enabled=False):
        eng.st.prof("standard")["channel"] = channel
        eng.st.prof("vip")["channel"] = ""
        x = eng.ex_cfg()
        x["groups"] = list(groups)
        x["group_failover_on"] = len(groups) > 1
        x["_group_failover_active_index"] = 0
        x["_group_failover_last_activity"] = 0
        x["enabled"] = bool(enabled)
        x["msg_ok"] = "جوین شدم ✅"
        eng.st["risk"]["_auto_off"] = False
        eng.st.save()

    async def cmd(text, mid=[30000]):
        mid[0] += 1
        before = len(sent)
        await CLIENT[0].handlers_me(Ev(text, mid[0]))
        return sent[before:]

    async def say(text):
        out = await cmd(text)
        return out[-1].raw_text if out else ""

    async def main():
        task = asyncio.create_task(mod.connect_and_run(eng, creds))
        client = None
        for _ in range(600):
            if CLIENTS:
                client = CLIENTS[-1]
                if client.handlers:
                    break
            await asyncio.sleep(0.02)
        CLIENT[0] = client
        me = None
        for b, fn in client.handlers:
            if b.kwargs.get("chats") == "me":
                me = fn
        if me is None:
            print("FAIL no saved-messages handler")
            return 1
        client.handlers_me = me

        # ═════════ A) جای‌نگهدارهای راهنما ذخیره نمی‌شوند ═════════
        reset()
        out = await say("کانال @channel")
        check("نمونهٔ راهنما" in out, "کانال @channel is refused as a placeholder")
        check(not eng.st.prof("standard")["channel"],
              "کانال @channel is NOT stored")

        out = await say("افزودن گروه @group")
        check("معتبر" in out or "نمونه" in out, "افزودن گروه @group is refused")
        check(not eng.ex_cfg()["groups"], "افزودن گروه @group is NOT stored")

        # ویزارد هم همین جای‌نگهدارها را رد می‌کند
        await say("تبادل سریع")
        out = await say("@channel")
        check("معتبر نیست" in out, "wizard rejects @channel as the channel")
        check(not eng.st.prof("standard")["channel"],
              "wizard does not store @channel")
        out = await say("@group")
        check("معتبر نیست" in out, "wizard rejects @group as the channel")
        await say("لغو")

        # نمونه‌های خودِ ربات (@mychannel/@mygroup) باید معتبر بمانند
        reset()
        await say("تبادل سریع")
        out = await say("@mychannel")
        check("گروه اصلی" in out, "@mychannel still accepted (bot's own example)")
        out = await say("@mygroup")
        check("پشتیبان" in out, "@mygroup still accepted")
        out = await say("رد")
        check("تبادل آماده‌ست" in out, "setup with @mychannel/@mygroup works")
        check(eng.ex_cfg()["enabled"] is True, "fresh setup turns exchange on")

        # ═════════ B) تنظیمِ آماده قابلِ ویرایش است ═════════
        reset(channel="@real_chan", groups=["@real_group"], enabled=True)
        out = await say("تبادل سریع")
        check("از قبل آماده" in out, "ready setup is still recognised")
        check("ویرایش" in out, "ready setup offers an edit path")
        check("کانال: @real_chan" in out, "ready summary shows the real channel")
        check("گروه اصلی: @real_group" in out, "ready summary shows the real group")

        out = await say("ویرایش")
        check("کدام را عوض کنم" in out, "ویرایش opens the field picker")
        check("کانال" in out and "گروه اصلی" in out and "پشتیبان" in out,
              "picker lists channel / group / backup")

        out = await say("ویرایش کانال")
        check("کانال" in out and "بفرست" in out, "picking channel asks for the value")
        out = await say("@better_chan")
        check("تغییر ذخیره شد" in out, "channel edit is confirmed")
        check(eng.st.prof("standard")["channel"] == "@better_chan",
              "channel edit changes the channel")
        check(eng.ex_cfg()["groups"] == ["@real_group"],
              "channel edit leaves the group untouched")
        check(eng.ex_cfg()["enabled"] is True,
              "channel edit keeps exchange on (no surprise toggling)")

        out = await say("تبادل سریع")
        out = await say("ویرایش گروه")
        out = await say("@better_group")
        check(eng.ex_cfg()["groups"] == ["@better_group"],
              "group edit changes only the primary group")
        check(eng.st.prof("standard")["channel"] == "@better_chan",
              "group edit leaves the channel untouched")

        out = await say("تبادل سریع")
        out = await say("ویرایش پشتیبان")
        out = await say("@backup_grp")
        check(eng.ex_cfg()["groups"] == ["@better_group", "@backup_grp"],
              "backup edit adds the optional backup group")
        check(eng.ex_cfg()["group_failover_on"] is True,
              "adding a backup opts into failover")
        check(eng.st.prof("standard")["channel"] == "@better_chan",
              "backup edit leaves the channel untouched")

        # یک پیام هم برای «ویرایش» و انتخابِ فیلد
        out = await say("تبادل سریع")
        out = await say("ویرایش کانال")
        out = await say("@one_shot_chan")
        check(eng.st.prof("standard")["channel"] == "@one_shot_chan",
              "field choice in the same message works")

        # ═════════ C) ویرایش هرگز بی‌اجازه روشن نمی‌کند ═════════
        reset(channel="@off_chan", groups=["@off_group"], enabled=False)
        out = await say("تبادل سریع")
        check("فقط روشنش کن" in out, "ready-but-off still says how to turn it on")
        check("تبادل روشن" in out, "ready-but-off shows the exact command")
        out = await say("ویرایش کانال")
        out = await say("@still_off")
        check(eng.st.prof("standard")["channel"] == "@still_off",
              "edit stores the new channel while off")
        check(eng.ex_cfg()["enabled"] is False,
              "edit does NOT silently enable a disabled exchange")
        check("خاموش" in out, "edit summary reports the exchange as off")

        out = await say("تبادل سریع")
        out = await say("لغو")
        check(eng.st.prof("standard")["channel"] == "@still_off",
              "cancel on the ready prompt changes nothing")
        check(eng.ex_cfg()["enabled"] is False, "cancel keeps exchange off")

        # ═════════ D) فرمانِ عادی وسطِ ویرایش بلعیده نمی‌شود ═════════
        reset(channel="@nav_chan", groups=["@nav_group"], enabled=True)
        await say("تبادل سریع")
        out = await say("پنل")
        check("💎 جفج" in out, "پنل still works from the ready/edit prompt")
        out = await say("تبادل")
        check("🔁 تبادل" in out, "تبادل page still works from the ready prompt")

        await say("تبادل سریع")
        out = await say("ویرایش")
        out = await say("تبادل")
        check("🔁 تبادل" in out, "تبادل page works from the field picker")
        check(eng.st.prof("standard")["channel"] == "@nav_chan",
              "leaving the picker with a command changes nothing")

        client._done.set()
        try:
            await asyncio.wait_for(task, timeout=15)
        except Exception:
            pass

        print("CHECKS %d" % CHECKS[0])
        print("FAILED %d" % len(FAILS))
        return 0

    sys.exit(asyncio.run(main()))
''')


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(ROOT)
    env = dict(os.environ, REPO=REPO, DATA=ROOT)
    r = subprocess.run([sys.executable, "-c", DRIVER], env=env,
                       text=True, capture_output=True, timeout=180)
    keep = [line for line in r.stdout.splitlines()
            if line.startswith(("OK ", "FAIL ", "CHECKS ", "FAILED "))]
    print("\n".join(keep) if keep else (r.stdout + r.stderr)[-4000:])

    checks = failed = 0
    for line in r.stdout.splitlines():
        if line.startswith("CHECKS "):
            checks = int(line.split()[1])
        elif line.startswith("FAILED "):
            failed = int(line.split()[1])

    problems = []
    if r.returncode != 0:
        problems.append("driver exited %d" % r.returncode)
        if not keep:
            print((r.stdout + r.stderr)[-4000:])
    if checks < 39:
        problems.append("expected at least 39 checks, got %d" % checks)
    if failed:
        problems.append("%d checks failed" % failed)

    print()
    if problems:
        print("❌ FAILED: " + " | ".join(problems))
        return 1
    print("✅ PASS  quick-exchange edit + placeholder-guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
