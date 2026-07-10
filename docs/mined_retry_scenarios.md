# Mined Retry Scenarios — Real Game-Dev Failures from Local Agent History

挖掘本地 AI 编码助手的对话历史, 找"单次对话中多次错误重试"的真实游戏开发场景,
转成 testcase 加进 bench。这是 `docs/collecting_better_testcases.md` 里"挖真实失败 >
合成"那条路的落地。

## 挖掘方法

`scripts/mine_retry_sessions.py` 扫 `~/.claude/projects/<project>/*.jsonl`(排除
benchmark 自己的临时工作区 `aigdbench-ws-*`), 按四类重试信号给每个会话打分:

| 信号 | 含义 | 权重 |
|---|---|---|
| `tool_error` | `tool_result.is_error=true`(命令退出非0、编译错、文件不存在) | 3 |
| `file_thrash` | 同一文件被 Edit/Write ≥3 次(反复返工) | 2 |
| `user_correction` | 用户纠正用语(不对/还是错/报错/重新/wrong/still…) | 2 |
| `godot_crash` | Godot 特定报错(Parse Error / SCRIPT ERROR / Could not find type…) | 4 |

`retry_score` = 加权和。脚本输出排序表 + 导出 `retry_scenarios.json` 供人工审阅。

```bash
python scripts/mine_retry_sessions.py --min-score 6 --json ./retry_scenarios.json
# 深读单个会话的时间线(任务 + 错误 + 编辑序列):
python scripts/mine_retry_sessions.py --inspect <session.jsonl> --json out.json
```

> 隐私: `retry_scenarios.json` / `mined_sessions/` / `inspect_*.json` 已加入
> `.gitignore`, 私人对话内容绝不入库。读 `~/.claude/projects` 需要本机授权
> (auto-mode 默认拦截访问对话历史)。

## Claude 历史挖掘结果(2026-06-30)

排除工具仓自身(AIGameDevBench/Survey/Collecter)后, 真实游戏开发重试会话排序:

| retry_score | 项目 | 引擎 | 信号 (te/ft/uc/gc) | 任务 |
|---|---|---|---|---|
| 155 | Documents/test | Godot | 9/57/5/1 | 修编译错 + 屏幕下方事件/NPC/物品右键无响应 |
| 37 | GameDevFeatsShowcase/ui-login | Godot | 5/11/0/0 | 让 UI 大小和窗口大小一致, 支持动态拉伸 |
| 27 | UE5Demo | Unreal | 9/0/0/0 | 装 unlua/puerTS 插件(偏环境配置) |
| 26 | Documents/test | Godot | 4/7/0/0 | DataCatalog/gm_panel 配置面板反复改 |
| 11 | UE5Demo | Unreal | 1/4/0/0 | character 基类 + AIController + navlink 寻路 |

### 深读还原的真实陷阱

**1. ui-login(GameDevFeatsShowcase, Godot)— 可重制 ✅**
- 任务: "让 UI 大小和窗口大小保持一致, 支持动态拉伸"
- 真实陷阱(Claude 自己在对话中诊断出, 又反复调 login.gd 8 次):
  - `project.godot` 设了 `window/stretch/mode="canvas_items"` + `aspect="expand"`,
    但**缺基准分辨率** `window/size/viewport_width` / `viewport_height` —— 拉伸模式
    只有设了基准分辨率才真正生效, 否则配置看似完整实则无效。
  - `login.tscn` 的中间 `Panel` 用**固定像素 offset**(±190/±120)居中, 窗口拉伸时
    面板尺寸不变。
- 另有一次 tool_error: Claude 第一次用 WSL 风格路径 `/mnt/c/...` Read 失败, 才改 `C:\`。

**2. Documents/test(Godot)— 部分可提炼 ⚠️**
- 任务: "存在编译错误请修改; 屏幕下方的事件/交互物/NPC 按键右键没有反应"
  (后续: 三栏切换 + 右键弹框改配置 + 拖拽到游戏区生成)
- 真实陷阱: `catalog_browser_panel.gd` 改了 35 次; 反复出现
  **`SCRIPT ERROR: Parse Error: Cannot infer the type of "<var>" variable because
  the value doesn't have a set type`** —— GDScript 类型推断陷阱(`var x := node.foo`
  在 node 无类型时无法 `:=` 推断)。
- 整会话需求太大、太项目特定, 不宜整体重制; 但"Cannot infer type"这个陷阱可单独提炼成
  一个精炼 case。(注: 这个项目就是现有 `survey-history_*` 的同源仓。)

