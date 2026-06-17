import sys
sys.path.insert(0, "/Users/kl/Documents/trae_projects2/cl4")
from calculations import calculate_liquid_level, calculate_liquid_sound_velocity, calculate_wall_sound_velocity
import numpy as np

print("=" * 90)
print("深度调试：寻找 -150% 液位的根源")
print("=" * 90)

print("\n1. 检查声速在各种极端温度下的计算：")
print("-" * 90)

for temp in [-200, -100, -50, -20, 0, 20, 100, 200, 300, 400, 500, 600]:
    v_wall = calculate_wall_sound_velocity("steel", temp)
    print(f"  T={temp:4d}°C  v_wall(steel)={v_wall:8.1f} m/s  {'⚠️ 负' if v_wall < 0 else '  '}")

print("\n   液化气声速随温度变化：")
for ltype in ["lpg", "lng", "generic", "co2"]:
    print(f"\n   --- {ltype} ---")
    for temp in [-200, -100, 0, 100, 300, 500]:
        v = calculate_liquid_sound_velocity(temp, ltype)
        status = "⚠️  负数！" if v < 0 else ""
        print(f"     T={temp:4d}°C  v={v:8.1f} m/s  {status}")

print("\n" + "=" * 90)
print("2. 检查液位计算的每个环节，寻找负数来源：")
print("=" * 90)

echo_time_us = 2000
material = "steel"
wall_thickness = 0.008
total_height = 1.5

test_scenarios = [
    (-10, "generic", "零下10°C，通用液化气"),
    (-30, "lpg", "零下30°C，LPG"),
    (350, "lng", "350°C，LNG"),
    (600, "generic", "600°C，通用液化气"),
]

for temp, ltype, desc in test_scenarios:
    echo_time_s = echo_time_us * 1e-6

    v_wall = calculate_wall_sound_velocity(material, temp)
    v_liquid = calculate_liquid_sound_velocity(temp, ltype)

    t_wall = 2.0 * wall_thickness / v_wall
    t_liquid = echo_time_s - t_wall

    print(f"\n场景: {desc}")
    print(f"  输入: T={temp}°C, echo={echo_time_us}μs")
    print(f"  v_wall={v_wall:.1f} m/s, v_liquid={v_liquid:.1f} m/s")
    print(f"  t_wall={t_wall*1e6:.2f} μs, t_liquid={t_liquid*1e6:.2f} μs")

    if t_liquid <= 0:
        print(f"  t_liquid <= 0, 设置 liquid_level = 0")
        liquid_level = 0.0
    else:
        liquid_level = (t_liquid * v_liquid) / 2.0
        print(f"  原始计算: liquid_level = (t_liquid * v_liquid) / 2 = ({t_liquid:.6f} * {v_liquid:.1f}) / 2 = {liquid_level:.4f} m")

    print(f"  np.clip 前: liquid_level = {liquid_level}")
    print(f"  np.clip 参数: a_min=0.0, a_max={total_height}")
    clipped = float(np.clip(liquid_level, 0.0, total_height))
    print(f"  np.clip 后: {clipped}")

    percentage = (clipped / total_height) * 100.0
    print(f"  百分比: {percentage:.2f}%")

    # 对比调用函数的结果
    result = calculate_liquid_level(echo_time_us, material, wall_thickness, total_height, temp, ltype)
    print(f"  函数返回: level={result.liquid_level:.4f} m, pct={result.level_percentage:.2f}%")
    print(f"  差异: {'一致 ✓' if abs(result.level_percentage - percentage) < 0.01 else '不一致 ⚠️'}")

print("\n" + "=" * 90)
print("3. 模拟用户场景：-150% 是怎么来的？")
print("=" * 90)

print("""
要得到 -150%，需要:
  level_percentage = -150
  => (liquid_level / total_height) * 100 = -150
  => liquid_level = -1.5 * total_height
  
需要满足:
1. np.clip 没有生效 或 参数顺序错误
2. v_liquid * t_liquid / 2 = -1.5 * total_height

让我们看看哪些组合能产生 -1.5 * total_height:
""")

for temp in range(-50, 501, 50):
    for ltype in ["generic", "lpg", "lng"]:
        v_liquid = calculate_liquid_sound_velocity(temp, ltype)
        if v_liquid < 0:
            # 假设 t_liquid = 0.002s (2000μs)
            t_liquid = 0.002
            level = (t_liquid * v_liquid) / 2.0
            pct = (level / 1.5) * 100
            if pct < -50:
                print(f"  T={temp:4d}°C, {ltype:8s}: v_liquid={v_liquid:8.1f}, level={level:.4f}m, pct={pct:.1f}%")

print("\n" + "=" * 90)
print("4. 检查 np.clip 在各种情况下的行为：")
print("=" * 90)

test_clip_cases = [
    (-2.25, 0.0, 1.5, "liquid_level=-2.25, 正常边界"),
    (-2.25, 1.5, 0.0, "参数顺序错误: a_min > a_max"),
    (2.25, 0.0, 1.5, "liquid_level > total_height"),
    (0.5, 1.5, 0.0, "参数顺序错误，中间值"),
]

for val, a_min, a_max, desc in test_clip_cases:
    result = np.clip(val, a_min, a_max)
    print(f"  np.clip({val}, {a_min}, {a_max}) = {result}  # {desc}")

print("\n" + "=" * 90)
