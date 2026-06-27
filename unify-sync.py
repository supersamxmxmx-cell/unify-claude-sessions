#!/usr/bin/env python3
"""
unify-sync — Claude Desktop Session 统一工具

让官方 Claude Desktop 和 Gateway (3p) Claude Desktop 共享同一份会话记录和配置。

用法:
    python3 unify-sync.py on       开启统一（备份 → 合并 → 软链接）
    python3 unify-sync.py off      关闭统一（恢复独立状态，可逆）
    python3 unify-sync.py status   查看当前状态（默认）
    python3 unify-sync.py backup   仅备份（不修改任何文件）

原理:
    官方 Claude 与 Gateway Claude 共用 ~/.claude/ 下的记忆和配置，
    但 Session 列表和 claude_desktop_config.json 各存一份。
    本工具通过符号链接 + 配置合并，让两边指向同一份 Session 数据。

作者: supersam | 日期: 2026-06-27
项目: https://github.com/supersamxmxmx-cell/unify-claude-sessions
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List

# ── 路径常量 ──────────────────────────────────────────────
HOME = Path.home()
LIB = HOME / "Library" / "Application Support"
OFFICIAL = LIB / "Claude"
GATEWAY = LIB / "Claude-3p"
SCRIPT_DIR = Path(__file__).resolve().parent
BACKUPS_DIR = SCRIPT_DIR / "backups"

# ── 终端颜色 ──────────────────────────────────────────────
C = {
    "red": "\033[0;31m",
    "green": "\033[0;32m",
    "yellow": "\033[1;33m",
    "cyan": "\033[0;36m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def color(c: str, text: str) -> str:
    return f"{C.get(c, '')}{text}{C['reset']}"


def log_info(msg: str) -> None:
    print(f"   {color('green', '✓')} {msg}")


def log_warn(msg: str) -> None:
    print(f"   {color('yellow', '⚠')} {msg}")


def log_error(msg: str) -> None:
    print(f"   {color('red', '✗')} {msg}")


def log_step(msg: str) -> None:
    print(f"\n{color('cyan', '▸')} {color('bold', msg)}")


# ── 工具函数 ──────────────────────────────────────────────


def count_sessions(dir_path: Path) -> int:
    """统计目录下 session JSON 文件数（排除 scheduled-tasks.json）"""
    if not dir_path.exists():
        return 0
    count = 0
    for f in dir_path.iterdir():
        if f.is_symlink() or f.is_file():
            if f.suffix == ".json" and f.name != "scheduled-tasks.json":
                count += 1
    return count


def find_session_dir(app_dir: Path) -> Optional[Path]:
    """在 app 目录下查找任一 session 子目录（不包括 .bak），不去尾斜杠"""
    sessions_root = app_dir / "claude-code-sessions"
    if not sessions_root.is_dir():
        return None
    for account_dir in sorted(sessions_root.iterdir()):
        if not account_dir.is_dir() and not account_dir.is_symlink():
            continue
        for session_dir in sorted(account_dir.iterdir()):
            if session_dir.name.endswith(".bak"):
                continue
            if session_dir.is_dir() or session_dir.is_symlink():
                return session_dir
    return None


def is_unified() -> Tuple[bool, Optional[Path]]:
    """返回 (是否已统一, Gateway session 目录如果存在)"""
    gw_session = find_session_dir(GATEWAY)
    if gw_session and gw_session.is_symlink():
        return True, gw_session
    return False, gw_session


def find_backup_dir(gw_session: Path) -> Optional[Path]:
    """查找 .bak 备份目录"""
    bak = gw_session.parent / (gw_session.name + ".bak")
    return bak if bak.is_dir() else None


def find_config_backup(app_dir: Path) -> Optional[Path]:
    """查找最近的 config 备份"""
    pattern = "claude_desktop_config.json.bak."
    candidates = sorted(
        [f for f in app_dir.iterdir() if f.name.startswith(pattern)],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


# ── 命令实现 ──────────────────────────────────────────────


def cmd_status() -> None:
    """查看当前状态"""
    print()
    print(color("bold", "═" * 55))
    print(color("bold", "  Claude Desktop Session 统一状态"))
    print(color("bold", "═" * 55))
    print()

    # Config 文件
    gw_config = GATEWAY / "claude_desktop_config.json"
    off_config = OFFICIAL / "claude_desktop_config.json"

    print(color("bold", "── claude_desktop_config.json ──"))
    if gw_config.is_symlink():
        target = os.readlink(str(gw_config))
        print(f"  Gateway: {color('green', '软链接')} → {target}")
    elif gw_config.is_file():
        print(f"  Gateway: {color('yellow', '独立文件')} (未统一)")
    else:
        print(f"  Gateway: {color('red', '不存在')}")
    print(f"  官方:    独立文件")

    # Session 目录
    print()
    print(color("bold", "── Session 目录 ──"))

    off_session = find_session_dir(OFFICIAL)
    off_count = count_sessions(off_session) if off_session else 0
    print(f"  官方:     {off_session}")
    print(f"            文件: {off_count} 个 session")

    unified, gw_session = is_unified()
    gw_count = count_sessions(gw_session) if gw_session else 0

    if unified and gw_session:
        target = os.readlink(str(gw_session))
        print(f"  Gateway:  {color('green', '软链接')} → {target}")
        print(f"            文件: {gw_count} 个 session {color('green', '(已统一)')}")
    elif gw_session:
        print(f"  Gateway:  {color('yellow', '独立目录')} (未统一)")
        print(f"            文件: {gw_count} 个 session")
    else:
        print(f"  Gateway:  {color('red', '不存在')}")

    # 备份
    print()
    print(color("bold", "── 备份 ──"))

    history_count = 0
    if BACKUPS_DIR.is_dir():
        history_count = len(
            [d for d in BACKUPS_DIR.iterdir() if d.is_dir()]
        )
    if history_count > 0:
        print(f"  历史备份:     {history_count} 份 ({BACKUPS_DIR})")
    else:
        print(f"  历史备份:     无")

    # 结论
    print()
    if unified:
        if gw_count == off_count:
            print(f"  {color('green', '状态: ✅ 已统一')}")
        else:
            print(
                f"  {color('green', '状态: ✅ 已统一')} "
                f"(session 数: 官方{off_count} / Gateway{gw_count})"
            )
    else:
        print(f"  {color('yellow', '状态: ⚠️  未统一')}")
    print()


def cmd_backup() -> None:
    """安全备份所有相关文件"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = BACKUPS_DIR / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    log_step(f"备份到: {backup_dir}")

    # 官方 config
    off_config = OFFICIAL / "claude_desktop_config.json"
    if off_config.is_file():
        shutil.copy2(off_config, backup_dir / "Claude-claude_desktop_config.json")
        log_info("已备份: Claude/claude_desktop_config.json")

    # Gateway config
    gw_config = GATEWAY / "claude_desktop_config.json"
    if gw_config.is_symlink():
        target = os.readlink(str(gw_config))
        if Path(target).is_file():
            shutil.copy2(target, backup_dir / "Claude-3p-claude_desktop_config.json")
            log_info("已备份: Gateway config (软链接 → 官方)")
    elif gw_config.is_file():
        shutil.copy2(gw_config, backup_dir / "Claude-3p-claude_desktop_config.json")
        log_info("已备份: Claude-3p/claude_desktop_config.json")

    # 官方 session
    off_session = find_session_dir(OFFICIAL)
    if off_session and off_session.is_dir():
        off_bak = backup_dir / "Claude-sessions"
        off_bak.mkdir(exist_ok=True)
        for f in off_session.iterdir():
            if f.suffix == ".json":
                shutil.copy2(f, off_bak / f.name)
        log_info(f"已备份: Claude sessions ({count_sessions(off_bak)} 个)")

    # Gateway session（仅当非软链接时）
    gw_session = find_session_dir(GATEWAY)
    if gw_session and not gw_session.is_symlink() and gw_session.is_dir():
        gw_bak = backup_dir / "Claude-3p-sessions"
        gw_bak.mkdir(exist_ok=True)
        for f in gw_session.iterdir():
            if f.suffix == ".json":
                shutil.copy2(f, gw_bak / f.name)
        log_info(f"已备份: Gateway sessions ({count_sessions(gw_bak)} 个)")
    elif gw_session and gw_session.is_symlink():
        log_info("Gateway session 是软链接，跳过备份（有 .bak 保护）")

    # Gateway 目录树
    gw_sessions_root = GATEWAY / "claude-code-sessions"
    if gw_sessions_root.is_dir():
        tree_bak = backup_dir / "Claude-3p-claude-code-sessions-tree"
        shutil.copytree(
            gw_sessions_root,
            tree_bak,
            dirs_exist_ok=True,
            symlinks=True,
        )
        log_info("已备份: Gateway claude-code-sessions 目录树")

    log_info(f"备份完成 {color('green', '✓')}")
    print(f"\n   备份路径: {backup_dir}")


