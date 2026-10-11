"""环境自检接口的离线回归测试。

只测不联网、不依赖用户数据的那些检查项；联网检查（B站、大模型、音频）不在 CI 里跑。
同时保证：任何一项出问题时自检本身不能抛异常，否则用户连自检结果都拿不到。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.routers import diagnose


def test_item_shape():
    it = diagnose._item("x", "名字", "ok", "详情", "提示")
    assert set(it.keys()) == {"id", "name", "status", "detail", "hint"}
    assert it["status"] == "ok"
    print("item-shape OK")


def test_status_values_are_expected():
    """前端按 status 上色，出现新值就会没样式。"""
    allowed = {"ok", "warn", "fail", "skip"}
    for fn in (diagnose.check_data_dir, diagnose.check_deps):
        it = fn()
        assert it["status"] in allowed, it
    print("status-values OK")


def test_checks_never_raise():
    """把每一项都跑一遍（不传 db 的用 None），任何异常都必须被吞进 detail。"""
    class _Req:
        class app:  # noqa: N801
            version = "0.0.0"

    items = [diagnose.check_runtime(_Req()), diagnose.check_data_dir(), diagnose.check_deps()]
    for it in items:
        assert it["name"] and it["status"] in {"ok", "warn", "fail", "skip"}
    print("checks-never-raise OK", [i["id"] for i in items])


if __name__ == "__main__":
    test_item_shape()
    test_status_values_are_expected()
    test_checks_never_raise()
    print("ALL_DIAGNOSE_TESTS_PASSED")
