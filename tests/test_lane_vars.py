#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تستِ ایستا: «استفاده از متغیرِ محلی که هنوز مقدار نگرفته» در حلقه‌های تبادل.

باگِ واقعی که این تست می‌گیرد
──────────────────────────────
داخل `membership_loop`، در شاخه‌ی «نتیجه نامشخص» از متغیرِ `_conf` استفاده
شده بود، در حالی که `_conf` فقط داخلِ شاخه‌ی «status == joined» (یا شاخه‌ی
«strikes پر شده») ساخته می‌شد:

    elif still is False:
        ...
        elif rec.get("status") == "joined":
            _conf = await confirm_peer_membership(...)
    else:
        if _conf is CHECK_DEFERRED:      # ← NameError در حالتِ نامشخص

نتیجه‌ی عملی: هر بار که چکِ عضویت «نامشخص» می‌شد (فلود/خطای API)، کلِ دورِ
حلقه با NameError می‌افتاد؛ نه شمارنده‌ی unk_streak بالا می‌رفت، نه فاصله‌ی
۱۰ دقیقه‌ای اعمال می‌شد، نه لفت/«نیومدی» پیش می‌رفت. اگر هم `_conf` از
رکوردِ قبلی مانده بود، تصمیمِ رکوردِ تازه با نتیجه‌ی رکوردِ قبلی گرفته
می‌شد (لفتِ اشتباه).

