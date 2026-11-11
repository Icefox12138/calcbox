# 从 socratic-tutor 迁移：diff 计划

| 项 | 值 |
|---|---|
| 来源 | `socratic-tutor/sidecar/app/{compute,compute_worker,sandbox_policy}.py` |
| 现状 | 467 + 26 + 51 行；仅 3 处环境变量前缀与 1 处临时目录前缀带 `SOCRATIC_` |
| 目标 | 独立 MIT 包 `calcbox`，教学侧只保留薄客户端 |
| 已做（0.2.0） | 契约、backends 注册表、**sympy + scipy + pint + control 全部迁移**、sandbox 同策略、worker 超时、api、mcp、cli、33 条测试 |

## 0. 一句话

这次迁移**不是重写**，是**搬家 + 去品牌 + 补契约**。逻辑一行不改，改的是名字、包边界和调用方式。

## 1. 文件映射

| 来源（socratic-tutor） | 目标（calcbox） | 处理 |
|---|---|---|
| `sidecar/app/compute.py`（467 行） | `calcbox/backends.py` + `calcbox/contract.py` | 拆分：结果组装/契约 → contract；后端实现 → backends |
| `sidecar/app/compute_worker.py`（26 行） | `calcbox/worker.py` | 改包内相对导入 |
| `sidecar/app/sandbox_policy.py`（51 行） | `calcbox/sandbox.py` | 改事件名与环境变量前缀 |
| `sidecar/tests/test_compute.py`（111 行） | `tests/test_symbolic.py` | 断言改为新契约字段 |
| `sidecar/tests/test_sandbox_policy.py`（60 行） | `tests/test_sandbox.py` | 同上 |
| `sidecar/app/main.py` 的 `/v1/compute*` 路由 | `calcbox/api.py` | 变成 `create_router()`，鉴权交回宿主 |

## 2. 去品牌：三处环境变量

| 现在 | 迁移后 | 说明 |
|---|---|---|
| `SOCRATIC_COMPUTE_EXTERNAL` | `CALCBOX_EXTERNAL` | 默认仍为 0（关闭外部引擎） |
| `SOCRATIC_SANDBOX_TEMP` | `CALCBOX_SANDBOX_TEMP` | worker 的工作目录 |
| 临时目录前缀 `socratic-compute-` | `calcbox-` | 仅可读性 |

兼容策略：迁移期**同时读新旧两个变量**（新优先），一个 minor 版本后删除旧名。

```python
def _external_enabled():
    for key in ("CALCBOX_EXTERNAL", "SOCRATIC_COMPUTE_EXTERNAL"):
        if key in os.environ:
            return str(os.environ[key]).lower() in ("1", "true", "yes")
    return False
```

## 3. 契约对齐（逐字段）

侧车 `compute()` 返回值与 calcbox `ComputeResult.to_dict()` 的差异清单：

| 字段 | sidecar | calcbox | 动作 |
|---|---|---|---|
| `ok` | ✅ | ✅ | 保留 |
| `backend` / `engine_version` | ✅ | ✅ | 保留 |
| `operation` / `input` / `variable` | ✅ | ✅ | 保留 |
| `result` / `latex` / `numeric` | ✅ | ✅ | 保留 |
| `details` | ✅（外部引擎 stdout/stderr） | ⬜ | 迁移时补到 contract |
| `verification` / `assumptions` | ✅ | ✅ | 保留，字段语义写入 README |
| `cross_check` / `disputed` | ✅ | `disputed` 已有，`cross_check` 待补 | 迁移时补 |
| `sandbox` | `"audit-only"` 或 `"external"` | 同 | 保留 |
| `input_sha256` / `generated_at` | ✅ | ✅ | 保留 |
| `elapsed_ms` | ❌（只有内部计时） | ✅ | 新增；侧车侧可忽略 |

**原则**：calcbox 的字段是超集；sidecar 迁移后直接透传，不改插件。

## 3b. 阶段 1 实际完成情况（0.1.0）