**3. UE5 AIController(Unreal C++)— 不进 bench ❌**
- 任务: "新建 UE5Demo character 基类, 用 AIController 寻路, 鼠标点击自动寻路, 能用
  navlink"; `DemoAIController.cpp` 改 4 次。
- 陷阱是 UE C++ 编译/API 错误。**bench 目前只支持 Godot**(验证器靠 godot 二进制),
  UE 无法在现有框架里跑。记录备查, 不重制。

## 待造 testcase(从真实场景重制, 两个)

> 状态: baseline 文件已部分写出(`testcases/ui-window-stretch-config/`),
> 但本会话 auto-mode 收紧后无法跑 `aigdbench smoke`/git/python 审计。需在新会话或
> 加 Bash 白名单后完成 scaffold → 写 verifier → 真实 git 生成 fix.diff → 审计绿
> (noop=0 / golden=1)→ 提交 → 更新 README。

### 待造 A: `ui-window-stretch-config`(intent_translation, py_config)
- **来源**: ui-login 会话。
- **baseline**: `project.godot` 有 stretch mode 但**缺** `window/size/viewport_width`
  / `viewport_height`(拉伸失效); 一个最小 `scenes/login.tscn`(Control 全屏锚点)。
- **task**: "让 UI 随窗口动态缩放。当前 project.godot 设了 stretch 模式但没设计基准
  分辨率, 所以拉伸不生效。补上基准分辨率(viewport_width=1280, viewport_height=720)
  使 canvas_items 拉伸真正生效。"
- **verifier(expected.json)**: 两个字段
  - `viewport_width` alias, files_glob `project.godot`, expected 1280
  - `viewport_height` alias, expected 720
  - baseline 没这俩字段 → found=None → fail → **noop=0**; golden 补上 → **1.0**。
- **trap**: 只设 stretch mode 而不设基准分辨率(看似配好其实无效)—— 真实会话里
  Claude 正是先漏了这步才反复调。
- ⚠️ 实现注意: py_config 的 `flatten_config` 对 `project.godot` 的斜杠键
  (`window/size/viewport_width`)拍平后, leaf = `key.split(".")[-1]`。需先验证
  flatten 后 leaf 是否等于 `viewport_width`(键里无 `.`, 末段可能是整个
  `window/size/viewport_width`)。若别名匹配不上, 改用能命中的 alias 串, 或改用
  `py_gdscript_ast`/自定义。**造之前先 flatten 验证一次。**

### 待造 B: `gdscript-cannot-infer-type`(behavior_logic, godot_scene_assert)
- **来源**: Documents/test 会话的高频陷阱。
- **baseline**: 一个 `.gd`, 函数里写 `var x := some_untyped.get_thing()` 触发
  `Parse Error: Cannot infer the type`(脚本加载失败 → L0 崩溃 / 验证器拿不到断言)。
- **task**: "修复 res://scripts/<x>.gd 的编译错误, 使脚本能加载并正确返回 X。"
- **verifier**: godot_scene_assert; baseline 因 parse error 整体失败 → noop=0;
  golden(给变量显式类型或去掉 `:=`)→ 脚本加载、断言通过 → 1.0。
- **trap**: GDScript `:=` 对无类型来源无法推断 —— 极高频真实编译错误。
- ⚠️ 实现注意: baseline 含 parse error 时, L0 gate 会判定崩溃。确认 noop 走的是
  "脚本加载失败 → 断言 JSON 缺失 → score 0", 与"golden 加载成功 → 1.0"两端都成立。

## Codex 历史挖掘(同方法, 不同格式)

`mine_retry_sessions.py` 已支持 Codex rollout 格式。Codex 会话在
`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`(本机 49 个), schema 与 Claude 不同:

| Claude (`.claude/projects`) | Codex (`.codex/sessions`) |
|---|---|
| `{type:user/assistant, message:{content:[...]}}` | `{type:message, role, content:[{type:input_text/output_text, text}]}` |
| `tool_result.is_error=true` | `function_call_output.output` 以 `Exit code: <非0>` 开头 |
| `tool_use(Edit/Write).file_path` | `function_call(apply_patch)` 里 `*** Update/Add File: <path>` |
| cwd 在每条 record 的 `cwd` 字段 | cwd 在 user message 的 `<environment_context><cwd>...` |

四信号评分逻辑复用, 权重相同。运行:

```bash
python scripts/mine_retry_sessions.py --codex --min-score 6 --json ./retry_scenarios_codex.json
```

