# Benchmark Testcases

每个子目录是一个 testcase: 在一个游戏 repo 的某个基线状态上, 给 AI 一个任务,
用一个**冻结的黄金验证器**给结果打分。设计目标: 不动手必须 0 分, 正确改动满分。

> `_templates/` 目录里的内容**不是** testcase: 没有顶层 `testcase.toml`, 不会被发现,
> 只是给新建 testcase 用的脚手架, 例如原 `bench-0001-attack-buff` 模板。

## 两套集合

仓库根下有两个目录, 服务不同目的:

| 目录 | 规模 | 用途 |
|---|---|---|
| `testcases/`（本目录） | ~519 个, 完整挖掘库 | 广度评测、统计显著性、研究真实修复分布 |
| `testcases_filtered/` | **30 个, 推荐评测集** | 快速冒烟 / 演示 / 开发迭代 / 验证器全链路自检 |

**`testcases_filtered/`（30 个精选）**: 从完整库人为再平衡挑出、oracle 最鲁棒的一组。全部自包含 folder 型,
5 个 category 全覆盖(behavior_logic ×19 / precise_edit ×4 / intent_translation ×3 / architecture ×2 / visual_audio ×2),
5 种验证器全覆盖(godot_scene_assert ×21 / py_config ×3 / py_gdscript_ast ×2 / py_tscn_diff ×2 / visual_static ×2),
全部通过 `aigdbench audit`(noop 0 / golden 1) 且带分级陷阱。选取标准与逐类代表性例子见
[`../docs/filtered_dataset_report.md`](../docs/filtered_dataset_report.md); 完整库分布见
[`../docs/full_dataset_report.md`](../docs/full_dataset_report.md)。

本目录 `testcases/` 由四部分构成: ①手工代表集(trap-driven) ②hard/brutal 加难集 ③真实 AI 失败挖掘集
④`survey-*` / `survey-fixcommit` 自动挖掘集(~485 个, git 型, `survey_bad_case` 验证)。下方索引逐一列出。

## 当前 testcase 索引

| id | category | verifier | source_kind | 备注 |
|---|---|---|---|---|
| gdb-task_0002 | behavior_logic | godot_scene_assert | folder | 干净 (noop 0 / patch 1) |
| gdb-task_0007 | behavior_logic | godot_scene_assert | folder | noop≈0.09 漏分 |
| gdb-task_0012 | behavior_logic | godot_scene_assert | folder | noop 被 L0 拦截, patch 1 |
| gdb-task_0013 | behavior_logic | godot_scene_assert | folder | 干净 |
| gdb-task_0025 | behavior_logic | godot_scene_assert | folder | 干净 |
| gdb-task_0027 | behavior_logic | godot_scene_assert | folder | noop≈0.10 漏分 |
| gdb-task_0051 | behavior_logic | godot_scene_assert | folder | noop≈0.20 漏分 |
| gdb-task_0052 | behavior_logic | godot_scene_assert | folder | noop≈0.23 漏分 |
| gdb-task_0103 | behavior_logic | godot_scene_assert | folder | noop≈0.21 漏分 |
| gdb-task_0281 | behavior_logic | godot_scene_assert | folder | noop≈0.21 漏分 |
| pathfinding-npc-bridge-astar | behavior_logic | godot_scene_assert | folder | 干净 (noop 0 / patch 1); NPC AStar3D 过双桥 |
| ui-window-stretch-config | intent_translation | py_config | folder | 干净; 真实挖掘 (stretch 缺基准分辨率) |
| gdscript-cannot-infer-type | behavior_logic | godot_scene_assert | folder | 干净; 真实挖掘 (`:=` 类型推断失败) |
| missing-resource-import | precise_edit | godot_scene_assert | folder | 干净; 真实挖掘 (引用缺失资源致加载崩溃) |
| survey-two-step-signal-oracle | architecture | survey_bad_case | git | 手写, oracle 紧 (3 文件) |
| survey-codex_…624e21 | precise_edit | survey_bad_case | git | oracle 10 文件 |
| survey-unknown_2026-06-25_000 | intent_translation | survey_bad_case | git | oracle 3 文件 |
| survey-history_2026-06-10_2f271c6_000 | behavior_logic | survey_bad_case | git | oracle 过宽 (94 文件) |
| survey-history_2026-06-12_445a385_005 | behavior_logic | survey_bad_case | git | oracle 过宽 (94 文件) |
| survey-history_2026-06-15_1781fe0_010 | behavior_logic | survey_bad_case | git | oracle 过宽 (2711 文件) |

