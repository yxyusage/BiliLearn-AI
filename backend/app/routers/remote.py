"""B 站远程视频：用已保存的 cookie 取流 + 本地代理，供笔记页内嵌播放（3b 双流方案）。

- 取流：yt-dlp（复用 backend 依赖），cookie 从设置里读，随请求头传入。
- 代理：带 Referer/UA 转发 B 站 CDN，支持 Range（进度条拖动）。
- 播放页：/api/remote/player?bvid=&page=&t= ，视频+音频双流在前端同步。
"""
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Dict

import yt_dlp
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, StreamingResponse

from ..database import SessionLocal
from ..services.settings_store import get_setting

router = APIRouter()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
REFERER = "https://www.bilibili.com/"
_TTL = 3600.0

_cache: Dict[str, dict] = {}
_inflight: Dict[str, threading.Event] = {}
_lock = threading.Lock()


def _cookie() -> str:
    db = SessionLocal()
    try:
        return get_setting(db, "bili_cookie", "")
    finally:
        db.close()


def _pick(info: dict):
    fmts = info.get("formats") or []

    def furl(f):
        return f.get("url") or ((f.get("fragments") or [{}])[0].get("url"))

    vids = [f for f in fmts if f.get("vcodec") not in (None, "none")
            and f.get("acodec") == "none" and furl(f)]
    auds = [f for f in fmts if f.get("acodec") not in (None, "none")
            and f.get("vcodec") == "none" and furl(f)]
    if not vids or not auds:
        raise RuntimeError("没有找到可用的音视频流")
    avc = [f for f in vids if str(f.get("vcodec", "")).startswith("avc")] or vids
    # 用 1080P「标准档」，排除「1080P 高码率 / 1080P+」（B站 format_id 30077）
    avc = [f for f in avc if str(f.get("format_id")) != "30077"]
    v = max(avc, key=lambda f: f.get("height") or 0)
    a = max(auds, key=lambda f: f.get("abr") or 0)
    return furl(v), furl(a), v.get("height"), (info.get("duration") or 0)


def _extract(bvid: str, page: int) -> dict:
    """同一个 bvid:page 只解析一次：并发请求用 Event 排队，避免 /v 和 /a 各解析一遍。"""
    key = "%s:%s" % (bvid, page)
    with _lock:
        c = _cache.get(key)
        if c and c["exp"] > time.time():
            return c
        ev = _inflight.get(key)
        mine = ev is None
        if mine:
            ev = threading.Event()
            _inflight[key] = ev
    if not mine:
        ev.wait(timeout=120)
        with _lock:
            c = _cache.get(key)
        if c:
            return c
        with _lock:
            ev = _inflight.get(key)
            if ev is None:
                ev = threading.Event()
                _inflight[key] = ev
            mine = True
    try:
        cookie = _cookie()
        opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "http_headers": {"Referer": REFERER, "User-Agent": UA, "Cookie": cookie},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                "https://www.bilibili.com/video/%s?p=%s" % (bvid, page), download=False)
        v_url, a_url, height, dur = _pick(info)
        entry = {"v": v_url, "a": a_url, "height": height, "dur": dur,
                 "exp": time.time() + _TTL}
        with _lock:
            _cache[key] = entry
        return entry
    finally:
        with _lock:
            if mine:
                _inflight.pop(key, None)
        ev.set()


def _proxy(url: str, request: Request):
    rng = request.headers.get("range")
    hdrs = {"User-Agent": UA, "Referer": REFERER}
    if rng:
        hdrs["Range"] = rng
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=hdrs)
    try:
        r = urllib.request.urlopen(req, timeout=60, context=ctx)
    except urllib.error.HTTPError as e:
        r = e
    status = getattr(r, "status", 200)

    def gen():
        try:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                r.close()
            except Exception:
                pass

    headers = {}
    for h in ("Content-Type", "Content-Length", "Content-Range"):
        v = r.headers.get(h) if r.headers else None
        if v:
            headers[h] = v
    headers.setdefault("Accept-Ranges", "bytes")
    return StreamingResponse(gen(), status_code=status, headers=headers)


async def _entry(bvid: str, page: int) -> dict:
    try:
        return await run_in_threadpool(_extract, bvid, page)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="取流失败：%s" % e)


@router.get("/v")
async def remote_v(request: Request, bvid: str = Query(...), page: int = Query(1)):
    e = await _entry(bvid, page)
    return _proxy(e["v"], request)


