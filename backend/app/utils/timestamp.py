"""全局统一时间戳工具，格式 HH:MM:SS。"""
import re

_TIME_RE = re.compile(r"^(?:(\d{1,3}):)?([0-5]?\d):([0-5]?\d)(?:[.,](\d{1,3}))?$")


def seconds_to_hms(seconds: float) -> str:
    """秒 -> HH:MM:SS"""
    seconds = max(0, int(round(float(seconds))))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def hms_to_seconds(hms: str) -> int:
    """HH:MM:SS -> 秒，兼容 MM:SS / 秒数 / 宽松格式。"""
    if hms is None:
        return 0
    if isinstance(hms, (int, float)):
        return int(hms)
    hms = str(hms).strip()
    m = _TIME_RE.match(hms)
    if m:
        h = int(m.group(1) or 0)
        mm = int(m.group(2))
        ss = int(m.group(3))
        return h * 3600 + mm * 60 + ss
    parts = [p for p in re.split(r"[:：]", hms) if p != ""]
    try:
        nums = [int(float(p)) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0] * 3600 + nums[1] * 60 + nums[2]


def normalize_hms(value) -> str:
    """把任意时间表示规范化为 HH:MM:SS。"""
    if isinstance(value, (int, float)):
        return seconds_to_hms(value)
    return seconds_to_hms(hms_to_seconds(str(value)))


def timestamp_from_text(text: str) -> str:
    """从文本中提取第一个 HH:MM:SS 时间戳，找不到返回空串。"""
    if not text:
        return ""
    m = re.search(r"\b(\d{1,3}):([0-5]\d):([0-5]\d)\b", text)
    if not m:
        return ""
    return normalize_hms(m.group(0))
