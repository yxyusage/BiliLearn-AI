"""网络辅助：系统代理不可用时自动回退直连。"""
import os

_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def has_proxy_env() -> bool:
    return any(os.environ.get(k) for k in _PROXY_KEYS)


def clear_proxy_env() -> dict:
    saved = {}
    for k in _PROXY_KEYS:
        if os.environ.get(k):
            saved[k] = os.environ[k]
            os.environ.pop(k, None)
    return saved


def restore_proxy_env(saved: dict) -> None:
    for k, v in saved.items():
        os.environ[k] = v