> **状态(2026-06-30)**: codex 挖掘脚本已写好, 但运行被 auto-mode 拦截 —— 之前为
> Claude 加的权限规则只覆盖 `~/.claude/projects`, 未覆盖 `~/.codex/sessions`。读 codex
> 历史需要在 settings 再加一条, 例如:
> `"permissions": { "allow": ["Read(//c/Users/WinterZhao/.codex/sessions/**)"] }`
> 或允许 `Bash` 跑该脚本。加完后跑上面的命令, 得到 codex 的重试场景排序, 再按本文件
> "深读 → 提炼陷阱 → 重制 folder testcase"的同一流程处理。
> 注: codex 会话同样含真实游戏项目(Documents/test 的 Godot NPC 面板系统、godot_demo
> 等), 预计能挖到与 survey-* 同源的 Godot 重试场景。

### Codex 挖掘结果(2026-06-30, 23 个会话 retry_score≥6)

跑通后实际结果(`--codex`)。注意两点偏差:
- codex 用 `apply_patch` 改文件, 我的 `*** Update File` 正则没匹配上其真实 patch 格式,
  所以 `file_thrash` 普遍为 0(待修: 解析 codex apply_patch 的实际 diff 头)。
- 高分会话多为**环境/工具链问题**(找不到 git/node/scons、编译 godot 源码、装 CLI),
  不是游戏逻辑反复写错 —— 这类不可重制成 gameplay testcase。

真正可重制的游戏开发陷阱(按 godot_crash 信号筛):

| score | 项目 | gc | 任务 | 真实陷阱 |
|---|---|---|---|---|
| 106 | GameDevFeatsShowcase | 4 | 新建 2D Godot 项目(PlayerOnly/NPC) | **场景引用 res://assets/player.svg 但缺 .import → headless 加载报 `No loader found for resource (expected Texture2D)` + main.tscn Parse Error**, codex 反复栽(player.svg 错误刷屏) |
| 86 | Documents/test | 5 | 编排多 agent 写进 skill | 偏 agent 编排, 非 gameplay |
| 13 | Documents/test | 1 | 接入 godot mcp | 环境接入 |

### 待造 C: `missing-resource-import`(behavior_logic / precise_edit, godot_scene_assert)
- **来源**: Codex GameDevFeatsShowcase 会话(score 106)。
- **真实陷阱**: 场景 `.tscn` 用 `[ext_resource type="Texture2D" path="res://assets/x.svg"]`
  引用了一张图, 但该图**没有对应的 `.import` 元文件 / 未被导入**, headless 启动时
  `No loader found for resource: res://assets/x.svg (expected type: Texture2D)`, 场景
  Parse Error 加载失败。这是真实高频陷阱, 且与 bench 的 L0 gate 天然契合。
- **重制思路**: baseline 场景引用一张缺 .import 的图(或路径错的资源)→ L0 加载崩溃 →
  noop=0。golden 修法是把引用改成内置可加载资源(如用 PlaceholderTexture2D / 程序生成的
  ColorRect / 修正路径), 使场景能 headless 加载并通过断言。
- ⚠️ 实现注意: bench 的 runner 在验证前会跑 `godot --import` 重建缓存。要让这个 case 成立,
  baseline 的"缺资源"必须是 import 也救不回来的(例如 ext_resource 指向**根本不存在**的
  路径, 或 type 与实际文件不符), 这样 L0 才真的失败。造之前先实测 noop 是否真的 L0 崩溃。

## 三个待造 testcase 汇总(供新会话重制)

| id | category | verifier | 来源 | 陷阱 |
|---|---|---|---|---|
| ui-window-stretch-config | intent_translation | py_config | Claude/ui-login | stretch 缺基准分辨率 |
| gdscript-cannot-infer-type | behavior_logic | godot_scene_assert | Claude/test | `:=` 类型推断失败 |
| missing-resource-import | precise_edit | godot_scene_assert | Codex/GameDevFeats | 场景引用缺失资源致加载崩溃 |

三个都要走标准流程: scaffold → baseline 复现陷阱 → verifier 围绕根因 → 真实 git 生成
fix.diff → `aigdbench smoke` 审计绿(noop=0 / golden=1)→ 提交 → 更新 README。

## 复用价值

挖掘脚本 + 这套四信号评分(Claude + Codex 两种格式)可周期性重跑, 随对话历史增长持续
产出真实失败场景, 喂给 bench。这是把"真实 agent 失败"持续转成 testcase 的可重复管线。
