const DEFAULT_API_BASE = 'http://127.0.0.1:8000/api';

// 后端地址可在侧边栏「设置」中修改，存于 chrome.storage.local.bililearn_ext_settings.backendUrl
async function getApiBase() {
  try {
    const stored = await chrome.storage.local.get(['bililearn_ext_settings']);
    const s = stored && stored.bililearn_ext_settings;
    const base = s && s.backendUrl ? String(s.backendUrl).replace(/\/+$/, '') : '';
    if (base) return base + '/api';
  } catch (e) { /* 读取失败回退默认地址 */ }
  return DEFAULT_API_BASE;
}

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(function (err) {
    console.error('Side panel behavior error:', err);
  });

async function apiRequest(path, options) {
  const url = (await getApiBase()) + path;
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

function downloadImage(dataUrl, filename) {
  return new Promise(function (resolve, reject) {
    chrome.downloads.download({
      url: dataUrl,
      filename: filename,
      saveAs: false
    }, function (downloadId) {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(downloadId);
      }
    });
  });
}

async function updateLearningStatus(noteId, status) {
  return apiRequest('/notes/' + noteId + '/learning-status', {
    method: 'PUT',
    body: JSON.stringify({ status: status })
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
        case 'downloadImage': {
          const result = await downloadImage(msg.dataUrl, msg.filename);
          sendResponse({ ok: true, data: result });
          break;
        }
        case 'updateLearningStatus': {
          const result = await updateLearningStatus(msg.noteId, msg.status);
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
