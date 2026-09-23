<template>
  <div class="dashboard-page" v-loading="loading">
    <div class="page-head">
      <h2 class="page-title">📊 学习数据</h2>
      <p class="page-sub">你的学习轨迹、掌握情况与复习节奏都在这里。</p>
    </div>

    <div class="stat-row">
      <el-card shadow="never" class="stat-card">
        <div class="stat-num">{{ display.notesDone }}<span class="stat-sub">/{{ display.notesTotal }}</span></div>
        <div class="stat-label">已生成笔记</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num">{{ display.wrongActive }}</div>
        <div class="stat-label">未掌握错题</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num">{{ display.reviewDue }}</div>
        <div class="stat-label">今日待复习（含逾期）</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num">{{ display.collectionsTotal }}</div>
        <div class="stat-label">合集任务</div>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card shadow="never" class="chart-card">
        <div class="chart-title">近 14 天笔记生成</div>
        <div ref="noteChart" class="chart"></div>
      </el-card>
      <el-card shadow="never" class="chart-card">
        <div class="chart-title">笔记学科分布</div>
        <div ref="subjectChart" class="chart"></div>
      </el-card>
      <el-card shadow="never" class="chart-card">
        <div class="chart-title">错题掌握状态</div>
        <div ref="wrongChart" class="chart"></div>
      </el-card>
      <el-card shadow="never" class="chart-card">
        <div class="chart-title">错题学科分布</div>
        <div ref="wrongSubjectChart" class="chart"></div>
      </el-card>
    </div>

    <el-card shadow="never" class="detail-card">
      <div class="detail-row">
        <div class="detail-item"><b>{{ display.reviewPlan }}</b><span>复习计划总数</span></div>
        <div class="detail-item"><b>{{ display.reviewOverdue }}</b><span>已逾期</span></div>
        <div class="detail-item"><b>{{ display.reviewDone }}</b><span>今日已完成复习</span></div>
        <div class="detail-item"><b>{{ display.wrongMastered }}</b><span>已掌握错题</span></div>
        <div class="detail-item"><b>{{ display.confusionsOpen }}</b><span>待解决的「没懂」</span></div>
      </div>
    </el-card>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '../api'
import { theme } from '../utils/theme'

