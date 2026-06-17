import numpy as np
from dataclasses import dataclass
from typing import Tuple


MATERIAL_SOUND_VELOCITY = {
    "steel": {
        "v0": 5900.0,
        "temp_coeff": -0.8,
    },
    "aluminum": {
        "v0": 6400.0,
        "temp_coeff": -1.2,
    },
    "stainless_steel": {
        "v0": 5790.0,
        "temp_coeff": -0.7,
    },
    "copper": {
        "v0": 4760.0,
        "temp_coeff": -0.9,
    },
}


LIQUID_GAS_PROPERTIES = {
    "lng": {
        "name": "液化天然气",
        "v0": 1470.0,
        "temp_coeff": -3.0,
        "reference_temp": -162.0,
    },
    "lpg": {
        "name": "液化石油气",
        "v0": 1300.0,
        "temp_coeff": -2.5,
        "reference_temp": 20.0,
    },
    "lin": {
        "name": "液氮",
        "v0": 940.0,
        "temp_coeff": -2.0,
        "reference_temp": -196.0,
    },
    "lo2": {
        "name": "液氧",
        "v0": 1140.0,
        "temp_coeff": -2.2,
        "reference_temp": -183.0,
    },
    "lar": {
        "name": "液氩",
        "v0": 1070.0,
        "temp_coeff": -2.1,
        "reference_temp": -186.0,
    },
    "co2": {
        "name": "液态二氧化碳",
        "v0": 1200.0,
        "temp_coeff": -2.8,
        "reference_temp": 20.0,
    },
    "generic": {
        "name": "通用液化气",
        "v0": 1200.0,
        "temp_coeff": -2.5,
        "reference_temp": 20.0,
    },
}


@dataclass
class CalculationResult:
    wall_sound_velocity: float
    liquid_sound_velocity: float
    wall_travel_time: float
    liquid_travel_time: float
    liquid_level: float
    level_percentage: float


def calculate_wall_sound_velocity(material: str, temperature: float) -> float:
    """
    根据材质和温度计算超声波在钢瓶壁中的传播速度 (m/s)

    原理: v(T) = v0 + α * (T - T0)
    其中 v0 为 20°C 时的声速, α 为温度系数, T0 = 20°C
    """
    if material not in MATERIAL_SOUND_VELOCITY:
        material = "steel"

    props = MATERIAL_SOUND_VELOCITY[material]
    reference_temp = 20.0
    v0 = props["v0"]
    alpha = props["temp_coeff"]

    return v0 + alpha * (temperature - reference_temp)


def calculate_liquid_sound_velocity(
    temperature: float, liquid_type: str = "generic"
) -> float:
    """
    根据温度计算超声波在液化气体中的传播速度 (m/s)

    使用一阶线性近似: v(T) = v0 + α * (T - T_ref)
    """
    if liquid_type not in LIQUID_GAS_PROPERTIES:
        liquid_type = "generic"

    props = LIQUID_GAS_PROPERTIES[liquid_type]
    v0 = props["v0"]
    alpha = props["temp_coeff"]
    t_ref = props["reference_temp"]

    return v0 + alpha * (temperature - t_ref)


def calculate_liquid_level(
    echo_time_us: float,
    material: str,
    wall_thickness: float,
    total_height: float,
    temperature: float,
    liquid_type: str = "generic",
) -> CalculationResult:
    """
    根据超声波回波时间计算液化气体液位

    物理原理:
    1. 总回波时间 = 2 * (壁传播时间 + 液体传播时间)
       超声波需要穿过壁 -> 到液面 -> 反射回来 -> 再穿过壁
    2. 壁传播时间 = 2 * wall_thickness / v_wall (去程+回程)
    3. 液体传播时间 = 2 * liquid_level / v_liquid (去程+回程)
    4. 所以: liquid_level = (总时间 - 壁时间) * v_liquid / 2

    参数:
        echo_time_us: 回波时间 (微秒)
        material: 钢瓶材质 (steel, aluminum, 等)
        wall_thickness: 钢瓶壁厚 (米)
        total_height: 钢瓶内部总高度 (米)
        temperature: 当前环境/介质温度 (°C)
        liquid_type: 液化气体类型 (默认 generic)

    返回:
        CalculationResult 包含计算过程和结果
    """
    echo_time_s = echo_time_us * 1e-6

    v_wall = calculate_wall_sound_velocity(material, temperature)

    v_liquid = calculate_liquid_sound_velocity(temperature, liquid_type)

    t_wall = 2.0 * wall_thickness / v_wall

    t_liquid = echo_time_s - t_wall

    if t_liquid <= 0:
        liquid_level = 0.0
    else:
        liquid_level = (t_liquid * v_liquid) / 2.0

    liquid_level = float(np.clip(liquid_level, 0.0, total_height))

    level_percentage = (liquid_level / total_height) * 100.0

    return CalculationResult(
        wall_sound_velocity=v_wall,
        liquid_sound_velocity=v_liquid,
        wall_travel_time=t_wall * 1e6,
        liquid_travel_time=t_liquid * 1e6 if t_liquid > 0 else 0.0,
        liquid_level=liquid_level,
        level_percentage=round(level_percentage, 2),
    )
