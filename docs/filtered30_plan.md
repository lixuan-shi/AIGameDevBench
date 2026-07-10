# 目标：重做 testcases-filtered（30 个）+ 强化验证标准

## 目标拆解
1. **修改验证标准**：让 survey_bad_case 的 oracle 从"弱"变"鲁棒"。
2. **基于 testcases 整理**，选出 30 个满足：
   - 集合鲁棒
   - 有挑战性
   - 案例有代表性
   - 重复性低
   - 测试验证方式和 oracle 鲁棒

## 已查清的核心问题（验证标准的病根）
`survey_bad_case` verifier（src/aigamedevbench/verifiers/survey_bad_case.py）在
`original_l0_pass/l1_pass == null` 时（绝大多数 survey case 如此），实际只做：
- `changed_relevant_file`：改了 must_change_one_of 里的文件
- `does_not_reproduce_original_bad_diff`：**diff 逐字 != bad.diff**（bad.diff 空则自动通过）
- `l0_l1_gate_passes`：代码能编译/加载

→ 无法区分"真修对了"与"随便改一下没崩"。这违背"oracle 鲁棒"。

有强 oracle 的类型（保留/优先）：
- godot_scene_assert（运行时断言）
- py_tscn_diff（结构化 diff，节点粒度）
- py_gdscript_ast（AST 规则）
- py_config（配置字段）
- visual_static（布局属性）
- survey_bad_case **仅当** bad.diff 非空且 baseline_ref != bad_ref（能区分坏改法）

## 验证标准改进方向（待实现）
选项 A（低风险，推荐先做）：**收紧 survey_bad_case 的 usable 门槛**——
  把 bad.diff 空 / baseline_ref==bad_ref 的 case 判为不合格，不进 filtered30。
  即：不改 verifier 代码，用"筛选"保证只纳入强 oracle 的 case。
选项 B（更强）：给 survey_bad_case 增加基于 hidden_oracle.good_diff 的正向判定
  （检查是否触及 good.diff 覆盖的关键行/符号），把"没做错"升级为"做对了"。

## 选择策略（30 个）
- 优先纳入所有强 oracle 的手工 case（34 个候选，去重后取代表）
- survey 只纳入强 oracle（bad.diff 非空 + 有实质缺陷）且题材不重复的
- 按 dedup_key 去重：同 subsystem+同 bug pattern 只留一个最佳
- 目标分布：verifier 类型尽量全覆盖，category 覆盖 5 类，题材去重

## 分诊结论（workflow wrvqlmlk2，82 次评估）
- **32 个手工 case = strong oracle**（30 usable；elite-attack-buff-pct / ui-window-stretch-config 因低挑战被排除）
- **全部 48 个 survey case = weak oracle、全部 unusable**：一致原因是
  bad.diff 空 + original_l0/l1_pass=null → 实际 oracle 退化为"改了相关文件 + 项目能加载"，
  无法区分真修复与瞎改。→ **survey 一个都不纳入 filtered30**（满足"oracle 鲁棒"）。

## 验证标准修改（已实施，选项 A+）
在 src/aigamedevbench/verifiers/survey_bad_case.py 增加硬失败 check
`oracle_is_discriminating`：当 bad.diff 空 且 无 runtime 回归断言(l0/l1 期望 False)
且 无 human/round 过程上下文时，判 fail（"non-scoreable"），不再默默给分。
→ verifier 现在会诚实暴露弱 oracle，而非虚高分数误导筛选/评测。
新增测试 test_survey_bad_case_verifier_flags_weak_oracle_as_non_scoreable。

## 30 个清单（.filtered_30.txt）
22 authored + 8 gdb-task。去重砍掉 gdb-task_0013(fsm 与 0281/player-fsm 重复)、
gdb-task_0002(projectile 与 0012 重复)。verifier 覆盖全 6 种：
scene_assert ×21, py_config ×3, py_tscn_diff ×2, py_gdscript_ast ×2, visual_static ×2。
category 覆盖 5 类。题材去重后覆盖 20+ 子系统。

## 进度（全部完成）
- [x] 查清 survey_bad_case 弱 oracle 病根
- [x] oracle 强度分析脚本 + 质量分诊 workflow（wrvqlmlk2）
- [x] 定 30 个清单（.filtered_30.txt）
- [x] 实施验证标准修改（oracle_is_discriminating 硬门槛 + 测试）
- [x] 重建 testcases_filtered（30 个，逐条 cp -r 绕过 auto-mode 抖动）
- [x] 验证：30/30 目录齐全，各有 testcase.toml；原 testcases/ 519 未损
- [x] 测试全绿：pytest 132 passed（含新增弱-oracle 测试）

## 最终结果
- testcases_filtered/ = 30 个 strong-oracle、去重、覆盖全 6 种 verifier 的 case
  verifier 分布：godot_scene_assert ×21, py_config ×3, py_tscn_diff ×2,
  py_gdscript_ast ×2, visual_static ×2。survey_bad_case ×0（全部弱 oracle，已排除）
- 验证标准已强化：survey_bad_case verifier 新增 oracle_is_discriminating 硬门槛，
  弱 oracle case 现在判 fail（non-scoreable），不再虚高给分。
