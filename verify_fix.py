import os
os.environ["DEBUG_SERVER_URL"] = "http://127.0.0.1:7777/event"
os.environ["DEBUG_SESSION_ID"] = "negative-level-percentage"
os.environ["DEBUG_RUN_ID"] = "post-fix-script-001"

import sys
sys.path.insert(0, "/Users/kl/Documents/trae_projects2/cl4")
from calculations import calculate_liquid_level, calculate_liquid_sound_velocity

SEP = "=" * 95
print(SEP)
print("POST-FIX 验证：修复后极端温度下的液位计算结果")
print(SEP)

test_cases = [
    (-10, "generic", "钢瓶 -10°C，通用液化气"),
    (-30, "lpg", "钢瓶 -30°C，LPG"),
    (-50, "lpg", "钢瓶 -50°C，LPG"),
    (-10, "lng", "钢瓶 -10°C，LNG（相对参考温度+152°C）"),
    (30, "lng", "钢瓶 30°C，LNG（相对参考温度+192°C）"),
    (350, "lng", "钢瓶 350°C，LNG（声速原计算为 -66 m/s）"),
    (600, "generic", "钢瓶 600°C，通用（声速原计算为 -250 m/s）"),
    (500, "lng", "钢瓶 500°C，LNG（声速原计算为 -516 m/s）"),
]

fixed_count = 0
for temp, ltype, desc in test_cases:
    result = calculate_liquid_level(
        echo_time_us=2000,
        material="steel",
        wall_thickness=0.008,
        total_height=1.5,
        temperature=temp,
        liquid_type=ltype,
    )
    v_raw_before = calculate_liquid_sound_velocity.__wrapped__(temp, ltype) if hasattr(calculate_liquid_sound_velocity, "__wrapped__") else "N/A"
    pct_ok = 0 <= result.level_percentage <= 100
    v_ok = result.liquid_sound_velocity > 0
    level_ok = 0 <= result.liquid_level <= 1.5
    all_ok = pct_ok and v_ok and level_ok
    if all_ok:
        fixed_count += 1
    status = "PASS" if all_ok else "FAIL"
    print(f"\n[{status}] {desc}")
    print(f"   T={temp} degC, v_liquid(修复后)={result.liquid_sound_velocity:.1f} m/s")
    print(f"   液位={result.liquid_level:.4f} m, 百分比={result.level_percentage:.2f}%")
    print(f"   检查项: v>0={v_ok}, 0<=level<=1.5={level_ok}, 0<=pct<=100={pct_ok}")

print("\n" + SEP)
print(f"验证结果：{fixed_count}/{len(test_cases)} 项测试全部通过")
print(SEP)

print("\n\n" + SEP)
print("极端构造场景测试（原代码会产生 -150% 的场景）：")
print(SEP)

evil_temps = [500, 600, 700, 800]
for temp in evil_temps:
    r = calculate_liquid_level(2000, "steel", 0.008, 1.5, temp, "lng")
    ok = 0 <= r.level_percentage <= 100
    print(f"  T={temp} degC, LNG: pct={r.level_percentage:6.2f}%, v_liquid={r.liquid_sound_velocity:7.1f}  {'PASS' if ok else 'FAIL'}")
