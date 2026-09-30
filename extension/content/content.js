(function () {
  'use strict';

  function getBvid() {
    var match = window.location.href.match(/\/video\/(BV[a-zA-Z0-9]+)/);
    if (match) return match[1];
    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.bvid) {
      return window.__INITIAL_STATE__.bvid;
    }
    return null;
  }

  function getPage() {
    var urlMatch = window.location.href.match(/[?&]p=(\d+)/);
    if (urlMatch) return parseInt(urlMatch[1], 10);
    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.p) {
      return parseInt(window.__INITIAL_STATE__.p, 10);
    }
    return 1;
  }

  function getVideoTitle() {
    var titleEl = document.querySelector('h1.video-title, .video-title, h1[title]');
    if (titleEl) {
      return titleEl.getAttribute('title') || titleEl.textContent.trim();
    }
    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.videoData) {
      return window.__INITIAL_STATE__.videoData.title;
    }
    return document.title.replace(/_哔哩哔哩.*$/, '').trim();
  }

  function getVideoElement() {
    return document.querySelector('video');
  }

  function seekTo(seconds) {
    var video = getVideoElement();
    if (!video) return false;
    try {
      video.currentTime = seconds;
      if (video.paused) video.play().catch(function () {});
      return true;
    } catch (e) {
      return false;
    }
  }

  function getCurrentTime() {
    var video = getVideoElement();
    return video ? video.currentTime : 0;
  }

  var lastTime = 0;
  var timeListeners = [];

  function onTimeUpdate() {
    var video = getVideoElement();
    if (!video) return;
    var t = Math.floor(video.currentTime);
    if (t !== lastTime) {
      lastTime = t;
      timeListeners.forEach(function (fn) {
        try { fn(t); } catch (e) {}
      });
    }
  }

  function startWatching() {
    var video = getVideoElement();
    if (video) {
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.addEventListener('timeupdate', onTimeUpdate);
    }
  }

  var observer = null;
  function ensureVideoWatched() {
    startWatching();
    if (observer) return;
    observer = new MutationObserver(function () {
      var video = getVideoElement();
      if (video && !video._bililearnWatched) {
        video._bililearnWatched = true;
        startWatching();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    switch (msg.type) {
      case 'getVideoInfo':
        sendResponse({
          ok: true,
          data: {
            bvid: getBvid(),
            page: getPage(),
            title: getVideoTitle(),
            url: window.location.href,
            currentTime: getCurrentTime()
          }
        });
        break;
      case 'seekTo':
        var success = seekTo(msg.seconds);
        sendResponse({ ok: success });
        break;
      case 'getCurrentTime':
        sendResponse({ ok: true, data: getCurrentTime() });
        break;
      default:
        sendResponse({ ok: false, error: '未知消息类型' });
    }
    return true;
  });

  ensureVideoWatched();
})();
