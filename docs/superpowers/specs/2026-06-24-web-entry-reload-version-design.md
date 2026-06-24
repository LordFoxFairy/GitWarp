# GitWarp Web 固定入口、Reload 与版本递增设计

## Context

当前 GitWarp 的 `gitwarp web start` 默认使用随机端口。虽然技术上可用，但对普通用户不友好：用户很难记住本次启动分配到的具体端口，也难以形成稳定心智模型。与此同时，Project Directory 对 unknown / unmanaged branches 的可见性仍然不够稳定，用户会觉得某些 branch “消失了”；此外，当仓库状态经过非 GitWarp 路径被修改后，缺少一个明确、可安全触发的轻修复入口。最后，版本号长期不递增，会让 install / upgrade / launcher probe / plugin cache 路径难以可靠判断“当前是不是新版本”，进而影响更新体验。

本次设计目标是一次性解决四类问题：

1. 为 `gitwarp web start` 提供用户可记忆的固定入口。
2. 为 Web / CLI 提供安全的 `reload` 轻修复能力。
3. 保证 unknown branches 在 Web 中始终可见，但不伪装成 GitWarp `base` / `task`。
4. 将版本号策略收敛为“每次用户可见变更都递增”，并增加测试守卫。

## Goals

- 用户默认只需要记住一个稳定的 Web 入口地址，而不是每次新的随机端口。
- `gitwarp web start` 在同一台机器上始终表现为“当前 active repo 的 Web Console 入口”。
- `reload` 能在不做破坏性清理的前提下，重新扫描 `.git`、`.gitwarp`、global registry 和 Web state，并补齐安全缺失项。
- 所有 unknown / unmanaged branches 在 Web 中保留可见性，并单独分区展示。
- 版本号与用户可见变更同步，确保 install / upgrade / launcher / probe / docs 不再长期漂移。

## Non-Goals

- 这次不做多 repo 并发代理路由；固定入口当前只服务一个 active repo。
- `reload` 不做 destructive cleanup，不自动删除 worktree / branch / dossier / stale entries。
- 这次不重新设计 matrix / next 的核心分类算法，只补充其在 Web 层的可见性与 reload 入口。
- 这次不引入复杂的版本元数据（如 commit hash、日期后缀）作为主要用户版本号。

## Recommended Architecture

### 1. 固定入口地址：单 active repo 接管模式

推荐把用户可见的固定入口定为：

- `http://127.0.0.1:6006`

系统内部仍然允许真实的 Web Console 服务运行在不同端口，但用户默认只需要访问固定入口。当前阶段不实现“一个代理分发多个后端 repo”的复杂方案，而是采用“全局单 active repo 接管固定入口”的策略。

行为规则：

- 若当前没有 GitWarp Web Console 占用固定入口，则 `gitwarp web start` 为当前 repo 建立固定入口。
- 若当前已有 GitWarp Web Console，且服务的是同一个 repo，则返回 `already_running: true`，直接复用。
- 若当前已有 GitWarp Web Console，但服务的是另一个 repo，则新的 repo 接管固定入口；旧的 active repo 退场。
- CLI 输出、Web state 文件、README 和 `gitwarp web status` 都必须同时报告：
  - `public_url`：用户应访问的固定入口（例如 `http://127.0.0.1:6006`）
  - `backend_url`：真实后端监听地址
  - `repo_root`
  - `active_repo_root`
  - `already_running`
  - `replaced_existing`

这样用户永远只记固定入口，而 GitWarp 内部仍保留真实后端地址用于调试和状态说明。

### 2. 端口策略

对用户暴露的端口优先固定为：

- `6006`

如果未来必须处理固定端口被非 GitWarp 进程占用的问题，可以在设计上保留 fallback 空间：在 `6000-6999` 中寻找下一个可用端口。但当前这一版以“固定入口优先”作为产品承诺，不把随机端口暴露给用户当主入口。

对 CLI / 文档语义来说，应始终表述为：

- 默认访问固定入口
- 只有调试或异常场景才需要关心 backend 实际端口

### 3. Reload：轻修复而非清理

新增显式 `reload` 能力，目标不是简单刷新 UI，而是执行一次“安全自愈式重载”。

推荐提供两层入口：

- CLI：`gitwarp reload`
- Web：Project Directory / Repository 页面上的 `Reload` 或 `Reload view`

`reload` 应做的事：

1. 重新扫描 `.git`：
   - branch refs
   - live worktrees
   - 当前 HEAD / branch / statusline
2. 重新读取 `.gitwarp`：
   - `ledger.json`
   - `dossiers/`
   - repo-local web state
3. 重新读取 global registry：
   - 当前 repo 是否已注册
   - registry 排序与去重
4. 补齐安全缺失项：
   - 缺失的 `.gitwarp/` runtime 目录
   - 缺失但应存在的 registry 注册
   - stale 的 Web state 记录
   - Project Directory summary 与 live repo state 不一致的情况
5. 重新计算：
   - matrix
   - next actions
   - branch summaries
   - project summary

`reload` 明确不做的事：

- 删除 worktree
- 删除 branch ref
- 删除 dossier
- 自动 prune stale entries
- 自动 collapse / sweep / remove

也就是说：

> `reload` 是重新扫描并补齐安全缺失项，不是 repair cleanup。

### 4. Unknown branches：单独区域保留可见性

所有不属于 GitWarp `base` / `task` 的 branch，都必须在 Web 中继续可见。它们不应被隐藏，也不应被错误归类进 `base`。

