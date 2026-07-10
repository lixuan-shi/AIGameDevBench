# Webhook → 并行 Benchmark → 自动发布 工作流规格

本文描述从收到 GitHub webhook 到（可选）自动发布插件新版本的完整链路：每一步做什么、
调用哪个镜像、结果存在哪里、是否打包/发布、以及哪些信息记进版本发布日志。

涉及的组件：

| 组件 | 文件 | 角色 |
|---|---|---|
| 编排器 | `scripts/bench-orchestrator.sh` | 常驻服务，接 webhook → 派发一次 benchmark 批次 |
| 镜像构建 | `scripts/build_runner_image.sh` | 拉最新插件 + vendor + 构建/发布 runner 镜像 |
| 并行矩阵 | `scripts/run_k8s_matrix.sh` | 每 testcase 一个 k8s Job，收集日志 → 聚合 report |
| 单 case 入口 | `docker/entrypoint.sh` | 容器内跑一个 testcase，report 打进 pod 日志 |
| Job 模板 | `docker/job-template.yaml` | 每个 Job 的 k8s 清单（envsubst 渲染） |
| 结果聚合 | `scripts/aggregate_report.py` | per-case JSON → `report.json` + `report.md` |
| 比较/发布 | `scripts/compare-and-maybe-release.sh` | 对比基线，达标则 bump 版本 + push main |
| 发布 | `agentic-game-development/.github/workflows/release-on-bump.yml` | 版本变更 → 打包 zip + 建 GitHub Release |

---

## 0. 前置状态（常驻）

- **编排器**以 `--mode http` 常驻监听 `0.0.0.0:8899`，`POST /trigger`，用 `x-bench-token` 鉴权。
  （备选 `--mode watch-logs`：直接 tail webhook receiver pod 日志，无需 receiver 改造。）
- **runner 镜像**：`harbor.omgwow.ai/beaver_hub-public/aigdbench-runner:latest`
  （编排器 `IMAGE` 默认值；含 Godot + `claude` CLI + `/opt/agd-plugin` + `/app/testcases_filtered`）。
  > ⚠️ 不要用 `xiaojun_private/...`——本机 robot 无拉取权限，会 `ImagePullBackOff` 全失败。
- **k8s Secret `aigdbench-harness`**：`HARNESS_CMD`、`ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`、
  `ANTHROPIC_MODEL`、`IS_SANDBOX`。
- **k8s Secret `harbor-cred`**：docker-registry 拉取凭证（`beaver_hub-public` robot），已挂到 `default` serviceaccount。

---

## 1. 收到 webhook

GitHub push → webhook receiver → `POST http://<host>:8899/trigger`：

```
Header: x-bench-token: <BENCH_TRIGGER_TOKEN>
Body:   {"repo":"owner/repo","ref":"refs/heads/main","after":"<sha>","delivery":"<uuid>"}
```

（完整契约见 `docs/webhook-forward-contract.md`。）编排器 HTTP handler 校验 token + JSON，
提取 `delivery/repo/ref/after`，回 `202 {"accepted":true}`（**快速应答，benchmark 异步跑**），
把这条 trigger 交给 bash 侧 `launch_batch`。

---

## 2. 去重 + 建批次目录

`launch_batch`（`bench-orchestrator.sh`）：

1. `delivery` id 经 `sanitize_id`（`[A-Za-z0-9._-]`，截 64 字符）。
2. **去重**：id 记在 `.orchestrator/seen`（`STATE_DIR`）；已见过则跳过——重投递/日志重读不会重复跑。
3. 建批次输出目录 **`results/<delivery-id>/`**（`RESULTS_ROOT`，默认 `./results`）。
4. 写面包屑 **`results/<id>/trigger.meta`**（注意是 `.meta` 不是 `.json`——因为矩阵启动会 `rm -f $out/*.json`）：
   ```json
   {"delivery":"...","repo":"...","ref":"...","after":"<sha>","image":"<IMAGE>"}
   ```

---

## 3. （可选 `--rebuild`）拉最新插件 + 重建镜像

默认**不重建**（复用预建的 `IMAGE`）。带 `--rebuild` 时，每次 trigger 调用
`build_runner_image.sh`：

1. `git pull` 插件仓 `agentic-game-development`（`PLUGIN_REPO`，默认 `../agentic-game-development`）；
2. 把 `plugins/agentic-game-development-superpowers/` vendor 进 `docker/vendor/agd-plugin`；
3. `docker build`（`--build-arg HARNESS_INSTALL='npm i -g @anthropic-ai/claude-code'`，Godot 4.5）；
4. **发布方式**二选一：
   - `--push`（默认）：推到 Harbor；Job 的 `imagePullPolicy: Always` 保证拉到刚推的 `:latest`；
   - `--import-k3s`：`docker save | k3s ctr images import`，导进本地 k3s containerd，不经 registry。
- 日志：**`results/<id>/rebuild.log`**。失败则回退用现有镜像继续。

