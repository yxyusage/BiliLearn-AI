"""Python 版本闸门与「依赖装不上」判断的离线测试。

贴的是两位用户真实遇到的两种情形：
1. Python 3.15 alpha → ctranslate2 没有预编译包 → pip 报 ResolutionImpossible；
2. 卸载残留的 Python 路径 → venv 报 did not find executable。
旧版一律把这些显示成"请检查网络连接"，把人引到错误方向。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "launcher"))

import pycompat  # noqa: E402


def test_parse_version():
    assert pycompat.parse_version("3.12.4") == (3, 12, 4)
    assert pycompat.parse_version("Python 3.15.0a3") == (3, 15, 0)
    assert pycompat.parse_version("不认识的文本") == ()
    print("parse-version OK")


def test_check_version_levels():
    assert pycompat.check_version((3, 9, 1))[0] == "old"
    # 3.14 也要放行：查过 PyPI，ctranslate2 4.x 与 av 都有 cp314 轮子，装得上
    for v in ((3, 10, 0), (3, 11, 9), (3, 12, 7), (3, 13, 9), (3, 14, 0), (3, 14, 9)):
        assert pycompat.check_version(v)[0] == "ok", (v, pycompat.check_version(v))
    # 3.15 起才是真正装不上的（cp315 轮子一个都没有）
    for v in ((3, 15, 0), (3, 16, 0)):
        assert pycompat.check_version(v)[0] == "too_new", (v, pycompat.check_version(v))
    # 太长的新版本号不能被误判（(3,13,9) > (3,13) 是元组比较的坑）
    assert pycompat.check_version((3, 13, 99))[0] == "ok"
    # 3.14 是"可用但未充分验证"，不是拦
    assert "3.12" in pycompat.check_version((3, 14, 0))[1]
    # 太新的提示里必须给出可执行的信息
    msg = pycompat.check_version((3, 15, 0))[1]
    assert "3.12" in msg and "ctranslate2" in msg and "python.org" in msg
    print("check-version OK")


def test_classify_too_new():
    sample = (
        "The conflict is caused by:\n"
        "    faster-whisper 1.2.0 depends on ctranslate2<5 and >=4.0\n"
        "Additionally, some packages in these conflicts have no matching distributions "
        "available for your environment:\n    ctranslate2\n"
        "ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/..."
    )
    kind, msg = pycompat.classify_pip_failure(sample)
    assert kind == "too_new", kind
    assert "ctranslate2" in msg and "3.12" in msg and "不是网络问题" in msg
    assert "your" not in pycompat._packages_in(sample), pycompat._packages_in(sample)
    print("classify-too-new OK")


def test_classify_network_and_unknown():
    kind, msg = pycompat.classify_pip_failure(
        "pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='pypi.org'): Read timed out.")
    assert kind == "network" and "网络" in msg, (kind, msg)
    kind2, _ = pycompat.classify_pip_failure("Successfully installed fastapi-0.115.0")
    assert kind2 == "unknown", kind2
    print("classify-network OK")


def test_probe_python():
    ok, ver, err = pycompat.probe_python(sys.executable)
    assert ok and pycompat.parse_version(ver), (ok, ver, err)
    ghost = str(ROOT / "nonexistent" / "Python315" / "python.exe")
    ok2, _v2, err2 = pycompat.probe_python(ghost)
    assert not ok2 and "不存在" in err2, err2
    ok3, _v3, err3 = pycompat.probe_python("")
    assert not ok3 and err3
    print("probe-python OK")


if __name__ == "__main__":
    test_parse_version()
    test_check_version_levels()
    test_classify_too_new()
    test_classify_network_and_unknown()
    test_probe_python()
    print("ALL_PYCOMPAT_TESTS_PASSED")
