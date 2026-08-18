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
          <el-menu-item index="/collections">合集任务</el-menu-item>
          <el-menu-item index="/config">模型配置</el-menu-item>
        </el-menu>
        <el-tooltip :content="isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
          <el-button class="theme-btn" circle text @click="toggleTheme">
            <span class="theme-icon">{{ isDark ? '☀️' : '🌙' }}</span>
          </el-button>
        </el-tooltip>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script>
import { theme, toggleTheme as doToggleTheme } from './utils/theme'

export default {
  name: 'App',
  computed: {
    activeMenu() {
      var path = this.$route.path
      if (path.indexOf('/history') === 0) return '/history'
      if (path.indexOf('/config') === 0) return '/config'
      if (path.indexOf('/collections') === 0) return '/collections'
      return '/'
    },
    isDark() {
      return theme.dark
    }
  },
  methods: {
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
  background: rgba(255, 255, 255, .75);
  backdrop-filter: blur(14px) saturate(1.5);
  -webkit-backdrop-filter: blur(14px) saturate(1.5);
  border-bottom: 1px solid rgba(0, 0, 0, .05);
  padding: 0 24px;
}
html.dark .app-header {
  background: rgba(15, 17, 20, .72);
  border-bottom: 1px solid rgba(255, 255, 255, .06);
}
.logo { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.logo-icon { font-size: 22px; }
.logo-text { font-size: 18px; font-weight: 700; color: #303133; }
.logo-sub { font-size: 12px; color: #909399; }
.nav-menu { border-bottom: none; }
.header-right { display: flex; align-items: center; gap: 8px; }
.theme-btn { font-size: 16px; }
.app-main { max-width: 1200px; width: 100%; margin: 0 auto; padding: 20px 16px; }
</style>
