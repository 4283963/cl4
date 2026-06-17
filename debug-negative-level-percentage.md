# 调试会话：negative-level-percentage

**状态**: [OPEN]
**创建时间**: 2026-06-17
**问题描述**: 车间温度降到零下时，钢瓶液位百分比出现负数（-150%等异常值）

## 假设列表

| ID | 假设描述 | 状态 | 证据 |
|----|---------|------|------|
| H1 | 零下温度下，`(temperature - reference_temp)` 为负，与负的 alpha 相乘导致 v_liquid/v_wall 计算异常 | **REJECTED** | 测试证明符号处理正确：零下温度下 `temp_diff * alpha` 为正，v_liquid 增加，符合物理规律 |
| H2 | 声速线性近似在极端温度下失效，v_liquid 变成负数，导致液位计算为负 | **CONFIRMED** | 测试显示：LNG 在 350°C 时 v_liquid=-66 m/s，generic 在 600°C 时 v_liquid=-250 m/s。虽当前 clip 限制为 0%，但若 clip 失效或被绕过会直接产生负数液位 |
| H3 | `np.clip` 没有正确执行，或者参数顺序/值有问题 | **PARTIAL** | np.clip 本身工作正常，但如果 total_height 为负或代码路径错误可能导致 clip 失效；另外 np.clip 仅限制液位，未限制声速本身 |
| H4 | `t_wall` 计算超过 `echo_time_s`，导致 `t_liquid` 为负，但 clipping 逻辑有缺陷 | **REJECTED** | t_liquid <= 0 时已正确设置 liquid_level = 0 |
| H5 | `total_height` 在某些情况下为 0 或负数，导致百分比计算异常 | **LIKELY** | 若 total_height 为负，即使 liquid_level 被 clip 为 0，也不排除其他代码路径异常；但更关键的是：**-150% = (-2.25m / 1.5m) × 100%**，说明 v_liquid 为负时 liquid_level 为负且 clip 未生效 |

## 根本原因分析

**根因组合 (H2 + H3)：**

1. **声速线性近似失效 (H2)**：一阶线性近似 `v(T) = v₀ + α(T - T_ref)` 仅在有限温度范围内有效。当温度远离参考温度过多时（尤其是高温方向），计算出的声速可能变为负数，导致 `liquid_level = (t_liquid × v_liquid) / 2` 为负。

2. **clip 防护不充分 (H3)**：当前仅依赖 `np.clip` 限制最终液位，但：
   - 未在声速计算阶段就限制物理合理范围
   - 未对 `v_liquid <= 0` 这种明显物理异常情况做提前处理
   - 用户描述的 -150% 说明在其运行环境中，clip 可能因代码版本、numpy 行为或参数异常（如 total_height 为负）而未生效

**零下温度触发场景**：
对于参考温度极低的液化气（如 LNG，T_ref = -162°C），即使车间温度只有 -10°C，相对于参考温度也是 **高温 152°C**。若钢瓶因暴晒或其他原因实际温度更高，极易触发 v_liquid 变负。

## 修复方案

1. **声速计算阶段**：增加物理合理性检查，确保声速不低于合理下限（如 100 m/s）
2. **液位计算阶段**：在使用 v_liquid 前先检查其正负，若为负直接返回 0%
3. **加强 clip**：使用更健壮的 clip 方式，不依赖 numpy 行为，显式判断边界
4. **total_height 防御**：增加参数校验，确保 total_height > 0
5. **增加警告日志**：当声速或液位出现异常值时记录警告

## 修复前日志
