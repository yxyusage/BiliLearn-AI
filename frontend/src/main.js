import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'katex/dist/katex.min.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import './style.css'
import { applyTheme } from './utils/theme'

applyTheme()

// PWA：仅生产构建注册 Service Worker（本地开发不干扰 HMR）
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  var reloading = false
  // 新版本 Service Worker 接管后自动刷新一次，避免浏览器继续显示旧界面
  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (reloading) return
    reloading = true
    window.location.reload()
  })
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('./sw.js?v=' + __APP_VERSION__).catch(function () { /* 非安全上下文或不可用时静默跳过 */ })
  })
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
