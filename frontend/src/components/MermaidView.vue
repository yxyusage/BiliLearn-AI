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
    return { loading: false, error: '', seq: 0 }
  },
  beforeUnmount() { this.cleanMermaidErrors() },
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
          primaryColor: '#16302d',
          primaryBorderColor: '#2fbfae',
          primaryTextColor: '#e2e9e8',
          lineColor: '#6e7b7b',
          edgeLabelBackground: '#141d20',
          clusterBkg: '#141d20',
          tertiaryColor: '#141d20',
          fontSize: '14px'
        } : {
          fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
          primaryColor: '#e6f4f1',
          primaryBorderColor: '#0d7e70',
          primaryTextColor: '#1e272b',
          lineColor: '#8a9296',
          edgeLabelBackground: '#ffffff',
          clusterBkg: '#f6f5f1',
          tertiaryColor: '#ffffff',
          fontSize: '14px'
        }
      })
      initialized = true
      lastDark = dark
    },
    async render() {
      var mySeq = ++this.seq
      if (!this.code) { this.error = ''; this.loading = false; return }
      this.ensureInit()
      this.loading = true
      this.error = ''
      this.cleanMermaidErrors()
      try {
        var id = 'mm-' + Date.now() + '-' + Math.floor(Math.random() * 1000)
        var result = await mermaid.render(id, this.code)
        if (mySeq !== this.seq) return
        if (this.$refs.container) {
          this.$refs.container.innerHTML = result.svg
          this.bindClicks()
        }
      } catch (e) {
        this.cleanMermaidErrors()
        if (mySeq === this.seq) this.error = '脑图渲染失败：' + (e.message || e)
      } finally {
        this.cleanMermaidErrors()
        if (mySeq === this.seq) this.loading = false
      }
    },
    cleanMermaidErrors() {
      try {
        var sel = document.querySelectorAll('body > div[id^="dmermaid"], body > div[id^="mm-"], body > [id*="textmermaid"]')
        sel.forEach(function (el) {
          if (el.textContent && el.textContent.indexOf('Syntax error') >= 0) el.remove()
          else if (el.id && el.id.indexOf('mm-') === 0 && !el.querySelector('svg')) el.remove()
        })
      } catch (e) { /* 忽略 */ }
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
.mermaid-view { min-height: 60px; overflow-x: auto; background: var(--c-bg-elev); border: 1px solid var(--c-border); border-radius: 10px; padding: 16px; }
.mermaid-view.compact { background: transparent; border: none; padding: 6px 0; min-height: 30px; }
.mm-error { color: var(--c-danger); padding: 20px; }
.mm-container svg { max-width: 100%; height: auto; }
.mm-hint { margin-top: 8px; color: var(--c-text-3); font-size: 12px; text-align: center; }
</style>