### 代表性 trap-driven 集 (2026-06-29 新增, 15 个)

按"能力 × 难度"矩阵设计, 每格填一个高频玩法系统, 每个 case 都围绕一个**具体的 AI 失败模式 (trap)** 构造: 显而易见的偷懒实现会踩坑得分不满, 只有正确改动满分。全部自包含 folder 型, 全部 `aigdbench audit` 通过 (noop 0 / golden 1)。设计见 [`../docs/superpowers/specs/2026-06-29-representative-testcase-set-design.md`](../docs/superpowers/specs/2026-06-29-representative-testcase-set-design.md)。

| id | category | 难度 | verifier | trap (AI 失败模式) | bad.diff |
|---|---|---|---|---|---|
| elite-attack-buff-pct | intent_translation | easy | py_config | +20% 写成照抄 50 或加 20 (=70) | — |
| platformer-jump-retune | intent_translation | med | py_config | 只改 jump_velocity, 漏掉耦合的 gravity (→0.5) | — |
| loot-drop-rate-rebalance | intent_translation | med | py_config | 三倍 legendary 但忘了减 common, 概率不归一 (→0.5) | — |
| hard-mode-difficulty-preset | intent_translation | hard | py_config | 意图跨两文件, 只改一个另一个留旧 (→0.5) | ✓ |
| collision-layer-precise-edit | precise_edit | easy | py_tscn_diff | 改对目标但扰动了别的节点 (→0.5) | — |
| timer-signal-wire | precise_edit | med | godot_scene_assert | 加了 Timer 节点但忘了连 timeout 信号 (→0.33) | ✓ |
| reparent-spawnpoint-precise | precise_edit | hard | py_tscn_diff | reparent 时扰动别的节点 / 丢 position (→0.5) | — |
| no-hardcoded-res-path | architecture | med | py_gdscript_ast | 仍硬编码 res:// 路径字符串 | — |
| component-layer-boundary | architecture | hard | py_gdscript_ast | 只改 extends, 仍 import ui/ 层 (→0.5) | — |
| ability-cooldown-gate | behavior_logic | easy | godot_scene_assert | 不记冷却时间, 每帧可发 | — |
| health-damage-death | behavior_logic | med | godot_scene_assert | HP 不 clamp / died 每次都发 (→0.6) | ✓ |
| player-fsm-transition-guard | behavior_logic | med | godot_scene_assert | 不调 enter()/exit(), 不挡非法转移 | — |
| pickup-inventory-ui-chain | behavior_logic | hard | godot_scene_assert | 信号没连 UI 不更新 / 重复入区重复计数 (→0.4) | ✓ |
| hud-healthbar-anchor | visual_audio | easy | visual_static | 用绝对偏移而非锚点, resize 时漂走 | — |
| menu-panel-layout | visual_audio | med | visual_static | 按钮顺序错 / 某项隐藏 (→0.67) | ✓ |

> 维护提示: `visual_static` 走 `--script` 模式, 其 `verifier.gd` 必须 `extends SceneTree` 并自行 load 场景 (不用 `verifier_scene.tscn`); 其余 godot 型走场景模式 `extends Node`。fix.diff 一律用真实 git 生成 (手搓 diff 易触发 corrupt patch)。`py_tscn_diff` 把任何新增 connection 视作副作用, 故"连信号"类用 `godot_scene_assert` 验。

