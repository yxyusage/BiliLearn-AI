(function () {
  'use strict';

  var state = {
    tab: null,
    videoInfo: null,
    note: null,
    noteDetail: null,
    backendOnline: false,
    polling: false,
    pollTimer: null,
    chatHistory: [],
    view: 'note-list',
    navStack: [],
    currentCollection: null,
    activeTab: 'note',
    lastTabUrl: '',
    // 最近一次识别到的 B 站视频标签页，用于 Edge 侧边栏等拿不到"活跃标签页"的场景兜底
    lastVideoTab: null,
    followTimer: null,
    settings: {
      fontSize: 14,
      theme: 'light',
      palette: 'paper',
      expandChapters: false,
      backendUrl: 'http://127.0.0.1:8000'
    }
  };

  var els = {};

  function $(id) { return document.getElementById(id); }

  function initEls() {
    els.backBtn = $('backBtn');
    els.appTitle = $('appTitle');
    els.captureBtn = $('captureBtn');
    els.refreshBtn = $('refreshBtn');
    els.toast = $('toast');
    els.videoInfo = $('videoInfo');
    els.themeToggle = $('themeToggle');
    els.openFullBtn = $('openFullBtn');
    els.settingsBtn = $('settingsBtn');
    els.settingsOverlay = $('settingsOverlay');
    els.settingsClose = $('settingsClose');
    els.paletteDots = document.querySelectorAll('.palette-dot');
    els.tabs = document.querySelectorAll('.tab');
    els.tabPanes = document.querySelectorAll('.tab-pane');
    els.noteLoading = $('noteLoading');
    els.noteError = $('noteError');
    els.errorTitle = $('errorTitle');
    els.errorDesc = $('errorDesc');
    els.errorRetry = $('errorRetry');
    els.noNote = $('noNote');
    els.generateBtn = $('generateBtn');
    els.recentNotes = $('recentNotes');
    els.recentNotesList = $('recentNotesList');
    els.generating = $('generating');
    els.genProgress = $('genProgress');
    els.noteContent = $('noteContent');
    els.regenBtn = $('regenBtn');
    els.noteSummary = $('noteSummary');
    els.chapterList = $('chapterList');
    els.chatMessages = $('chatMessages');
    els.chatInput = $('chatInput');
    els.chatSend = $('chatSend');
    els.quizLoading = $('quizLoading');
    els.quizEmpty = $('quizEmpty');
    els.quizList = $('quizList');
    els.generateQuizBtn = $('generateQuizBtn');
    els.collLoading = $('collLoading');
    els.collectionList = $('collectionList');
    els.collEmpty = $('collEmpty');
    els.collListContainer = $('collListContainer');
    els.collDetailContainer = $('collDetailContainer');
    els.collDetailTitle = $('collDetailTitle');
    els.collDetailMeta = $('collDetailMeta');
    els.collDetailProgress = $('collDetailProgress');
    els.collEpisodeList = $('collEpisodeList');
    els.captureCount = $('captureCount');
    els.captureEmpty = $('captureEmpty');
    els.captureGrid = $('captureGrid');
    els.clearCaptureBtn = $('clearCaptureBtn');
    els.learningStatusSelectEl = $('learningStatusSelectEl');
    els.fontDec = $('fontDec');
    els.fontInc = $('fontInc');
    els.fontValue = $('fontValue');
    els.expandChapters = $('expandChapters');
    els.backendUrl = $('backendUrl');
    els.backendStatus = $('backendStatus');
    els.saveSettings = $('saveSettings');
  }

  function loadSettings() {
    try {
      chrome.storage.local.get(['bililearn_ext_settings'], function (result) {
        if (result.bililearn_ext_settings) {
          state.settings = Object.assign(state.settings, result.bililearn_ext_settings);
        }
        applySettings();
      });
    } catch (e) {
      applySettings();
    }
  }

  function saveSettings() {
    try { chrome.storage.local.set({ bililearn_ext_settings: state.settings }); } catch (e) {}
  }

  function applySettings() {
    document.documentElement.style.setProperty('--font-size', state.settings.fontSize + 'px');
    els.fontValue.textContent = state.settings.fontSize + 'px';
    document.documentElement.setAttribute('data-theme', state.settings.theme);
    document.documentElement.setAttribute('data-palette', state.settings.palette);
    els.themeToggle.textContent = state.settings.theme === 'dark' ? '☀️' : '🌙';
    els.paletteDots.forEach(function (dot) {
      dot.classList.toggle('active', dot.dataset.palette === state.settings.palette);
    });
    els.expandChapters.checked = state.settings.expandChapters;
    els.backendUrl.value = state.settings.backendUrl;
    if (state.noteDetail) renderNote();
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

  function isVideoTab(tab) {
    return !!(tab && tab.id != null && tab.url && /bilibili\.com\/video\//.test(tab.url));
  }

  function queryTabs(query) {
    return new Promise(function (resolve) {
      try {
        if (!chrome.tabs || !chrome.tabs.query) { resolve([]); return; }
        chrome.tabs.query(query, function (tabs) {
          if (chrome.runtime.lastError) { resolve([]); return; }
          resolve(tabs || []);
        });
      } catch (e) {
        resolve([]);
      }
    });
  }

  function rememberVideoTab(tab) {
    if (isVideoTab(tab)) {
      state.lastVideoTab = { id: tab.id, url: tab.url, windowId: tab.windowId, title: tab.title || '' };
    }
    return tab || null;
  }

  // 找出"用户正在看的 B 站视频标签页"。
  // Edge 的侧边栏里 chrome.tabs.query({active:true,currentWindow:true}) 可能返回空、
  // 或返回的不是 B 站页面；此时绝不能直接判定"这个视频没有笔记"，要逐级兜底：
  //   活跃标签页 → 最近聚焦窗口的活跃标签页 → 所有 B 站视频页 → 上次记住的那个
  async function getCurrentTab() {
    var found = (await queryTabs({ active: true, currentWindow: true })).filter(isVideoTab);
    if (found.length) return rememberVideoTab(found[0]);

    found = (await queryTabs({ active: true, lastFocusedWindow: true })).filter(isVideoTab);
    if (found.length) return rememberVideoTab(found[0]);

    var all = (await queryTabs({ url: ['*://*.bilibili.com/video/*'] })).filter(isVideoTab);
    if (all.length) {
      var remembered = all.filter(function (t) {
        return state.lastVideoTab && t.id === state.lastVideoTab.id;
      });
      if (remembered.length) return rememberVideoTab(remembered[0]);
      var sameWindow = all.filter(function (t) {
        return state.lastVideoTab && t.windowId === state.lastVideoTab.windowId;
      });
      return rememberVideoTab((sameWindow.length ? sameWindow : all)[0]);
    }

    if (state.lastVideoTab) {
      var fresh = (await queryTabs({})).filter(function (t) { return t.id === state.lastVideoTab.id; });
      if (fresh.length && isVideoTab(fresh[0])) return rememberVideoTab(fresh[0]);
    }
    return null;
  }

  function parseTimestamp(ts) {
    if (!ts) return null;
    if (typeof ts === 'number') return ts;
    var parts = String(ts).split(':');
    if (parts.length === 3) return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2]);
    if (parts.length === 2) return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
    return null;
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function showNoteState(name) {
    els.noteLoading.style.display = name === 'loading' ? 'block' : 'none';
    els.noteError.style.display = name === 'error' ? 'block' : 'none';
    els.noNote.style.display = name === 'none' ? 'block' : 'none';
    els.generating.style.display = name === 'generating' ? 'block' : 'none';
    els.noteContent.style.display = name === 'content' ? 'block' : 'none';
  }

  function showError(title, desc) {
    els.errorTitle.textContent = title;
    els.errorDesc.textContent = desc || '';
    showNoteState('error');
  }

  async function checkBackend() {
    var resp = await sendBg({ type: 'checkBackend' });
    state.backendOnline = resp.ok && resp.data && resp.data.online;
    els.backendStatus.textContent = state.backendOnline ? '已连接' : '未连接';
    els.backendStatus.className = 'status-badge ' + (state.backendOnline ? 'online' : 'offline');
    return state.backendOnline;
  }

  // 内容脚本可能没注入：Edge 的站点访问权限、扩展刚更新、或从 B 站站内 SPA 路由跳转过来。
  // 按需补注入再重试一次，避免直接报"无法获取视频信息"（content.js 自带防重复注入）
  // 返回 {ok, reason}：失败时把原因带出来，好让提示能说清楚到底卡在哪
  async function ensureContentScript(tabId) {
    if (!chrome.scripting || !chrome.scripting.executeScript) {
      return { ok: false, reason: '扩展缺少 scripting 权限，请到扩展页点一次「🔄 重新加载」' };
    }
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['content/content.js']
      });
      try {
        await chrome.scripting.insertCSS({ target: { tabId: tabId }, files: ['content/content.css'] });
      } catch (e) { /* 样式注入失败不影响功能 */ }
      return { ok: true };
    } catch (e) {
      return { ok: false, reason: (e && e.message) ? e.message : '注入内容脚本失败' };
    }
  }

  async function loadVideoInfo() {
    if (!chrome.tabs || !chrome.tabs.query) {
      els.videoInfo.innerHTML = '<div class="vi-loading">当前上下文读不到标签页（浏览器限制）。<br>请点工具栏图标打开侧边栏重试。</div>';
      return false;
    }
    var tab = await getCurrentTab();
    state.tab = tab;
    if (!tab || tab.id == null) {
      els.videoInfo.innerHTML = '<div class="vi-loading">未检测到 B 站视频标签页。<br>请把 B 站视频页切到前台，再点右上角 🔄 刷新。</div>';
      return false;
    }
    if (!tab.url) {
      els.videoInfo.innerHTML = '<div class="vi-loading">读不到标签页地址（扩展缺少「标签页」权限）。</div>';
      return false;
    }
    if (!/bilibili\.com\/video\//.test(tab.url)) {
      els.videoInfo.innerHTML = '<div class="vi-loading">当前标签页不是 B 站视频页：<br><span class="vi-url">' + escapeHtml(tab.url) + '</span></div>';
      return false;
    }
    var resp = await sendContent(tab.id, { type: 'getVideoInfo' });
    var injectReason = '';
    if (!resp.ok || !resp.data || !resp.data.bvid) {
      // 内容脚本不在（常见于：从合集页 SPA 跳到视频页、扩展刚更新、标签页是更新前打开的）
      var injected = await ensureContentScript(tab.id);
      if (injected.ok) {
        resp = await sendContent(tab.id, { type: 'getVideoInfo' });
      } else {
        injectReason = injected.reason;
      }
    }
    if (!resp.ok || !resp.data || !resp.data.bvid) {
      // 页面刚跳转时脚本可能还没就绪，稍等一下再试一次（B 站换集是 SPA 跳转，时序很敏感）
      await new Promise(function (r) { setTimeout(r, 700); });
      resp = await sendContent(tab.id, { type: 'getVideoInfo' });
    }
    if (!resp.ok || !resp.data || !resp.data.bvid) {
      els.videoInfo.innerHTML = '<div class="vi-loading">已找到视频页，但读不到视频信息（' +
        escapeHtml(injectReason || resp.error || '内容脚本无响应') + '）。<br>' +
        '按 F5 刷新一次 B 站页面即可；若反复出现，请到扩展页点一次「🔄 重新加载」。</div>';
      return false;
    }
    state.videoInfo = resp.data;
    rememberVideoTab(tab);
    els.videoInfo.innerHTML =
      '<div class="vi-title">' + escapeHtml(resp.data.title || '未知标题') + '</div>' +
      '<div class="vi-meta"><span class="vi-bvid">' + escapeHtml(resp.data.bvid) + '</span><span>P' + (resp.data.page || 1) + '</span></div>';
    return true;
  }

  async function checkNote() {
    if (!state.videoInfo || !state.videoInfo.bvid) return;
    state.noteDetail = null;
    showNoteState('loading');
    var resp = await sendBg({ type: 'getNoteByBvid', bvid: state.videoInfo.bvid, page: state.videoInfo.page });
    if (resp.ok && resp.data) {
      state.note = resp.data;
      if (resp.data.status === 'done') {
        await loadNoteDetail(resp.data.id);
        renderNote();
        renderQuiz();
      } else if (resp.data.status === 'processing') {
        showNoteState('generating');
        startPolling(resp.data.id);
      } else {
        showNoteState('none');
      }
    } else {
      state.note = null;
      showNoteState('none');
      loadRecentNotes();
    }
  }

  async function loadRecentNotes() {
    try {
      var resp = await sendBg({ type: 'getAllNotes' });
      if (resp.ok && resp.data && Array.isArray(resp.data) && resp.data.length > 0) {
        renderRecentNotes(resp.data.slice(0, 10));
        els.recentNotes.style.display = 'block';
      } else {
        els.recentNotes.style.display = 'none';
      }
    } catch (e) {
      els.recentNotes.style.display = 'none';
    }
  }

  function renderRecentNotes(notes) {
    var html = '';
    notes.forEach(function (n) {
      var date = n.created_at ? n.created_at.substring(0, 10) : '';
      html += '<div class="rn-item" data-id="' + n.id + '">';
      html += '<div class="rn-item-title">' + escapeHtml(n.title || '未命名') + '</div>';
      html += '<div class="rn-item-meta"><span>' + escapeHtml(n.bvid || '') + '</span><span>P' + (n.page || 1) + '</span><span>' + date + '</span></div>';
      html += '</div>';
    });
    els.recentNotesList.innerHTML = html;
    els.recentNotesList.querySelectorAll('.rn-item').forEach(function (item) {
      item.addEventListener('click', function () {
        var noteId = parseInt(item.dataset.id, 10);
        if (noteId) openNoteById(noteId);
      });
    });
  }

  async function openNoteById(noteId, skipPush) {
    showNoteState('loading');
    try {
      var resp = await sendBg({ type: 'getNoteDetail', noteId: noteId });
      if (resp.ok && resp.data) {
        if (!skipPush) pushNav();
        state.note = resp.data;
        state.noteDetail = resp.data;
        if (resp.data.status === 'done') {
          setView('note-detail');
          renderNote();
          renderQuiz();
        } else if (resp.data.status === 'processing') {
          setView('note-detail');
          showNoteState('generating');
          startPolling(noteId);
        } else {
          state.navStack.pop();
          showNoteState('none');
          loadRecentNotes();
        }
      } else {
        showError('加载失败', resp.error || '无法加载笔记');
      }
    } catch (e) {
      showError('加载失败', e.message);
    }
  }

  async function loadNoteDetail(noteId) {
    var resp = await sendBg({ type: 'getNoteDetail', noteId: noteId });
    if (resp.ok && resp.data) state.noteDetail = resp.data;
  }

  function renderNote() {
    showNoteState('content');
    var detail = state.noteDetail || state.note;
    var noteData = detail.note || {};
    els.noteSummary.textContent = noteData.summary || detail.summary || '暂无摘要';
    if (els.learningStatusSelectEl) {
      els.learningStatusSelectEl.value = detail.learning_status || 'unlearned';
    }

    var chapters = noteData.chapters || [];
    var html = '';
    if (chapters.length === 0) {
      html = '<div style="text-align:center;color:var(--text-3);padding:16px;font-size:12px">暂无章节内容</div>';
    } else {
      chapters.forEach(function (ch, i) {
        var time = parseTimestamp(ch.time_stamp);
        var expanded = state.settings.expandChapters ? 'expanded' : '';
        html += '<div class="chapter-card ' + expanded + '" data-index="' + i + '">';
        html += '<div class="chapter-header">';
        html += '<span class="chapter-no">' + (i + 1) + '</span>';
        html += '<span class="chapter-title">' + escapeHtml(ch.title || '未命名章节') + '</span>';
        if (time !== null) html += '<span class="chapter-time" data-time="' + time + '">' + escapeHtml(String(ch.time_stamp)) + '</span>';
        html += '<span class="chapter-toggle">▶</span></div>';
        html += '<div class="chapter-body">' + renderSections(ch.sections || []) + '</div></div>';
      });
    }
    els.chapterList.innerHTML = html;

    els.chapterList.querySelectorAll('.chapter-header').forEach(function (header) {
      header.addEventListener('click', function (e) {
        if (e.target.classList.contains('chapter-time')) return;
        header.parentElement.classList.toggle('expanded');
      });
    });
    els.chapterList.querySelectorAll('.chapter-time').forEach(function (timeEl) {
      timeEl.addEventListener('click', function (e) {
        e.stopPropagation();
        var time = parseFloat(timeEl.dataset.time);
        if (!isNaN(time) && state.tab) sendContent(state.tab.id, { type: 'seekTo', seconds: time });
      });
    });
    renderMathInElement(els.chapterList);
  }

  function renderSections(sections) {
    var html = '';
    sections.forEach(function (sec) {
      if (sec.heading) html += '<div class="section-heading">' + escapeHtml(sec.heading) + '</div>';
      (sec.blocks || []).forEach(function (block) {
        switch (block.type) {
          case 'text': html += '<div class="section-text">' + renderInline(block.content || '') + '</div>'; break;
          case 'formula':
            var fc = (block.content || '').trim().replace(/^\$+/, '').replace(/\$+$/, '');
            html += '<div class="section-formula"><span class="formula-display" data-latex="' + escapeHtml(fc) + '"></span></div>';
            break;
          case 'code': html += '<pre class="section-code"><code>' + escapeHtml(block.content || '') + '</code></pre>'; break;
          case 'list':
            var tag = block.ordered ? 'ol' : 'ul';
            html += '<' + tag + ' class="section-list">';
            (block.items || []).forEach(function (item) { html += '<li>' + renderInline(item) + '</li>'; });
            html += '</' + tag + '>'; break;
          case 'steps':
            html += '<div class="section-steps">';
            (block.items || []).forEach(function (step) { html += '<div class="step-item">' + renderInline(step) + '</div>'; });
            html += '</div>'; break;
          case 'table': html += renderTable(block); break;
          case 'quote': html += '<div class="section-quote">' + renderInline(block.content || '') + '</div>'; break;
          case 'heading': html += '<div class="section-heading">' + escapeHtml(block.content || '') + '</div>'; break;
        }
      });
    });
    return html;
  }

  function renderInline(text) {
    var escaped = escapeHtml(text);
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\$([^$]+?)\$/g, function (m, latex) {
      return '<span class="formula-inline" data-latex="' + latex.replace(/"/g, '&quot;') + '"></span>';
    });
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
  }

  // 单选答案：模型返回字母时补全选项文本，返回文本时原样展示
  function answerDisplay(q) {
    var ans = String(q.answer || '').trim();
    var m = ans.match(/^([A-Da-d])(?:[\.、\)）:：]|$)/);
    if (m) {
      var idx = m[1].toUpperCase().charCodeAt(0) - 65;
      if (idx >= 0 && idx < q.options.length) {
        return m[1].toUpperCase() + '. ' + q.options[idx];
      }
    }
    var stripped = ans.replace(/^[A-Da-d][\.、\)）:：]\s*/, '');
    for (var i = 0; i < q.options.length; i++) {
      var opt = String(q.options[i]).replace(/^[A-Da-d][\.、\)）:：]\s*/, '');
      if (stripped && (stripped === opt || stripped.indexOf(opt) >= 0 || opt.indexOf(stripped) >= 0)) {
        return String.fromCharCode(65 + i) + '. ' + q.options[i];
      }
    }
    return ans;
  }

  function renderTable(block) {
    var headers = block.headers || [];
    var rows = block.rows || [];
    var html = '<div style="overflow-x:auto"><table class="section-table"><thead><tr>';
    headers.forEach(function (h) { html += '<th>' + escapeHtml(h) + '</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(function (row) {
      html += '<tr>';
      row.forEach(function (cell) { html += '<td>' + escapeHtml(cell) + '</td>'; });
      html += '</tr>';
    });
    return html + '</tbody></table></div>';
  }

  function renderMathInElement(el) {
    if (typeof katex === 'undefined') return;
    el.querySelectorAll('.formula-display').forEach(function (node) {
      try { katex.render(node.dataset.latex || '', node, { displayMode: true, throwOnError: false, output: 'html' }); }
      catch (e) { node.textContent = node.dataset.latex || ''; }
    });
    el.querySelectorAll('.formula-inline').forEach(function (node) {
      try { katex.render(node.dataset.latex || '', node, { displayMode: false, throwOnError: false, output: 'html' }); }
      catch (e) { node.textContent = '$' + (node.dataset.latex || '') + '$'; }
    });
  }

  async function generateNote() {
    if (!state.videoInfo || !state.videoInfo.bvid) {
      // 原来这里直接 return，点了没有任何反应；现在明确告诉用户原因
      showToast('还没识别到视频，请把 B 站视频页切到前台后点右上角 🔄 重试');
      return;
    }
    els.generateBtn.disabled = true;
    els.generateBtn.innerHTML = '<span>⏳ 提交中...</span>';
    try {
      var resp = await sendBg({ type: 'generateNote', bvid: state.videoInfo.bvid, page: state.videoInfo.page, title: state.videoInfo.title });
      if (resp.ok && resp.data) {
        state.note = resp.data;
        showNoteState('generating');
        startPolling(resp.data.id);
      } else throw new Error(resp.error || '生成失败');
    } catch (e) {
      els.generateBtn.disabled = false;
      els.generateBtn.innerHTML = '<span>⚡ 生成笔记</span>';
      showError('生成失败', e.message || '请检查后端是否正常运行');
    }
  }

  function startPolling(noteId) {
    if (state.polling) return;
    state.polling = true;
    var progress = 0;
    var progTimer = setInterval(function () {
      progress = Math.min(progress + Math.random() * 8, 90);
      els.genProgress.style.width = progress + '%';
    }, 800);
    function poll() {
      if (!state.polling) return;
      sendBg({ type: 'getNoteDetail', noteId: noteId }).then(function (resp) {
        if (!state.polling) return;
        if (resp.ok && resp.data) {
          state.note = resp.data;
          state.noteDetail = resp.data;
          if (resp.data.status === 'done') {
            state.polling = false; clearInterval(progTimer);
            els.genProgress.style.width = '100%';
            setTimeout(function () { renderNote(); renderQuiz(); }, 300);
            return;
          }
          if (resp.data.status === 'failed') {
            state.polling = false; clearInterval(progTimer);
            showNoteState('none');
            els.generateBtn.disabled = false;
            els.generateBtn.innerHTML = '<span>⚡ 重新生成</span>';
            return;
          }
        }
        state.pollTimer = setTimeout(poll, 3000);
      }).catch(function () { if (state.polling) state.pollTimer = setTimeout(poll, 5000); });
    }
    poll();
  }

  function stopPolling() {
    state.polling = false;
    if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }
  }

  function renderQuiz() {
    var detail = state.noteDetail || state.note;
    var quizzes = (detail && detail.quizzes) || {};
    var questions = quizzes.questions || [];
    if (questions.length === 0) {
      els.quizEmpty.style.display = 'block';
      els.quizList.style.display = 'none';
      return;
    }
    els.quizEmpty.style.display = 'none';
    els.quizList.style.display = 'block';
    var typeMap = { single: '单选', judge: '判断', fill: '填空', calc: '计算' };
    var diffMap = { basic: '基础', medium: '中档', advanced: '拔高' };
    var html = '';
    questions.forEach(function (q, i) {
      html += '<div class="quiz-item" data-q="' + i + '">';
      html += '<div class="quiz-header"><span class="quiz-no">' + (i + 1) + '</span>';
      html += '<span class="quiz-type">' + (typeMap[q.type] || q.type) + '</span>';
      html += '<span class="quiz-diff ' + (q.difficulty || 'basic') + '">' + (diffMap[q.difficulty || 'basic'] || '') + '</span></div>';
      html += '<div class="quiz-stem">' + renderInline(q.stem || '') + '</div>';
      if (q.type === 'single' && q.options && q.options.length) {
        html += '<div class="quiz-options">';
        q.options.forEach(function (opt, oi) {
          // 选项同样要走 LaTeX/Markdown 渲染，否则 $S_1+S_2$ 会原样显示
          html += '<div class="quiz-option" data-opt="' + oi + '">' + String.fromCharCode(65 + oi) + '. ' + renderInline(opt) + '</div>';
        });
        html += '</div>';
      } else if (q.type === 'judge') {
        html += '<div class="quiz-options">';
        html += '<div class="quiz-option" data-opt="true">✓ 正确</div>';
        html += '<div class="quiz-option" data-opt="false">✗ 错误</div>';
        html += '</div>';
      } else if (q.type === 'fill') {
        html += '<input class="quiz-fill-input" type="text" placeholder="输入答案...">';
      } else {
        html += '<textarea class="quiz-fill-input" rows="2" placeholder="输入计算过程和答案..."></textarea>';
      }
      html += '<div class="quiz-actions"><button class="btn btn-outline btn-sm quiz-check">查看答案</button></div>';
      var answerText = q.type === 'single' && q.options && q.options.length
        ? answerDisplay(q)
        : (q.answer || '');
      html += '<div class="quiz-answer"><strong>答案：</strong>' + renderInline(answerText) + (q.explanation ? '<br><strong>解析：</strong>' + renderInline(q.explanation) : '') + '</div>';
      html += '</div>';
    });
    els.quizList.innerHTML = html;
    renderMathInElement(els.quizList);

    els.quizList.querySelectorAll('.quiz-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        var item = opt.closest('.quiz-item');
        item.querySelectorAll('.quiz-option').forEach(function (o) { o.classList.remove('selected'); });
        opt.classList.add('selected');
      });
    });
    els.quizList.querySelectorAll('.quiz-check').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item = btn.closest('.quiz-item');
        var answer = item.querySelector('.quiz-answer');
        answer.classList.toggle('show');
        btn.textContent = answer.classList.contains('show') ? '隐藏答案' : '查看答案';
      });
    });
  }

  function appendChatMsg(role, content) {
    var empty = els.chatMessages.querySelector('.chat-empty');
    if (empty) empty.remove();
    var div = document.createElement('div');
    div.className = 'msg msg-' + role;
    var avatar = role === 'user' ? '🧑' : '🤖';
    div.innerHTML = '<div class="msg-avatar">' + avatar + '</div><div class="msg-bubble">' + content + '</div>';
    els.chatMessages.appendChild(div);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    renderMathInElement(div);
  }

  async function sendChat() {
    var text = els.chatInput.value.trim();
    if (!text) return;
    if (!state.note) {
      appendChatMsg('ai', '⚠️ 请先在「笔记」标签中打开一篇笔记，再进行提问');
      return;
    }
    appendChatMsg('user', escapeHtml(text).replace(/\n/g, '<br>'));
    els.chatInput.value = '';
    els.chatSend.disabled = true;
    els.chatSend.textContent = '...';
    try {
      var history = state.chatHistory.slice(-10);
      var resp = await sendBg({ type: 'chatNote', noteId: state.note.id, message: text, history: history });
      if (resp.ok && resp.data && resp.data.reply) {
        var reply = resp.data.reply;
        state.chatHistory.push({ role: 'user', content: text });
        state.chatHistory.push({ role: 'assistant', content: reply });
        appendChatMsg('ai', formatChatReply(reply));
      } else {
        appendChatMsg('ai', '⚠️ ' + (resp.error || 'AI 答疑失败'));
      }
    } catch (e) {
      appendChatMsg('ai', '⚠️ ' + e.message);
    }
    els.chatSend.disabled = false;
    els.chatSend.textContent = '发送';
  }

  function formatChatReply(text) {
    var html = escapeHtml(text);
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\$([^$]+?)\$/g, function (m, latex) {
      return '<span class="formula-inline" data-latex="' + latex.replace(/"/g, '&quot;') + '"></span>';
    });
    return html;
  }

  async function loadCollections() {
    els.collLoading.style.display = 'block';
    els.collectionList.style.display = 'none';
    els.collEmpty.style.display = 'none';
    try {
      var resp = await sendBg({ type: 'getCollections' });
      if (resp.ok && resp.data && Array.isArray(resp.data) && resp.data.length > 0) {
        renderCollections(resp.data);
      } else {
        els.collEmpty.style.display = 'block';
      }
    } catch (e) {
      els.collEmpty.style.display = 'block';
    }
    els.collLoading.style.display = 'none';
  }

  function renderCollections(collections) {
    var html = '';
    collections.forEach(function (coll) {
      var total = coll.total || 0;
      var done = coll.done_count || 0;
      var pct = total > 0 ? Math.round(done / total * 100) : 0;
      html += '<div class="collection-item" data-id="' + coll.id + '">';
      html += '<div class="coll-title">' + escapeHtml(coll.title || '未命名合集') + '</div>';
      html += '<div class="coll-meta"><span>' + done + '/' + total + ' 集</span><span>' + pct + '%</span></div>';
      html += '<div class="coll-progress"><div class="coll-progress-fill" style="width:' + pct + '%"></div></div></div>';
    });
    els.collectionList.innerHTML = html;
    els.collectionList.style.display = 'block';
    els.collectionList.querySelectorAll('.collection-item').forEach(function (item) {
      item.addEventListener('click', function () {
        var id = parseInt(item.dataset.id, 10);
        if (id) openCollectionDetail(id);
      });
    });
  }

  function setView(view) {
    state.view = view;
    els.backBtn.style.display = state.navStack.length > 0 ? 'block' : 'none';
    if (view === 'coll-detail') {
      els.collListContainer.style.display = 'none';
      els.collDetailContainer.style.display = 'block';
      els.appTitle.textContent = '合集详情';
    } else if (view === 'coll-list') {
      els.collListContainer.style.display = 'block';
      els.collDetailContainer.style.display = 'none';
      els.appTitle.textContent = 'BiliLearn';
    } else if (view === 'note-detail') {
      els.appTitle.textContent = '笔记详情';
    } else {
      els.appTitle.textContent = 'BiliLearn';
    }
  }

  function pushNav() {
    state.navStack.push({
      view: state.view,
      noteId: state.note ? state.note.id : null,
      collId: state.currentCollection ? state.currentCollection.id : null
    });
  }

  function goBack() {
    if (state.navStack.length === 0) return;
    var prev = state.navStack.pop();
    state.note = null;
    state.noteDetail = null;
    state.chatHistory = [];
    if (prev.view === 'coll-detail' && prev.collId) {
      setView('coll-detail');
      openCollectionDetail(prev.collId, true);
    } else if (prev.view === 'coll-list') {
      setView('coll-list');
      loadCollections();
    } else {
      setView('note-list');
      checkNote();
    }
  }

  // 判断当前显示的笔记是否就对应标签页里的那个视频
  function noteMatchesTab() {
    if (!state.note || !state.videoInfo) return false;
    var sameBvid = (state.note.bvid || '') === (state.videoInfo.bvid || '');
    var samePage = (state.note.page || 1) === (state.videoInfo.page || 1);
    return sameBvid && samePage;
  }

  // 重新读取当前标签页的视频信息，并把侧边栏切到该视频对应的笔记
  async function syncToTab(force) {
    var ok = await loadVideoInfo();
    if (!ok) {
      // 不要在这里覆盖 loadVideoInfo 写的具体原因（否则只会看到笼统的"请在 B 站视频页面使用"）
      // 关键：若当前地址仍指向已经显示出来的那篇笔记（内容脚本暂时读不到），就保留内容，
      // 否则 B 站站内换集（SPA 跳转）时会"闪一下笔记就消失了"
      var url = (state.tab && state.tab.url) ? state.tab.url : '';
      if (state.note && state.noteDetail && state.note.bvid && url.indexOf(state.note.bvid) >= 0) {
        showNoteState('content');
        return false;
      }
      state.videoInfo = null;
      state.note = null;
      state.noteDetail = null;
      showNoteState('none');
      return false;
    }
    // 记下当前 URL，避免自动跟随逻辑重复触发
    state.lastTabUrl = (state.tab && state.tab.url) ? state.tab.url : '';
    if (!force && noteMatchesTab() && state.view === 'note-detail') {
      // 视频没变：只重载当前笔记内容
      await openNoteById(state.note.id, true);
      renderQuiz();
      return true;
    }
    state.navStack = [];
    state.currentCollection = null;
    state.chatHistory = [];
    setView('note-list');
    await checkNote();
    renderQuiz();
    return true;
  }

  function refreshCurrent() {
    els.refreshBtn.style.opacity = '0.5';
    setTimeout(function () { els.refreshBtn.style.opacity = '1'; }, 500);
    if (state.view === 'coll-detail' && state.currentCollection && state.currentCollection.id) {
      openCollectionDetail(state.currentCollection.id, true);
    } else if (state.view === 'coll-list') {
      loadCollections();
    } else {
      // 直接切集的场景：必须重新识别标签页视频，否则会一直停留在上一个视频的笔记
      syncToTab(false);
    }
  }

  // 跟随 B 站站内换集（URL 变化）自动刷新，不用手动点刷新或重开侧边栏
  async function followActiveTab() {
    if (state.view !== 'note-list' && state.view !== 'note-detail') return;
    if (state.activeTab !== 'note' && state.activeTab !== 'chat' && state.activeTab !== 'quiz') return;
    var tab = await getCurrentTab();
    if (!tab || !tab.url || !/bilibili\.com\/video\//.test(tab.url)) return;
    if (tab.url === state.lastTabUrl) return;
    state.lastTabUrl = tab.url;
    var ok = await syncToTab(true);
    if (!ok) return;
    if (state.activeTab === 'chat') resetChatMessages();
    if (state.activeTab === 'quiz') renderQuiz();
  }

  function startFollowingTab() {
    if (state.followTimer) return;
    state.followTimer = setInterval(function () { followActiveTab(); }, 2500);
    try {
      chrome.tabs.onUpdated.addListener(function (tabId, changeInfo) {
        if (changeInfo && changeInfo.url) followActiveTab();
      });
      chrome.tabs.onActivated.addListener(function (info) {
        try {
          chrome.tabs.get(info.tabId, function (t) {
            if (!chrome.runtime.lastError) rememberVideoTab(t);
          });
        } catch (e) { /* 忽略：只是缓存 */ }
        followActiveTab();
      });
    } catch (e) { /* 权限不足时退回轮询 */ }
  }

  function resetChatMessages() {
    state.chatHistory = [];
    if (els.chatMessages) {
      els.chatMessages.innerHTML = '<div class="chat-empty"><div class="ce-icon">💬</div><p>AI 答疑</p>' +
        '<p class="ce-desc">基于当前笔记内容回答你的问题</p></div>';
    }
  }

  function showToast(message, duration) {
    els.toast.textContent = message;
    els.toast.style.display = 'block';
    clearTimeout(els.toast._timer);
    els.toast._timer = setTimeout(function () {
      els.toast.style.display = 'none';
    }, duration || 2500);
  }

  function formatTime(seconds) {
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = Math.floor(seconds % 60);
    return (h > 0 ? String(h).padStart(2, '0') + '' : '') +
      String(m).padStart(2, '0') + String(s).padStart(2, '0');
  }

  function sanitizeFilename(name) {
    return String(name || 'video')
      .replace(/[\\/:*?"<>|]/g, '_')
      .replace(/\s+/g, '_')
      .substring(0, 50);
  }

  // 截图统一落在下载目录下的这个根文件夹里，再按视频分子文件夹
  var CAPTURE_ROOT = 'BiliLearn-AI截图';
  var MAX_CAPTURES = 60;

  // 老版本截图没有 id：用「时间戳 + BV + 时间点」生成稳定 id，
  // 否则每次渲染都会变，删除/下载就找不到对应记录了。
  function captureId(item) {
    if (!item.id) {
      item.id = 'c' + String(item.timestamp || 0)
        + '_' + String(item.bvid || '').replace(/[^0-9a-zA-Z]/g, '')
        + '_' + String(item.time || '').replace(/[^0-9a-zA-Z]/g, '');
    }
    return item.id;
  }

  // 同一个 BV + 同一个分 P 视为同一个视频
  function captureGroupKey(item) {
    if (item.bvid) return item.bvid + '#P' + (item.page || 1);
    return 'title:' + String(item.title || 'video');
  }

  // 每个视频一个子文件夹：<视频标题>_P<分P>
  function captureFolder(item) {
    var name = sanitizeFilename(item.title || item.bvid || 'video');
    var page = parseInt(item.page, 10) || 1;
    if (page > 1) name += '_P' + page;
    return name;
  }

  function captureDownloadPath(item) {
    return CAPTURE_ROOT + '/' + captureFolder(item) + '/' + sanitizeFilename(item.time || 'frame') + '.png';
  }

  async function captureScreenshot() {
    if (!state.tab || state.tab.id == null) {
      // Edge 侧边栏下初次可能没识别到标签页，截图前再兜底找一次
      var again = await getCurrentTab();
      if (again) {
        state.tab = again;
        if (!state.videoInfo) await loadVideoInfo();
      }
    }
    if (!state.tab || state.tab.id == null) {
      showToast('未检测到 B 站视频标签页：请切到视频页后重试');
      return;
    }
    els.captureBtn.style.opacity = '0.5';
    try {
      var resp = await sendContent(state.tab.id, { type: 'captureVideo' });
      if (resp.ok && resp.data) {
        var time = formatTime(resp.currentTime || 0);
        var item = {
          id: '',
          filename: '',
          dataUrl: resp.data,
          title: state.videoInfo ? state.videoInfo.title : 'video',
          time: time,
          bvid: state.videoInfo ? state.videoInfo.bvid : '',
          page: state.videoInfo ? state.videoInfo.page : 1,
          timestamp: Date.now()
        };
        captureId(item);
        item.filename = captureDownloadPath(item);
        var downloadResp = await sendBg({ type: 'downloadImage', dataUrl: resp.data, filename: item.filename });
        if (downloadResp.ok) {
          await saveCaptureHistory(item);
          showToast('📷 截图已保存：' + item.filename);
        } else {
          showToast('下载失败：' + (downloadResp.error || '未知错误'));
        }
      } else {
        showToast('截图失败：' + (resp.error || '未知错误'));
      }
    } catch (e) {
      showToast('截图失败：' + e.message);
    }
    els.captureBtn.style.opacity = '1';
  }

  function loadCaptureHistory() {
    return new Promise(function (resolve) {
      chrome.storage.local.get({ captureHistory: [] }, function (result) {
        resolve(result.captureHistory || []);
      });
    });
  }

  function writeCaptureHistory(list) {
    return new Promise(function (resolve, reject) {
      chrome.storage.local.set({ captureHistory: list }, function () {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve();
      });
    });
  }

  async function saveCaptureHistory(item) {
    try {
      var list = await loadCaptureHistory();
      list.unshift(item);
      if (list.length > MAX_CAPTURES) list = list.slice(0, MAX_CAPTURES);
      await writeCaptureHistory(list);
      renderCaptureHistory();
    } catch (e) {
      showToast('截图已下载，但截图历史保存失败：' + (e.message || e));
    }
  }

  // 兼容旧数据：老版本没有 id / 没有下载路径
  function ensureCaptureFields(item) {
    captureId(item);
    if (!item.filename) item.filename = captureDownloadPath(item);
    if (!item.time) item.time = '00-00-00';
    return item;
  }

  async function deleteCapture(id) {
    var list = await loadCaptureHistory();
    list = list.filter(function (x) { return ensureCaptureFields(x).id !== id; });
    await writeCaptureHistory(list);
    renderCaptureHistory();
  }

  async function clearCaptureGroup(groupKey) {
    var list = await loadCaptureHistory();
    list = list.filter(function (x) { return captureGroupKey(ensureCaptureFields(x)) !== groupKey; });
    await writeCaptureHistory(list);
    renderCaptureHistory();
  }

  async function clearCaptures() {
    await writeCaptureHistory([]);
    renderCaptureHistory();
  }

  function captureItemHtml(item) {
    ensureCaptureFields(item);
    return '<div class="capture-item" data-id="' + escapeHtml(item.id) + '">' +
      '<img src="' + item.dataUrl + '" alt="' + escapeHtml(item.time || '') + '">' +
      '<div class="capture-item-actions">' +
        '<button class="capture-action-btn" data-action="view" title="查看大图">🔍</button>' +
        '<button class="capture-action-btn" data-action="download" title="重新下载">⬇️</button>' +
        '<button class="capture-action-btn" data-action="delete" title="删除">🗑️</button>' +
      '</div>' +
      '<div class="capture-item-info">' +
        '<div class="capture-item-time">' + escapeHtml(item.time || '') + ' · ' + new Date(item.timestamp).toLocaleString() + '</div>' +
      '</div>' +
    '</div>';
  }

  async function renderCaptureHistory() {
    var list = await loadCaptureHistory();
    els.captureCount.textContent = list.length + ' 张';
    if (list.length === 0) {
      els.captureEmpty.style.display = 'block';
      els.captureGrid.style.display = 'none';
      els.captureGrid.innerHTML = '';
      return;
    }
    els.captureEmpty.style.display = 'none';
    els.captureGrid.style.display = 'block';
    // 按视频分组（保持最近截图所在视频排在最前）
    var groups = [];
    var index = {};
    list.forEach(function (item) {
      ensureCaptureFields(item);
      var key = captureGroupKey(item);
      if (!index[key]) {
        index[key] = {
          key: key,
          title: item.title || item.bvid || '未知视频',
          bvid: item.bvid || '',
          page: item.page || 1,
          items: []
        };
        groups.push(index[key]);
      }
      index[key].items.push(item);
    });
    els.captureGrid.innerHTML = groups.map(function (g) {
      var meta = [];
      if (g.bvid) meta.push(g.bvid);
      meta.push('P' + g.page);
      meta.push(g.items.length + ' 张');
      var head = '<div class="capture-group-head">' +
        '<div class="capture-group-title" title="' + escapeHtml(g.title) + '">' + escapeHtml(g.title) + '</div>' +
        '<div class="capture-group-meta"><span>' + escapeHtml(meta.join(' · ')) + '</span>' +
        '<button class="capture-group-clear" data-group="' + escapeHtml(g.key) + '" title="清空该视频的截图">清空本视频</button></div>' +
        '</div>';
      return '<div class="capture-group">' + head +
        '<div class="capture-group-grid">' + g.items.map(captureItemHtml).join('') + '</div></div>';
    }).join('');
  }

  function viewCaptureLarge(dataUrl, filename) {
    var viewer = document.createElement('div');
    viewer.className = 'capture-viewer';
    viewer.innerHTML = '<button class="capture-viewer-close">✕</button><img src="' + dataUrl + '" alt="' + escapeHtml(filename) + '">';
    viewer.addEventListener('click', function (e) {
      if (e.target === viewer || e.target.classList.contains('capture-viewer-close')) {
        document.body.removeChild(viewer);
      }
    });
    document.body.appendChild(viewer);
  }

  async function openCollectionDetail(collId, skipPush) {
    els.collDetailContainer.style.display = 'block';
    els.collListContainer.style.display = 'none';
    els.collEpisodeList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-3)"><div class="spinner"></div></div>';
    if (!skipPush) pushNav();
    setView('coll-detail');
    try {
      var resp = await sendBg({ type: 'getCollectionDetail', collId: collId });
      if (resp.ok && resp.data) {
        state.currentCollection = resp.data;
        renderCollectionDetail(resp.data);
      } else {
        if (!skipPush) state.navStack.pop();
        els.collEpisodeList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-3)">加载失败</div>';
      }
    } catch (e) {
      if (!skipPush) state.navStack.pop();
      els.collEpisodeList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-3)">加载失败：' + escapeHtml(e.message) + '</div>';
    }
  }

  function renderCollectionDetail(coll) {
    var total = coll.total || 0;
    var done = coll.done_count || 0;
    var pct = total > 0 ? Math.round(done / total * 100) : 0;
    els.collDetailTitle.textContent = coll.title || '未命名合集';
    els.collDetailMeta.innerHTML = '<span>' + done + '/' + total + ' 集</span><span>' + pct + '%</span><span>' + (coll.status === 'done' ? '已完成' : coll.status === 'processing' ? '进行中' : '部分完成') + '</span>';
    els.collDetailProgress.innerHTML = '<div class="coll-detail-progress-fill" style="width:' + pct + '%"></div>';

    var results = coll.results || [];
    if (results.length === 0) {
      els.collEpisodeList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-3)">暂无视频数据</div>';
      return;
    }
    var html = '';
    results.forEach(function (r, i) {
      var statusText = r.status === 'done' ? '✓ 已完成' : r.status === 'failed' ? '✗ 失败' : '待处理';
      var statusClass = r.status === 'done' ? 'done' : r.status === 'failed' ? 'failed' : 'pending';
      var clickable = r.status === 'done' && r.note_id ? '' : 'disabled';
      html += '<div class="coll-episode-item ' + clickable + '" data-note-id="' + (r.note_id || '') + '" data-page="' + (r.page || '') + '">';
      html += '<span class="coll-episode-num">P' + (r.page || (i + 1)) + '</span>';
      html += '<div class="coll-episode-info"><div class="coll-episode-title">' + escapeHtml(r.title || ('第' + (i + 1) + '集')) + '</div>';
      html += '<div class="coll-episode-status ' + statusClass + '">' + statusText + '</div></div>';
      if (r.status === 'done' && r.note_id) html += '<span class="coll-episode-arrow">›</span>';
      html += '</div>';
    });
    els.collEpisodeList.innerHTML = html;
    els.collEpisodeList.querySelectorAll('.coll-episode-item:not(.disabled)').forEach(function (item) {
      item.addEventListener('click', function () {
        var noteId = parseInt(item.dataset.noteId, 10);
        var page = parseInt(item.dataset.page, 10);
        if (noteId) {
          if (state.currentCollection && state.currentCollection.bvid && page) {
            var url = 'https://www.bilibili.com/video/' + state.currentCollection.bvid + '/?p=' + page;
            chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
              if (tabs[0]) chrome.tabs.update(tabs[0].id, { url: url });
            });
          }
          openNoteById(noteId);
        }
      });
    });
  }

  async function generateQuiz() {
    if (!state.note || !state.note.id) {
      els.quizEmpty.style.display = 'block';
      els.quizEmpty.querySelector('.empty-desc').textContent = '请先在「笔记」标签中打开一篇笔记';
      return;
    }
    els.generateQuizBtn.disabled = true;
    els.generateQuizBtn.innerHTML = '<span>⏳ 生成中...</span>';
    els.quizEmpty.style.display = 'none';
    els.quizLoading.style.display = 'block';
    try {
      var resp = await sendBg({ type: 'generateQuiz', noteId: state.note.id });
      if (resp.ok && resp.data) {
        if (state.noteDetail) state.noteDetail.quizzes = resp.data;
        renderQuiz();
      } else {
        els.quizLoading.style.display = 'none';
        els.quizEmpty.style.display = 'block';
        els.quizEmpty.querySelector('.empty-desc').textContent = resp.error || '生成失败，请稍后重试';
      }
    } catch (e) {
      els.quizLoading.style.display = 'none';
      els.quizEmpty.style.display = 'block';
      els.quizEmpty.querySelector('.empty-desc').textContent = '生成失败：' + e.message;
    }
    els.generateQuizBtn.disabled = false;
    els.generateQuizBtn.innerHTML = '<span>🎯 生成自测题</span>';
  }

  function switchTab(tabName) {
    state.activeTab = tabName;
    state.navStack = [];
    state.currentCollection = null;
    els.tabs.forEach(function (t) { t.classList.toggle('active', t.dataset.tab === tabName); });
    els.tabPanes.forEach(function (p) { p.classList.toggle('active', p.id === 'tab-' + tabName); });
    els.backBtn.style.display = 'none';
    if (tabName === 'collection') {
      setView('coll-list');
      loadCollections();
    }
    if (tabName === 'note') {
      setView('note-list');
      // 每次进入笔记页都重新识别当前标签页，站内换集后不会再显示上一集的笔记
      syncToTab(true);
    }
    if (tabName === 'chat') {
      if (!state.note) {
        els.chatMessages.innerHTML = '<div class="chat-empty"><div class="ce-icon">💬</div><p>请先打开一篇笔记</p><p class="ce-desc">在「笔记」标签中打开笔记后，即可基于笔记内容提问</p></div>';
      }
    }
    if (tabName === 'quiz') {
      if (!state.note) {
        els.quizEmpty.style.display = 'block';
        els.quizList.style.display = 'none';
        els.quizLoading.style.display = 'none';
        els.quizEmpty.querySelector('.empty-desc').textContent = '请先在「笔记」标签中打开一篇笔记';
        els.generateQuizBtn.style.display = 'none';
      } else {
        els.generateQuizBtn.style.display = '';
        renderQuiz();
      }
    }
    if (tabName === 'capture') {
      renderCaptureHistory();
    }
  }

  function initEvents() {
    els.backBtn.addEventListener('click', goBack);
    els.refreshBtn.addEventListener('click', refreshCurrent);
    els.captureBtn.addEventListener('click', captureScreenshot);
    els.clearCaptureBtn.addEventListener('click', function () {
      if (confirm('确定清空所有截图历史？已下载到本地的图片不会被删除。')) clearCaptures();
    });
    els.captureGrid.addEventListener('click', async function (e) {
      var groupBtn = e.target.closest('.capture-group-clear');
      if (groupBtn) {
        if (confirm('确定清空该视频的截图记录？已下载到本地的图片不会被删除。')) {
          clearCaptureGroup(groupBtn.dataset.group);
        }
        return;
      }
      var itemEl = e.target.closest('.capture-item');
      if (!itemEl) return;
      var id = itemEl.dataset.id;
      var list = await loadCaptureHistory();
      var cap = null;
      for (var i = 0; i < list.length; i++) {
        if (ensureCaptureFields(list[i]).id === id) { cap = list[i]; break; }
      }
      if (!cap) return;
      var action = e.target.closest('.capture-action-btn');
      var act = action ? action.dataset.action : 'view';
      if (act === 'view') viewCaptureLarge(cap.dataUrl, cap.filename);
      else if (act === 'download') sendBg({ type: 'downloadImage', dataUrl: cap.dataUrl, filename: cap.filename });
      else if (act === 'delete') deleteCapture(id);
    });

    if (els.learningStatusSelectEl) {
      els.learningStatusSelectEl.addEventListener('change', async function () {
        if (!state.note || !state.note.id) return;
        var status = els.learningStatusSelectEl.value;
        try {
          var resp = await sendBg({ type: 'updateLearningStatus', noteId: state.note.id, status: status });
          if (resp.ok) {
            if (state.note) state.note.learning_status = status;
            if (state.noteDetail) state.noteDetail.learning_status = status;
            showToast('已标记为「' + (status === 'completed' ? '已学完' : status === 'learning' ? '学习中' : '未学') + '」');
          } else {
            showToast('更新失败：' + (resp.error || '未知错误'));
          }
        } catch (e) {
          showToast('更新失败：' + e.message);
        }
      });
    }

    els.themeToggle.addEventListener('click', function () {
      state.settings.theme = state.settings.theme === 'dark' ? 'light' : 'dark';
      applySettings(); saveSettings();
    });

    els.paletteDots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        state.settings.palette = dot.dataset.palette;
        applySettings(); saveSettings();
      });
    });

    els.openFullBtn.addEventListener('click', function () {
      if (state.note && state.note.id) {
        chrome.tabs.create({ url: state.settings.backendUrl + '/#/note/' + state.note.id, active: true });
      }
    });

    els.settingsBtn.addEventListener('click', function () { els.settingsOverlay.style.display = 'flex'; });
    els.settingsClose.addEventListener('click', function () { els.settingsOverlay.style.display = 'none'; });
    els.settingsOverlay.addEventListener('click', function (e) {
      if (e.target === els.settingsOverlay) els.settingsOverlay.style.display = 'none';
    });

    els.tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { switchTab(tab.dataset.tab); });
    });

    els.errorRetry.addEventListener('click', init);
    els.generateBtn.addEventListener('click', generateNote);
    els.regenBtn.addEventListener('click', function () { if (confirm('确定要重新生成笔记吗？')) generateNote(); });
    els.generateQuizBtn.addEventListener('click', generateQuiz);

    els.chatSend.addEventListener('click', sendChat);
    els.chatInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });

    els.fontDec.addEventListener('click', function () {
      if (state.settings.fontSize > 12) { state.settings.fontSize -= 1; applySettings(); saveSettings(); }
    });
    els.fontInc.addEventListener('click', function () {
      if (state.settings.fontSize < 20) { state.settings.fontSize += 1; applySettings(); saveSettings(); }
    });
    els.expandChapters.addEventListener('change', function () {
      state.settings.expandChapters = els.expandChapters.checked;
      saveSettings();
      if (state.noteDetail) renderNote();
    });
    els.saveSettings.addEventListener('click', function () {
      state.settings.backendUrl = els.backendUrl.value.replace(/\/$/, '');
      saveSettings(); checkBackend();
      els.settingsOverlay.style.display = 'none';
    });
  }

  async function init() {
    initEls();
    loadSettings();
    initEvents();
    await checkBackend();
    var hasVideo = await loadVideoInfo();
    if (state.tab && state.tab.url) state.lastTabUrl = state.tab.url;
    if (hasVideo) { await checkNote(); } else { showNoteState('none'); }
    startFollowingTab();
  }

  document.addEventListener('DOMContentLoaded', init);
  window.addEventListener('unload', function () {
    stopPolling();
    if (state.followTimer) clearInterval(state.followTimer);
  });
})();
