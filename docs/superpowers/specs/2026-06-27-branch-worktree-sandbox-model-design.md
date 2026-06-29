# GitWarp Branch / Worktree / Sandbox 模型设计

## Context

GitWarp 当前的主要问题不是“能力不够”，而是对象语义容易混层。用户在使用过程中会同时遇到：Git branch、Git worktree、GitWarp 的 base/task 角色、agent 执行上下文，以及 instruction/dossier/ledger 等附加机制。如果这些层没有被严格拆开，用户就会出现典型困惑：

- 现在看到的是 branch 还是 worktree？
- 这是 Git 原生对象，还是 GitWarp 受管对象？
- 为什么有些 branch 消失了？
- 为什么 agent 看起来在 `.git` 里做了奇怪的事？
- 为什么两个 worktree 理论上该隔离，却又会被某个 symlink/config 重新连回去？

用户已经明确指出了正确的基线：**GitWarp 本来就应该站在 Git / GitHub 的心智模型之上实现**。也就是说，Git branch 依然是代码资产，Git worktree 依然是独立工作目录，GitWarp 只能做包装层和管理层，而不能重新发明底层语义，更不能破坏 Git 原生 worktree 的隔离性。

这份设计的目标，是把 GitWarp 的对象模型、展示模型、命令职责和隔离原则重新收紧到 Git / GitHub 心智之上，让系统既更可信，也更容易被人类和 agent 正确使用。

## Goals

1. 明确区分 Git 原生对象与 GitWarp 受管对象。
2. 把 branch 重新确立为代码资产的一等视图，把 sandbox/worktree 作为执行视图。
3. 保证 unknown / unmanaged branches 永远可见，不再“消失”。
4. 保证 GitWarp 的 instruction / config 机制不再破坏 Git worktree 原生隔离。
5. 让 CLI、Web、文档和 agent 工作流统一使用同一套术语和对象边界。

## Non-Goals

- 这次不改变 Git 本身的 ref / worktree / merge 语义。
- 这次不重新设计 matrix / next 的底层算法，只修正它们在产品中的定位和展示边界。
- 这次不试图把所有历史分支自动分类为 `base` 或 `task`。
- 这次不引入新的“第四种 Git 对象”；GitWarp 只增加管理视图，不替代 Git 模型。

## Foundational Principle

> Git 是真模型，GitHub / GitLab 是用户已习惯的展示心智，GitWarp 是建立在其上的包装与管理层。

必须从这条原则推导出所有产品行为：

- branch 是 Git ref，也是用户关心的代码资产。
- worktree 是 Git 提供的独立工作目录。
- GitWarp sandbox 只是 GitWarp-managed worktree，不是新的 Git 对象。
- agent 只是进入某个 sandbox 工作的执行者，不定义 branch 或 worktree 的身份。
- GitWarp 的任何附加机制都不能破坏 Git worktree 原生隔离。

## Core Object Model

### 1. Git 原生层

#### Branch
- 定义：Git ref。
- 角色：代码资产。
- 用户关心它的生命周期、合并状态、用途和是否仍有价值。
- 任何长期线、短期线、历史线，本质都先是 branch。

#### Worktree
- 定义：Git worktree 对应的独立工作目录。
- 角色：执行容器的底座。
- 一个 worktree 可以 checkout 某个 branch 或某个 detached commit。
- 每个 worktree 的工作区文件默认应该彼此隔离。

### 2. GitWarp 包装层

#### Sandbox
- 定义：GitWarp-managed worktree。
- 成立条件：至少具备 worktree 实体 + ledger metadata + dossier + status/purpose/agent 等管理信息。
- 不是所有 worktree 都是 sandbox；未托管 worktree 只是 unmanaged worktree。

#### Role (`base` / `task`)
- 定义：GitWarp 给 branch/worktree 附加的角色标签。
- `base`：长期协调线。
- `task`：短生命周期执行线。
- 角色标签不是 Git 原生对象类型，只是 GitWarp 的受管分类。

