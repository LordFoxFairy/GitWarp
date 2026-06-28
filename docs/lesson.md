- 场景：用户明确表示不喜欢执行过程中被频繁追问，希望我按最佳方案自主实现，最后直接交付成品。
  我做错的：在可由现有上下文和最佳实践自行决策的地方仍频繁向用户确认，打断了用户节奏。
  下次怎么避免：默认自主决策并持续执行；只有在存在关键歧义、不可逆外部影响或必须由用户拍板的选择时才提问。

- 场景：跑全量测试套件后用户发现 Web Project Directory 被上千个 `/T/tmpXXXX` 死目录刷屏。
  我做错的：根因不是代码 fallback，而是测试隔离缺陷——`GitWarpTestCase.setUp` 没设 `GITWARP_HOME`，`run_gitwarp` 子进程继承真实环境，叠加 commit faad764 让 `init` 自动写全局 registry，于是测试把真实 `~/.gitwarp/projects.json` 污染到 1600+ 条。
  下次怎么避免：任何会触发 `init`/`add`/register 的测试必须隔离 `GITWARP_HOME`（在基类 setUp 注入临时 home 并在 tearDown 还原）；新增「会写全局/HOME 状态」的行为时，先检查测试基类是否已隔离该路径。