export default {
  name: 'DashboardView',
  data() {
    return {
      loading: false,
      stats: {
        notes: { total: 0, done: 0, by_subject: [], last_14d: {} },
        wrong_answers: { total: 0, active: 0, mastered: 0, by_subject: [], last_14d: {} },
        review: { due_today: 0, overdue: 0, done_today: 0, total_plan: 0 },
        collections: { total: 0, done: 0 },
        confusions: { open: 0, total: 0 }
      },
      charts: [],
      display: { notesDone: 0, notesTotal: 0, wrongActive: 0, reviewDue: 0, collectionsTotal: 0, reviewPlan: 0, reviewOverdue: 0, reviewDone: 0, wrongMastered: 0, confusionsOpen: 0 },
      animTimers: []
    }
  },
  created() {
    this.load()
  },
  mounted() {
    window.addEventListener('resize', this.resizeCharts)
  },
  watch: {
    'theme.dark': function () { this.retheme() },
    'theme.palette': function () { this.retheme() }
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.resizeCharts)
    this.charts.forEach(function (c) { c.dispose() })
    this.animTimers.forEach(function (id) { cancelAnimationFrame(id) })
  },
  methods: {
    startCountUp() {
      var self = this
      var targets = {
        notesDone: this.stats.notes.done,
        notesTotal: this.stats.notes.total,
        wrongActive: this.stats.wrong_answers.active,
        reviewDue: this.stats.review.due_today,
        collectionsTotal: this.stats.collections.total,
        reviewPlan: this.stats.review.total_plan,
        reviewOverdue: this.stats.review.overdue,
        reviewDone: this.stats.review.done_today,
        wrongMastered: this.stats.wrong_answers.mastered,
        confusionsOpen: this.stats.confusions.open
      }
      Object.keys(targets).forEach(function (key) {
        self.animateTo(key, targets[key] || 0)
      })
    },
    animateTo(key, target) {
      var self = this
      var start = 0
      var duration = 900
      var startTime = null
      function step(ts) {
        if (!startTime) startTime = ts
        var p = Math.min((ts - startTime) / duration, 1)
        var eased = 1 - Math.pow(1 - p, 3)
        self.display[key] = Math.round(start + (target - start) * eased)
        if (p < 1) {
          var id = requestAnimationFrame(step)
          self.animTimers.push(id)
        }
      }
      var id = requestAnimationFrame(step)
      this.animTimers.push(id)
    },
    cssVar(name, fallback) {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    },
    async load() {
      this.loading = true
      try {
        var data = await api.get('/stats/summary')
        this.stats = data
        this.$nextTick(this.renderCharts)
        this.startCountUp()
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    resizeCharts() {
      this.charts.forEach(function (c) { c.resize() })
    },
    retheme() {
      this.charts.forEach(function (c) {
        try { c.dispose() } catch (e) { /* 忽略 */ }
      })
      this.charts = []
      var self = this
      this.$nextTick(function () { self.renderCharts() })
    },
    makeChart(ref) {
      if (!this.$refs[ref]) return null
      var chart = echarts.init(this.$refs[ref])
      this.charts.push(chart)
      return chart
    },
    renderCharts() {
      var text = this.cssVar('--c-text-2', '#556066')
      var border = this.cssVar('--c-border', '#e4e2da')
      var primary = this.cssVar('--c-primary', '#0d7e70')
      var accent = this.cssVar('--c-accent', '#b45309')
      var success = this.cssVar('--c-success', '#2f8f5b')
      var danger = this.cssVar('--c-danger', '#c2413d')

      var axis = {
        axisLine: { lineStyle: { color: border } },
        axisLabel: { color: text, fontSize: 11 },
        splitLine: { lineStyle: { color: border, type: 'dashed' } }
      }

      var note = this.makeChart('noteChart')
      if (note) {
        var days = Object.keys(this.stats.notes.last_14d)
        var self = this
        note.setOption({
          grid: { left: 34, right: 12, top: 16, bottom: 26 },
          tooltip: { trigger: 'axis' },
          xAxis: Object.assign({ type: 'category', data: days.map(function (d) { return d.slice(5) }) }, axis),
          yAxis: Object.assign({ type: 'value', minInterval: 1 }, axis),
          series: [{
            type: 'bar',
            data: days.map(function (d) { return self.stats.notes.last_14d[d] }),
            itemStyle: { color: primary, borderRadius: [4, 4, 0, 0] },
            barMaxWidth: 22
          }]
        })
      }

      var subject = this.makeChart('subjectChart')
      if (subject) {
        subject.setOption({
          tooltip: { trigger: 'item' },
          legend: { bottom: 0, textStyle: { color: text, fontSize: 11 } },
          series: [{
            type: 'pie',
            radius: ['42%', '66%'],
            center: ['50%', '44%'],
            label: { color: text, fontSize: 11 },
            itemStyle: { borderColor: this.cssVar('--c-bg-elev', '#fff'), borderWidth: 2 },
            data: this.stats.notes.by_subject.map(function (s, i) {
              return { name: s.name, value: s.value, itemStyle: { color: ['', primary, accent, success, '#2563eb', '#7c3aed'][i % 6] } }
            })
          }]
        })
      }

      var wrong = this.makeChart('wrongChart')
      if (wrong) {
        wrong.setOption({
          tooltip: { trigger: 'item' },
          legend: { bottom: 0, textStyle: { color: text, fontSize: 11 } },
          series: [{
            type: 'pie',
            radius: ['42%', '66%'],
            center: ['50%', '44%'],
            label: { color: text, fontSize: 11 },
            itemStyle: { borderColor: this.cssVar('--c-bg-elev', '#fff'), borderWidth: 2 },
            data: [
              { name: '未掌握', value: this.stats.wrong_answers.active, itemStyle: { color: danger } },
              { name: '已掌握', value: this.stats.wrong_answers.mastered, itemStyle: { color: success } }
            ]
          }]
        })
      }

      var wrongSubject = this.makeChart('wrongSubjectChart')
      if (wrongSubject) {
        var ws = this.stats.wrong_answers.by_subject
        wrongSubject.setOption({
          grid: { left: 40, right: 16, top: 16, bottom: 26 },
          tooltip: { trigger: 'axis' },
          xAxis: Object.assign({ type: 'category', data: ws.map(function (s) { return s.name }) }, axis),
          yAxis: Object.assign({ type: 'value', minInterval: 1 }, axis),
          series: [{
            type: 'bar',
            data: ws.map(function (s) { return s.value }),
            itemStyle: { color: accent, borderRadius: [4, 4, 0, 0] },
            barMaxWidth: 30
          }]
        })
      }
    }
  }
}
</script>

<style scoped>
.dashboard-page { max-width: 1100px; margin: 0 auto; }
.page-head { margin-bottom: 16px; }
.page-title { margin: 0 0 6px; font-size: 22px; color: var(--c-text); }
.page-sub { margin: 0; color: var(--c-text-2); font-size: 13px; }

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.stat-card { border-radius: 12px; text-align: center; padding: 10px 0; }
.stat-num { font-size: 26px; font-weight: 800; color: var(--c-primary); font-variant-numeric: tabular-nums; }
.stat-sub { font-size: 14px; font-weight: 400; color: var(--c-text-3); }
.stat-label { font-size: 13px; color: var(--c-text-2); margin-top: 2px; }

.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.chart-card { border-radius: 12px; }
.chart-title { font-size: 14px; font-weight: 600; color: var(--c-text); margin-bottom: 4px; }
.chart { height: 260px; width: 100%; }

.detail-card { border-radius: 12px; }
.detail-row { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-item { flex: 1; min-width: 110px; text-align: center; padding: 6px 0; }
.detail-item b { display: block; font-size: 20px; color: var(--c-text); }
.detail-item span { font-size: 12px; color: var(--c-text-3); }

@media (max-width: 900px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr; }
}
</style>