#### Agent session
- 定义：进入某个 sandbox 工作的执行者。
- 角色：消费 sandbox，而不是创造新的 Git 对象层。
- 正确表达方式永远是：某 agent 正在某 sandbox 中工作，而不是“agent 拥有某个 branch”。

## Core User Mental Model

推荐用户心智：

> branch 是代码资产，worktree 是独立工作目录，sandbox 是 GitWarp-managed worktree，agent 只是进入 sandbox 工作。

从这句心智衍生出几个必须成立的判断：

- branch 不是 sandbox。
- sandbox 不是 agent。
- agent 不是 branch。
- GitWarp 不应该让路径、branch 名或 agent 名替代对象类型本身。

## Display and Interaction Model

## Human-first default: branch-centric

对人类用户，系统默认应先展示 branch，再展示 branch 之下的 sandbox / worktree 关系。

原因：
- 人类首先关心“我有哪些代码线”。
- 用户要决定的是保留、合并、删除、接管还是托管某条线。
- worktree 和 sandbox 更适合作为执行与操作细节，而不是资产清单本身。

## Agent-first operational view: sandbox-centric

对 agent 或自动化，系统可以先展示 sandbox：
- 当前路径
- dossier
- status
- purpose
- agent identity
- parent branch / base relationship

因为 agent 真正消费的是执行容器，而不是资产清单。

## Required naming boundaries

### `Branch`
只表示 Git ref，不表示目录、不表示 sandbox、不表示当前 agent。

### `Worktree`
只表示 Git worktree 对应的独立本地目录，不表示 role，不表示 ownership。

### `Sandbox`
只表示 GitWarp-managed worktree。不是所有 worktree 都是 sandbox。

### `Agent`
只表示执行者。任何地方都不应用 “agent branch” / “claude worktree” 这样的说法混淆对象层级。

## Concrete Product Rules

## 1. Asset vs container

### 资产层
属于资产层的对象：
- default branch
- feature branches
- bugfix branches
- release branches
- 历史但仍存在的 Git refs

### 容器层
属于容器层的对象：
- Git worktree
- GitWarp sandbox
- 当前 agent session

资产层回答“这是什么代码线”；容器层回答“这线现在在哪儿执行”。

## 2. `base` role rule

`base` 只表示 GitWarp 认定的长期 branch 角色。

默认应被视为 `base` 的对象：
- `main`
- 用户显式创建或标记的长期 feature branch
- 明确作为长期协调线存在的受管 branch

未知分支不能因为“不知道是什么”就自动塞进 `base`。长期线才叫 `base`；未知线仍应保留为 unmanaged / other。

## 3. `task` role rule

`task` 只表示 GitWarp 为短期执行创建的 branch 角色。

推荐满足以下强信号才判定为 `task`：
- GitWarp 创建或 adopt
- 有 ledger metadata
- 有 dossier
- 有明确 parent/base relationship
- 用途明显是短期执行线

仅仅因为 branch 名像 `agent/*`，不足以自动判为 `task`。

## 4. `unmanaged / other` rule

所有 Git 真实存在、但不属于 GitWarp 受管模型的 branch，都必须在产品里继续可见。

它们应该被统一展示为：
- Unmanaged Branches
- Other Branches
- 或合并成 `Unmanaged / Other Branches`

产品含义不是“垃圾桶”，而是：

> 这些是真实存在的 Git 资产，只是当前不在 GitWarp 托管模型内。

## 5. Sandbox rule

Sandbox 必须严格定义为 GitWarp-managed worktree。

条件：
- 有 worktree
- 有 GitWarp ledger row
- 有 dossier
- 有 status/purpose/agent 等管理信息

不满足这些条件的 worktree 仍然是 worktree，但不是 sandbox。

## 6. Isolation rule

这是本次设计的硬约束：

