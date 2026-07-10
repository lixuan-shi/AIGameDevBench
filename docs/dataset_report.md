# AIGameDevBench 数据集报告

> 目的：让读者在几分钟内对本数据集的**规模、构成、分类依据**建立直观、具体、准确的认识。
> 覆盖两个数据集：**全量 `testcases/`（519 个）** 与 **精选 `testcases_filtered/`（50 个）**。
> 统计基准：`testcase.toml` 元数据（每个 case 一个）。日期：2026-07-01。

---

## 0. 一句话概览

AIGameDevBench 是一个针对 **AI 在 Godot 引擎中做游戏开发** 的受控基准。每个 testcase 给 AI 一个起始工程（baseline）和一个任务描述，AI 产出代码修改，再由一个**可判定的 verifier** 自动打分。数据集由两类来源构成：**少量高质量手工精制** + **大量从真实开源项目 git 修复历史自动挖掘（survey）**。

| | 全量 `testcases/` | 精选 `testcases_filtered/` |
|---|---|---|
| 总数 | **519** | **50** |
| 手工精制 | 34（6.6%） | **34（68%）** |
| survey 自动挖掘 | 485（93.4%） | 16（32%） |
| 主验证方式 | survey_bad_case（回归重现） | godot_scene_assert（运行时断言）为主 |
| 定位 | 广度、真实性、规模 | 质量、多样性、可读性——快速评测/演示用 |

**一句话区别**：全量数据集"多而真实但同质"（93% 是同一种自动挖掘 + 同一种 verifier）；精选集"少而精且多样"（以手工 case 为骨干，补 16 个题材各异的 survey 代表）。

---

## 1. 分类依据（两个正交维度）

数据集用**两个独立维度**给 case 归类，理解这两个维度是读懂分布的前提：

### 维度 A — `category`：任务考察的**能力类型**
| category | 含义 | 典型任务 |
|---|---|---|
| `behavior_logic` | 游戏运行时行为 / 逻辑正确性 | 伤害结算、状态机转移、寻路、存档正确性 |
| `architecture` | 代码结构 / 分层 / 依赖约束 | 组件边界、禁止硬编码资源路径 |
| `precise_edit` | 对指定文件 / 节点 / 属性的精确改动 | 改碰撞层、重挂 spawnpoint、接信号 |
| `intent_translation` | 把自然语言意图翻译成配置 / 数值 | 难度预设、掉落率、跳跃手感调参 |
| `visual_audio` | 视觉 / 布局 / 音频呈现 | HUD 血条锚点、菜单面板布局 |

### 维度 B — `verifier.type`：任务如何**被自动判定**
| verifier | 判定方式 |
|---|---|
| `survey_bad_case` | 重现"已知坏例"检测：是否复发原始 bad case（回归测试） |
| `godot_scene_assert` | 在 Godot 里加载场景、运行、对运行时状态做断言 |
| `py_config` | Python 检查配置 / 数值字段是否符合期望 |
| `py_tscn_diff` | 比对 `.tscn` 场景文件的结构化差异 |
| `py_gdscript_ast` | 解析 GDScript AST 检查结构约束 |
| `visual_static` | 静态检查视觉 / 布局属性 |

### 来源族（source family）——数据从哪来
| 前缀 | 来源 | 说明 |
|---|---|---|
| `survey-fixcommit_*` | 开源项目 git 修复提交 | 自动挖掘：某个 fix commit 前的状态 = baseline，让 AI 重现修复 |
| `survey-history_*` | 开源项目 git 历史 | 同上，取自历史快照 |
| `gdb-task_*` | 手工制作（编号任务） | 有专门 verifier / checkpoints |
| 具名 case（如 `health-damage-death`） | 手工制作 | 自包含 folder 工程 + 专门 verifier |

---

## 2. 全量数据集 `testcases/`（519）

### 2.1 按 category
| category | 数量 | 占比 |
|---|---:|---:|
| behavior_logic | 334 | 64.4% |
| architecture | 86 | 16.6% |
| precise_edit | 54 | 10.4% |
| intent_translation | 43 | 8.3% |
| visual_audio | 2 | 0.4% |

→ **严重偏向 behavior_logic**（近 2/3）；visual_audio 几乎缺席。

### 2.2 按 verifier
| verifier | 数量 | 占比 |
|---|---:|---:|
| survey_bad_case | 485 | 93.4% |
| godot_scene_assert | 23 | 4.4% |
| py_config | 5 | 1.0% |
| visual_static | 2 | 0.4% |
| py_tscn_diff | 2 | 0.4% |
| py_gdscript_ast | 2 | 0.4% |

→ **93% 用同一种 verifier**（survey_bad_case）。判定方式高度同质。

### 2.3 按来源族
| 来源族 | 数量 | 占比 |
|---|---:|---:|
| survey-fixcommit | 469 | 90.4% |
| survey-history | 16 | 3.1% |
| gdb-task（手工） | 10 | 1.9% |
| 具名手工 case | 24 | 4.6% |

