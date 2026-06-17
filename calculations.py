import numpy as np
from dataclasses import dataclass
from typing import Tuple
import os, urllib.request, json, uuid
RUN_ID = os.environ.get("DEBUG_RUN_ID", "pre-fix-" + uuid.uuid4().hex[:8])
def _dbg(hypo, data):
    try:
        data["hypothesisId"] = hypo
        data["runId"] = RUN_ID
        req = urllib.request.Request(os.environ["DEBUG_SERVER_URL"], data=json.dumps(data).encode(), headers={"Content-Type": "application/json", "X-Session-Id": os.environ["DEBUG_SESSION_ID"]}, method="POST")
        urllib.request.urlopen(req, timeout=0.5).read()
    except Exception: pass


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

    注意: 一阶线性近似仅在合理温度范围内有效, 超出范围会限制到物理合理值
    """
    if material not in MATERIAL_SOUND_VELOCITY:
        material = "steel"

    props = MATERIAL_SOUND_VELOCITY[material]
    reference_temp = 20.0
    v0 = props["v0"]
    alpha = props["temp_coeff"]

    #region debug-point H1-wall-sound-vel
    temp_diff = temperature - reference_temp
    result = v0 + alpha * temp_diff
    _dbg("H1", {"fn": "calculate_wall_sound_velocity", "material": material, "temperature": temperature, "reference_temp": reference_temp, "temp_diff": temp_diff, "alpha": alpha, "v0": v0, "raw_result": result})
    #endregion

    min_v_wall = v0 * 0.5
    max_v_wall = v0 * 1.5
    result = max(min_v_wall, min(result, max_v_wall))

    #region debug-point H1-wall-sound-vel-clamped
    _dbg("H2", {"fn": "calculate_wall_sound_velocity", "clamped_result": result, "min_allowed": min_v_wall, "max_allowed": max_v_wall, "was_clamped": result != (v0 + alpha * temp_diff)})
    #endregion

    return result


def calculate_liquid_sound_velocity(
    temperature: float, liquid_type: str = "generic"
) -> float:
    """
    根据温度计算超声波在液化气体中的传播速度 (m/s)

    使用一阶线性近似: v(T) = v0 + α * (T - T_ref)

    注意: 一阶线性近似仅在合理温度范围内有效, 超出范围会限制到物理合理值。
          声速不能为负或接近零, 否则液位计算会出错。
    """
    if liquid_type not in LIQUID_GAS_PROPERTIES:
        liquid_type = "generic"

    props = LIQUID_GAS_PROPERTIES[liquid_type]
    v0 = props["v0"]
    alpha = props["temp_coeff"]
    t_ref = props["reference_temp"]

    #region debug-point H1-H2-liquid-sound-vel
    temp_diff = temperature - t_ref
    raw_result = v0 + alpha * temp_diff
    _dbg("H1", {"fn": "calculate_liquid_sound_velocity", "liquid_type": liquid_type, "temperature": temperature, "reference_temp": t_ref, "temp_diff": temp_diff, "alpha": alpha, "v0": v0, "raw_result": raw_result})
    _dbg("H2", {"fn": "calculate_liquid_sound_velocity", "v_liquid_raw": raw_result, "is_negative": raw_result < 0})
    #endregion

    min_v_liquid = max(100.0, v0 * 0.3)
    max_v_liquid = v0 * 1.8
    result = max(min_v_liquid, min(raw_result, max_v_liquid))

    #region debug-point H2-liquid-sound-vel-clamped
    _dbg("H2", {"fn": "calculate_liquid_sound_velocity", "v_liquid_clamped": result, "min_allowed": min_v_liquid, "max_allowed": max_v_liquid, "was_clamped": result != raw_result, "clamp_reason": "negative_or_too_low" if raw_result < min_v_liquid else "too_high" if raw_result > max_v_liquid else "none"})
    #endregion

    return result


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
    #region debug-point H5-total-height-validation
    _dbg("H5", {"fn": "calculate_liquid_level", "total_height_input": total_height, "wall_thickness": wall_thickness, "echo_time_us": echo_time_us})
    #endregion

    if total_height <= 0:
        _dbg("H5", {"fn": "calculate_liquid_level", "error": "total_height <= 0", "fallback": "return 0%"})
        return CalculationResult(
            wall_sound_velocity=0.0,
            liquid_sound_velocity=0.0,
            wall_travel_time=0.0,
            liquid_travel_time=0.0,
            liquid_level=0.0,
            level_percentage=0.0,
        )

    echo_time_s = echo_time_us * 1e-6

    v_wall = calculate_wall_sound_velocity(material, temperature)

    v_liquid = calculate_liquid_sound_velocity(temperature, liquid_type)

    #region debug-point H2-v-liquid-guard
    _dbg("H2", {"fn": "calculate_liquid_level", "v_liquid_before_guard": v_liquid, "v_wall": v_wall, "v_liquid_valid": v_liquid > 0})
    if v_liquid <= 0:
        _dbg("H2", {"fn": "calculate_liquid_level", "error": "v_liquid <= 0 after clamping", "fallback": "return 0%"})
        return CalculationResult(
            wall_sound_velocity=v_wall,
            liquid_sound_velocity=v_liquid,
            wall_travel_time=0.0,
            liquid_travel_time=0.0,
            liquid_level=0.0,
            level_percentage=0.0,
        )
    #endregion

    t_wall = 2.0 * wall_thickness / v_wall

    t_liquid = echo_time_s - t_wall

    #region debug-point H4-t-liquid
    _dbg("H4", {"echo_time_us": echo_time_us, "echo_time_s": echo_time_s, "t_wall_s": t_wall, "t_wall_us": t_wall * 1e6, "t_liquid_s": t_liquid, "t_liquid_us": t_liquid * 1e6, "v_wall": v_wall, "v_liquid": v_liquid, "wall_thickness": wall_thickness, "is_t_liquid_neg": t_liquid <= 0})
    #endregion

    if t_liquid <= 0:
        liquid_level = 0.0
    else:
        liquid_level = (t_liquid * v_liquid) / 2.0

    #region debug-point H2-H3-before-clip
    _dbg("H2", {"t_liquid_pos": t_liquid > 0, "unclipped_level": liquid_level, "v_liquid_sign": "neg" if v_liquid < 0 else "pos", "level_sign": "neg" if liquid_level < 0 else "pos"})
    _dbg("H5", {"total_height": total_height, "is_total_height_positive": total_height > 0})
    #endregion

    liquid_level_clipped = max(0.0, min(liquid_level, total_height))

    #region debug-point H3-after-clip
    _dbg("H3", {"unclipped_level": liquid_level, "clipped_level": liquid_level_clipped, "clip_min": 0.0, "clip_max": total_height, "clip_worked": liquid_level_clipped == max(0.0, min(liquid_level, total_height)), "used_explicit_clip": True})
    #endregion

    level_percentage = (liquid_level_clipped / total_height) * 100.0

    level_percentage = max(0.0, min(level_percentage, 100.0))

    #region debug-point H5-percentage
    _dbg("H5", {"liquid_level_clipped": liquid_level_clipped, "level_percentage": level_percentage, "percentage_sign": "neg" if level_percentage < 0 else "pos", "percentage_clamped": level_percentage > 100 or level_percentage < 0})
    #endregion

    return CalculationResult(
        wall_sound_velocity=v_wall,
        liquid_sound_velocity=v_liquid,
        wall_travel_time=t_wall * 1e6,
        liquid_travel_time=t_liquid * 1e6 if t_liquid > 0 else 0.0,
        liquid_level=liquid_level_clipped,
        level_percentage=round(level_percentage, 2),
    )