> GitWarp 不得通过 instruction、config mount、共享路径、symlink 等机制破坏 Git worktree 原生隔离。

直接推导：
- 进入 worktree 的 instruction 文件默认必须是 copy。
- GitWarp 不应在主流程中允许 instruction symlink。
- 两个 worktree 不应通过 GitWarp-managed instruction/config 再共享同一份可写内容。

## CLI Responsibilities

### `gitwarp branches`
职责：branch inventory。

它应回答：
- 我有哪些 branch？
- 哪些是 base？
- 哪些是 task？
- 哪些是 unmanaged？
- 哪些 branch 当前有 live worktree / sandbox？

推荐稳定保留字段：
- `name`
- `branch_role`
- `managed_state`
- `has_worktree`
- `worktree_path`
- `agent_id`
- `status`
- `merged_to_base`
- `category`
- `classification_basis`

### `gitwarp board`
职责：sandbox board。

它不是全 branch 资产视图，而是 GitWarp-managed sandbox 视图。应优先展示：
- sandbox path
- checked-out branch
- agent
- status
- latest progress
- dossier

### `gitwarp matrix`
职责：诊断与控制平面。

它负责解释：
- Git branch refs
- live Git worktrees
- GitWarp ledger rows
- dossier dirs

它不是默认主导航入口，而是当用户需要理解 drift / orphan / stale / unmanaged 状态时的诊断视图。

### `gitwarp next`
职责：从 matrix 推导出的 action queue。

用户心智应是：
- `branches` 看资产
- `board` 看执行
- `matrix` 看诊断
- `next` 看系统建议动作

## Web Information Architecture

推荐 Web 顶层稳定成以下几个区：

1. Projects
2. Branches
3. Sandboxes
4. Repository
5. Health / Diagnostics

### Project Directory
只承担项目入口与摘要，不承担 branch/sandbox 语义解释主体。

### Branches view
必须是 branch-first，按以下分区展示：
- Primary / Default
- Base Branches
- Task Branches
- Unmanaged / Other Branches

每行建议字段：
- Branch
- Role
- Managed state
- Live sandbox/worktree
- Agent
- Merge / cleanup state
- Recommended action

### Sandboxes view
必须是 execution-first：
- sandbox path
- checked-out branch
- agent
- dossier
- status
- latest progress
- parent base

### Repository view
只负责 code browser / file tree / committed content，不再承担 branch/sandbox 主语义解释。

### Matrix / Diagnostics view
继续保留为控制平面与诊断页。

## Product Language Rules

### 尽量避免或禁用的混层说法
- workspace（太容易同时指 repo / worktree / sandbox）
- agent branch
- task workspace（若不同时标明 branch/worktree）

### 推荐统一说法
- branch
- worktree
- sandbox
- managed worktree
- unmanaged branch
- unmanaged worktree

## State Transition Rules

### branch → base
需要显式用户动作或明确 GitWarp create role base。

### branch → task
必须通过 GitWarp 受管创建 / adopt，并写入完整元数据。

### unmanaged branch → managed
可以提供显式动作（例如 adopt as base / adopt as task），但不能自动偷判。

### worktree → sandbox
只有写入 ledger + dossier 后，才算 GitWarp sandbox。

## Design Review Checklist

任一界面或命令，如果用户看完后无法回答下面四个问题，就是设计失败：

1. 这是 branch、worktree，还是 sandbox？
2. 这是 Git 原生对象，还是 GitWarp 受管对象？
3. 这是代码资产，还是执行容器？
4. 它现在是 base / task / unmanaged 中的哪类，为什么？

## Recommendation

推荐将 GitWarp 全部产品表面统一到以下定义上：

> GitWarp manages Git worktrees as sandboxes, but it never replaces Git’s branch model.

对应中文心智：

> GitWarp 用 sandbox 管理 worktree，但 branch 仍然是代码资产的真模型；GitWarp 不替代 Git，只增强 Git worktree 的可管理性与可恢复性。