无论是否重建，都调 `capture_plugin_change` 记录**本次被测的插件内容**到
**`results/<id>/plugin_change.meta`**（`.meta` 以躲过矩阵的 `*.json` 清除）：
- `commit` / `branch` / `subject`（插件仓 HEAD）；
- `base_ref`（默认 `origin/main`）/ `range`；
- `changed_files` / `log` / `diff`（限 `plugins/agentic-game-development-superpowers` 子目录，diff 截 4000 行，超出置 `diff_truncated:true`）。

---

## 4. 并行跑 benchmark（每 testcase 一个 k8s Job）

编排器在本地枚举 testcase id（`LOCAL_TESTCASES_DIR`，默认 `testcases_filtered/`，去掉 `_`/`README` 前缀），
用 `-t` 显式传给矩阵（**避免矩阵在编排器主机上依赖 docker 做 discover**），然后调：

```
run_k8s_matrix.sh -i <IMAGE> -d command -s aigdbench-harness \
  -j 16 -n default -D /app/testcases_filtered -t "<ids>" -o results/<id> --no-push --no-build
```

`run_k8s_matrix.sh` 每 testcase：

1. `envsubst` 渲染 `docker/job-template.yaml` → `results/<id>/logs/<tc>.job.yaml`，`kubectl create`；
   - Job：`backoffLimit:0`、`activeDeadlineSeconds = TIMEOUT+300`（`-T` 默认 900 → deadline 1200s；
     编排链路实际用 `-T 1800`）、`ttlSecondsAfterFinished = ${TTL_AFTER_FINISHED}`（默认 **14400s/4h**）、
     `imagePullPolicy: Always`、`restartPolicy: Never`、`emptyDir` 挂 `/out`、`envFrom` 挂 harness Secret。
2. 容器 `entrypoint.sh` 内 `aigdbench run --driver command`：
   - HARNESS_CMD（来自 Secret）：`claude -p {task} --dangerously-skip-permissions --plugin-dir /opt/agd-plugin`；
   - 跑 folder 型（含 snapshot 型）→ godot import → L0/L1 门禁 → 验证器打分；
   - **report 打进 pod 日志**，包在 `<<<AIGDBENCH_REPORT_BEGIN/END>>>` 标记间（无需共享存储）。
3. **并发**：`-j 16` 门控在飞 Job 数（数 `.status.active`）。
4. **收集（边完边收）**：矩阵 wait 每个 Job 完成的**当下立即** `kubectl logs job/<jn>` 抓标记间的 JSON
   → `results/<id>/<tc>.json`，pod 全量日志存 `results/<id>/logs/<tc>.pod.log`。
   > 关键：必须"完成即收"而非"全部等完再统一收"——否则 `ttlSecondsAfterFinished` 会在收集前把早完成的
   > Job/pod GC 掉，导致空日志被合成 0 分假记录。TTL 4h 是二次兜底。
   抓不到可解析 report → 合成一条 `status:error` 的 0 分记录（不留静默空洞）。

---

## 5. 聚合 report

`aggregate_report.py` 把 `results/<id>/*.json`（per-case）聚合：

- **`results/<id>/report.json`**（顶层字段）：`driver`、`image`、`harness_cmd`、`namespace`、
  `count`、`passed`、`mean_score`、`testcases[]`（每个：`testcase_id`/`category`/`score`/`status`/
  `wall_time`/`exit_code`/`error`/`log`）。
- **`results/<id>/report.md`**：可读汇总（driver/image、均分、按 category 聚合、逐 case 表）。

聚合后编排器回填两块进 `report.json`：
- `report["trigger"]` = `{delivery, repo, ref, after}`；
- `report["plugin_change"]` = `plugin_change.meta` 内容（第 3 步），并另存一份
  **`results/<id>/plugin_change.json`**（此时矩阵已不再清 `*.json`）。

**批次日志**：`results/<id>/batch.log`（末尾 `EXIT=<code>`）。

### 批次目录产物一览 `results/<delivery-id>/`
```
trigger.meta          # 触发面包屑
plugin_change.meta    # 被测插件内容（矩阵期间存活）
plugin_change.json    # 同上，聚合后另存（文档化产物）
<tc>.json             # 每 testcase 结果
report.json           # 聚合报告（+ trigger + plugin_change）
report.md             # 可读汇总
batch.log             # 矩阵运行日志
rebuild.log           # (--rebuild) 镜像重建日志
release.log           # 比较/发布步骤日志
logs/<tc>.job.yaml    # 渲染出的 Job 清单
logs/<tc>.pod.log     # 每 testcase 的 pod 全量日志（含 harness 输出）
```

---

## 6. 比较基线 + （可选）自动发布

批次产出 `report.json` 后，编排器调 `compare-and-maybe-release.sh`
（`--auto-release` 才会真正写；否则只报告"会怎么做"）。日志：**`results/<id>/release.log`**。