| 项 | 状态 |
|---|---|
| sympy 9 个操作（simplify/diff/integrate/solve/limit/value/latex/factor/expand） | ✅ 与 sidecar 逐行一致 |
| 脱字符归一化、禁用令牌、变量单字母、表达式长度上限 | ✅ 一致 |
| 子进程 worker + 超时杀进程 | ✅ 一致（CALCBOX_WORKER=0 可退回进程内，仅调试用） |
| sandbox 策略 | ✅ 一致（网络 / 进程 / 工作区外写入），仅环境变量改名 |
| 结果字段 | ✅ 超集：新增 elapsed_ms 与 credentials；verification 同时给 ok 与 passed |
| scipy（quad/minimize/root，含 sympy 交叉验证与 disputed） | ✅ 0.2.0 |
| pint（convert）/ control（step） | ✅ 0.2.0 |
| wolfram / lean | ⏳ 阶段 3，默认关闭且返回 BackendUnavailable |
| 测试 | 33 条通过；parity 15/15 |

与 sidecar 的行为差异：integrate 额外支持 target="a,b" 定积分（sidecar 忽略该参数），属向后兼容的超集。

发现并修正的两个坑：worker 内部会再次走 worker（递归）→ 进 worker 后置 CALCBOX_WORKER=0；沙箱最初拒绝了 ctypes.dlopen，而 sympy 导入会触发它 → 策略回到与 sidecar 一致的最小集合。
## 4. sidecar 侧的改造（三阶段）

### 阶段 A：并行期（不改行为）

```python
# sidecar/app/compute.py 变成薄壳
from calcbox import compute as _compute, backend_status as _status

def compute(*args, **kwargs):
    return _compute(*args, **kwargs)

def backend_status():
    return _status()
```

插件、API、测试全部不动。风险：calcbox 与 sidecar 的 operations 集合必须一致（当前一致）。

### 阶段 B：路由下线

- 删除 `/v1/compute`、`/v1/compute/backends` 的 sidecar 实现；
- `docs/SIDECAR-CONTRACT.md` 改写为「计算由 calcbox 提供，端点见其 CONTRACT」；
- 保留一个 minor 版本的 308 重定向或 501 + `{"code":"moved","to":"calcbox"}`。

### 阶段 C：插件解耦

```diff
- const r = await call(config, "/v1/compute", { … })
+ const r = await callCompute(config, { … })   // 走 MCP 或 calcbox 的 HTTP
```

`compute_math`、`ptc_calc` 两个工具的实现换成 calcbox 客户端；工具名与参数**不变**，避免破坏使用方。

## 5. 测试迁移

| 现在 | 迁移后 | 断言调整 |
|---|---|---|
| `test_compute.py`：11 条 | `tests/test_symbolic.py` | 增加 `verification`、`input_sha256`、`elapsed_ms` |
| `test_sandbox_policy.py`：3 条 | `tests/test_sandbox.py` | 事件名从 `SOCRATIC_*` 改 `CALCBOX_*` |
| 侧车 `test_no_index.py` 等 | 不动 | 与本包无关 |

目标：calcbox 独立跑 `python -m unittest discover` 全绿，不依赖 sidecar 任何模块（当前骨架已满足：10 条通过）。

## 6. 发布步骤

1. 本仓 `0.0.1`：骨架（已完成）；
2. 迁移 sympy 全操作 + `test_symbolic` → `0.1.0`（PyPI）；
3. 迁移 scipy/pint/control → `0.2.0`；
4. MCP 发布（`calcbox-mcp` 入口已有）；
5. sidecar 依赖 `calcbox>=0.1,<0.2`，进入阶段 A。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 两处实现漂移（并行期） | 阶段 A 的壳**只转发**，不保留副本；CI 加一条 “sidecar 端 compute 输出来自 calcbox” 的断言 |
| 契约字段缺失（`details`/`cross_check`） | 迁移时补齐；见 §3 |
| 外部引擎许可 | 默认关闭；文档写明 Wolfram/Lean 由使用者自备，不随包分发 |
| 安全预期错位 | README 与 SECURITY 首屏写明 audit-only |
| 包名冲突 | 发布前 `pip index`/`npm view` 核对；`calcbox` 当前未被占用（PyPI 404） |

## 8. 验收标准

- [ ] `pip install calcbox[symbolic]` 后 `calcbox "x**2" --op integrate` 输出含 `verification`
- [ ] `backend_status()` 在只装 sympy 时，其余五个后端返回 `available: false` + reason
- [ ] 关闭 `CALCBOX_EXTERNAL` 时 `eval`/`check` 返回 503 而非崩溃
- [ ] sidecar 删除 compute.py 后，插件 `compute_math` 的行为与迁移前逐字节一致（对同一批表达式）
