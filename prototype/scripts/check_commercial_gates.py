"""S04 commercial-gates checker — 6 static file-system checks.

Exit 0 = all pass, 1 = any fail, 2 = script error.
Pure grep/file-read; no runtime dependencies.
"""
from __future__ import annotations

import glob
import os
import re
import sys

BASE = os.path.join(os.path.dirname(__file__), os.pardir)
results: list[tuple[bool, str, str]] = []


def _read(relpath: str) -> str:
    with open(os.path.join(BASE, relpath), encoding="utf-8") as f:
        return f.read()


def gate(num: int, name: str, ok: bool, detail: str) -> None:
    tag = "PASS" if ok else "FAIL"
    results.append((ok, f"闸门 {num}: {name}", detail))
    print(f"[{tag}] 闸门 {num}: {name} — {detail}")


# ── Gate 1: startup validation ──────────────────────────────────────────────
try:
    cfg = _read("apps/api/config.py")
    has_jwt = "ZHICE_JWT_SECRET" in cfg and "validate_required_secrets" in cfg
    has_admin = "ZHICE_ADMIN_PASSWORD" in cfg and "validate_required_secrets" in cfg
    gate(1, "启动校验", has_jwt and has_admin,
         "ZHICE_JWT_SECRET + ZHICE_ADMIN_PASSWORD in validate_required_secrets"
         if has_jwt and has_admin else "缺少启动校验环境变量")
except Exception as e:
    gate(1, "启动校验", False, str(e))

# ── Gate 2: admin entrance closed ───────────────────────────────────────────
try:
    auth_init = _read("apps/api/auth/__init__.py")
    has_require_admin = "def require_admin" in auth_init
    payment = _read("apps/api/routes/payment.py")
    admin_call = "require_admin(" in payment
    gate(2, "admin 入口关闭", has_require_admin and admin_call,
         "require_admin 定义存在且 payment.py 调用"
         if has_require_admin and admin_call
         else f"require_admin 定义={'有' if has_require_admin else '无'}, "
              f"payment.py 调用={'有' if admin_call else '无'}")
except Exception as e:
    gate(2, "admin 入口关闭", False, str(e))

# ── Gate 3: visibility column ───────────────────────────────────────────────
try:
    models = _read("packages/shared/db_models.py")
    has_vis = bool(re.search(r"class\s+ReportArchive", models)) and "visibility" in models
    migration_glob = glob.glob(os.path.join(BASE, "alembic/versions/0003*"))
    has_mig = len(migration_glob) > 0
    gate(3, "visibility 列", has_vis and has_mig,
         f"ReportArchive.visibility={'有' if has_vis else '无'}, "
         f"0003 migration={'有' if has_mig else '无'}")
except Exception as e:
    gate(3, "visibility 列", False, str(e))

# ── Gate 4: require_vip matrix ──────────────────────────────────────────────
try:
    route_dir = os.path.join(BASE, "apps/api/routes")
    count = 0
    for py in glob.glob(os.path.join(route_dir, "*.py")):
        with open(py, encoding="utf-8") as f:
            count += f.read().count("require_vip")
    gate(4, "require_vip 矩阵", count >= 5,
         f"require_vip 出现 {count} 次 (≥5)")
except Exception as e:
    gate(4, "require_vip 矩阵", False, str(e))

# ── Gate 5: staging 403 on /api/payment/order ───────────────────────────────
try:
    payment = _read("apps/api/routes/payment.py")
    has_debug_check = "settings.debug" in payment
    has_403 = "403" in payment and "在线支付" in payment
    ok = has_debug_check and has_403
    gate(5, "staging 403", ok,
         "payment/order debug 闸门 + 403 + 在线支付文案"
         if ok else f"debug check={'有' if has_debug_check else '无'}, "
                    f"403+在线支付={'有' if has_403 else '无'}")
except Exception as e:
    gate(5, "staging 403", False, str(e))

# ── Gate 6: frontend "在线支付" always gated ────────────────────────────────
try:
    src_dir = os.path.join(BASE, "apps/web/src")
    issues: list[str] = []
    for root, _dirs, files in os.walk(src_dir):
        for fn in files:
            if not fn.endswith((".tsx", ".ts", ".jsx", ".js")):
                continue
            fpath = os.path.join(root, fn)
            with open(fpath, encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if "在线支付" in line:
                    ctx = "".join(lines[max(0, i - 4):min(len(lines), i + 3)])
                    if not ("内测" in ctx or "disabled" in ctx or "未开放" in ctx):
                        rel = os.path.relpath(fpath, BASE)
                        issues.append(f"{rel}:{i}")
    gate(6, "前端内测中文案", len(issues) == 0,
         "所有 '在线支付' 均伴随 '内测'/'disabled'/'未开放'"
         if not issues else f"未 gated: {', '.join(issues)}")
except Exception as e:
    gate(6, "前端内测中文案", False, str(e))

# ── Summary ─────────────────────────────────────────────────────────────────
passed = sum(1 for ok, *_ in results if ok)
total = len(results)
print(f"\n{'=' * 40}")
print(f"结果: {passed}/{total} 闸门通过")
sys.exit(0 if passed == total else 1)
