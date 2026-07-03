# 全量数据集报告 — `testcases/`（519 个）

> 目的：让读者快速、准确地认识 AIGameDevBench **全量**数据集的规模与构成。
> 统计基准：每个 case 的 `testcase.toml` 元数据。日期：2026-07-01。
> （精选子集见 `filtered_dataset_report.md`。）

---

## 0. 一句话概览

AIGameDevBench 是针对 **AI 在 Godot 引擎做游戏开发** 的受控基准：每个 testcase 给 AI 一个起始工程 + 任务描述，AI 产出代码修改，再由**可判定的 verifier** 自动打分。

全量数据集 **519 个 case**，最鲜明的特征是**高度同质**：

- **93.4%** 来自开源项目 git 修复历史的**自动挖掘**（survey），仅 6.6% 手工精制；
- **93.4%** 用同一种 verifier（`survey_bad_case`，回归重现）；
- **64.4%** 属于 `behavior_logic` 一类。

它的价值在**广度、真实性、规模**——数据来自 6 个真实开源 Godot 项目、跨 2018–2026 八年。

---

## 1. 分类依据（三个正交维度）

### 维度 A — `category`：任务考察的能力类型
| category | 含义 |
|---|---|
| `behavior_logic` | 游戏运行时行为 / 逻辑正确性（伤害、状态机、寻路、存档） |
| `architecture` | 代码结构 / 分层 / 依赖约束 |
| `precise_edit` | 对指定文件 / 节点 / 属性的精确改动 |
| `intent_translation` | 把自然语言意图翻译成配置 / 数值 |
| `visual_audio` | 视觉 / 布局 / 音频呈现 |

### 维度 B — `verifier.type`：如何被自动判定
| verifier | 判定方式 |
|---|---|
| `survey_bad_case` | 重现"已知坏例"检测：修改后是否复发原始 bad case（回归） |
| `godot_scene_assert` | 在 Godot 加载场景、运行、对运行时状态断言 |
| `py_config` | Python 检查配置 / 数值字段 |
| `py_tscn_diff` | 比对 `.tscn` 场景文件结构化差异 |
| `py_gdscript_ast` | 解析 GDScript AST 检查结构约束 |
| `visual_static` | 静态检查视觉 / 布局属性 |

### 维度 C — 来源族：数据从哪来
| 前缀 | 来源 | 说明 |
|---|---|---|
| `survey-fixcommit_*` | 开源项目某个 fix commit | commit 前状态 = baseline，让 AI 重现修复 |
| `survey-history_*` | 开源项目历史快照 | 同上 |
| `gdb-task_*` | 手工（编号任务，源自教程） | 有专门 verifier |
| 具名 case | 手工自包含工程 | 有专门 verifier + golden/bad 参照 |

---

## 2. 分布

### 2.1 按 category
| category | 数量 | 占比 | |
|---|---:|---:|---|
| behavior_logic | 334 | 64.4% | `████████████████` |
| architecture | 86 | 16.6% | `████` |
| precise_edit | 54 | 10.4% | `██▌` |
| intent_translation | 43 | 8.3% | `██` |
| visual_audio | 2 | 0.4% | `▏` |

→ 近 2/3 是 behavior_logic；visual_audio 几乎缺席（仅 2 个）。

### 2.2 按 verifier
| verifier | 数量 | 占比 | |
|---|---:|---:|---|
| survey_bad_case | 485 | 93.4% | `███████████████████` |
| godot_scene_assert | 23 | 4.4% | `▉` |
| py_config | 5 | 1.0% | `▏` |
| visual_static | 2 | 0.4% | `▏` |
| py_tscn_diff | 2 | 0.4% | `▏` |
| py_gdscript_ast | 2 | 0.4% | `▏` |

→ 判定方式高度单一：93% 是 survey_bad_case。

### 2.3 按来源族
| 来源族 | 数量 | 占比 |
|---|---:|---:|
| survey-fixcommit | 469 | 90.4% |
| survey-history | 16 | 3.1% |
| gdb-task（手工） | 10 | 1.9% |
| 具名手工 case | 24 | 4.6% |

→ **93.4% 自动挖掘 / 6.6% 手工**。

### 2.4 survey 来源仓库（485 个 survey 的分布）
6 个真实开源 Godot 项目，覆盖不同游戏类型：

| 源仓库 | 游戏类型 | 数量 | |
|---|---|---:|---|
| Super-Mario-Bros.-Remastered-Public | 平台跳跃 | 144 | `██████████` |
| jdungeon | 多人地牢 RPG | 93 | `██████▌` |
| tabletop-club | 桌游 / 物理模拟 | 70 | `█████` |
| godot-open-rpg | 回合制 RPG | 63 | `████▌` |
| a-little-game-called-mario | 平台 | 59 | `████` |
| godot-open-rts | 即时战略 | 56 | `████` |

### 2.5 按年份（修复提交日期）
| 年 | 数量 | |
|---|---:|---|
| 2018 | 27 | `██▊` |
| 2019 | 12 | `█▎` |
| 2020 | 1 | `▏` |
| 2021 | 1 | `▏` |
| 2022 | 103 | `██████████▍` |
| 2023 | 156 | `███████████████▋` |
| 2024 | 23 | `██▍` |
| 2025 | 153 | `███████████████▍` |
| 2026 | 9 | `▉` |

→ 跨度 2018–2026，集中于 2022 / 2023 / 2025。

---

## 3. survey case 的机制（占 93%，务必理解）

`survey_bad_case` 类 case 的构造：
1. 取开源项目一个 **fix commit** —— 该 commit 修复了某个缺陷；
2. commit **之前**的代码快照 = baseline（含缺陷）；
3. 任务：让 AI 修复该缺陷；
4. verifier（`survey_bad_case.json`）检测修改后是否**复发原始坏例**（回归判定）；
5. `bad.diff` 记录了当初导致坏例的错误改法，`provenance.bad_case_type`（A1/A2/…）是内部分类码。

**脱敏说明**：survey case 的 `task` 字段原本内嵌了 fix commit 的标题、哈希、内部分类码（会直接泄露解法和评分机制），已批量重写为中性形式：

```
task = "Investigate and fix the defect in the following file(s),
        making the affected feature behave correctly: <受影响文件列表>."
```

原始 commit 信息仍保留在 `provenance` 与 `bad.diff` 中（供 grader / 复现用，AI 看不到）。

---

## 4. 关键提醒（使用全量数据集时）

- **同质性偏差**：93% 同一 verifier + 同一挖掘方式，64% 同一 category。若要做能力细分评测，非 behavior_logic / 非 survey 的样本量极小（visual_audio 仅 2 个、各 py_* verifier 仅 2–5 个），统计力弱。
- **优势在真实性与规模**：数据取自真实项目的真实修复，抗过拟合，适合正式广度评测与统计显著性分析。
- **快速迭代 / 演示 / verifier 覆盖** 请改用精选子集 `testcases_filtered/`（50 个，见另一份报告）。
