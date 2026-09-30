const API_BASE = 'http://127.0.0.1:8000/api';

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(function (err) {
    console.error('Side panel behavior error:', err);
  });

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

async function getCollections() {
  return apiRequest('/collections?limit=50');
}

async function getAllNotes() {
  return apiRequest('/notes?limit=200');
}

async function getCollectionDetail(collId) {
  return apiRequest('/collections/' + collId);
}

async function generateQuiz(noteId) {
  return apiRequest('/quiz/generate', {
    method: 'POST',
    body: JSON.stringify({ note_id: noteId })
  });
}

async function chatNote(noteId, message, history) {
  return apiRequest('/notes/' + noteId + '/chat', {
    method: 'POST',
    body: JSON.stringify({ message: message, history: history || [] })
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
        case 'getCollections': {
          const result = await getCollections();
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'getAllNotes': {
          const result = await getAllNotes();
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'chatNote': {
          const result = await chatNote(msg.noteId, msg.message, msg.history);
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'getCollectionDetail': {
          const result = await getCollectionDetail(msg.collId);
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'generateQuiz': {
          const result = await generateQuiz(msg.noteId);
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
