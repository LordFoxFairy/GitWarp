# 当前任务状态

- [x] 完成 GitWarp add 后端与 Web 实现
  - 目标：完成 `gitwarp add`、`/api/add`、Project Directory add 入口、项目排序与相关测试/文档/验证。
  - 当前状态：已完成
  - 已验证：`python3 -m unittest discover -s tests -p test_web_api.py -v`、`python3 -m unittest discover -s tests -p test_packaging.py -v`、`cd web/console && npm run build`、`cd web/console && npm run check:dist`、`scripts/check-release.sh`

- [x] 排查 Web 未显示新 init 仓库
  - 现象：在 A 仓库启动 `gitwarp web` 后，再在 B 仓库执行 `gitwarp init`，Project Directory 中没有 B；同时 `add` 后列表中的 B 只显示空 summary，像“没 init 一样”。
  - 根因：1) `init` 只初始化 repo runtime，没有把仓库写入全局项目 registry；2) Project Directory 对 registry 中的非当前仓库只渲染 lazy summary，没有读取 live repo summary。
  - 修复：`init` 现在会同步注册到全局项目目录；`add` 复用 `init`；Project Directory 对 registry 仓库读取 live summary，因此会显示真实 worktree/statusline/counts。
  - 已验证：`python3 -m unittest discover -s tests -p 'test_doctor.py' -v`、`python3 -m unittest discover -s tests -p 'test_web_api.py' -v`、`python3 -m unittest discover -s tests -p 'test_packaging.py' -v`、`scripts/check-release.sh`