→ **93.4% 自动挖掘，6.6% 手工**。

### 2.4 survey 来源仓库（485 个 survey case 的分布）
6 个真实开源 Godot 项目，覆盖不同游戏类型：

| 源仓库 | 游戏类型 | 数量 |
|---|---|---:|
| Super-Mario-Bros.-Remastered-Public | 平台跳跃 | 144 |
| jdungeon | 多人地牢 RPG | 93 |
| tabletop-club | 桌游 / 物理模拟 | 70 |
| godot-open-rpg | 回合制 RPG | 63 |
| a-little-game-called-mario | 平台 | 59 |
| godot-open-rts | 即时战略 | 56 |

### 2.5 按年份（case id 中的修复提交日期）
| 年 | 数量 |
|---|---:|
| 2018 | 27 |
| 2019 | 12 |
| 2020 | 1 |
| 2021 | 1 |
| 2022 | 103 |
| 2023 | 156 |
| 2024 | 23 |
| 2025 | 153 |
| 2026 | 9 |

→ 时间跨度 2018–2026，集中在 2022 / 2023 / 2025 三个高峰。

---

## 3. 精选数据集 `testcases_filtered/`（50）

### 3.1 挑选依据（明确的两步策略）
1. **质量优先**：全部 34 个手工精制 case 无条件纳入——它们有专门 verifier、checkpoints、清晰的任务描述与 golden/bad 参照，质量最高。
2. **多样性补充**：从 485 个 survey 中挑 16 个补到 50。挑选标准是
   - **题材多样**：按源仓库（游戏类型）加权，覆盖尽可能多的游戏子系统；
   - **实质性**：只选真实行为 / 逻辑 / 架构缺陷，剔除纯格式 / 版本号 / 空白 churn（最终 15 个 high-substance + 1 个 medium）。

### 3.2 按 category
| category | 数量 | 占比 | vs 全量 |
|---|---:|---:|---|
| behavior_logic | 36 | 72% | 略高（骨干 case 多为行为逻辑） |
| intent_translation | 6 | 12% | 显著提升（全量 8.3%） |
| precise_edit | 4 | 8% | 相近 |
| architecture | 2 | 4% | 下降（全量 16.6%，因手工 arch case 少） |
| visual_audio | 2 | 4% | **提升**（全量仅 0.4%，把仅有的 2 个都纳入） |

→ 精选集**主动把稀有类型（visual_audio）全部保留**，改善长尾覆盖。

### 3.3 按 verifier（这是与全量最大的差异）
| verifier | 数量 | 占比 | vs 全量 |
|---|---:|---:|---|
| godot_scene_assert | 23 | 46% | **4.4% → 46%** |
| survey_bad_case | 16 | 32% | 93.4% → 32% |
| py_config | 5 | 10% | 提升 |
| py_tscn_diff | 2 | 4% | 提升 |
| py_gdscript_ast | 2 | 4% | 提升 |
| visual_static | 2 | 4% | 提升 |

→ 精选集**全部 6 种 verifier 均有代表**，从"93% 单一 verifier"变为运行时断言主导、判定方式均衡。

### 3.4 按来源
| 来源 | 数量 | 说明 |
|---|---:|---|
| 手工（folder + gdb-task） | 34 | source_kind = `folder` |
| survey（git 挖掘） | 16 | source_kind = `git` |

16 个 survey 覆盖全部 6 个源仓库、15+ 个不同游戏子系统：
战斗/计分、敌人 AI、存档/读档、投射物物理、行为树状态机、对话/NPC 交互、
物理交互、网络多人大厅、资源导入、寻路、任务系统、推箱子解谜、角色碰撞、
攻击调度、导航架构。

---

## 4. 两个数据集怎么选用

| 场景 | 用哪个 | 原因 |
|---|---|---|
| 快速冒烟 / 演示 / 开发迭代 | **filtered 50** | 小、快、多样，verifier 覆盖全，可读性高 |
| 正式广度评测 / 统计显著性 | **全量 519** | 规模大、来自真实项目，抗过拟合 |
| 考察运行时行为能力 | filtered（46% scene_assert）或全量按 verifier 过滤 | |
| 研究真实修复分布 | 全量 survey 子集 | 保留真实 git 修复的自然分布 |

---

## 5. 关键提醒（数据集偏差）

- **全量高度同质**：93% 是 survey_bad_case + git 挖掘，behavior_logic 占 64%。用全量做能力细分评测时，非 behavior_logic / 非 survey 的样本量很小（如 visual_audio 仅 2 个），统计力弱。
- **survey task 已脱敏**：survey case 的 `task` 字段原本内嵌了 fix commit 标题 / 哈希 / 内部分类码（会泄露解法与评分机制），已批量重写为"只给受影响文件 + 中性目标"。原始信息保留在 `provenance` 与 `bad.diff` 中。
- **filtered 是人为均衡的子集**，不反映真实分布——它牺牲"代表真实频率"换取"覆盖广、质量高、判定多样"。做分布性研究时不要拿它当总体样本。
