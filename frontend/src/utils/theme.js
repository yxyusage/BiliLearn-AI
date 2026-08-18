import { reactive } from 'vue'

export const theme = reactive({
  dark: localStorage.getItem('bililearn-theme') === 'dark'
})

export function applyTheme() {
  document.documentElement.classList.toggle('dark', theme.dark)
  localStorage.setItem('bililearn-theme', theme.dark ? 'dark' : 'light')
}

function getCenter(event) {
  if (event && event.clientX) return { x: event.clientX, y: event.clientY }
  var btn = document.querySelector('.theme-btn')
  if (btn) {
    var r = btn.getBoundingClientRect()
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
  }
  return { x: window.innerWidth / 2, y: 48 }
}

export function toggleTheme(event) {
  var doc = document.documentElement
  var c = getCenter(event)
  doc.style.setProperty('--theme-x', c.x + 'px')
  doc.style.setProperty('--theme-y', c.y + 'px')
  var targetDark = !theme.dark

  // 优先使用 View Transitions API（Chrome/Edge），从按钮位置圆形展开
  if (document.startViewTransition) {
    document.startViewTransition(function () {
      theme.dark = targetDark
      applyTheme()
    })
    return
  }

  // 回退：圆形遮罩扩散
  var overlay = document.createElement('div')
  overlay.style.cssText =
    'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:99999;pointer-events:none;' +
    'background:' + (targetDark ? '#0f1114' : '#f2f4f8') + ';' +
    'clip-path:circle(0px at ' + c.x + 'px ' + c.y + 'px);transition:clip-path .45s ease;'
  document.body.appendChild(overlay)
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      overlay.style.clipPath = 'circle(150% at ' + c.x + 'px ' + c.y + 'px)'
    })
  })
  setTimeout(function () {
    theme.dark = targetDark
    applyTheme()
    setTimeout(function () {
      overlay.style.transition = 'clip-path .45s ease, opacity .3s ease'
      overlay.style.opacity = '0'
      setTimeout(function () { overlay.remove() }, 320)
    }, 60)
  }, 230)
}