推荐在 Web 的 branch / matrix 相关展示里分成三个层次：

1. `Base Branches`
2. `Task Branches`
3. `Unmanaged / Other Branches`

第三层用于展示：

- Git 中存在、但不属于 GitWarp 管理模型的 ref
- 无法安全判定为 `base` / `task` 的分支
- 历史遗留或用户手动维护的分支

每个 unknown branch 至少要展示：

- branch name
- 是否有 live worktree
- 是否只是 local ref
- cleanup safety
- classification basis
- 如果存在，推荐动作

这样既不丢 branch，又不会污染 `base` / `task` 的语义边界。

### 5. 版本号：每次用户可见变更都递增

版本号继续以单一真源维护：

- `src/gitwarp/__init__.py::__version__`

规则改为：

> 每次 main 上出现用户可见变更，就必须递增版本号。

用户可见变更包括但不限于：

- CLI 默认行为变化
- Web 行为变化
- install / upgrade / launcher 逻辑变化
- 文档承诺的产品行为变化

版本推进规则建议：

- patch：修 bug、小体验修正、小默认行为变化
- minor：新增命令、新功能、新默认入口能力

当前这次功能（固定入口、reload、新 branch 展示语义）如果最终实现，倾向于至少 bump minor；如果拆批进入 main，则其中单独的 bugfix 可按 patch 递增。

## File-Level Design

### A. Web 固定入口 / active repo 状态

可能修改：

- `src/gitwarp/webapp/lifecycle.py`
  - 增加全局 fixed-entry state 管理
  - 增加 active repo 接管逻辑
  - 为 `start/status/stop` 返回 `public_url` / `backend_url` / `active_repo_root`
- `src/gitwarp/webapp/server.py`
  - 支持固定入口语义与 readiness payload 扩展
- `src/gitwarp/adapters/cli/system.py`
  - `cmd_web` 返回新字段
- `tests/test_cli_lifecycle.py`
- `tests/test_web_api.py`

### B. Reload

可能新增或修改：

- `src/gitwarp/application/use_cases/` 中新增 reload use case
- `src/gitwarp/adapters/cli/parser.py`
  - 新增 `reload` 命令
- `src/gitwarp/adapters/cli/system.py`
- `src/gitwarp/webapp/contracts.py`
- `src/gitwarp/webapp/controllers.py`
- `tests/test_cli_lifecycle.py`
- `tests/test_web_api.py`

### C. Unknown branches 展示

可能修改：

- `src/gitwarp/application/use_cases/web_state.py`
- branches / matrix payload 生成逻辑
- `web/console/src/app/components/BranchesPanel.tsx`
- 可能的 Project Directory / matrix 相关组件
- `tests/test_web_api.py`
- `tests/test_packaging.py`

### D. 版本号守卫

可能修改：

- `src/gitwarp/__init__.py`
- `tests/test_runtime_sync.py`
- 相关 install / upgrade / launcher probe 测试
- `README.md` / `skills/gitwarp/SKILL.md` 中的升级说明（若需补充）

## Error Handling

### 固定入口被非 GitWarp 进程占用

当前推荐行为：

- 明确返回错误，指出 `6006` 已被非 GitWarp 进程占用
- 提示用户手动停止占用者，或未来若启用 fallback，再显式给出备用入口

不建议在第一版偷偷切随机端口，因为这会破坏“固定入口”的心智。

### Reload 遇到非法状态

- ledger / registry / web state 非法时，返回可读错误或 warning
- 在能安全补齐的前提下补齐
- 在不能安全修复时，只报告，不删除

### Unknown branches 无法进一步分类

- 仍保留在 `Unmanaged / Other Branches`
- 附带 `classification_basis`
- 不要因为无法判定而隐藏

## Testing Plan

至少新增或扩展以下验证：

### 固定入口 / active repo

- `gitwarp web start` 默认返回固定 `public_url`
- 同 repo 再次 start 返回 `already_running`
- 不同 repo start 时返回 `replaced_existing`
- `status` 能显示当前 active repo 与固定入口

### Reload

- 非 GitWarp 手动改动后，`reload` 能恢复 Project Directory / matrix / summary
- 缺失 registry 注册时，`reload` 能补注册
- 不会触发任何 destructive cleanup

### Unknown branches

- unknown branches 出现在 `Unmanaged / Other Branches`
- 不被归类为 `base` / `task`
- matrix / next / branch panel 里仍可追踪

### 版本号

- `gitwarp --version` 与 `__version__` 一致
- launcher / install / upgrade probe 反映版本变化
- 新版本未 bump 时测试应能发现问题

### 全量

- `scripts/check-release.sh`

## Recommended Rollout Order

1. 先做版本号策略与测试守卫，避免后续实现再次出现“行为变了但版本没变”。
2. 再做 fixed-entry Web lifecycle，确保 `gitwarp web start/status/stop` 的入口语义稳定。
3. 再加入 `reload` 轻修复能力。
4. 最后收口 unknown branches 在 Web 中的单独展示与文案。

## Recommendation

推荐按以下成品定义实施：

- `gitwarp web start` 默认提供固定入口 `127.0.0.1:6006`
- 当前阶段采用“全局单 active repo 接管固定入口”的实现策略
- 新增 `gitwarp reload`，执行轻修复式重载，不做 destructive cleanup
- Web 新增 `Unmanaged / Other Branches` 区域，保证 unknown branches 可见
- 将版本策略收敛为“每次用户可见变更都递增”，并用测试守卫固化
