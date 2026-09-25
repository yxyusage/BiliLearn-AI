<template>
  <el-container class="app-container">
    <!-- 左侧侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }" v-if="!isMobile">
      <div class="sidebar-header" @click="$router.push('/')">
        <span class="sb-logo-icon">📚</span>
        <span class="sb-logo-text" v-if="!sidebarCollapsed">BiliLearn-AI</span>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/" class="sb-item" :class="{active: activeMenu === '/'}" @click="activeNav='/'" v-tooltip="'首页'">
          <span class="sb-icon">🏠</span>
          <span class="sb-label" v-if="!sidebarCollapsed">首页</span>
        </router-link>
        <router-link to="/history" class="sb-item" :class="{active: activeMenu === '/history'}">
          <span class="sb-icon">📋</span>
          <span class="sb-label" v-if="!sidebarCollapsed">历史笔记</span>
        </router-link>
        <router-link to="/review" class="sb-item" :class="{active: activeMenu === '/review'}">
          <span class="sb-icon">🔄</span>
          <span class="sb-label" v-if="!sidebarCollapsed">复习中心</span>
        </router-link>
        <router-link to="/stats" class="sb-item" :class="{active: activeMenu === '/stats'}">
          <span class="sb-icon">📊</span>
          <span class="sb-label" v-if="!sidebarCollapsed">学习数据</span>
        </router-link>
        <router-link to="/collections" class="sb-item" :class="{active: activeMenu === '/collections'}">
          <span class="sb-icon">📚</span>
          <span class="sb-label" v-if="!sidebarCollapsed">合集任务</span>
        </router-link>
        <router-link to="/favorites" class="sb-item" :class="{active: activeMenu === '/favorites'}">
          <span class="sb-icon">⭐</span>
          <span class="sb-label" v-if="!sidebarCollapsed">收藏夹</span>
        </router-link>
        <div class="sb-divider" v-if="!sidebarCollapsed"></div>
        <router-link to="/config" class="sb-item" :class="{active: activeMenu === '/config'}">
          <span class="sb-icon">⚙️</span>
          <span class="sb-label" v-if="!sidebarCollapsed">设置</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <el-tooltip :content="isDark ? '浅色模式' : '深色模式'" placement="right">
          <button class="sb-theme-btn" @click="toggleTheme">
            <span>{{ isDark ? '☀️' : '🌙' }}</span>
          </button>
        </el-tooltip>
        <button class="sb-collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <span :class="{rotated: sidebarCollapsed}">◀</span>
        </button>
      </div>
    </aside>

    <!-- 移动端顶部栏 -->
    <el-header class="app-header" v-if="isMobile">
      <div class="logo" @click="$router.push('/')">
        <span class="logo-icon">📚</span>
        <span class="logo-text">BiliLearn-AI</span>
      </div>
      <el-tooltip :content="isDark ? '浅色模式' : '深色模式'" placement="bottom">
        <el-button class="theme-btn" circle text @click="toggleTheme">
          <span class="theme-icon">{{ isDark ? '☀️' : '🌙' }}</span>
        </el-button>
      </el-tooltip>
    </el-header>

    <el-main class="app-main" :class="{ 'with-sidebar': !isMobile, 'sidebar-collapsed': sidebarCollapsed && !isMobile }">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>

    <!-- 移动端底部导航 -->
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
    return {
      isMobile: window.innerWidth <= 768,
      sidebarCollapsed: localStorage.getItem('bililearn-sidebar-collapsed') === '1'
    }
  },
  mounted() {
    window.addEventListener('resize', this.checkMobile)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.checkMobile)
  },
  watch: {
    sidebarCollapsed(val) {
      localStorage.setItem('bililearn-sidebar-collapsed', val ? '1' : '0')
    }
  },
  computed: {
    activeMenu() {
      var path = this.$route.path
      if (path.indexOf('/history') === 0) return '/history'
      if (path.indexOf('/review') === 0) return '/review'
      if (path.indexOf('/stats') === 0) return '/stats'
      if (path.indexOf('/config') === 0) return '/config'
      if (path.indexOf('/collections') === 0) return '/collections'
      if (path.indexOf('/favorites') === 0) return '/favorites'
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

/* 侧边栏 */
.sidebar {
  position: fixed;
  left: 0; top: 0; bottom: 0;
  width: 220px;
  background: var(--c-bg-elev);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  z-index: 200;
  transition: width .25s var(--ease-out, ease);
  overflow: hidden;
}
.sidebar.collapsed { width: 60px; }
.sidebar-header {
  display: flex; align-items: center; gap: 10px;
  padding: 18px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--c-border);
  min-height: 60px;
}
.sb-logo-icon { font-size: 22px; flex-shrink: 0; }
.sb-logo-text { font-size: 16px; font-weight: 700; color: var(--c-text); white-space: nowrap; }
.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  overflow-y: auto;
}
.sb-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  text-decoration: none;
  color: var(--c-text-2);
  font-size: 14px;
  margin-bottom: 2px;
  transition: all .18s ease;
  white-space: nowrap;
}
.sb-item:hover { background: var(--c-bg-hover, rgba(0,0,0,.04)); color: var(--c-text); }
.sb-item.active {
  background: color-mix(in srgb, var(--c-primary) 12%, transparent);
  color: var(--c-primary);
  font-weight: 600;
}
.sb-icon { font-size: 18px; flex-shrink: 0; width: 24px; text-align: center; }
.sb-label { flex: 1; }
.sb-divider { height: 1px; background: var(--c-border); margin: 8px 4px; }
.sidebar-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px;
  border-top: 1px solid var(--c-border);
}
.sb-theme-btn, .sb-collapse-btn {
  width: 36px; height: 36px;
  border: none; background: transparent;
  border-radius: 8px; cursor: pointer;
  font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s;
  color: var(--c-text-2);
}
.sb-theme-btn:hover, .sb-collapse-btn:hover { background: var(--c-bg-hover, rgba(0,0,0,.04)); }
.sb-collapse-btn span { display: inline-block; transition: transform .25s; font-size: 12px; }
.sb-collapse-btn span.rotated { transform: rotate(180deg); }

