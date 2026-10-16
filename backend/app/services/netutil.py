"""网络辅助：系统代理不可用时自动回退直连。"""
import os

_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
_NO_PROXY_KEYS = ("NO_PROXY", "no_proxy")


def _normalize_no_proxy_entry(entry: str) -> str:
    """把单条 NO_PROXY 项归一化成 httpx 能解析的形式。

    httpx 0.28 的 get_environment_proxies 只认「裸」IPv6 字面量：带方括号的
    ``[::1]`` 会走通配分支生成 ``all://*[::1]``，IPv6 CIDR（``::1/128``）会生成
    ``all://[::1/128]``，两者都会被 URLPattern 当成 host:port 解析并抛
    ``InvalidURL: Invalid port: ...`` —— 只要环境里有这样的项，进程内**任何**
    ``httpx.Client()`` 都构造不出来。

    这里把它们降级成 httpx 支持的等价写法：

    - ``[::1]`` / ``[::1]:8080`` → ``::1``（端口无法表达，降级为无端口，绕过范围是
      操作者意图的超集；httpx 的 IPv6 绕过项本来就匹配所有端口）
    - ``::1/128`` → ``::1``（/128 就是单地址，语义完全一致）
    - ``2001:db8::/32`` → ``2001:db8::``（前缀无法表达，降级为基地址）

    其余形式（域名、IPv4、IPv4 CIDR、带 scheme 的 URL、``*``、空串）原样返回。
    """
    entry = (entry or "").strip()
    if not entry:
        return ""

    # 去掉方括号，同时把 :port 后缀剥掉
    #   [::1]        -> ::1
    #   [::1]:8080   -> ::1
    #   [2001:db8::1]:443 -> 2001:db8::1
    if entry.startswith("["):
        host, sep, rest = entry[1:].partition("]")
        if sep:
            entry = host
        # 没有闭合的 ] 就按原样处理（可能是畸形输入）
        else:
            entry = entry.lstrip("[")

    # 剥掉 CIDR 前缀（IPv6 CIDR httpx 无法编译）
    if "/" in entry:
        head, _, tail = entry.partition("/")
        if tail.isdigit() and ":" in head:
            entry = head

    return entry


def sanitize_no_proxy() -> None:
    """清理 NO_PROXY / no_proxy，去掉 httpx 无法解析的 IPv6 写法。

    触发场景很常见：Clash Verge / mihomo 默认导出
    ``no_proxy=127.0.0.1,localhost,::1,[::1]``，而 ``[::1]`` 会让 httpx 在
    构造 Client 时抛 ``InvalidURL: Invalid port: ':1]'``，表现为整个后端所有
    网络请求（视频解析、字幕、模型调用、环境自检）全部失败。

    只在确实含方括号或 IPv6 CIDR 时改写；其余情况逐字节保持原值不动。
    """
    for key in _NO_PROXY_KEYS:
        raw = os.environ.get(key)
        if not raw:
            continue
        # 快速跳过：不含方括号、也不像 IPv6 CIDR 就不用动
        if "[" not in raw and not _has_ipv6_cidr(raw):
            continue
        parts = []
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            normalized = _normalize_no_proxy_entry(item)
            if normalized:
                parts.append(normalized)
        os.environ[key] = ",".join(parts)


def _has_ipv6_cidr(raw: str) -> bool:
    """判断 NO_PROXY 里是否含 IPv6 CIDR 项（如 ::1/128、2001:db8::/32）。"""
    for item in raw.split(","):
        item = item.strip()
        head, sep, tail = item.partition("/")
        if sep and tail.isdigit() and ":" in head:
            return True
    return False


sanitize_no_proxy()


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
