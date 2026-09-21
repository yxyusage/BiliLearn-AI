/* BiliLearn-AI Service Worker：静态资源缓存优先，API 走网络优先。 */
const VERSION = 'bililearn-v1.6.0'
const STATIC_ASSETS = ['./', './index.html', './manifest.webmanifest', './icon.svg', './icon-maskable.svg']

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(VERSION).then(function (cache) {
      return cache.addAll(STATIC_ASSETS)
    }).then(function () {
      return self.skipWaiting()
    })
  )
})

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION }).map(function (k) { return caches.delete(k) }))
    }).then(function () {
      return self.clients.claim()
    })
  )
})

self.addEventListener('fetch', function (event) {
  var req = event.request
  if (req.method !== 'GET') return
  var url = new URL(req.url)

  // 接口请求：网络优先，失败回退缓存（离线复习错题可用）
  if (url.pathname.indexOf('/api/') === 0) {
    event.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone()
        caches.open(VERSION).then(function (cache) { cache.put(req, copy) })
        return res
      }).catch(function () {
        return caches.match(req)
      })
    )
    return
  }

  // 静态资源（含 /assets/*）：缓存优先 + 后台更新
  event.respondWith(
    caches.match(req).then(function (cached) {
      if (cached) {
        fetch(req).then(function (res) {
          if (res && res.ok) {
            caches.open(VERSION).then(function (cache) { cache.put(req, res) })
          }
        }).catch(function () { /* 离线时忽略 */ })
        return cached
      }
      return fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone()
          caches.open(VERSION).then(function (cache) { cache.put(req, copy) })
        }
        return res
      })
    })
  )
})
