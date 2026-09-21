import { reactive } from 'vue'

const THEME_KEY = 'bililearn-theme'
const PALETTE_KEY = 'bililearn-palette'

export const PALETTES = {
  // 纸墨青：墨青主色 + 暖纸白，学术书卷气（默认）
  paper: {
    name: '纸墨青',
    light: {
      '--el-color-primary': '#0d7e70', '--el-color-primary-light-3': '#56a59b', '--el-color-primary-light-5': '#86bfb8',
      '--el-color-primary-light-7': '#b6d8d3', '--el-color-primary-light-8': '#cee2e2', '--el-color-primary-light-9': '#e6f2f0',
      '--el-color-primary-dark-2': '#0a655a', '--el-color-success': '#2f8f5b', '--el-color-warning': '#b45309', '--el-color-danger': '#c2413d',
      '--c-primary': '#0d7e70', '--c-primary-hover': '#0f8c7d', '--c-primary-active': '#0b665b', '--c-primary-soft': '#e6f4f1', '--c-primary-border': '#b7ded7',
      '--c-accent': '#b45309', '--c-accent-soft': '#fbf3e2', '--c-accent-border': '#eed9b4',
      '--c-danger': '#c2413d', '--c-danger-soft': '#f9eceb', '--c-success': '#2f8f5b', '--c-success-soft': '#e7f4ec',
      '--c-bg': '#f6f5f1', '--c-bg-elev': '#ffffff', '--c-bg-soft': '#f1f0eb', '--c-border': '#e4e2da', '--c-border-light': '#edebe4',
      '--c-text': '#1e272b', '--c-text-2': '#556066', '--c-text-3': '#8a9296',
      '--c-code-bg': '#16202a', '--c-code-text': '#dce6ec',
      '--c-shadow-card': '0 1px 2px rgba(23, 32, 38, .05)', '--c-shadow-hover': '0 10px 28px rgba(23, 32, 38, .09)',
      '--c-badge-definition': '#1d4ed8', '--c-badge-definition-soft': '#e8effd', '--c-badge-definition-border': '#c6d8f8',
      '--c-badge-concept': '#0d7e70', '--c-badge-concept-soft': '#e6f4f1', '--c-badge-concept-border': '#b7ded7',
      '--c-badge-derivation': '#6d28d9', '--c-badge-derivation-soft': '#f1ebfd', '--c-badge-derivation-border': '#d8c8f6',
      '--c-badge-example': '#b45309', '--c-badge-example-soft': '#fbf3e2', '--c-badge-example-border': '#eed9b4',
      '--c-badge-code': '#334155', '--c-badge-code-soft': '#eef1f5', '--c-badge-code-border': '#d3dae3',
      '--c-badge-comparison': '#0e7490', '--c-badge-comparison-soft': '#e4f4f8', '--c-badge-comparison-border': '#b9dee8',
      '--c-badge-conclusion': '#047857', '--c-badge-conclusion-soft': '#e3f5ee', '--c-badge-conclusion-border': '#b8e4d5',
      '--c-badge-keypoints': '#be123c', '--c-badge-keypoints-soft': '#fce9ee', '--c-badge-keypoints-border': '#f4c8d3'
    },
    dark: {
      '--el-color-primary': '#2fbfae', '--el-color-primary-light-3': '#5ccfbf', '--el-color-primary-light-5': '#82dccf',
      '--el-color-primary-light-7': '#2a4a46', '--el-color-primary-light-8': '#233c39', '--el-color-primary-light-9': '#1c312f',
      '--el-color-primary-dark-2': '#54cdbf', '--el-color-success': '#4caf7d', '--el-color-warning': '#e8a340', '--el-color-danger': '#e06a65',
      '--c-primary': '#2fbfae', '--c-primary-hover': '#44cebd', '--c-primary-active': '#28a899', '--c-primary-soft': 'rgba(47,191,174,.13)', '--c-primary-border': 'rgba(47,191,174,.32)',
      '--c-accent': '#e8a340', '--c-accent-soft': 'rgba(232,163,64,.12)', '--c-accent-border': 'rgba(232,163,64,.3)',
      '--c-danger': '#e06a65', '--c-danger-soft': 'rgba(224,106,101,.13)', '--c-success': '#4caf7d', '--c-success-soft': 'rgba(76,175,125,.13)',
      '--c-bg': '#0d1416', '--c-bg-elev': '#141d20', '--c-bg-soft': '#1b2529', '--c-border': '#28343a', '--c-border-light': '#222d31',
      '--c-text': '#e2e9e8', '--c-text-2': '#9aa7a6', '--c-text-3': '#6e7b7b',
      '--c-code-bg': '#0b1117', '--c-code-text': '#dce6ec',
      '--c-shadow-card': '0 1px 2px rgba(0, 0, 0, .3)', '--c-shadow-hover': '0 10px 28px rgba(0, 0, 0, .45)',
      '--c-badge-definition': '#8fb6ff', '--c-badge-definition-soft': 'rgba(96,150,255,.16)', '--c-badge-definition-border': 'rgba(96,150,255,.3)',
      '--c-badge-concept': '#5fcfc0', '--c-badge-concept-soft': 'rgba(47,191,174,.14)', '--c-badge-concept-border': 'rgba(47,191,174,.3)',
      '--c-badge-derivation': '#c0a6ff', '--c-badge-derivation-soft': 'rgba(167,130,255,.17)', '--c-badge-derivation-border': 'rgba(167,130,255,.32)',
      '--c-badge-example': '#e8a340', '--c-badge-example-soft': 'rgba(232,163,64,.15)', '--c-badge-example-border': 'rgba(232,163,64,.3)',
      '--c-badge-code': '#b0bcc9', '--c-badge-code-soft': 'rgba(160,174,192,.15)', '--c-badge-code-border': 'rgba(160,174,192,.3)',
      '--c-badge-comparison': '#5cc6e4', '--c-badge-comparison-soft': 'rgba(56,189,220,.15)', '--c-badge-comparison-border': 'rgba(56,189,220,.3)',
      '--c-badge-conclusion': '#5fcfa3', '--c-badge-conclusion-soft': 'rgba(60,190,140,.15)', '--c-badge-conclusion-border': 'rgba(60,190,140,.3)',
      '--c-badge-keypoints': '#f0809c', '--c-badge-keypoints-soft': 'rgba(240,110,140,.15)', '--c-badge-keypoints-border': 'rgba(240,110,140,.3)'
    }
  },
  // 海盐蓝：冷静蓝调 + 冷白纸，适合长时间阅读
  ocean: {
    name: '海盐蓝',
    light: {
      '--el-color-primary': '#2563eb', '--el-color-primary-light-3': '#5b8def', '--el-color-primary-light-5': '#85a9f3',
      '--el-color-primary-light-7': '#b0c7f8', '--el-color-primary-light-8': '#c5d6fa', '--el-color-primary-light-9': '#dbe6fc',
      '--el-color-primary-dark-2': '#1e52c4', '--el-color-success': '#16a34a', '--el-color-warning': '#ea580c', '--el-color-danger': '#dc2626',
      '--c-primary': '#2563eb', '--c-primary-hover': '#2f6ff0', '--c-primary-active': '#1e52c4', '--c-primary-soft': '#e8effd', '--c-primary-border': '#c4d5f5',
      '--c-accent': '#ea580c', '--c-accent-soft': '#fdede5', '--c-accent-border': '#f6cdb8',
      '--c-danger': '#dc2626', '--c-danger-soft': '#fdeaea', '--c-success': '#16a34a', '--c-success-soft': '#e6f6ec',
      '--c-bg': '#f5f7fb', '--c-bg-elev': '#ffffff', '--c-bg-soft': '#eef1f7', '--c-border': '#dfe4ee', '--c-border-light': '#e9edf5',
      '--c-text': '#1c2532', '--c-text-2': '#4d5a6d', '--c-text-3': '#8692a6',
      '--c-code-bg': '#16202a', '--c-code-text': '#dce6ec',
      '--c-shadow-card': '0 1px 2px rgba(28, 37, 50, .05)', '--c-shadow-hover': '0 10px 28px rgba(28, 37, 50, .1)',
      '--c-badge-definition': '#1d4ed8', '--c-badge-definition-soft': '#e8effd', '--c-badge-definition-border': '#c6d8f8',
      '--c-badge-concept': '#2563eb', '--c-badge-concept-soft': '#e8effd', '--c-badge-concept-border': '#c4d5f5',
      '--c-badge-derivation': '#7c3aed', '--c-badge-derivation-soft': '#f1ebfd', '--c-badge-derivation-border': '#d8c8f6',
      '--c-badge-example': '#d97706', '--c-badge-example-soft': '#fdf3e4', '--c-badge-example-border': '#f3dcc0',
      '--c-badge-code': '#475569', '--c-badge-code-soft': '#eef1f5', '--c-badge-code-border': '#d3dae3',
      '--c-badge-comparison': '#0891b2', '--c-badge-comparison-soft': '#e0f5fa', '--c-badge-comparison-border': '#b8e3ef',
      '--c-badge-conclusion': '#059669', '--c-badge-conclusion-soft': '#e3f5ee', '--c-badge-conclusion-border': '#b8e4d5',
      '--c-badge-keypoints': '#e11d48', '--c-badge-keypoints-soft': '#fde9ee', '--c-badge-keypoints-border': '#f6c9d4'
    },
    dark: {
      '--el-color-primary': '#60a5fa', '--el-color-primary-light-3': '#7ab5fb', '--el-color-primary-light-5': '#96c6fc',
      '--el-color-primary-light-7': '#274a75', '--el-color-primary-light-8': '#203e63', '--el-color-primary-light-9': '#1b3455',
      '--el-color-primary-dark-2': '#7cb7fb', '--el-color-success': '#4ade80', '--el-color-warning': '#fbbf24', '--el-color-danger': '#f87171',
      '--c-primary': '#60a5fa', '--c-primary-hover': '#7ab7fc', '--c-primary-active': '#4a92e8', '--c-primary-soft': 'rgba(96,165,250,.14)', '--c-primary-border': 'rgba(96,165,250,.32)',
      '--c-accent': '#fbbf24', '--c-accent-soft': 'rgba(251,191,36,.13)', '--c-accent-border': 'rgba(251,191,36,.3)',
      '--c-danger': '#f87171', '--c-danger-soft': 'rgba(248,113,113,.13)', '--c-success': '#4ade80', '--c-success-soft': 'rgba(74,222,128,.13)',
      '--c-bg': '#0c1220', '--c-bg-elev': '#131b2e', '--c-bg-soft': '#1a2438', '--c-border': '#28344d', '--c-border-light': '#212c45',
      '--c-text': '#e6ecf5', '--c-text-2': '#9fb0c9', '--c-text-3': '#6c7c99',
      '--c-code-bg': '#0b1117', '--c-code-text': '#dce6ec',
      '--c-shadow-card': '0 1px 2px rgba(0, 0, 0, .3)', '--c-shadow-hover': '0 10px 28px rgba(0, 0, 0, .45)',
      '--c-badge-definition': '#93b8ff', '--c-badge-definition-soft': 'rgba(96,150,255,.17)', '--c-badge-definition-border': 'rgba(96,150,255,.32)',
      '--c-badge-concept': '#7db4fb', '--c-badge-concept-soft': 'rgba(96,165,250,.15)', '--c-badge-concept-border': 'rgba(96,165,250,.32)',
      '--c-badge-derivation': '#c4a8ff', '--c-badge-derivation-soft': 'rgba(167,130,255,.17)', '--c-badge-derivation-border': 'rgba(167,130,255,.32)',
      '--c-badge-example': '#fbbf24', '--c-badge-example-soft': 'rgba(251,191,36,.15)', '--c-badge-example-border': 'rgba(251,191,36,.3)',
      '--c-badge-code': '#b7c3d6', '--c-badge-code-soft': 'rgba(160,174,192,.15)', '--c-badge-code-border': 'rgba(160,174,192,.3)',
      '--c-badge-comparison': '#5fd0ec', '--c-badge-comparison-soft': 'rgba(56,189,220,.15)', '--c-badge-comparison-border': 'rgba(56,189,220,.3)',
      '--c-badge-conclusion': '#5fd3a5', '--c-badge-conclusion-soft': 'rgba(60,190,140,.15)', '--c-badge-conclusion-border': 'rgba(60,190,140,.3)',
      '--c-badge-keypoints': '#f5879e', '--c-badge-keypoints-soft': 'rgba(240,110,140,.15)', '--c-badge-keypoints-border': 'rgba(240,110,140,.3)'
    }
  },
  // 秋日橙：暖陶土主色 + 暖米纸，专注学习的小暖窝
  sunset: {
    name: '秋日橙',
    light: {
      '--el-color-primary': '#bf5b2d', '--el-color-primary-light-3': '#d0885f', '--el-color-primary-light-5': '#dfa888',
      '--el-color-primary-light-7': '#eed0bd', '--el-color-primary-light-8': '#f4ddd0', '--el-color-primary-light-9': '#f9ebe2',
      '--el-color-primary-dark-2': '#a44e25', '--el-color-success': '#55893f', '--el-color-warning': '#a16207', '--el-color-danger': '#d43d3d',
      '--c-primary': '#bf5b2d', '--c-primary-hover': '#cc6a38', '--c-primary-active': '#a64f26', '--c-primary-soft': '#fbeee7', '--c-primary-border': '#f0d4c6',
      '--c-accent': '#a16207', '--c-accent-soft': '#fbf3e0', '--c-accent-border': '#ecd9ad',
      '--c-danger': '#d43d3d', '--c-danger-soft': '#fbeaea', '--c-success': '#55893f', '--c-success-soft': '#eaf3e4',
      '--c-bg': '#faf6f0', '--c-bg-elev': '#fffdf9', '--c-bg-soft': '#f3ede4', '--c-border': '#e8dfd2', '--c-border-light': '#efe8dc',
      '--c-text': '#2d241c', '--c-text-2': '#6b5d4e', '--c-text-3': '#9b8d7d',
      '--c-code-bg': '#2a1f16', '--c-code-text': '#f0e6dc',
      '--c-shadow-card': '0 1px 2px rgba(80, 60, 40, .06)', '--c-shadow-hover': '0 10px 28px rgba(80, 60, 40, .12)',
      '--c-badge-definition': '#0f766e', '--c-badge-definition-soft': '#e6f4f1', '--c-badge-definition-border': '#bfe0da',
      '--c-badge-concept': '#bf5b2d', '--c-badge-concept-soft': '#fbeee7', '--c-badge-concept-border': '#f0d4c6',
      '--c-badge-derivation': '#6d28d9', '--c-badge-derivation-soft': '#f1ebfd', '--c-badge-derivation-border': '#d8c8f6',
      '--c-badge-example': '#a16207', '--c-badge-example-soft': '#fbf3e0', '--c-badge-example-border': '#ecd9ad',
      '--c-badge-code': '#57534e', '--c-badge-code-soft': '#f0ede9', '--c-badge-code-border': '#ddd6ce',
      '--c-badge-comparison': '#0e7490', '--c-badge-comparison-soft': '#e4f4f8', '--c-badge-comparison-border': '#b9dee8',
      '--c-badge-conclusion': '#4d7c0f', '--c-badge-conclusion-soft': '#eef5e3', '--c-badge-conclusion-border': '#d2e5bc',
      '--c-badge-keypoints': '#be123c', '--c-badge-keypoints-soft': '#fce9ee', '--c-badge-keypoints-border': '#f4c8d3'
    },
    dark: {
      '--el-color-primary': '#e8843f', '--el-color-primary-light-3': '#ec9a5f', '--el-color-primary-light-5': '#f1b383',
      '--el-color-primary-light-7': '#4a3322', '--el-color-primary-light-8': '#3e2b1c', '--el-color-primary-light-9': '#332418',
      '--el-color-primary-dark-2': '#eb9660', '--el-color-success': '#6fae54', '--el-color-warning': '#e8b04a', '--el-color-danger': '#e06a5a',
      '--c-primary': '#e8843f', '--c-primary-hover': '#f09455', '--c-primary-active': '#d87433', '--c-primary-soft': 'rgba(232,132,63,.14)', '--c-primary-border': 'rgba(232,132,63,.32)',
      '--c-accent': '#e8b04a', '--c-accent-soft': 'rgba(232,176,74,.13)', '--c-accent-border': 'rgba(232,176,74,.3)',
      '--c-danger': '#e06a5a', '--c-danger-soft': 'rgba(224,106,90,.13)', '--c-success': '#6fae54', '--c-success-soft': 'rgba(111,174,84,.13)',
      '--c-bg': '#17120d', '--c-bg-elev': '#201811', '--c-bg-soft': '#2a2018', '--c-border': '#3a2e23', '--c-border-light': '#31271d',
      '--c-text': '#f0e8de', '--c-text-2': '#b3a390', '--c-text-3': '#82715f',
      '--c-code-bg': '#1c130b', '--c-code-text': '#e8ddd0',
      '--c-shadow-card': '0 1px 2px rgba(0, 0, 0, .3)', '--c-shadow-hover': '0 10px 28px rgba(0, 0, 0, .45)',
      '--c-badge-definition': '#6ec4b8', '--c-badge-definition-soft': 'rgba(60,190,170,.16)', '--c-badge-definition-border': 'rgba(60,190,170,.32)',
      '--c-badge-concept': '#ed9b63', '--c-badge-concept-soft': 'rgba(232,132,63,.15)', '--c-badge-concept-border': 'rgba(232,132,63,.32)',
      '--c-badge-derivation': '#c0a6ff', '--c-badge-derivation-soft': 'rgba(167,130,255,.17)', '--c-badge-derivation-border': 'rgba(167,130,255,.32)',
      '--c-badge-example': '#e8b04a', '--c-badge-example-soft': 'rgba(232,176,74,.15)', '--c-badge-example-border': 'rgba(232,176,74,.3)',
      '--c-badge-code': '#c9c0b5', '--c-badge-code-soft': 'rgba(180,170,155,.15)', '--c-badge-code-border': 'rgba(180,170,155,.3)',
      '--c-badge-comparison': '#5fd0ec', '--c-badge-comparison-soft': 'rgba(56,189,220,.15)', '--c-badge-comparison-border': 'rgba(56,189,220,.3)',
      '--c-badge-conclusion': '#9ccf6a', '--c-badge-conclusion-soft': 'rgba(140,200,90,.15)', '--c-badge-conclusion-border': 'rgba(140,200,90,.3)',
      '--c-badge-keypoints': '#f0809c', '--c-badge-keypoints-soft': 'rgba(240,110,140,.15)', '--c-badge-keypoints-border': 'rgba(240,110,140,.3)'
    }
  }
}

function loadPalette() {
  var p = localStorage.getItem(PALETTE_KEY)
  return PALETTES[p] ? p : 'paper'
}

export const theme = reactive({
  dark: localStorage.getItem(THEME_KEY) === 'dark',
  palette: loadPalette()
})

export function applyTheme() {
  var el = document.documentElement
  el.classList.toggle('dark', theme.dark)
  var vars = PALETTES[theme.palette] && PALETTES[theme.palette][theme.dark ? 'dark' : 'light']
  if (vars) {
    Object.keys(vars).forEach(function (k) { el.style.setProperty(k, vars[k]) })
  }
  localStorage.setItem(THEME_KEY, theme.dark ? 'dark' : 'light')
  localStorage.setItem(PALETTE_KEY, theme.palette)
}

export function setPalette(name) {
  if (!PALETTES[name]) return
  theme.palette = name
  applyTheme()
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

function currentBg() {
  return getComputedStyle(document.documentElement).getPropertyValue('--c-bg').trim() || (theme.dark ? '#0d1416' : '#f6f5f1')
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
    'background:' + (targetDark ? currentBg() : currentBg()) + ';' +
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
