<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="logo" @click="$router.push('/')">
        <span class="logo-icon">📚</span>
        <span class="logo-text">BiliLearn-AI</span>
        <span class="logo-sub">B站全学科AI学习助手</span>
      </div>
      <div class="header-right">
        <el-menu mode="horizontal" :default-active="activeMenu" router class="nav-menu">
          <el-menu-item index="/">生成笔记</el-menu-item>
          <el-menu-item index="/history">历史笔记</el-menu-item>
          <el-menu-item index="/review">复习中心</el-menu-item>
          <el-menu-item index="/stats">学习数据</el-menu-item>
          <el-menu-item index="/collections">合集任务</el-menu-item>
          <el-menu-item index="/favorites">收藏夹</el-menu-item>
          <el-menu-item index="/config">设置</el-menu-item>
        </el-menu>
        <el-tooltip :content="isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
          <el-button class="theme-btn" circle text @click="toggleTheme">
            <span class="theme-icon">{{ isDark ? '☀️' : '🌙' }}</span>
          </el-button>
        </el-tooltip>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>
    <nav class="mobile-nav" v-if="isMobile">
      <router-link to="/" class="mnav-item" :class="{active: activeMenu === '/'}">
        <span class="mnav-icon">🏠</span><span class="mnav-label">首页</span>
      </router-link>
      <router-link to="/history" class="mnav-item" :class="{active: activeMenu === '/history'}">
        <span class="mnav-icon">📋</span><span class="mnav-label">笔记</span>
      </router-link>
      <router-link to="/review" class="mnav-item" :class="{active: activeMenu === '/review'}">
        <span class="mnav-icon">🔄</span><span class="mnav-label">复习</span>
      </router-link>
      <router-link to="/stats" class="mnav-item" :class="{active: activeMenu === '/stats'}">
        <span class="mnav-icon">📊</span><span class="mnav-label">数据</span>
      </router-link>
      <router-link to="/config" class="mnav-item" :class="{active: activeMenu === '/config'}">
        <span class="mnav-icon">⚙️</span><span class="mnav-label">设置</span>
      </router-link>
    </nav>
  </el-container>
</template>

<script>
import { theme, toggleTheme as doToggleTheme } from './utils/theme'

export default {
  name: 'App',
  data() {
    return { isMobile: window.innerWidth <= 768 }
  },
  mounted() {
    window.addEventListener('resize', this.checkMobile)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.checkMobile)
  },
  computed: {
    activeMenu() {
      var path = this.$route.path
      if (path.indexOf('/history') === 0) return '/history'
      if (path.indexOf('/review') === 0) return '/review'
      if (path.indexOf('/stats') === 0) return '/stats'
      if (path.indexOf('/config') === 0) return '/config'
      if (path.indexOf('/collections') === 0) return '/collections'
      return '/'
    },
    isDark() {
      return theme.dark
    }
  },
  methods: {
    checkMobile() {
      this.isMobile = window.innerWidth <= 768
    },
    toggleTheme(e) {
      doToggleTheme(e)
    }
  }
}
</script>

<style scoped>
.app-container { min-height: 100vh; }
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  background: color-mix(in srgb, var(--c-bg-elev) 82%, transparent);
  backdrop-filter: blur(14px) saturate(1.5);
  -webkit-backdrop-filter: blur(14px) saturate(1.5);
  border-bottom: 1px solid var(--c-border);
  padding: 0 24px;
}
.logo { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.logo-icon { font-size: 22px; }
.logo-text { font-size: 18px; font-weight: 700; color: var(--c-text); }
.logo-sub { font-size: 12px; color: var(--c-text-3); }
.nav-menu { border-bottom: none; }
.header-right { display: flex; align-items: center; gap: 8px; }
.theme-btn { font-size: 16px; }
.app-main { max-width: 1200px; width: 100%; margin: 0 auto; padding: 20px 16px; }

@media (max-width: 768px) {
  .app-header { padding: 0 12px; height: 52px; }
  .logo-sub { display: none; }
  .logo-text { font-size: 15px; }
  .header-right { gap: 4px; }
  .nav-menu { display: none; }
  .app-main { padding: 12px 10px 72px; }
}
.mobile-nav {
  display: none;
}
@media (max-width: 768px) {
  .mobile-nav {
    display: flex;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    height: 58px;
    background: color-mix(in srgb, var(--c-bg-elev) 92%, transparent);
    backdrop-filter: blur(14px) saturate(1.5);
    -webkit-backdrop-filter: blur(14px) saturate(1.5);
    border-top: 1px solid var(--c-border);
    z-index: 100;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }
  .mnav-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    text-decoration: none;
    color: var(--c-text-3);
    font-size: 11px;
    transition: color .2s, transform .15s;
  }
  .mnav-item:active { transform: scale(.92); }
  .mnav-item.active { color: var(--c-primary); }
  .mnav-icon { font-size: 20px; line-height: 1; }
  .mnav-label { font-size: 11px; }
}
</style>

<style>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
