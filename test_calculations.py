import os
os.environ["DEBUG_SERVER_URL"] = "http://127.0.0.1:7777/event"
os.environ["DEBUG_SESSION_ID"] = "negative-level-percentage"
os.environ["DEBUG_RUN_ID"] = "pre-fix-script-001"

import sys
sys.path.insert(0, "/Users/kl/Documents/trae_projects2/cl4")
from calculations import calculate_liquid_level

test_cases = [
    (-10, "lpg", "钢瓶 0°C 以下，LPG"),
    (-30, "lpg", "钢瓶 -30°C，LPG"),
    (-50, "lpg", "钢瓶 -50°C，LPG"),
    (-100, "lng", "钢瓶 -100°C，LNG"),
    (-10, "lng", "钢瓶 -10°C，LNG（LNG 参考温度 -162°C）"),
    (30, "lng", "钢瓶 30°C，LNG（温度高于参考温度 192°C）"),
    (200, "lng", "钢瓶 200°C，LNG"),
    (350, "lng", "钢瓶 350°C，LNG（临界温度）"),
    (-20, "generic", "钢瓶 -20°C，通用"),
]

print("=" * 80)
print("液位计算测试（零下及极端温度）")
print("=" * 80)

for temp, ltype, desc in test_cases:
    result = calculate_liquid_level(
        echo_time_us=2000,
        material="steel",
        wall_thickness=0.008,
        total_height=1.5,
        temperature=temp,
        liquid_type=ltype,
    )
    status = "⚠️  异常" if result.level_percentage < 0 or result.level_percentage > 100 else "✅ 正常"
    v_status = "⚠️  v_liquid 负" if result.liquid_sound_velocity < 0 else "  "
    print(f"\n{status} {desc}")
    print(f"   温度 = {temp}°C, 液化气 = {ltype}")
    print(f"   壁声速 = {result.wall_sound_velocity:.1f} m/s, 液体声速 = {result.liquid_sound_velocity:.1f} m/s {v_status}")
    print(f"   壁传播时间 = {result.wall_travel_time:.2f} μs, 液体传播时间 = {result.liquid_travel_time:.2f} μs")
    print(f"   液位 = {result.liquid_level:.4f} m, 百分比 = {result.level_percentage:.2f}%")

print("\n" + "=" * 80)
print("测试完成！检查 Debug Server 日志: http://127.0.0.1:7777/logs")
