#!/usr/bin/env python3
"""刷新 index.html 里的内置仓库缓存。

页面「公开项目」区域优先实时调用 GitHub API，失败（断网 / 限流 / 接口变动）时
回退到 ``<script id="repo-fallback">`` 里的这份缓存。本脚本按 GitHub 上的真实
仓库刷新缓存，让回退路径也显示最新数据。

用法::

    python scripts/sync_repos.py               # 拉取 GitHub 并写回 index.html
    python scripts/sync_repos.py --check       # 离线校验缓存格式（CI 用，不联网）
    python scripts/sync_repos.py --check-live  # 联网比对缓存与线上仓库，只报告不写回

CI 里可用 ``GITHUB_TOKEN`` 提高限流额度；脚本只写公开仓库，带 token 也不会把
私有仓库带进页面。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "zhaojiale2021"
SITE_REPO = f"{OWNER}.github.io"
ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
API = "https://api.github.com"

# 页面 JS 按这些字段渲染卡片，字段与顺序都要和 index.html 里保持一致
FIELDS = (
    "name",
    "full_name",
    "html_url",
    "description",
    "language",
    "topics",
    "fork",
    "homepage",
    "license",
    "default_branch",
    "has_readme",
    "updated_at",
    "pushed_at",
)

BLOCK = re.compile(
    r'(?P<open><script id="repo-fallback" type="application/json">)'
    r"(?P<body>.*?)"
    r"(?P<close></script>)",
    re.S,
)
ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def log(message: str) -> None:
    print(message, flush=True)


def api(path: str):
    """调用 GitHub REST API，返回解析后的 JSON。"""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{SITE_REPO}-cache-sync",  # GitHub API 强制要求 User-Agent
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{API}{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def readme_exists(full_name: str, fallback: bool) -> bool:
    """探测 README 是否存在——页面据此决定要不要显示 README 按钮。"""
    try:
        api(f"/repos/{full_name}/readme")
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        log(f"  ! {full_name} 的 README 探测失败（HTTP {error.code}），沿用缓存值 {fallback}")
        return fallback


def fetch_repos(cached: dict) -> list[dict]:
    """拉取公开仓库并转换成页面缓存的格式，按最近推送时间倒序。"""
    repos = api(f"/users/{OWNER}/repos?per_page=100&sort=updated")
    # 带 token 调用时这个接口会把私有仓库一起返回——必须显式过滤，别写进公开页面
    projects = [
        repo
        for repo in repos
        if not repo["fork"] and not repo["private"] and repo["name"] != SITE_REPO
    ]
    if len(projects) < 2:
        raise SystemExit(f"线上只返回 {len(projects)} 个公开仓库，疑似接口异常，已放弃写回")

    entries = []
    for repo in sorted(projects, key=lambda r: r.get("pushed_at") or "", reverse=True):
        entries.append(
            {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "description": repo.get("description"),
                "language": repo.get("language"),
                "topics": sorted(repo.get("topics") or []),
                "fork": False,
                "homepage": repo.get("homepage") or None,
                "license": (repo.get("license") or {}).get("spdx_id"),
                "default_branch": repo.get("default_branch") or "main",
                "has_readme": readme_exists(
                    repo["full_name"], cached.get(repo["name"], {}).get("has_readme", True)
                ),
                "updated_at": repo.get("updated_at"),
                "pushed_at": repo.get("pushed_at"),
            }
        )
    return entries


def render(entries: list[dict]) -> str:
    """按 index.html 里的缩进风格序列化（整块再缩进 2 个空格）。"""
    body = json.dumps(entries, ensure_ascii=False, indent=2)
    return "\n".join(f"  {line}" for line in body.splitlines())


def read_cached():
    """读出现有缓存，用于校验和差异比较。

    按二进制读取，保留原有的换行风格——否则在 Windows 上写回时会把整个文件
    的 LF 变成 CRLF，diff 里满屏都是无意义的改动。
    """
    raw = INDEX.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    match = BLOCK.search(text)
    if match is None:
        raise SystemExit('index.html 里找不到 <script id="repo-fallback"> 块')
    try:
        entries = json.loads(match.group("body"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"内置缓存不是合法 JSON：{error}")
    if not isinstance(entries, list):
        raise SystemExit("内置缓存应该是 JSON 数组")
    return text, newline, match, entries


def check(entries: list[dict]) -> list[str]:
    """校验缓存内容是否符合页面约定（离线）。"""
    problems = []
    if len({entry.get("name") for entry in entries}) != len(entries):
        problems.append("存在重名仓库")

    previous = None
    for index, entry in enumerate(entries, 1):
        where = f"第 {index} 条（{entry.get('name') or '未命名'}）"
        missing = [field for field in FIELDS if field not in entry]
        extra = [field for field in entry if field not in FIELDS]
        if missing:
            problems.append(f"{where} 缺字段：{', '.join(missing)}")
        if extra:
            problems.append(f"{where} 多字段：{', '.join(extra)}")
        elif list(entry) != list(FIELDS):
            problems.append(f"{where} 字段顺序与页面约定不一致")
        if entry.get("fork") is not False:
            problems.append(f"{where} 是 fork，页面会过滤掉，不该进缓存")
        if entry.get("name") == SITE_REPO:
            problems.append(f"{where} 是本仓库自身，不该进缓存")
        if entry.get("full_name") != f"{OWNER}/{entry.get('name')}":
            problems.append(f"{where} full_name 与 name 不一致")
        elif entry.get("html_url") != f"https://github.com/{entry['full_name']}":
            problems.append(f"{where} html_url 与 full_name 不一致")
        for field in ("updated_at", "pushed_at"):
            value = entry.get(field)
            if value and not ISO_UTC.fullmatch(value):
                problems.append(f"{where} {field} 不是 UTC ISO 时间：{value}")
        if not isinstance(entry.get("topics"), list):
            problems.append(f"{where} topics 应该是数组")
        if previous is not None and (entry.get("pushed_at") or "") > previous:
            problems.append(f"{where} 未按 pushed_at 倒序排列")
        previous = entry.get("pushed_at") or ""
    return problems


def diff(cached: list[dict], fresh: list[dict]) -> list[str]:
    """比较缓存与线上数据，返回人类可读的差异行。"""
    old = {entry["name"]: entry for entry in cached}
    new = {entry["name"]: entry for entry in fresh}
    lines = [f"+ 新增 {name}" for name in new if name not in old]
    lines += [f"- 移除 {name}" for name in old if name not in new]
    for name in new:
        if name in old:
            changed = [field for field in FIELDS if old[name].get(field) != new[name].get(field)]
            if changed:
                lines.append(f"~ 更新 {name}：{', '.join(changed)}")
    return lines


def write(text: str, newline: str, match: re.Match, entries: list[dict]) -> bool:
    """把新缓存写回 index.html，内容没变则不动文件。"""
    body = f"\n{render(entries)}\n  "
    updated = text[: match.start("body")] + body + text[match.end("body") :]
    if updated == text:
        return False
    INDEX.write_text(updated, encoding="utf-8", newline=newline)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="刷新 index.html 内置仓库缓存")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="离线校验缓存格式（不联网）")
    group.add_argument(
        "--check-live", action="store_true", help="联网比对缓存与线上仓库，只报告不写回"
    )
    args = parser.parse_args()

    text, newline, match, cached = read_cached()
    cached_by_name = {entry["name"]: entry for entry in cached}

    if args.check:
        problems = check(cached)
        if problems:
            log("内置缓存校验未通过：")
            for problem in problems:
                log(f"  - {problem}")
            return 1
        log(f"内置缓存校验通过：{len(cached)} 个公开仓库")
        return 0

    fresh = fetch_repos(cached_by_name)
    lines = diff(cached, fresh)

    if args.check_live:
        if not lines:
            log("缓存与线上一致")
            return 0
        log("缓存与线上存在差异（未写回，去掉 --check-live 即可刷新）：")
        for line in lines:
            log(f"  {line}")
        return 0

    problems = check(fresh)
    if problems:
        log("新缓存未通过校验，已放弃写回：")
        for problem in problems:
            log(f"  - {problem}")
        return 1

    if write(text, newline, match, fresh):
        log("index.html 内置缓存已更新：")
        for line in lines:
            log(f"  {line}")
    else:
        log("缓存已是最新，未改动 index.html")
    return 0


if __name__ == "__main__":
    # Windows 控制台默认可能不是 UTF-8，中文输出会炸
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