**基线来源**：`agentic-game-development/workflow/benchmark-baseline.json`（in-repo 权威；
release 时另作为 asset 上传一份留痕）。记录当前 release 的 `mean_score` + `plugin_commit`。

**门禁**：`delta = new_mean_score − baseline_mean_score`；**`delta >= min-delta`（默认 0，即"不低于上一版本"）** 判为达标
（运营口径："benchmark 结果不低于上一版本即打出新版本"）。

**决策分支**：
1. **无基线**（首次）：以当前版本建立基线，**不发布**（`--auto-release` 时提交 + push 基线文件）。
2. **低于基线**（delta < min-delta）：不发布，基线不动。
3. **不低于基线但插件 commit 未变**（`plugin_commit == baseline.plugin_commit`）：不发布
   （内容相同，避免同一插件反复发版）。
4. **不低于基线 + 插件已变** → **发布**（需 `--auto-release`）：
   - `bump_manifests`：semver bump（`--bump patch|minor|major`，默认 patch）两个 manifest
     （`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`）+ marketplace.json（若 pin 了版本）；
   - `write_baseline`：把基线刷新到新版本、新分数、新 `plugin_commit`、per-case 分数表；
   - 切到插件仓 `main`，commit（`chore(plugin): bump to vX.Y.Z (benchmark <score>, delta <d> vs vBASE; not lower)`），
     **push main** —— 触发插件仓的 `release-on-bump.yml`。

---

## 7. 打包 + 建 Release（发布日志内容）

插件仓 `.github/workflows/release-on-bump.yml` 检测到 `plugin.json` version 变更后：

- **打包两个 zip**（内容一致，各留对应平台 manifest）：
  - `agentic-game-development-superpowers-claude-<version>.zip`
  - `agentic-game-development-superpowers-codex-<version>.zip`
- **建 GitHub Release**，tag `v<version>`（已存在且未 `force` 则跳过）。
- **Release 资产**：两个 zip + `benchmark-baseline-<version>.json`（该版本被 cut 时的基线快照，留痕）。

**版本发布日志（release notes）记录的信息**：
```
自动发布 (release-on-bump)。plugin.json version 变更触发。

## 发布产物
| 平台 | Artifact |
| Claude Code | agentic-game-development-superpowers-claude-<version>.zip |
| Codex       | agentic-game-development-superpowers-codex-<version>.zip |
（两 zip 内容一致，各留对应平台 manifest）

## 自动更新
- Claude Code：订阅 marketplace 后启动自动拉取此版本。
- Codex / 其他 agent：运行 Scripts/update-agent-skills.sh（或 .ps1）同步。
```

> 注：release notes 本身不内联 benchmark 分数正文；**分数/provenance 通过随发布上传的
> `benchmark-baseline-<version>.json`（含 `mean_score`/`count`/`image`/`plugin_commit`/per-case 分数）体现**。
> 而"这次跑到底测了什么插件内容 + 得了多少分"完整记录在 benchmark 侧的
> `results/<delivery-id>/report.json`（`trigger` + `plugin_change` + `mean_score` + 逐 case）。

---

## 端到端时序（默认 `--rebuild --auto-release`）

```
GitHub push
  → webhook receiver → POST :8899/trigger {delivery,repo,ref,after}
    → 编排器: 去重(seen) → results/<id>/ + trigger.meta
      → build_runner_image.sh: git pull 插件 → vendor → docker build → push/import   (rebuild.log)
      → capture_plugin_change → plugin_change.meta
      → run_k8s_matrix.sh: 每 testcase 一 Job (claude+plugin) → 边完边收 pod 日志       (batch.log, logs/)
        → aggregate_report.py → report.json + report.md
      → 回填 trigger + plugin_change 进 report.json (+ plugin_change.json)
      → compare-and-maybe-release.sh: 比基线, delta>=0 且插件变 → bump+push main         (release.log)
        → 插件仓 release-on-bump.yml: 打 2 个 zip + 建 Release v<version> + 上传基线快照
```

## 关键默认值 / 覆盖

| 项 | 默认 | 覆盖 |
|---|---|---|
| 镜像 | `beaver_hub-public/aigdbench-runner:latest` | `--image` / `IMAGE` |
| 并发 | 16 | `--jobs` |
| testcase 集 | `/app/testcases_filtered`（30 个） | `--testcases-dir` |
| harness Secret | `aigdbench-harness` | `--secret` |
| Job 超时 | deadline = TIMEOUT+300 | 矩阵 `-T` / `-A` |
| Job TTL | 14400s (4h) | `TTL_AFTER_FINISHED` |
| 发布门槛 | delta ≥ 0（不低于） | `--min-delta` |
| 版本 bump | patch | `--bump` |
| 自动发布 | 关（仅报告） | `--auto-release` |
| 每次重建镜像 | 关（复用镜像） | `--rebuild` / `--rebuild-import-k3s` |
