"""S02/T06 静态扫 mock 防护 —— 4 个广义 PATTERNS + 1 条 routes 局部隐式-mock 规则

规则 1-4（PATTERNS）：广义匹配 apps/ 与 packages/ 全部源码，禁止
  • `MOCK_<UPPER>` 命名常量
  • `"mock": true` JSON 字面量
  • `mock: true` JS/TS 对象字面量
  • `mock=True` Python 关键字参数
ALLOWLIST 用于豁免 D005 已审计的渲染常量 / 契约 helper docstring。

规则 5（scan_implicit_mock）：仅扫 `apps/api/routes/*.py`，对每个出现 `mock=True`
或 `"mock": true` 的行 N，检查 N±5 行内是否有 `data_status` 字段或 `wrap_contract`
调用——若无则视为隐式 mock（即代码声明了 mock 但没在 D004 契约里挂数据状态），
emit `[FAIL: implicit-mock]`。这条规则覆盖了 PATTERNS 漏不到的"语义级隐式 mock"
（如有人 hack 一个 dict 里 mock=True 但没走 wrap_contract 路径）。

参见 `.gsd/DECISIONS.md::D004`（数据契约）+ `D005`（白名单豁免原则）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["apps", "packages"]
SKIP_PARTS = {
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}

PATTERNS = [
    re.compile(r"\bMOCK_[A-Z0-9_]+\b"),
    re.compile(r'"mock"\s*:\s*true', re.IGNORECASE),
    re.compile(r"\bmock\s*:\s*true", re.IGNORECASE),
    re.compile(r"\bmock\s*=\s*True\b"),
]

ALLOWLIST = {
    "apps/web/src/components/MockBanner.tsx",
    # M001/S02 D005 EXEMPT 白名单：DataStatusBadge 的 MOCK_COLOR/MOCK_LABEL 是渲染常量
    # 命名（演示数据徽标），不是运行时 mock 逻辑。
    "apps/web/src/components/DataStatusBadge.tsx",
    # M001/S02 D004 数据契约 helper 的 docstring/error message 引用 "mock=True ⟺ data_status='mock'"
    # 是契约约束的描述文本（防御性 ValueError 抛出），不是默认开启 mock 路径。
    "apps/api/utils/contract.py",
}


# 隐式 mock 检测的"附近行窗口"半径
_IMPLICIT_WINDOW = 5

# 行内出现"看起来像 mock=True"的标志
_IMPLICIT_MOCK_LINE = re.compile(
    r"\bmock\s*=\s*True\b"  # Python 关键字参数
    r'|"mock"\s*:\s*[Tt]rue'  # JSON / dict 字面量
)

# 附近窗口内必须出现的"契约挂钩"（任一即可视为合法）
_CONTRACT_CONTEXT = re.compile(
    r"\bdata_status\b"
    r"|\bwrap_contract\s*\("
)


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel in ALLOWLIST:
        return True
    if path.suffix not in SUFFIXES:
        return True
    return any(part in SKIP_PARTS for part in path.parts)


def scan_implicit_mock(file_path: Path) -> list[tuple[str, int, str]]:
    """对 routes/*.py 文件做隐式 mock 扫描。

    返回 list[(rel_path, lineno, line_snippet)]。每条匹配 mock=True 但 ±5 行
    内没有 data_status / wrap_contract 上下文的行被视为隐式 mock 违规。
    """
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    rel = file_path.relative_to(ROOT).as_posix()
    violations: list[tuple[str, int, str]] = []
    for i, line in enumerate(lines):
        if not _IMPLICIT_MOCK_LINE.search(line):
            continue
        start = max(0, i - _IMPLICIT_WINDOW)
        end = min(len(lines), i + _IMPLICIT_WINDOW + 1)
        window = lines[start:end]
        if any(_CONTRACT_CONTEXT.search(w) for w in window):
            continue
        violations.append((rel, i + 1, line.strip()[:180]))
    return violations


def main() -> int:
    hits: list[tuple[str, int, str]] = []
    implicit_hits: list[tuple[str, int, str]] = []

    # 规则 1-4：广义模式扫描 apps/ + packages/
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if should_skip(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if any(pattern.search(line) for pattern in PATTERNS):
                    hits.append((path.relative_to(ROOT).as_posix(), lineno, line.strip()[:180]))

    # 规则 5：routes/*.py 隐式 mock 扫描
    routes_dir = ROOT / "apps" / "api" / "routes"
    if routes_dir.exists():
        for path in sorted(routes_dir.glob("*.py")):
            if should_skip(path):
                continue
            implicit_hits.extend(scan_implicit_mock(path))

    if hits:
        for filename, lineno, line in hits:
            print(f"[FAIL] {filename}:{lineno} {line}")
    if implicit_hits:
        for filename, lineno, line in implicit_hits:
            print(f"[FAIL: implicit-mock] {filename}:{lineno} {line}")

    total = len(hits) + len(implicit_hits)
    if total:
        print(
            f"\nMock scan failed: {len(hits)} pattern hits + {len(implicit_hits)} implicit-mock hits",
            file=sys.stderr,
        )
        return 1

    print(
        "Mock scan passed: no MOCK_/mock=true 字面量 in apps+packages, "
        "no implicit mock=True without data_status in apps/api/routes/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