این تست بدون اجرای تلگرام، با تحلیلِ جریانِ داده روی AST بررسی می‌کند که
هر «خواندنِ» متغیرِ محلی، روی همه‌ی مسیرها قبلاً مقدار گرفته باشد.
"""
import ast
import io
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "95.py")

TARGET = "membership_loop"


# ───────────────────────── ابزارهای تحلیل ─────────────────────────
def bound_names(node):
    """اسم‌هایی که یک «هدفِ انتساب» می‌بندد."""
    out = set()

    def walk(t):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                walk(e)
        elif isinstance(t, ast.Starred):
            walk(t.value)

    walk(node)
    return out


class Flow(ast.NodeVisitor):
    """جریانِ «قطعاً مقدار گرفته» روی یک تابع.

    فقط اسم‌هایی بررسی می‌شوند که *محلیِ همین تابع* هستند؛ اسم‌های بیرونی
    (closure/گلوبال/بیلدین) کنار گذاشته می‌شوند تا تست پرصدا نشود.
    """

    def __init__(self, fn):
        self.fn = fn
        self.locals = set()
        self.problems = []          # [(lineno, name)]
        self._collect_locals(fn)

    # اسم‌هایی که خودِ تابع (در هر عمقی، جز توابعِ تودرتو) می‌بندد
    def _collect_locals(self, fn):
        for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs:
            self.locals.add(a.arg)
        if fn.args.vararg:
            self.locals.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            self.locals.add(fn.args.kwarg.arg)
        for node in ast.walk(fn):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda, ast.ClassDef)) and node is not fn:
                # توابعِ تودرتو اسکوپِ جدا دارند؛ فقط اسمِ خودشان بسته می‌شود
                if getattr(node, "name", None):
                    self.locals.add(node.name)
                continue
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    self.locals |= bound_names(t)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                self.locals |= bound_names(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                self.locals |= bound_names(node.target)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for it in node.items:
                    if it.optional_vars is not None:
                        self.locals |= bound_names(it.optional_vars)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                self.locals.add(node.name)
            elif isinstance(node, (ast.comprehension,)):
                self.locals |= bound_names(node.target)
            elif isinstance(node, ast.NamedExpr):
                self.locals |= bound_names(node.target)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for al in node.names:
                    self.locals.add((al.asname or al.name).split(".")[0])
        # پارامترهای lambda/comprehension هم محلی‌اند ولی چون در
        # comprehension از locals حذفشان می‌کنیم، این‌جا مهم نیست.

    # ── خواندن‌ها ──
    def check_expr(self, node, assigned, extra=frozenset()):
        """همه‌ی Name های Load داخلِ یک عبارت را بررسی می‌کند."""
        if node is None:
            return
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, ast.Name):
                if (isinstance(n.ctx, ast.Load) and n.id in self.locals
                        and n.id not in assigned and n.id not in extra):
                    self.problems.append((n.lineno, n.id))
            elif isinstance(n, ast.Lambda):
                # بدنه‌ی لامبدا اسکوپِ جداست؛ فقط دیفالت‌ها
                for d in n.args.defaults + [x for x in n.args.kw_defaults if x]:
                    self.check_expr(d, assigned)
            elif isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                               ast.DictComp)):
                gens = set()
                for g in n.generators:
                    gens |= bound_names(g.target)
                    self.check_expr(g.iter, assigned, gens)
                    for cond in g.ifs:
                        self.check_expr(cond, assigned, set(gens) | set(extra))
                elts = [n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]
                for e in elts:
                    self.check_expr(e, assigned, set(gens) | set(extra))
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            else:
                for ch in ast.iter_child_nodes(n):
                    stack.append(ch)

    # ── بلوک‌ها: برمی‌گرداند «قطعاً مقدار گرفته» در پایانِ بلوک ──
    def block(self, stmts, assigned):
        cur = set(assigned)
        for st in stmts:
            cur = self.stmt(st, cur)
            if isinstance(st, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                # بقیه‌ی بلوک اجرا نمی‌شود؛ برای جلوگیری از گزارشِ کاذب،
                # با همه‌ی اسم‌ها ادامه می‌دهیم.
                cur = set(self.locals) | cur
        return cur

    def stmt(self, st, assigned):
        # خواندن‌های همین دستور
        if isinstance(st, ast.Assign):
            self.check_expr(st.value, assigned)
            for t in st.targets:
                if not isinstance(t, (ast.Name, ast.Tuple, ast.List, ast.Starred)):
                    self.check_expr(t, assigned)      # x[i] = ... / x.a = ...
            return assigned | set().union(*(bound_names(t) for t in st.targets))
        if isinstance(st, ast.AugAssign):
            self.check_expr(st.value, assigned)
            if isinstance(st.target, ast.Name) and st.target.id in self.locals:
                return assigned | {st.target.id}
            self.check_expr(st.target, assigned)
            return assigned
        if isinstance(st, ast.AnnAssign):
            if st.value is not None:
                self.check_expr(st.value, assigned)
                return assigned | bound_names(st.target)
            return assigned
        if isinstance(st, ast.Expr):
            self.check_expr(st.value, assigned)
            return assigned
        if isinstance(st, (ast.For, ast.AsyncFor)):
            self.check_expr(st.iter, assigned)
            inner = self.block(st.body, assigned | bound_names(st.target))
            end = assigned | bound_names(st.target) | inner
            end = self.block(st.orelse, end)
            return end
        if isinstance(st, ast.While):
            self.check_expr(st.test, assigned)
            self.block(st.body, assigned)
            return self.block(st.orelse, assigned)
        if isinstance(st, ast.If):
            self.check_expr(st.test, assigned)
            a = self.block(st.body, assigned)
            b = self.block(st.orelse, assigned) if st.orelse else assigned
            return a & b
        if isinstance(st, ast.Try):
            body_end = self.block(st.body, assigned)
            else_end = self.block(st.orelse, body_end) if st.orelse else body_end
            ends = [else_end]
            for h in st.handlers:
                base = assigned | ({h.name} if h.name else set())
                self.check_expr(h.type, assigned)
                ends.append(self.block(h.body, base))
            end = set.intersection(*[set(e) for e in ends]) if ends else assigned
            if st.finalbody:
                end = self.block(st.finalbody, end)
            return end
        if isinstance(st, (ast.With, ast.AsyncWith)):
            cur = assigned
            for it in st.items:
                self.check_expr(it.context_expr, cur)
                if it.optional_vars is not None:
                    cur = cur | bound_names(it.optional_vars)
            return self.block(st.body, cur)
        if isinstance(st, (ast.Return, ast.Raise)):
            if getattr(st, "value", None) is not None:
                self.check_expr(st.value, assigned)
            if getattr(st, "exc", None) is not None:
                self.check_expr(st.exc, assigned)
            return assigned
        if isinstance(st, ast.Delete):
            return assigned
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # دیفِ تودرتو: بدنه‌اش اسکوپِ جداست؛ فقط دیفالت‌ها/دکوریتورها
            for d in st.decorator_list:
                self.check_expr(d, assigned)
            for d in st.args.defaults + [x for x in st.args.kw_defaults if x]:
                self.check_expr(d, assigned)
            return assigned | {st.name}
        if isinstance(st, ast.ClassDef):
            return assigned | {st.name}
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            add = {(al.asname or al.name).split(".")[0] for al in st.names}
            return assigned | add
        if isinstance(st, (ast.Global, ast.Nonlocal)):
            return assigned
        if isinstance(st, ast.Assert):
            self.check_expr(st.test, assigned)
            self.check_expr(st.msg, assigned)
            return assigned
        # بقیه (Pass/Break/Continue/Import/...) → فقط فرزندان را بگرد
        for ch in ast.iter_child_nodes(st):
            if isinstance(ch, ast.stmt):
                assigned = self.stmt(ch, assigned)
            elif isinstance(ch, ast.expr):
                self.check_expr(ch, assigned)
        return assigned

    def run(self):
        seed = set()
        for a in (self.fn.args.args + self.fn.args.kwonlyargs
                  + self.fn.args.posonlyargs):
            seed.add(a.arg)
        if self.fn.args.vararg:
            seed.add(self.fn.args.vararg.arg)
        if self.fn.args.kwarg:
            seed.add(self.fn.args.kwarg.arg)
        self.block(self.fn.body, seed)
        return self.problems


def analyze(source_text, func_name=TARGET):
    tree = ast.parse(source_text)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == func_name:
            target = node
            break
    if target is None:
        raise SystemExit(f"تابعِ {func_name} پیدا نشد")
    return Flow(target).run()


# ───────────────────────── اجرای تست ─────────────────────────
FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


def main():
    src = io.open(SRC, encoding="utf-8").read()

    probs = analyze(src)
    check("V1: هیچ خواندنِ «قبل از مقدارگیری» در membership_loop نیست",
          probs == [], probs)

    # همان بررسی روی **همه‌ی** توابعِ 95.py — باگِ `_conf` فقط یک نمونه بود
    tree = ast.parse(src)
    every = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for l, n in Flow(node).run():
                if n != "self":
                    every.append((node.name, l, n))
    check("V1b: هیچ تابعی در 95.py خواندنِ قبل از مقدارگیری ندارد",
          every == [], every[:8])

    # ── خودِ ابزار هم باید باگِ واقعی را بگیرد، وگرنه تستِ توخالی است ──
    broken = src.replace(
        "                        if still is CHECK_DEFERRED:",
        "                        if _conf is CHECK_DEFERRED:", 1)
    check("V2: نمونه‌ی باگ‌دار عوض شد", broken != src)
    bprobs = analyze(broken)
    names = sorted({n for _, n in bprobs})
    check("V2: ابزار همان باگِ `_conf` را می‌گیرد", "_conf" in names, bprobs)

    # ── سالم‌بودنِ الگوی متعارف: انتساب در هر دو شاخه ──
    ok_sample = '''
async def membership_loop():
    for rec in items:
        if cond:
            v = 1
        else:
            v = 2
        use(v)
'''
    check("V3: if/else با انتساب در هر دو شاخه سالم است",
          analyze(ok_sample, "membership_loop") == [],
          analyze(ok_sample, "membership_loop"))

    bad_sample = '''
async def membership_loop():
    for rec in items:
        if cond:
            v = 1
        use(v)
'''
    check("V4: انتسابِ فقط داخلِ یک شاخه گرفته می‌شود",
          [n for _, n in analyze(bad_sample, "membership_loop")] == ["v"],
          analyze(bad_sample, "membership_loop"))

    try_sample = '''
async def membership_loop():
    for rec in items:
        try:
            v = load()
        except Exception:
            v = None
        use(v)
'''
    check("V5: try/except که در هر دو مسیر مقدار می‌دهد سالم است",
          analyze(try_sample, "membership_loop") == [],
          analyze(try_sample, "membership_loop"))

    print()
    if FAILS:
        print("FAILED:", FAILS)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