### hard / brutal 加难集 (2026-06-30 新增, 5 个)

第一批 15 个对强 harness (Claude) 区分度不足 (它几乎全过)。这 5 个专门拉难度: 多 trap 叠加、多文件多系统联动、对抗型隐藏 bug, 逼近 gdb-task_0025/0281 体量。全部 godot_scene_assert, 自包含, `aigdbench audit` 通过。

| id | category | 难度 | trap | 已验证部分分 |
|---|---|---|---|---|
| wave-spawner-hidden-bugs | behavior_logic | hard | baseline 能跑但藏 3 个 bug (off-by-one / 边界 / 末波), 强 harness 易"看着对就不改" | 只修1个 bug → 0.17 |
| inventory-equipment-system | behavior_logic | hard | 双文件 6 个独立 trap (堆叠/容量/装备替换不叠加/卸下) | re-equip 叠加 → 0.67 (bad.diff) |
| damage-formula-refactor | behavior_logic | hard | 交互规则: 暴击在减防之后 / 最小伤害 1 / 满防暴击仍 ≥1 | 暴击在减防之前 → 0.20 |
| wave-combat-score-system | behavior_logic | brutal | 多系统: 敌人 FSM + 波次 spawn/wire + 连击计分 + 胜利, 双文件端到端 | — |
| event-bus-priority-dispatch | behavior_logic | brutal | 优先级派发 + 平局插入序 + 退订 + 重订更新 + 派发前安全移除 | — |

### 从真实 AI 失败挖掘的 case (2026-06-29 新增, 3 个)

不是合成的, 而是用 `scripts/mine_retry_sessions.py` 扫本地 Claude/Codex 对话历史, 挑出"单次对话反复重试"的真实游戏开发会话, 深读还原其根因陷阱后重制成 testcase。挖掘方法与场景溯源见 [`../docs/mined_retry_scenarios.md`](../docs/mined_retry_scenarios.md)。全部自包含, `aigdbench audit` 通过 (noop 0 / golden 1)。

| id | category | verifier | 来源会话 | 真实陷阱 (AI 反复栽的地方) |
|---|---|---|---|---|
| ui-window-stretch-config | intent_translation | py_config | Claude / ui-login | project.godot 设了 stretch mode + aspect=expand 却漏掉基准分辨率 window/size/viewport_width/height, canvas_items 拉伸静默失效 |
| gdscript-cannot-infer-type | behavior_logic | godot_scene_assert | Claude / Documents-test | `var x := untyped_array[i]` 从无类型来源用 `:=` 推断, 报 "Parse Error: Cannot infer the type", 脚本整体加载失败 |
| missing-resource-import | precise_edit | godot_scene_assert | Codex / GameDevFeatsShowcase | 场景 ext_resource 引用一张不存在的 Texture2D, headless 启动 "No loader found for resource ... expected type: Texture2D", 场景加载崩溃 |

> 备注: `ui-window-stretch-config` 顺带给 `py_config` 的 `flatten_config` 加了 Godot `.godot`/`.cfg` 配置解析 (此前只认 .json/.toml/.tres, project.godot 会拍平成空), 别名用完整斜杠键 `window/size/viewport_width`。`missing-resource-import` 的 noop 走 L0 加载 gate 崩溃 (缺资源 import 也救不回), golden 改用内置 PlaceholderTexture2D 无外部依赖。

健康度详情见 [`../docs/testcase_audit.md`](../docs/testcase_audit.md);
机器可读快照 [`../docs/testcase_health.json`](../docs/testcase_health.json)
由 `python scripts/audit_testcases.py` 生成。收集更好 testcase 的方法论见
[`../docs/collecting_better_testcases.md`](../docs/collecting_better_testcases.md)。

### git 型 testcase 依赖的外部 repo

`survey-*` 都是 git 型, 必须在对应 `source_repo` 内运行, 非自包含。

