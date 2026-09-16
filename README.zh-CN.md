# 跨设备 Agent 接力

[English](README.md) | [简体中文](README.zh-CN.md)

这是一套给编码 Agent 使用的轻量工作流，让科研项目能够在台式机、笔记本和可选的远端计算节点之间连续工作，而不假设聊天记录或私有记忆可以跨会话共享。

核心是把不同状态分开：

- 普通 Git 分支保存源码、测试和可复现的项目事实；
- 私有 `agent-relay` 分支只保存一份简短的接棒账本；
- 本地覆盖层让 Codex 与 Claude Code 遵守同一套规则，但不污染产品分支；
- 远端计算节点只接收经过验证的 Git bundle，不保存 GitHub 凭据。

本仓库包含一个采用开放 Agent Skills 目录结构的 Codex Skill。模板和脚本也可以被其他编码 Agent 当作普通仓库规则使用。

## 为什么不把所有内容都写进 `AGENTS.md`？

稳定规则、当前任务状态、产品历史和机器凭据的生命周期完全不同。混在一起容易产生过时指令、冗长上下文和意外泄露。本工作流为每类信息指定独立通道，并限制动态账本的长度。

## 支持的拓扑

| 场景 | 产品同步 | 接棒同步 | 远端交付 |
|---|---|---|---|
| 单台电脑 | Git | 本地账本 | 无 |
| 台式机 + 笔记本 | 私有 GitHub 仓库 | 私有 `agent-relay` 分支 | 无 |
| 台式机 + 笔记本 + 计算节点 | 私有 GitHub 仓库 | 私有 `agent-relay` 分支 | SSH 上的已验证 bundle |

计算节点不是第三个源码编辑位置。它只运行确定的 commit，并返回验证证据。

## 安装 Skill

仓库级安装：把 `.agents/skills/cross-device-relay` 复制到目标仓库的同一路径。Codex 会从 `.agents/skills` 发现仓库级 Skill。

个人级安装：把该 Skill 文件夹复制到用户 Skill 目录。之后可以显式调用 `$cross-device-relay`，也可以让 Codex 在跨设备协作任务中自动选择它。

## 初始化项目

```bash
python .agents/skills/cross-device-relay/scripts/relay.py init --repo /path/to/project
```

该命令会创建本地 `.relay/current.md`；在文件不存在且未被跟踪时创建兼容的 `AGENTS.md` 和 `CLAUDE.md`；并把本地覆盖层加入 `.git/info/exclude`。它不会覆盖已有的受版本控制 Agent 指令。

典型接棒流程：

```bash
python .agents/skills/cross-device-relay/scripts/relay.py doctor --repo .
python .agents/skills/cross-device-relay/scripts/relay.py preview-state --repo .
python .agents/skills/cross-device-relay/scripts/relay.py pull-state --repo . --accept
python .agents/skills/cross-device-relay/scripts/relay.py claim --repo . --agent CODEX
# 工作、验证，并更新账本
python .agents/skills/cross-device-relay/scripts/relay.py release --repo .
python .agents/skills/cross-device-relay/scripts/relay.py push-state --repo .
```

状态命令通过临时 checkout 操作独立的 `agent-relay` 分支，不会切换产品工作区，也不会把账本加入产品历史。拉取时先显示差异，只有显式提供 `--accept` 才覆盖不同的本地账本。发布和接收前会阻止常见凭据、私钥内容、个人主目录路径及机器专属 SSH 配置。

这个扫描只是一层额外保护，不代表账本可以存放敏感信息。`agent-relay` 必须仅用于私有远端。

## 把已推送的 commit 交付给远端节点

```bash
python .agents/skills/cross-device-relay/scripts/sync_runner.py \
  --repo . --host lab-runner --remote-repo projects/example --bootstrap
```

首次创建远端 checkout 时使用 `--bootstrap`，后续更新省略它。脚本要求：已有非交互 SSH 信任、本地 tracked worktree 干净、目标 commit 已推送、远端历史可以 fast-forward。脚本不会安装软件、创建凭据或运行项目专属测试。

## `.gitignore` 不是接棒协议

- `.gitignore`：由 Git 跟踪，适合所有 clone 都应忽略的生成物。
- `.git/info/exclude`：仅当前 clone 生效，适合不应改变产品仓库的接棒覆盖层。
- 两者都不是安全边界；秘密一旦进入 Git 历史，之后再忽略也无法真正删除。

Skill 的 `assets/gitignore.example` 提供了一个可调整的项目级示例。

## 匿名科研示例

一个图像增强项目在台式机和笔记本上编辑。两台电脑都把产品 commit 推到私有 GitHub 仓库，并通过 `agent-relay` 交换简短接棒状态。实验室 GPU 主机不保存 GitHub token，只通过 bundle 脚本接收已经推送的 commit、运行评估并返回结果。本地 Agent 规则和实时账本不会进入实验室 checkout。

## 与相近方案的区别

| 项目 | 擅长方向 | 本项目的取舍 |
|---|---|---|
| [Agent Handoff](https://github.com/artyomboyko/Agent_Handoff) | GitHub Issue、PR、认领和仓库内长期记忆 | 适合多人团队；本项目不强制项目管理流程 |
| [claude-codex-handoff](https://github.com/OpenMOSS/claude-codex-handoff) | JSONL 双向消息、lease、cursor、定时唤醒 | 适合同时运行的 Agent；本项目坚持串行持棒 |
| [agent-handoff-kit](https://github.com/jimozo/agent-handoff-kit) | 每 Agent 分支、会话日志轮换、多种交棒模式 | 功能完整但文件较多；本项目只保留一个有界账本 |
| [shared-agent-memory](https://github.com/dan-calin/shared-agent-memory) | MCP 共享记忆、语义检索和文件级认领 | 适合长期知识检索；本项目保持零服务、低依赖 |
| [coding-agent-toolkit](https://github.com/stefan-jansen/coding-agent-toolkit) | 从需求、计划、Issue 到 PR 和发布的全流程 | 适合规范化交付；本项目只解决连续性和安全传输 |
| [agent-handoff](https://github.com/im-ian/agent-handoff) | 通过私有 hub 同步整套 Claude/Codex 配置 | 适合迁移 Agent 全局环境；本项目只同步项目级状态 |

本项目吸收了三项高价值、低复杂度设计：覆盖前预览差异、只读 `doctor`、发布前秘密与个人路径扫描。暂不引入异步消息总线、MCP 记忆服务、全套 Issue/PR 状态机、自动过期锁或整套 Agent 配置同步。

## 安全性质

- 不自动 force-push、reset、merge、删除、创建凭据或安装软件。
- 未推送或 tracked worktree 不干净时，不向计算节点交付。
- 历史分叉时，不更新计算节点。
- 初始化时不覆盖已有的受版本控制 Agent 指令。
- 不在验证 commit 前声称另一台机器已同步。
- 不静默覆盖不同的本地接棒账本。
- 账本匹配常见秘密或个人路径模式时，拒绝发布。

## 许可证

MIT，见 [LICENSE](LICENSE)。
