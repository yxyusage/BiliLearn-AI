(function () {
  'use strict';

  var state = {
    tab: null,
    videoInfo: null,
    note: null,
    noteDetail: null,
    backendOnline: false,
    polling: false,
    pollTimer: null
  };

  var els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function initEls() {
    els.backendStatus = $('backendStatus');
    els.loadingState = $('loadingState');
    els.errorState = $('errorState');
    els.errorTitle = $('errorTitle');
    els.errorDesc = $('errorDesc');
    els.retryBtn = $('retryBtn');
    els.notBilibili = $('notBilibili');
    els.mainView = $('mainView');
    els.videoTitle = $('videoTitle');
    els.videoBvid = $('videoBvid');
    els.noNote = $('noNote');
    els.generateBtn = $('generateBtn');
    els.generating = $('generating');
    els.progressFill = $('progressFill');
    els.genTip = $('genTip');
    els.noteDetail = $('noteDetail');
    els.noteSummary = $('noteSummary');
    els.chapterList = $('chapterList');
    els.regenBtn = $('regenBtn');
    els.openFullBtn = $('openFullBtn');
  }

  function showView(name) {
    els.loadingState.style.display = name === 'loading' ? 'block' : 'none';
    els.errorState.style.display = name === 'error' ? 'block' : 'none';
    els.notBilibili.style.display = name === 'notbilibili' ? 'block' : 'none';
    els.mainView.style.display = name === 'main' ? 'block' : 'none';
  }

  function showError(title, desc) {
    els.errorTitle.textContent = title;
    els.errorDesc.textContent = desc || '';
    showView('error');
  }

  function setBackendStatus(online) {
    state.backendOnline = online;
    els.backendStatus.classList.remove('online', 'offline');
    els.backendStatus.classList.add(online ? 'online' : 'offline');
    els.backendStatus.querySelector('.status-text').textContent = online ? '后端已连接' : '后端未启动';
  }

  function sendBg(msg) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(msg, function (resp) {
        resolve(resp || { ok: false, error: '无响应' });
      });
    });
  }

  function sendContent(tabId, msg) {
    return new Promise(function (resolve) {
      chrome.tabs.sendMessage(tabId, msg, function (resp) {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
        } else {
          resolve(resp || { ok: false, error: '无响应' });
        }
      });
    });
  }

  function getCurrentTab() {
    return new Promise(function (resolve) {
      chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        resolve(tabs[0] || null);
      });
    });
  }

  function parseTimestamp(ts) {
    if (!ts) return null;
    if (typeof ts === 'number') return ts;
    var parts = String(ts).split(':');
    if (parts.length === 3) {
      return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2]);
    } else if (parts.length === 2) {
      return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
    }
    return null;
  }

  function formatTime(seconds) {
    if (seconds == null || isNaN(seconds)) return '00:00';
    var s = Math.floor(seconds);
    var m = Math.floor(s / 60);
    var sec = s % 60;
    if (m >= 60) {
      var h = Math.floor(m / 60);
      m = m % 60;
      return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
    }
    return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  async function checkBackend() {
    var resp = await sendBg({ type: 'checkBackend' });
    setBackendStatus(resp.ok && resp.data && resp.data.online);
    return state.backendOnline;
  }

  async function loadVideoInfo() {
    var tab = await getCurrentTab();
    state.tab = tab;
    if (!tab || !tab.url) {
      showView('notbilibili');
      return false;
    }
    var isBilibili = /bilibili\.com\/video\//.test(tab.url);
    if (!isBilibili) {
      showView('notbilibili');
      return false;
    }
    var resp = await sendContent(tab.id, { type: 'getVideoInfo' });
    if (!resp.ok) {
      var errMsg = resp.error || '未知错误';
      showError('插件未注入到页面', '错误信息：' + errMsg + '\n请刷新当前 B 站视频页面（按 F5），然后重新点击插件图标');
      return false;
    }
    if (!resp.data || !resp.data.bvid) {
      showError('无法获取视频信息', '请确保页面已完全加载，或刷新页面后重试');
      return false;
    }
    state.videoInfo = resp.data;
    els.videoTitle.textContent = resp.data.title || '未知标题';
    els.videoBvid.textContent = resp.data.bvid;
    return true;
  }

  async function checkNote() {
    if (!state.videoInfo || !state.videoInfo.bvid) return;
    var resp = await sendBg({ type: 'getNoteByBvid', bvid: state.videoInfo.bvid, page: state.videoInfo.page });
    if (resp.ok && resp.data) {
      state.note = resp.data;
      if (resp.data.status === 'done') {
        await loadNoteDetail(resp.data.id);
        showNoteDetail();
      } else if (resp.data.status === 'processing') {
        showGenerating();
        startPolling(resp.data.id);
      } else if (resp.data.status === 'failed') {
        showNoNote();
        els.generateBtn.textContent = '重新生成';
      } else {
        showNoNote();
      }
    } else {
      state.note = null;
      showNoNote();
    }
  }

  async function loadNoteDetail(noteId) {
    var resp = await sendBg({ type: 'getNoteDetail', noteId: noteId });
    if (resp.ok && resp.data) {
      state.noteDetail = resp.data;
    }
  }

  function showNoNote() {
    els.noNote.style.display = 'block';
    els.generating.style.display = 'none';
    els.noteDetail.style.display = 'none';
  }

  function showGenerating() {
    els.noNote.style.display = 'none';
    els.generating.style.display = 'block';
    els.noteDetail.style.display = 'none';
    var progress = 0;
    var timer = setInterval(function () {
      progress = Math.min(progress + Math.random() * 8, 90);
      els.progressFill.style.width = progress + '%';
    }, 800);
    state._progressTimer = timer;
  }

  function showNoteDetail() {
    els.noNote.style.display = 'none';
    els.generating.style.display = 'none';
    els.noteDetail.style.display = 'block';
    if (state._progressTimer) {
      clearInterval(state._progressTimer);
      state._progressTimer = null;
    }
    els.progressFill.style.width = '100%';

    var detail = state.noteDetail || state.note;
    var noteData = detail.note || {};
    els.noteSummary.textContent = noteData.summary || detail.summary || '暂无摘要';

    var chapters = (noteData.chapters || []).filter(function (ch) {
      return ch && ch.title;
    });
    var html = '';
    if (chapters.length === 0) {
      html = '<div style="text-align:center;color:#b0b8bc;padding:12px;font-size:12px">暂无章节</div>';
    } else {
      chapters.forEach(function (ch, i) {
        var time = parseTimestamp(ch.time_stamp) || ch.time || (ch.sections && ch.sections[0] && parseTimestamp(ch.sections[0].time_stamp));
        var timeStr = ch.time_stamp ? String(ch.time_stamp) : (time ? formatTime(time) : '');
        html += '<div class="chapter-item" data-index="' + i + '"' + (time ? ' data-time="' + time + '"' : '') + '>'
          + '<span class="chapter-no">' + (i + 1) + '</span>'
          + '<span class="chapter-name">' + escapeHtml(ch.title) + '</span>'
          + (timeStr ? '<span class="chapter-time">' + timeStr + '</span>' : '')
          + '</div>';
      });
    }
    els.chapterList.innerHTML = html;

    els.chapterList.querySelectorAll('.chapter-item').forEach(function (item) {
      item.addEventListener('click', function () {
        var time = parseFloat(item.getAttribute('data-time'));
        if (!isNaN(time) && state.tab) {
          sendContent(state.tab.id, { type: 'seekTo', seconds: time });
        }
      });
    });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  async function generateNote() {
    if (!state.videoInfo) return;
    els.generateBtn.disabled = true;
    els.generateBtn.innerHTML = '<span class="btn-icon">⏳</span> 提交中...';
    try {
      var resp = await sendBg({
        type: 'generateNote',
        bvid: state.videoInfo.bvid,
        page: state.videoInfo.page,
        title: state.videoInfo.title,
        url: state.videoInfo.url
      });
      if (resp.ok && resp.data) {
        state.note = resp.data;
        showGenerating();
        startPolling(resp.data.id);
      } else {
        throw new Error(resp.error || '生成失败');
      }
    } catch (e) {
      els.generateBtn.disabled = false;
      els.generateBtn.innerHTML = '<span class="btn-icon">⚡</span> 生成笔记';
      showError('生成失败', e.message || '请检查后端是否正常运行');
    }
  }

  function startPolling(noteId) {
    if (state.polling) return;
    state.polling = true;
    var count = 0;
    function poll() {
      if (!state.polling) return;
      count++;
      sendBg({ type: 'getNoteDetail', noteId: noteId }).then(function (resp) {
        if (!state.polling) return;
        if (resp.ok && resp.data) {
          state.note = resp.data;
          state.noteDetail = resp.data;
          if (resp.data.status === 'done') {
            state.polling = false;
            showNoteDetail();
            return;
          } else if (resp.data.status === 'failed') {
            state.polling = false;
            showNoNote();
            els.generateBtn.textContent = '重新生成';
            els.generateBtn.disabled = false;
            return;
          }
        }
        if (count < 120) {
          state.pollTimer = setTimeout(poll, 3000);
        } else {
          state.polling = false;
          els.genTip.textContent = '生成时间较长，可关闭弹窗稍后再来查看';
        }
      }).catch(function () {
        if (state.polling) {
          state.pollTimer = setTimeout(poll, 5000);
        }
      });
    }
    poll();
  }

  function stopPolling() {
    state.polling = false;
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
  }

  function openFullPage() {
    if (state.note && state.note.id) {
      chrome.tabs.create({ url: 'http://127.0.0.1:8000/#/note/' + state.note.id });
    }
  }

  async function init() {
    initEls();
    showView('loading');

    els.retryBtn.addEventListener('click', function () {
      init();
    });

    els.generateBtn.addEventListener('click', generateNote);
    els.regenBtn.addEventListener('click', function () {
      if (confirm('确定要重新生成笔记吗？')) {
        generateNote();
      }
    });
    els.openFullBtn.addEventListener('click', openFullPage);

    var online = await checkBackend();
    if (!online) {
      showError('后端未启动', '请先启动 BiliLearn-AI 后端服务（运行 start.bat），然后重试');
      return;
    }

    var hasVideo = await loadVideoInfo();
    if (!hasVideo) return;

    showView('main');
    await checkNote();
  }

  document.addEventListener('DOMContentLoaded', init);

  window.addEventListener('unload', function () {
    stopPolling();
  });
})();
