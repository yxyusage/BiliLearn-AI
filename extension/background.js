const API_BASE = 'http://127.0.0.1:8000/api';

async function apiRequest(path, options) {
  const url = API_BASE + path;
  const opts = Object.assign({
    headers: { 'Content-Type': 'application/json' }
  }, options || {});
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    let msg = '请求失败';
    try {
      const err = await resp.json();
      msg = err.detail || err.message || msg;
    } catch (e) {}
    throw new Error(msg + ' (' + resp.status + ')');
  }
  return resp.json();
}

async function checkBackend() {
  try {
    await apiRequest('/config');
    return { online: true };
  } catch (e) {
    return { online: false, error: e.message };
  }
}

async function getNoteByBvid(bvid, page) {
  const list = await apiRequest('/notes?limit=200');
  if (!Array.isArray(list)) return null;
  const p = page || 1;
  const match = list.filter(function (n) {
    return n.bvid === bvid && (n.page === p || !n.page);
  });
  if (match.length > 0) {
    match.sort(function (a, b) {
      return new Date(b.created_at) - new Date(a.created_at);
    });
    return match[0];
  }
  return null;
}

async function getNoteDetail(noteId) {
  return apiRequest('/notes/' + noteId);
}

async function generateNote(bvid, page, title) {
  return apiRequest('/notes/generate', {
    method: 'POST',
    body: JSON.stringify({
      bvid: bvid,
      page: page || 1,
      subject: 'general',
      title: title || ''
    })
  });
}

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  (async function () {
    try {
      switch (msg.type) {
        case 'checkBackend': {
          const result = await checkBackend();
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'getNoteByBvid': {
          const note = await getNoteByBvid(msg.bvid, msg.page);
          sendResponse({ ok: true, data: note });
          break;
        }
        case 'getNoteDetail': {
          const detail = await getNoteDetail(msg.noteId);
          sendResponse({ ok: true, data: detail });
          break;
        }
        case 'generateNote': {
          const result = await generateNote(msg.bvid, msg.page, msg.title);
          sendResponse({ ok: true, data: result });
          break;
        }
        default:
          sendResponse({ ok: false, error: '未知消息类型: ' + msg.type });
      }
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }
  })();
  return true;
});

chrome.runtime.onInstalled.addListener(function () {
  console.log('BiliLearn-AI 笔记助手已安装');
});
