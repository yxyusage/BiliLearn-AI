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
    settings: {
      fontSize: 14,
      theme: 'light',
      expandChapters: false,
      backendUrl: 'http://127.0.0.1:8000'
    }
  };

  var els = {};

  function $(id) { return document.getElementById(id); }

  function initEls() {
    els.videoInfo = $('videoInfo');
    els.refreshBtn = $('refreshBtn');
    els.closeBtn = $('closeBtn');
    els.tabs = document.querySelectorAll('.tab');
    els.tabPanes = document.querySelectorAll('.tab-pane');
    els.noteLoading = $('noteLoading');
    els.noteError = $('noteError');
    els.errorTitle = $('errorTitle');
    els.errorDesc = $('errorDesc');
    els.errorRetry = $('errorRetry');
    els.noNote = $('noNote');
    els.generateBtn = $('generateBtn');
    els.generating = $('generating');
    els.genProgress = $('genProgress');
    els.noteContent = $('noteContent');
    els.regenBtn = $('regenBtn');
    els.openFullBtn = $('openFullBtn');
    els.noteSummary = $('noteSummary');
    els.chapterList = $('chapterList');
    els.collLoading = $('collLoading');
    els.collectionList = $('collectionList');
    els.collEmpty = $('collEmpty');
    els.fontDec = $('fontDec');
    els.fontInc = $('fontInc');
    els.fontValue = $('fontValue');
    els.themeBtns = document.querySelectorAll('.theme-btn');
    els.expandChapters = $('expandChapters');
    els.backendUrl = $('backendUrl');
    els.backendStatus = $('backendStatus');
    els.saveSettings = $('saveSettings');
  }

  function loadSettings() {
    try {
      var saved = chrome.storage.local.get(['bililearn_settings'], function (result) {
        if (result.bililearn_settings) {
          state.settings = Object.assign(state.settings, result.bililearn_settings);
        }
        applySettings();
      });
    } catch (e) {
      applySettings();
    }
  }

  function saveSettings() {
    try {
      chrome.storage.local.set({ bililearn_settings: state.settings });
    } catch (e) {}
  }

  function applySettings() {
    document.documentElement.style.setProperty('--font-size', state.settings.fontSize + 'px');
    els.fontValue.textContent = state.settings.fontSize + 'px';
    document.documentElement.setAttribute('data-theme', state.settings.theme);
    els.themeBtns.forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.theme === state.settings.theme);
    });
    els.expandChapters.checked = state.settings.expandChapters;
    els.backendUrl.value = state.settings.backendUrl;
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

  async function loadVideoInfo() {
    var tab = await getCurrentTab();
    state.tab = tab;
    if (!tab || !tab.url) {
      els.videoInfo.innerHTML = '<div class="vi-loading">请在 B 站视频页面使用</div>';
      return false;
    }
    var isBilibili = /bilibili\.com\/video\//.test(tab.url);
    if (!isBilibili) {
      els.videoInfo.innerHTML = '<div class="vi-loading">请在 B 站视频页面使用</div>';
      return false;
    }
    var resp = await sendContent(tab.id, { type: 'getVideoInfo' });
    if (!resp.ok || !resp.data || !resp.data.bvid) {
      els.videoInfo.innerHTML = '<div class="vi-loading">无法获取视频信息，请刷新页面后重试</div>';
      return false;
    }
    state.videoInfo = resp.data;
    els.videoInfo.innerHTML =
      '<div class="vi-title">' + escapeHtml(resp.data.title || '未知标题') + '</div>' +
      '<div class="vi-meta"><span class="vi-bvid">' + escapeHtml(resp.data.bvid) + '</span>' +
      '<span>P' + (resp.data.page || 1) + '</span></div>';
    return true;
  }

  async function checkNote() {
    if (!state.videoInfo || !state.videoInfo.bvid) return;
    showNoteState('loading');
    var resp = await sendBg({ type: 'getNoteByBvid', bvid: state.videoInfo.bvid, page: state.videoInfo.page });
    if (resp.ok && resp.data) {
      state.note = resp.data;
      if (resp.data.status === 'done') {
        await loadNoteDetail(resp.data.id);
        renderNote();
      } else if (resp.data.status === 'processing') {
        showNoteState('generating');
        startPolling(resp.data.id);
      } else {
        showNoteState('none');
      }
    } else {
      state.note = null;
      showNoteState('none');
    }
  }

  async function loadNoteDetail(noteId) {
    var resp = await sendBg({ type: 'getNoteDetail', noteId: noteId });
    if (resp.ok && resp.data) {
      state.noteDetail = resp.data;
    }
  }

  function renderNote() {
    showNoteState('content');
    var detail = state.noteDetail || state.note;
    var noteData = detail.note || {};

    var summary = noteData.summary || detail.summary || '';
    els.noteSummary.textContent = summary || '暂无摘要';

    var chapters = noteData.chapters || [];
    var html = '';
    if (chapters.length === 0) {
      html = '<div style="text-align:center;color:var(--text-muted);padding:20px;font-size:12px">暂无章节内容</div>';
    } else {
      chapters.forEach(function (ch, i) {
        var time = parseTimestamp(ch.time_stamp);
        var expanded = state.settings.expandChapters ? 'expanded' : '';
        html += '<div class="chapter-card ' + expanded + '" data-index="' + i + '">';
        html += '<div class="chapter-header">';
        html += '<span class="chapter-no">' + (i + 1) + '</span>';
        html += '<span class="chapter-title">' + escapeHtml(ch.title || '未命名章节') + '</span>';
        if (time !== null) {
          html += '<span class="chapter-time" data-time="' + time + '">' + escapeHtml(String(ch.time_stamp)) + '</span>';
        }
        html += '<span class="chapter-toggle">▶</span>';
        html += '</div>';
        html += '<div class="chapter-body">';
        html += renderSections(ch.sections || []);
        html += '</div></div>';
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
        if (!isNaN(time) && state.tab) {
          sendContent(state.tab.id, { type: 'seekTo', seconds: time });
        }
      });
    });

    renderMathInElement(els.chapterList);
  }

  function renderMathInElement(el) {
    if (typeof katex === 'undefined') return;
    el.querySelectorAll('.formula-display').forEach(function (node) {
      try {
        katex.render(node.dataset.latex || '', node, {
          displayMode: true,
          throwOnError: false,
          output: 'html'
        });
      } catch (e) {
        node.textContent = node.dataset.latex || '';
      }
    });
    el.querySelectorAll('.formula-inline').forEach(function (node) {
      try {
        katex.render(node.dataset.latex || '', node, {
          displayMode: false,
          throwOnError: false,
          output: 'html'
        });
      } catch (e) {
        node.textContent = '$' + (node.dataset.latex || '') + '$';
      }
    });
  }

  function renderSections(sections) {
    var html = '';
    sections.forEach(function (sec) {
      if (sec.heading) {
        html += '<div class="section-heading">' + escapeHtml(sec.heading) + '</div>';
      }
      var blocks = sec.blocks || [];
      blocks.forEach(function (block) {
        switch (block.type) {
          case 'text':
            html += '<div class="section-text">' + renderInline(block.content || '') + '</div>';
            break;
          case 'formula':
            var fcontent = (block.content || '').trim().replace(/^\$+/, '').replace(/\$+$/, '');
            html += '<div class="section-formula"><span class="formula-display" data-latex="' + escapeHtml(fcontent) + '"></span></div>';
            break;
          case 'code':
            html += '<pre class="section-code"><code>' + escapeHtml(block.content || '') + '</code></pre>';
            break;
          case 'list':
            var tag = block.ordered ? 'ol' : 'ul';
            html += '<' + tag + ' class="section-list">';
            (block.items || []).forEach(function (item) {
              html += '<li>' + renderInline(item) + '</li>';
            });
            html += '</' + tag + '>';
            break;
          case 'steps':
            html += '<div class="section-steps">';
            (block.items || []).forEach(function (step) {
              html += '<div class="step-item">' + renderInline(step) + '</div>';
            });
            html += '</div>';
            break;
          case 'table':
            html += renderTable(block);
            break;
          case 'quote':
            html += '<div class="section-quote">' + renderInline(block.content || '') + '</div>';
            break;
          case 'heading':
            html += '<div class="section-heading">' + escapeHtml(block.content || '') + '</div>';
            break;
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
    return escaped;
  }

  function renderTable(block) {
    var headers = block.headers || [];
    var rows = block.rows || [];
    var html = '<div style="overflow-x:auto"><table class="section-table"><thead><tr>';
    headers.forEach(function (h) {
      html += '<th>' + escapeHtml(h) + '</th>';
    });
    html += '</tr></thead><tbody>';
    rows.forEach(function (row) {
      html += '<tr>';
      row.forEach(function (cell) {
        html += '<td>' + escapeHtml(cell) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    return html;
  }

  async function generateNote() {
    if (!state.videoInfo) return;
    els.generateBtn.disabled = true;
    els.generateBtn.innerHTML = '<span>⏳ 提交中...</span>';
    try {
      var resp = await sendBg({
        type: 'generateNote',
        bvid: state.videoInfo.bvid,
        page: state.videoInfo.page,
        title: state.videoInfo.title
      });
      if (resp.ok && resp.data) {
        state.note = resp.data;
        showNoteState('generating');
        startPolling(resp.data.id);
      } else {
        throw new Error(resp.error || '生成失败');
      }
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
            state.polling = false;
            clearInterval(progTimer);
            els.genProgress.style.width = '100%';
            setTimeout(function () { renderNote(); }, 300);
            return;
          } else if (resp.data.status === 'failed') {
            state.polling = false;
            clearInterval(progTimer);
            showNoteState('none');
            els.generateBtn.disabled = false;
            els.generateBtn.innerHTML = '<span>⚡ 重新生成</span>';
            return;
          }
        }
        state.pollTimer = setTimeout(poll, 3000);
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

  async function loadCollections() {
    els.collLoading.style.display = 'block';
    els.collectionList.style.display = 'none';
    els.collEmpty.style.display = 'none';
    try {
      var resp = await sendBg({ type: 'getCollections' });
      if (resp.ok && resp.data && Array.isArray(resp.data)) {
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
    if (collections.length === 0) {
      els.collEmpty.style.display = 'block';
      return;
    }
    var html = '';
    collections.forEach(function (coll) {
      var total = coll.total || 0;
      var done = coll.done_count || 0;
      var pct = total > 0 ? Math.round(done / total * 100) : 0;
      html += '<div class="collection-item" data-id="' + coll.id + '">';
      html += '<div class="coll-title">' + escapeHtml(coll.title || '未命名合集') + '</div>';
      html += '<div class="coll-meta"><span>' + done + '/' + total + ' 集</span><span>' + pct + '%</span></div>';
      html += '<div class="coll-progress"><div class="coll-progress-fill" style="width:' + pct + '%"></div></div>';
      html += '</div>';
    });
    els.collectionList.innerHTML = html;
    els.collectionList.style.display = 'block';
  }

  function switchTab(tabName) {
    els.tabs.forEach(function (t) {
      t.classList.toggle('active', t.dataset.tab === tabName);
    });
    els.tabPanes.forEach(function (p) {
      p.classList.toggle('active', p.id === 'tab-' + tabName);
    });
    if (tabName === 'collection') {
      loadCollections();
    }
  }

  function initEvents() {
    els.refreshBtn.addEventListener('click', function () {
      stopPolling();
      init();
    });

    els.closeBtn.addEventListener('click', function () {
      window.close();
    });

    els.tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        switchTab(tab.dataset.tab);
      });
    });

    els.errorRetry.addEventListener('click', function () {
      init();
    });

    els.generateBtn.addEventListener('click', generateNote);

    els.regenBtn.addEventListener('click', function () {
      if (confirm('确定要重新生成笔记吗？')) {
        generateNote();
      }
    });

    els.openFullBtn.addEventListener('click', function () {
      if (state.note && state.note.id) {
        chrome.tabs.create({ url: state.settings.backendUrl + '/#/note/' + state.note.id });
      }
    });

    els.fontDec.addEventListener('click', function () {
      if (state.settings.fontSize > 12) {
        state.settings.fontSize -= 1;
        applySettings();
        saveSettings();
      }
    });

    els.fontInc.addEventListener('click', function () {
      if (state.settings.fontSize < 20) {
        state.settings.fontSize += 1;
        applySettings();
        saveSettings();
      }
    });

    els.themeBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.settings.theme = btn.dataset.theme;
        applySettings();
        saveSettings();
      });
    });

    els.expandChapters.addEventListener('change', function () {
      state.settings.expandChapters = els.expandChapters.checked;
      saveSettings();
      if (state.noteDetail) {
        renderNote();
      }
    });

    els.saveSettings.addEventListener('click', function () {
      state.settings.backendUrl = els.backendUrl.value.replace(/\/$/, '');
      saveSettings();
      checkBackend();
      alert('设置已保存');
    });
  }

  async function init() {
    initEls();
    loadSettings();
    initEvents();
    await checkBackend();
    var hasVideo = await loadVideoInfo();
    if (hasVideo) {
      await checkNote();
    } else {
      showNoteState('none');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  window.addEventListener('unload', stopPolling);
})();