| testcase 组 | source_repo | baseline_ref |
|---|---|---|
| survey-codex_…624e21 / survey-unknown_…000 | `C:\Users\WinterZhao\Codes\godot_demo` | 540455d… |
| survey-history_* (3) | `C:\Users\WinterZhao\Documents\test` | 各自 commit |
| survey-two-step-signal-oracle | `C:\tmp\godot_demo_survey_badcase` | ca63631… |

## 目录格式

```
bench-0001-attack-buff/
  testcase.toml        # 必需: manifest
  expected.json        # py_config 用
  expected_delta.json  # py_tscn_diff 用(配 baseline/<scene>.tscn)
  arch_rules.json      # py_gdscript_ast 用
  verifier.gd          # godot_scenetree / visual_static / interaction_routing 用
  fix.diff             # 可选: 已知正确改动, 用于自测验证器
```

### testcase.toml

```toml
[testcase]
id = "bench-0001-attack-buff"
category = "intent_translation"   # 见下方五类
baseline_ref = "<源 repo 的 commit SHA>"   # runner 用 git worktree checkout 这个点
source_repo = "godot-creature-sim"          # 可选, 仅记录
task = "用自然语言写清要 AI 做什么"

[verifier]
type = "py_config"     # 见下方验证器类型
entry = "expected.json"

[scoring]
mode = "fields"        # checkpoints | fields | tristate | weighted
```

### 五个 category

| category | 含义 | 典型验证器 |
|---|---|---|
| `behavior_logic` | 运行时行为对不对 | `godot_scenetree` / `godot_scene_assert` |
| `intent_translation` | 把自然语言意图翻成正确数值/配置 | `py_config` |
| `precise_edit` | 精确改动且无副作用 | `py_tscn_diff` |
| `architecture` | 代码结构/依赖约束 | `py_gdscript_ast` |
| `visual_audio` | 视觉/布局 | `visual_static` |

### 验证器类型

**纯 Python(无需 Godot)**
- `py_config` — 读 `expected.json`, 在 `files_glob` 命中的配置里按 `aliases` 找字段,
  比对 `expected`。`must_differ_from_base=true` 时, 值等于 `base` 判失败。
- `py_tscn_diff` — 读 `expected_delta.json` + `baseline/<scene>.tscn`, 对比工作区场景的
  增删节点/改属性。三态打分: 缺意图改动 -> fail, 有意图但有副作用 -> partial, 干净命中 -> pass。
- `py_gdscript_ast` — 读 `arch_rules.json`, 对 `target_files` 跑规则
  (`forbid_import_glob` / `forbid_hardcoded_res_path` / `require_extends`),
  每违反一条扣 `weight`, score = max(0, 100 - 扣分) / 100。

**需要 Godot 在 PATH 上**
- `godot_scenetree` / `visual_static` / `interaction_routing` — 把 `verifier.gd`
  (`extends SceneTree`)注入工作区跑 headless, 脚本 print 出
  `{"assertions":[{"name","pass"}]}`, 据此打分, 跑完删除临时脚本。
- `godot_scene_assert` — 通过验证场景启动项目, 支持 autoload 和主场景节点, 同样读取 assertion JSON。

## 怎么跑

执行起点取决于 testcase 的 `source_kind`:

- `folder` 型: **自包含, 任意目录都能跑**。runner 把 `baseline/` 拷进临时区、`git init`,
  资源导入由 runner 自动完成。
- `git` 型: runner 用 `git worktree` checkout `baseline_ref`, 所以必须在目标游戏 repo 内执行。

需要 Godot 的验证器(`godot_scene_assert` 等)要求 `godot` 在 PATH 上, 或用 `--godot-binary` 指定。