@router.get("/a")
async def remote_a(request: Request, bvid: str = Query(...), page: int = Query(1)):
    e = await _entry(bvid, page)
    return _proxy(e["a"], request)


@router.get("/info")
async def remote_info(bvid: str = Query(...), page: int = Query(1)):
    e = await _entry(bvid, page)
    return {"height": e["height"], "duration": e["dur"]}


PLAYER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;height:100%;background:#000;overflow:hidden;font-family:sans-serif}
video{width:100%;height:100%;object-fit:contain;background:#000}
#load{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
color:#9ab;font-size:14px;background:rgba(0,0,0,.55);z-index:5}
#bar{position:absolute;top:8px;right:10px;display:flex;align-items:center;gap:8px;
background:rgba(0,0,0,.55);padding:5px 10px;border-radius:8px;z-index:6;color:#fff}
#bar input[type=range]{width:88px;vertical-align:middle}
#bar button{background:none;border:0;color:#fff;cursor:pointer;font-size:15px;padding:0}
</style></head><body>
<video id="v" controls playsinline></video>
<audio id="a"></audio>
<div id="load">加载中…</div>
<div id="bar"><button id="mute" title="静音">🔊</button><input id="vol" type="range" min="0" max="1" step="0.01" value="1"></div>
<script>
(function(){
  var q=new URLSearchParams(location.search);
  var bvid=q.get('bvid')||'', page=q.get('page')||'1', t0=parseFloat(q.get('t')||'0');
  if(!bvid){document.body.innerHTML='<p style="color:#fff;font:14px sans-serif;padding:20px">缺少 bvid</p>';return;}
  var v=document.getElementById('v'),a=document.getElementById('a'),load=document.getElementById('load'),
      vs=document.getElementById('vol'),mb=document.getElementById('mute');
  var qs='?bvid='+encodeURIComponent(bvid)+'&page='+encodeURIComponent(page);
  v.src='/api/remote/v'+qs; a.src='/api/remote/a'+qs;
  v.preload='auto'; a.preload='auto'; a.volume=1;
  // 视频无音轨，原生音量无效，这里用自定义滑条控制音频
  vs.addEventListener('input',function(){ a.volume=parseFloat(vs.value); a.muted=false; mb.textContent='🔊'; });
  mb.addEventListener('click',function(){ a.muted=!a.muted; mb.textContent=a.muted?'🔇':'🔊'; if(!a.muted) a.volume=parseFloat(vs.value); });
  var syncing=false;
  function playA(){ if(!v.paused) a.play().catch(function(){}); }
  function align(){
    syncing=true; a.pause();
    var t=v.currentTime;
    if(Math.abs(a.currentTime-t)<0.05){ syncing=false; playA(); return; }
    var done=function(){ a.removeEventListener('seeked',done); playA(); syncing=false; };
    a.addEventListener('seeked',done);
    try{ a.currentTime=t; }catch(e){ syncing=false; }
    setTimeout(function(){ if(syncing){ syncing=false; playA(); } },2000);
  }
  v.addEventListener('play',function(){ (Math.abs(a.currentTime-v.currentTime)>0.4)?align():playA(); });
  v.addEventListener('pause',function(){ a.pause(); });
  v.addEventListener('seeked',function(){ align(); });
  v.addEventListener('ratechange',function(){ if(!syncing) a.playbackRate=v.playbackRate; });
  v.addEventListener('timeupdate',function(){
    if(syncing||v.seeking||a.seeking) return;
    var d=a.currentTime-v.currentTime;
    if(Math.abs(d)>0.6) align();
    else if(Math.abs(d)>0.08) a.playbackRate=v.playbackRate*(d<0?1.03:0.97);
    else a.playbackRate=v.playbackRate;
  });
  v.addEventListener('waiting',function(){ load.style.display='flex'; });
  v.addEventListener('canplay',function(){ load.style.display='none'; });
  v.addEventListener('playing',function(){ load.style.display='none'; });
  v.addEventListener('error',function(){ load.textContent='视频加载失败，刷新重试'; load.style.display='flex'; });
  v.addEventListener('loadedmetadata',function(){
    load.style.display='none';
    if(t0>0){ try{ v.currentTime=t0; }catch(e){} }
  });
  if(t0>0){ v.addEventListener('canplay',function once(){ v.removeEventListener('canplay',once); v.play().catch(function(){}); }); }
})();
</script></body></html>"""


@router.get("/player", response_class=HTMLResponse)
async def player():
    return HTMLResponse(PLAYER_HTML)