/* 主内容区 */
.app-main {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 20px;
  transition: padding .25s ease;
}
.app-main.with-sidebar {
  margin-left: 220px;
  max-width: calc(1200px + 220px);
  padding-left: 40px;
  padding-right: 40px;
}
.app-main.sidebar-collapsed {
  margin-left: 60px;
  max-width: calc(1200px + 60px);
}

/* 移动端 */
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
  background: color-mix(in srgb, var(--c-bg-elev) 82%, transparent);
  backdrop-filter: blur(14px) saturate(1.5);
  border-bottom: 1px solid var(--c-border);
  padding: 0 16px; height: 52px;
}
.logo { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.logo-icon { font-size: 20px; }
.logo-text { font-size: 15px; font-weight: 700; color: var(--c-text); }
.theme-btn { font-size: 16px; }

@media (max-width: 768px) {
  .app-main { padding: 12px 10px 72px; margin-left: 0 !important; max-width: 100% !important; }
}
.mobile-nav { display: none; }
@media (max-width: 768px) {
  .mobile-nav {
    display: flex; position: fixed; bottom: 0; left: 0; right: 0;
    height: 58px;
    background: color-mix(in srgb, var(--c-bg-elev) 92%, transparent);
    backdrop-filter: blur(14px) saturate(1.5);
    border-top: 1px solid var(--c-border);
    z-index: 100;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }
  .mnav-item {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 2px;
    text-decoration: none; color: var(--c-text-3); font-size: 11px;
    transition: color .2s, transform .15s;
  }
  .mnav-item:active { transform: scale(.92); }
  .mnav-item.active { color: var(--c-primary); }
  .mnav-icon { font-size: 20px; line-height: 1; }
  .mnav-label { font-size: 11px; }
}
</style>

<style>
.page-enter-active, .page-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
