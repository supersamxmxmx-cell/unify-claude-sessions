# unify-sync — Claude Desktop Session 统一工具

**让官方 Claude Desktop 和 Gateway (3p) Claude Desktop 共享同一份会话记录和配置**

---

## 问题

使用 Gateway（ccswitch 等）连接 Claude Desktop 时，3p 版本会创建独立的 profile 目录（`Claude-3p/`），导致：

- Session 列表为空（看不到之前在官方版的历史会话）
- 收藏、分组、项目权限各自独立
- 两边的配置不同步

但实际上，**底层数据完全兼容**——只是物理上分成了两个目录。

## 解决思路

两个 app 的 session 数据天然存储在不同位置：

```
官方 Claude:  ~/Library/Application Support/Claude/claude-code-sessions/
Gateway:      ~/Library/Application Support/Claude-3p/claude-code-sessions/
```

本工具的做法：

1. **把 Gateway 的 session 目录替换成一个指向官方目录的符号链接（symlink）**
   - Gateway 读 session 时，跟随 symlink，实际读的是官方目录的文件
   - 两边从此看到同一批 session

2. **开启前，把 Gateway 独有的 session 文件复制到官方目录**
   - 这样官方 Claude 也能看到 Gateway 之前创建的 session

3. **关闭时，删除 symlink，从快照恢复 Gateway 的原始目录**
   - Gateway 的 session 文件在 `on` 前已保存快照，`off` 时完整恢复

```
on 之后的文件结构：

官方目录（真实目录）
  ├── local_xxx.json   ← 官方原有的 session
  ├── local_yyy.json   ← 官方原有的 session
  └── local_zzz.json   ← 从 Gateway 复制过来的 session

Gateway 目录（symlink）──→ 指向官方目录
  （Gateway 读到的就是上面这 3 个文件）
```

**效果**：
- 两边看到完全相同的 session 列表
- 任意一个 app 创建的新会话，另一个立刻可见
- 随时可逆（`off` 一键恢复独立状态）

## 快速开始

```bash
# 下载（一行）
curl -O https://raw.githubusercontent.com/supersamxmxmx-cell/unify-claude-sessions/main/unify-sync.py

# 查看当前状态
python3 unify-sync.py status

# 开启统一
python3 unify-sync.py on

# 重启两个 Claude Desktop → 生效！
```

## 命令

| 命令 | 作用 | 可逆 |
|---|---|---|
| `python3 unify-sync.py status` | 查看当前统一状态 | - |
| `python3 unify-sync.py backup` | 仅备份所有数据（不修改） | - |
| `python3 unify-sync.py on` | 开启统一 | ✅ 随时 off |
| `python3 unify-sync.py off` | 关闭统一，恢复独立 | ✅ 完全恢复 |

## 原理详解

### `on` 做了什么

1. **备份** — 把当前官方和 Gateway 的所有 session 备份到 `backups/<时间戳>/`
2. **快照** — 把 Gateway 当前的 session 保存到 `.gw_snapshot/`（`off` 时用于恢复）
3. **迁移** — 把 Gateway 独有的 session 文件**复制到官方目录**（让官方 Claude 也能看到这些 session）
4. **symlink** — 删除 Gateway 的 session 目录，创建软链接指向官方目录（Gateway 从此通过 symlink 读到官方的所有 session）
5. **合并 config** — 深度合并 `claude_desktop_config.json`，两个 account UUID 的收藏/分组等配置共存

### `off` 做了什么

1. **删 symlink** — 移除 Gateway session 目录的软链接
2. **恢复快照** — 把 `.gw_snapshot/` 的内容还原到 Gateway 的独立 session 目录（Gateway 回到自己的 session）
3. **清理官方目录** — 把 `on` 时从 Gateway 迁移到官方的 session 文件从官方目录删除（官方恢复干净状态）
4. **移除 config 软链接** — Gateway 重启后会自动重建自己的配置

`on` / `off` 完全对称，两边各自保持干净：

| 状态 | 官方 Claude 看到 | Gateway 看到 |
|---|---|---|
| **off（独立）** | 只有官方自己的 session | 只有 Gateway 自己的 session |
| **on（统一）** | 官方 + Gateway 的 session | 官方 + Gateway 的 session（通过 symlink）|

## 注意事项

### 分组显示

Session 列表的分组方式两个 app 可能不一致。建议两边都切换成**按项目目录分组**：在 session 列表 UI 找分组切换图标，选 **Group by directory**。

### 统一期间新建的 session 去哪了

统一状态（`on`）下，两个 app 创建的 session 都写入**官方目录**（因为 Gateway 的目录是指向官方的 symlink）。

`off` 之后：
- Gateway 恢复到 `on` 之前的**快照**状态，所以统一期间新建的 session 在 Gateway 里**看不到**
- 但这些 session 文件仍然在**官方目录**，官方 Claude 可以看到 ✅

如需让 Gateway 也包含这些 session，重新执行一次 `on` 即可（新的快照会包含它们）。

## 目录结构

```
~/Library/Application Support/
├── Claude/                           ← 官方版（真实目录）
│   ├── claude_desktop_config.json    ← 合并后包含两个 account UUID
│   └── claude-code-sessions/
│       └── be5c9dd2-.../
│           └── 318824e3-.../         ← 所有 session JSON（含从 Gateway 迁移的）
│
└── Claude-3p/                        ← Gateway 版
    ├── claude_desktop_config.json    → [symlink → 官方 config]（on 状态）
    └── claude-code-sessions/
        └── fbf8cc10-.../
            └── 00000000.../          → [symlink → 官方 session 目录]（on 状态）

~/Documents/claude desktop对话同步/   ← 本项目
├── unify-sync.py                     ← 主 CLI
├── .gw_snapshot/                     ← Gateway session 快照（off 恢复用，不提交）
├── backups/                          ← 历史备份（不提交）
└── README.md
```

## 安全保证

- ✅ **每次 `on` 自动备份** — 原始数据存入 `backups/<时间戳>/`，永不丢失
- ✅ **快照保护** — `on` 前保存 Gateway session 快照，`off` 完整恢复
- ✅ **可逆开关** — `off` 完全恢复独立状态
- ✅ **官方目录安全** — `off` 不删除官方目录的任何文件
- ✅ **无网络操作** — 纯本地文件操作

## 依赖

- Python 3.6+（macOS 内置，无需安装）
- 零外部依赖

## 许可

MIT

## 作者

supersam — 2026-06-27
GitHub: [supersamxmxmx-cell/unify-claude-sessions](https://github.com/supersamxmxmx-cell/unify-claude-sessions)

---

## 附录：也可集成到 ccswitch

ccswitch 已有 `unifyCodexSessionHistory` 开关（针对 Codex）。本工具的思路可以做成 ccswitch 针对 Claude Desktop 3p 的同类功能：

```json
{
  "localMigrations": {
    "claudeDesktop3pProfileUnifyV1": {
      "completedAt": "2026-06-27T...",
      "unifiedSessions": 42
    }
  },
  "unifyClaudeDesktop3pProfiles": true
}
```

向 ccswitch 提 feature request 时可直接引用本项目。