def cmd_merge_configs() -> bool:
    """合并两边配置（account-keyed 字段共存），返回是否成功"""
    log_step("合并 claude_desktop_config.json ...")

    off_config = OFFICIAL / "claude_desktop_config.json"
    gw_config = GATEWAY / "claude_desktop_config.json"

    if not off_config.is_file():
        log_error(f"官方 config 不存在: {off_config}")
        return False

    if not gw_config.is_file() or gw_config.is_symlink():
        log_warn("Gateway config 不存在或已是软链接，跳过合并")
        return True

    try:
        with open(off_config) as f:
            official = json.load(f)
        with open(gw_config) as f:
            gateway = json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"JSON 解析失败: {e}")
        return False

    def deep_merge(base: dict, overlay: dict) -> dict:
        """递归合并：account-keyed dict 保留两份，列表合并去重"""
        for k, v in overlay.items():
            if k not in base:
                base[k] = v
            elif isinstance(v, dict) and isinstance(base[k], dict):
                deep_merge(base[k], v)
            elif isinstance(v, list) and isinstance(base[k], list):
                merged = list(base[k])
                for item in v:
                    if item not in merged:
                        merged.append(item)
                base[k] = merged
        return base

    merged = deep_merge(official, gateway)

    # 特别处理 starred sessions
    off_starred = (
        official.get("preferences", {})
        .get("epitaxyPrefs", {})
        .get("starred-local-code-sessions", [])
    )
    gw_starred = (
        gateway.get("preferences", {})
        .get("epitaxyPrefs", {})
        .get("starred-local-code-sessions", [])
    )
    all_starred = list(dict.fromkeys(off_starred + gw_starred))
    merged["preferences"]["epitaxyPrefs"]["starred-local-code-sessions"] = all_starred

    with open(off_config, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # 统计 account UUID
    uuids = set()
    for k in merged.get("preferences", {}).get("epitaxyPrefs", {}):
        for part in k.split("."):
            if len(part) == 36 and part.count("-") >= 4:
                uuids.add(part)

    log_info(f"已合并 {len(uuids)} 个 account UUID, {len(all_starred)} 个 starred session")
    return True


def cmd_on() -> None:
    """开启统一"""
    print()
    print(color("bold", "╔══════════════════════════════════════════╗"))
    print(color("bold", "║  Claude Desktop Session 统一工具         ║"))
    print(color("bold", "║  官方版 ⇄ Gateway (3p) 会话互通         ║"))
    print(color("bold", "╚══════════════════════════════════════════╝"))
    print()

    # 前置检查
    if not OFFICIAL.is_dir():
        log_error(f"未找到官方 Claude Desktop 数据目录: {OFFICIAL}")
        sys.exit(1)
    if not GATEWAY.is_dir():
        log_error(f"未找到 Gateway Claude Desktop 数据目录: {GATEWAY}")
        sys.exit(1)

    # 1. 安全备份
    log_step("第 1 步：安全备份 ...")
    cmd_backup()
    print()

    # 2. 发现路径
    log_step("第 2 步：发现 session 目录 ...")

    off_session = find_session_dir(OFFICIAL)
    if not off_session:
        log_error("未找到官方 session 目录")
        sys.exit(1)

    log_info(f"官方 session 目录: {off_session}")
    log_info(f"  文件数: {count_sessions(off_session)}")

    gw_session = find_session_dir(GATEWAY)
    if not gw_session:
        log_error("未找到 Gateway session 目录")
        sys.exit(1)

    log_info(f"Gateway session 目录: {gw_session}")
    log_info(f"  文件数: {count_sessions(gw_session)}")

    # 3. 合并配置
    log_step("第 3 步：合并配置 ...")
    cmd_merge_configs()

    # 创建 config 软链接
    gw_config = GATEWAY / "claude_desktop_config.json"
    if not gw_config.is_symlink():
        gw_config.unlink(missing_ok=True)
        os.symlink(str(OFFICIAL / "claude_desktop_config.json"), str(gw_config))
        log_info("Config 软链接: Gateway → 官方")

    # 4. 合并 session
    log_step("第 4 步：合并 session 数据 ...")

    if gw_session.is_symlink():
        target = os.readlink(str(gw_session))
        if target == str(off_session):
            log_info("已指向官方目录，跳过")
        else:
            log_warn(f"指向其他位置: {target}")
            log_warn("如需重新指向官方目录，请先执行 'off' 再 'on'")
    else:
        # 把 Gateway 独有的 session 复制到官方目录
        off_files = {f.name for f in off_session.iterdir() if f.suffix == ".json"}
        migrated = 0
        for f in gw_session.iterdir():
            if f.suffix == ".json" and f.name not in off_files:
                shutil.copy2(f, off_session / f.name)
                migrated += 1
                log_info(f"迁移 Gateway 独有: {f.name}")

        if migrated > 0:
            log_info(f"共迁移 {migrated} 个 Gateway 独有 session")
        else:
            log_info("无 Gateway 独有 session 需要迁移")

        # 删除原目录，创建软链接
        shutil.rmtree(str(gw_session))
        os.symlink(str(off_session), str(gw_session))
        log_info(f"Session 软链接: Gateway → 官方 {color('green', '✓')}")

    # 完成
    print()
    print(color("bold", "╔══════════════════════════════════════════╗"))
    print(color("bold", "║  ✅ 统一完成！                          ║"))
    print(color("bold", "║                                          ║"))
    print(color("bold", "║  两个 Claude Desktop 现在共享:           ║"))
    print(color("bold", "║  • Session 历史 (互见)                   ║"))
    print(color("bold", "║  • 收藏 / 分组 / Pin                    ║"))
    print(color("bold", "║  • 项目记忆 (本已共享)                   ║"))
    print(color("bold", "║                                          ║"))
    print(color("bold", "║  ⚠️  请重启两个 Claude Desktop 以生效   ║"))
    print(color("bold", "║  随时运行 'unify-sync off' 恢复         ║"))
    print(color("bold", "╚══════════════════════════════════════════╝"))
    print()


def cmd_off() -> None:
    """关闭统一，恢复独立"""
    print()

    unified, gw_session = is_unified()
    gw_config = GATEWAY / "claude_desktop_config.json"

    if not unified and not gw_config.is_symlink():
        log_info("当前未统一，无需操作")
        return

    log_step("正在关闭统一，恢复独立状态 ...")

    # 1. 恢复 config（移除软链接，app 重启会重建）
    if gw_config.is_symlink():
        log_info("移除 config 软链接 ...")
        gw_config.unlink()
        log_info("Gateway config 软链接已移除，重启 app 会自动重建")

    # 2. 恢复 session 目录
    if gw_session and gw_session.is_symlink():
        log_info("移除 session 软链接 ...")
        gw_session.unlink()
        gw_session.mkdir(parents=True, exist_ok=True)
        log_info("已创建空 session 目录，Gateway 只可见自己的 session")

    print()
    log_info(f"{color('green', '✅ 已恢复独立状态')}")
    log_info("两个 Claude Desktop 现在各自独立")
    log_info("⚠️  请重启两个 Claude Desktop 以生效")
    print()


# ── 主入口 ─────────────────────────────────────────────────


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"

    commands = {
        "on": ("开启 session 统一", cmd_on),
        "off": ("关闭统一，恢复独立", cmd_off),
        "status": ("查看当前状态", cmd_status),
        "backup": ("安全备份（不修改）", cmd_backup),
        "merge": ("仅合并配置（不创建软链接）", cmd_merge_configs),
    }

    if command in ("-h", "--help", "help"):
        print()
        print(f"{color('bold', 'unify-sync')} — Claude Desktop Session 统一工具")
        print()
        print("用法:")
        print(f"  python3 {Path(__file__).name} <命令>")
        print()
        print("命令:")
        for name, (desc, _) in commands.items():
            print(f"  {name:<10} {desc}")
        print()
        print(f"示例:")
        print(f"  python3 {Path(__file__).name} on       # 开启统一")
        print(f"  python3 {Path(__file__).name} status   # 查看状态")
        print(f"  python3 {Path(__file__).name} off      # 关闭统一")
        print()
        return

    if command not in commands:
        print(f"{color('red', '未知命令')}: {command}")
        print(f"可用命令: {', '.join(commands.keys())}")
        print(f"运行 'python3 {Path(__file__).name} --help' 查看更多")
        sys.exit(1)

    _, handler = commands[command]
    handler()


if __name__ == "__main__":
    main()