```bash
TCDIR='C:\Users\WinterZhao\Codes\AIGameDevBench\testcases'

# 列出
aigdbench list --testcases-dir "$TCDIR"

# 基线对照: noop 什么都不改 -> 必须 fail / 0.00
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 --driver noop

# 回放正确改动: patch 应用 fix.diff -> pass / 1.00
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver patch --patch testcases/gdb-task_0002/fix.diff
```

### 三种 driver

| `--driver` | 作用 | 必带参数 |
|---|---|---|
| `noop` | 什么都不改, 基线对照(应得 0) | - |
| `patch` | 应用一个现成的 diff(回放正确改动或离线评一个 AI 的产出) | `--patch <file>` |
| `command` | 在工作区内调用任意命令行 harness 现场完成任务 | `--harness-cmd '<模板>'` |

`--driver command` 用占位符把任务交给 harness: `{task}`(任务原文, 单参数)、
`{task_file}`(工作区里的 `TASK.md` 路径)、`{workspace}`(工作区路径)。命令模板用
`shlex` 切分, 不经过 shell。

```bash
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver command --harness-cmd 'codex exec --cd {workspace} {task}' \
  --timeout 600 --log-dir harness-logs --report report.json
```

> harness 不要 commit 自己的改动: runner 用 `git status --porcelain` 检测变化。
> 一旦 commit, 工作区就干净了, 检测不到改动, 得 0 分。改完留在工作区即可。

离线评一个 AI: 让它在起点状态完成 `task` -> `git diff > ai.diff` ->
`--driver patch --patch ai.diff` 出分。

## 示例:gdb-task_0002

`behavior_logic` + `godot_scene_assert`, folder 型(自包含, 需要 Godot)。任务是让子弹
命中敌人时推进任务、命中后自我移除、离屏 50 像素自我移除。verifier 逐 checkpoint 打分。

| driver | status | score |
|---|---|---|
| noop | fail | 0.00 |
| patch (fix.diff) | pass | 1.00 |

## 注意

- 入口脚本 `aigdbench` 若不在 PATH, 用
  `python -c "from aigamedevbench.cli import main; main()"` 后接同样的子命令/参数调用,
  或先 `pip install -e .`。
- `--testcases-dir` 传 Windows 原生路径(`C:\...`), 不要用 git-bash 的 `/c/...`。

## 两种起点形态(source_kind)

| source_kind | 起点 | 谁用 |
|---|---|---|
| `git` | 源 repo 的一个 commit, runner 用 `git worktree` checkout | 原生 testcase, 必须在目标游戏 repo 内跑 |
| `folder` | testcase 自带的 `baseline/` 子目录(自包含 Godot 项目), runner 拷进临时区并 `git init` | 可独立跑, 无需在游戏 repo 内 |

## 从 GameDevBench 导入任务(folder + godot_scene_assert)

GameDevBench 每个 task 是自包含项目 + 一个黄金验证器(`scenes/test.tscn` + `scripts/test.gd`,
打印 `VALIDATION_PASSED/FAILED`)。导入脚本把它转成本仓的 folder-type testcase:

```
gdb-task_0002/
  testcase.toml          # source_kind="folder", verifier.type="godot_scene_assert"
  baseline/              # 起点项目
  verifier_scene.tscn    # 由 test.tscn 改来, 脚本路径换成占位符 __VERIFIER_GD__
  verifier.gd            # 由 test.gd 转译: extends Node, 逐 checkpoint 打印 {"assertions":[...]}
  fix.diff               # baseline -> ground-truth 的 diff, 自测用
```

`godot_scene_assert` 走场景模式而非 `--script`, 是为了让被测项目的 autoload 和主场景节点正常加载。

导入:

```bash
python scripts/import_gamedevbench.py --gdb ../GameDevBench --out testcases --tasks task_0002 task_0003
```

脚本会跳过 `requires_display` 任务。`test.gd -> verifier.gd` 默认产单 checkpoint 兜底;
要逐断言部分得分需手工拆分。导入后务必自测两条硬不变量: `noop -> 0.00` 且
`patch fix.diff -> 1.00`。
