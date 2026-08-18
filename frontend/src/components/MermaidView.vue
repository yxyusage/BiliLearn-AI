<template>
  <div class="mermaid-view" :class="{ compact: compact }" v-loading="loading">
    <div v-if="error" class="mm-error">{{ error }}</div>
    <template v-else>
      <div ref="container" class="mm-container"></div>
      <div v-if="!compact" class="mm-hint">💡 点击任意节点跳转到视频对应位置</div>
    </template>
  </div>
</template>

<script>
import mermaid from 'mermaid'
import { hmsCompactToSeconds } from '../utils/time'
import { theme } from '../utils/theme'

let initialized = false
let lastDark = null

export default {
  name: 'MermaidView',
  props: {
    code: { type: String, default: '' },
    compact: { type: Boolean, default: false }
  },
  emits: ['node-click'],
  data() {
    return { loading: false, error: '' }
  },
  watch: {
    code: {
      immediate: true,
      handler() { this.render() }
    },
    'theme.dark'() {
      initialized = false
      this.render()
    }
  },
  methods: {
    ensureInit() {
      if (initialized && lastDark === theme.dark) return
      var dark = theme.dark
      mermaid.initialize({
        startOnLoad: false,
        theme: dark ? 'dark' : 'base',
        securityLevel: 'loose',
        flowchart: { htmlLabels: true, curve: 'basis', nodeSpacing: 40, rankSpacing: 50 },
        themeVariables: dark ? {
          fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
          primaryColor: '#263445',
          primaryBorderColor: '#409eff',
          primaryTextColor: '#e5eaf3',
          lineColor: '#6b7785',
          edgeLabelBackground: '#1d1e1f',
          clusterBkg: '#1d1e1f',
          fontSize: '14px'
        } : {
          fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
          primaryColor: '#e8f4ff',
          primaryBorderColor: '#409eff',
          primaryTextColor: '#1f2d3d',
          lineColor: '#909399',
          edgeLabelBackground: '#ffffff',
          clusterBkg: '#f5f7fa',
          fontSize: '14px'
        }
      })
      initialized = true
      lastDark = dark
    },
    async render() {
      if (!this.code) { this.error = ''; return }
      this.ensureInit()
      this.loading = true
      this.error = ''
      try {
        var id = 'mm-' + Date.now() + '-' + Math.floor(Math.random() * 1000)
        var result = await mermaid.render(id, this.code)
        if (this.$refs.container) {
          this.$refs.container.innerHTML = result.svg
          this.bindClicks()
        }
      } catch (e) {
        this.error = '脑图渲染失败：' + (e.message || e)
      } finally {
        this.loading = false
      }
    },
    bindClicks() {
      var self = this
      var nodes = this.$refs.container.querySelectorAll('[id^="flowchart-t_"], [id^="flowchart-p"]')
      nodes.forEach(function (n) {
        n.style.cursor = 'pointer'
        n.addEventListener('click', function () {
          var mp = n.id.match(/^flowchart-p(\d+)_(\d{6})/)
          if (mp) {
            self.$emit('node-click', hmsCompactToSeconds(mp[2]), parseInt(mp[1], 10))
            return
          }
          var m = n.id.match(/t_(\d{6})/)
          if (m) self.$emit('node-click', hmsCompactToSeconds(m[1]))
        })
      })
    }
  }
}
</script>

<style scoped>
.mermaid-view { min-height: 60px; overflow-x: auto; background: #fafcff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; }
.mermaid-view.compact { background: transparent; border: none; padding: 6px 0; min-height: 30px; }
.mm-error { color: #f56c6c; padding: 20px; }
.mm-container svg { max-width: 100%; height: auto; }
.mm-hint { margin-top: 8px; color: #909399; font-size: 12px; text-align: center; }
</style>
