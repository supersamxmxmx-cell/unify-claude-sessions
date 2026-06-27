# unify-sync — Claude Desktop Session 统一工具

**让官方 Claude Desktop 和 Gateway (3p) Claude Desktop 共享同一份会话记录和配置**

---

## 问题

使用 Gateway (ccswitch 等) 连接 Claude Desktop 时，3p 版本会创建独立的 profile 目录 (`Claude-3p/`)，导致：

- Session 列表为空（看不到之前在官方版的历史会话）
- 收藏、分组、项目权限各自独立
- 两边的配置不同步

但实际上，**底层数据完全兼容**——只是物理上分成了两个目录。

## 解决

通过**安全备份 + 深度合并 + 符号链接**，让两个 app 的数据目录指向同一物理位置：

```
官方 Claude                     Gateway Claude
     │                               │
     │  同 ~/.claude/ (记忆/skill) ← 本就共享
     │                               │
     ├─ Session JSON ────symlink────┤  ← 本工具统一
     ├─ Config JSON ────symlink────┤  ← 本工具统一
```

**效果**：
- 任意一个 app 创建的新会话，另一个立刻可见
- 收藏/分组/Pin 实时同步
- 随时可逆（一键恢复独立状态）

## 快速开始

```bash
# 1. 查看当前状态
python3 unify-sync.py status

# 2. 安全备份（无修改，建议先做）
python3 unify-sync.py backup

# 3. 开启统一
python3 unify-sync.py on

# 4. 重启两个 Claude Desktop → 生效！
```

## 命令

| 命令 | 作用 | 是否可逆 |
|---|---|---|
| `python3 unify-sync.py status` | 查看当前统一状态 | - |
| `python3 unify-sync.py backup` | 仅备份所有数据（不修改） | - |
| `python3 unify-sync.py on` | 开启统一 | ✅ 随时 off |
| `python3 unify-sync.py off` | 关闭统一，恢复独立 | ✅ 完全恢复 |
| `python3 unify-sync.py merge` | 仅合并配置（不创建软链接） | - |

## 原理

### on — 做了什么

1. **安全备份** — 每次操作前自动备份原始文件到 `backups/` 目录
2. **配置合并** — 深度合并 `claude_desktop_config.json`，两个 account UUID 的配置共存
3. **Session 合并** — Gateway 独有的 session 文件迁移到官方目录
4. **符号链接** — Gateway 的 session 目录指向官方目录
5. **.bak 保留** — Gateway 原始 session 目录保留为 `xxx.bak`，用于撤销

### off — 恢复

1. 移除符号链接
2. 从 `.bak` 恢复原始 session 目录
3. 从备份恢复原始 config
4. 两边完全回到独立状态

## 目录结构

```
~/
├── .claude/                          ← 本就共享（记忆/skill/settings）
│   ├── CLAUDE.md
│   ├── projects/
│   ├── skills/
│   └── settings.json
│
├── Library/Application Support/
│   ├── Claude/                       ← 官方版
│   │   ├── claude_desktop_config.json    ← 配置（合并后包含两个 UUID）
│   │   └── claude-code-sessions/         ← Session 总目录
│   │       └── be5c9dd2-.../             ← 官方 account
│   │           └── 318824e3-.../        ← 所有 session JSON
│   │
│   └── Claude-3p/                    ← Gateway 版
│       ├── claude_desktop_config.json → [symlink → Claude/...]
│       └── claude-code-sessions/
│           └── fbf8cc10-.../         ← Gateway account
│               ├── 00000000-.../      → [symlink → Claude/.../318824e3-.../]
│               └── 00000000-....bak/ ← 原始备份（用于撤销）
│
└── Documents/claude desktop对话同步/  ← 本项目
    ├── unify-sync.py                 ← 主 CLI
    ├── backups/                      ← 操作历史备份
    ├── lib/                          ← 预留
    └── README.md
```

## 安全保证

- ✅ **每次操作前自动备份** — 原始数据永不丢失
- ✅ **Session .bak 目录** — Gateway 原始 session 完整保留
- ✅ **可逆开关** — `off` 命令完全恢复独立状态
- ✅ **只读采集** — 只在合并阶段复制文件，不修改原始 session JSON
- ✅ **无网络操作** — 纯本地文件操作，不联网
- ✅ **幂等** — 重复执行 `on`/`off` 不会损坏数据

## 依赖

- Python 3.6+（macOS 内置）
- 零外部依赖

## 许可

MIT

## 作者

supersam — 2026-06-27

---

## 附录：也可集成到 ccswitch

ccswitch 已有 `unifyCodexSessionHistory` 开关。本工具的思路可以做成 ccswitch 的一个 migration：

```json
{
  "localMigrations": {
    "claudeDesktop3pProfileUnifyV1": {
      "completedAt": "2026-06-27T...",
      "unifiedSessions": 41
    }
  },
  "unifyClaudeDesktop3pProfiles": true
}
```

向 ccswitch 提 feature request 时可直接引用本项目。
