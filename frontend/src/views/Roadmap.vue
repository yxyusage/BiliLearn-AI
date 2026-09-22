<template>
  <div class="roadmap-page">
    <div class="rp-header">
      <h2>🗺️ 合集学习线路图</h2>
      <p class="rp-sub">粘贴 B站合集/番剧链接，AI 帮你把几十集拆成知识模块、标注重难点，再根据你的水平推荐从哪开始看</p>
    </div>

    <el-card v-if="!preview" class="rp-input-card" shadow="never">
      <el-input v-model="url" placeholder="粘贴 B站合集/视频链接，如 https://www.bilibili.com/video/BVxxxx" size="large" />
      <el-button type="primary" size="large" :loading="loading" @click="doPreview">解析分P列表</el-button>
    </el-card>

    <div v-if="preview && !jobId" class="rp-pick">
      <el-alert :title="preview.title + '（共 ' + preview.total + ' 集）'" type="success" :closable="false" />
      <div class="rp-pick-row">
        <span>从第</span>
        <el-input-number v-model="startPage" :min="1" :max="preview.total" size="small" style="width:90px" />
        <span>集到第</span>
        <el-input-number v-model="endPage" :min="1" :max="preview.total" size="small" style="width:90px" />
        <span>集（0 = 到最后）</span>
        <el-button type="primary" :loading="loading" @click="startAnalyze">生成路线图（{{ rangeLabel }}）</el-button>
      </div>
      <div class="rp-eps-preview">
        <div v-for="p in preview.pages" :key="p.page" class="rp-ep-item">
          <span class="rp-ep-no">P{{ p.page }}</span>
          <span>{{ p.title }}</span>
        </div>
      </div>
      <el-button text @click="reset">换个链接</el-button>
    </div>

    <div v-if="jobId" class="rp-body">
      <el-alert v-if="status === 'running'" :title="'正在解析第 ' + doneCount + ' / ' + total + ' 集…'" type="info" :closable="false" />
      <el-alert v-if="status === 'failed'" :title="'生成失败：' + error" type="error" :closable="false" />

      <template v-if="status === 'done'">
        <el-card shadow="never" class="rp-overview">
          <b>📚 {{ result.title || title }}</b>
          <p v-if="result.overview" class="rp-ov-text">{{ result.overview }}</p>
        </el-card>

        <div v-for="m in (result.modules || [])" :key="m.name" class="rp-module">
          <div class="rp-module-head">📦 {{ m.name }}</div>
          <div class="rp-eps">
            <div v-for="e in m.episodes" :key="e.page" class="rp-ep" :class="'tag-' + e.tag">
              <span class="rp-ep-no">P{{ e.page }}</span>
              <span class="rp-ep-title">{{ e.title }}</span>
              <span class="rp-ep-tag">{{ tagLabel(e.tag) }}</span>
              <span v-if="e.reason" class="rp-ep-reason">{{ e.reason }}</span>
            </div>
          </div>
        </div>

        <el-divider />

        <div v-if="!quiz.length" class="rp-quiz-entry">
          <el-button type="primary" plain :loading="quizLoading" @click="genQuiz">🧪 测测我的水平（5题）</el-button>
        </div>

        <template v-else>
          <div class="rp-quiz">
            <h3>诊断题</h3>
            <div v-for="(q, i) in quiz" :key="i" class="rp-q">
              <div class="rp-q-stem">{{ i + 1 }}. {{ q.question }}</div>
              <el-radio-group v-model="answers[i]">
                <el-radio v-for="(opt, j) in q.options" :key="j" :value="opt.charAt(0)">{{ opt }}</el-radio>
              </el-radio-group>
            </div>
            <el-button type="primary" :loading="recLoading" @click="submitQuiz">提交并推荐起点</el-button>
          </div>
        </template>

        <el-alert v-if="recommend.level" :closable="false" class="rp-rec" type="success">
          <b>你的水平：{{ recommend.level }}</b>
          <div v-if="recommend.start_from && recommend.start_from.length">从这些集开始：P{{ recommend.start_from.join(', P') }}</div>
          <div v-if="recommend.skip && recommend.skip.length">可跳过：P{{ recommend.skip.join(', P') }}</div>
          <div v-if="recommend.advice">{{ recommend.advice }}</div>
        </el-alert>

        <div class="rp-actions">
          <el-button @click="reset">分析另一个合集</el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'RoadmapView',
  data() {
    return {
      url: '', loading: false,
      preview: null, startPage: 1, endPage: 0,
      jobId: null, status: '', total: 0, doneCount: 0, error: '', title: '',
      result: {}, quiz: [], answers: {}, recommend: {},
      quizLoading: false, recLoading: false, timer: null
    }
  },
  computed: {
    rangeLabel() {
      if (!this.preview) return ''
      const s = this.startPage, e = this.endPage || this.preview.total
      return 'P' + s + ' - P' + e
    }
  },
  beforeUnmount() { if (this.timer) clearInterval(this.timer) },
  mounted() {
    const saved = localStorage.getItem('roadmap_job')
    if (saved) {
      this.jobId = parseInt(saved)
      this.status = 'running'
      this.poll()
    }
  },
  methods: {
    tagLabel(t) { return { prereq: '前置必学', core: '重点', optional: '可跳过' }[t] || t },
    async doPreview() {
      if (!this.url) { ElMessage.warning('请粘贴链接'); return }
      this.loading = true
      try {
        const r = await api.post('/roadmap/preview', { url: this.url })
        this.preview = r
        this.startPage = 1
        this.endPage = Math.min(r.total, 20)
      } catch (e) { ElMessage.error(e.message) }
      finally { this.loading = false }
    },
    async startAnalyze() {
      this.loading = true
      try {
        const r = await api.post('/roadmap/analyze', { url: this.url, start_page: this.startPage, end_page: this.endPage })
        this.jobId = r.id
        localStorage.setItem('roadmap_job', String(r.id))
        this.status = 'running'
        this.poll()
      } catch (e) { ElMessage.error(e.message) }
      finally { this.loading = false }
    },
    poll() {
      this.timer = setInterval(async () => {
        try {
          const r = await api.get('/roadmap/' + this.jobId)
          this.status = r.status
          this.total = r.total
          this.doneCount = r.done_count
          this.error = r.error
          this.title = r.title
          if (r.result) this.result = r.result
          if (r.quiz) this.quiz = r.quiz
          if (r.recommend) this.recommend = r.recommend
          if (this.status === 'done' || this.status === 'failed') { clearInterval(this.timer); localStorage.removeItem('roadmap_job') }
        } catch (e) { clearInterval(this.timer) }
      }, 2500)
    },
    async genQuiz() {
      this.quizLoading = true
      try {
        const r = await api.post('/roadmap/' + this.jobId + '/quiz')
        this.quiz = r.quiz
      } catch (e) { ElMessage.error(e.message) }
      finally { this.quizLoading = false }
    },
    async submitQuiz() {
      this.recLoading = true
      try {
        const answers = this.quiz.map((q, i) => ({ page: i, correct: this.answers[i] === q.answer }))
        const r = await api.post('/roadmap/' + this.jobId + '/recommend', { answers })
        this.recommend = r.recommend
      } catch (e) { ElMessage.error(e.message) }
      finally { this.recLoading = false }
    },
    async generateNotes() {
      try {
        const bvid = this.preview ? this.preview.bvid : ''
        if (!bvid) { ElMessage.warning('缺少视频信息'); return }
        const res = await api.post('/collections/start', {
          bvid: bvid,
          subject: 'general',
          start_page: this.startPage,
          end_page: this.endPage,
          title: this.title || ''
        })
        ElMessage.success('批量笔记任务已启动，共 ' + res.total + ' 集')
        this.$router.push('/collections/' + res.id)
      } catch (e) { ElMessage.error(e.message) }
    },
    reset() {
      if (this.timer) clearInterval(this.timer)
      this.jobId = null; this.url = ''; this.preview = null; this.result = {}; this.quiz = []; this.answers = {}; this.recommend = {}; localStorage.removeItem('roadmap_job')
    }
  }
}
</script>

<style scoped>
.roadmap-page { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.rp-header h2 { margin: 0 0 6px; font-size: 22px; }
.rp-sub { color: var(--c-text-3); font-size: 13px; margin: 0 0 18px; }
.rp-input-card :deep(.el-input) { margin-bottom: 12px; }
.rp-pick { margin-top: 16px; }
.rp-pick-row { display: flex; align-items: center; gap: 8px; margin: 14px 0; flex-wrap: wrap; font-size: 14px; }
.rp-eps-preview { max-height: 300px; overflow-y: auto; border: 1px solid var(--c-border); border-radius: 8px; padding: 8px; margin-bottom: 12px; }
.rp-ep-item { display: flex; gap: 10px; padding: 4px 8px; font-size: 13px; }
.rp-ep-no { font-weight: 700; color: var(--c-primary); min-width: 36px; }
.rp-body { margin-top: 16px; }
.rp-overview { margin-bottom: 16px; }
.rp-ov-text { margin: 6px 0 0; color: var(--c-text-2); font-size: 14px; line-height: 1.7; }
.rp-module { margin-bottom: 16px; }
.rp-module-head { font-weight: 700; font-size: 15px; margin-bottom: 8px; color: var(--c-primary); }
.rp-eps { display: flex; flex-direction: column; gap: 6px; }
.rp-ep { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--c-border); background: var(--c-bg-elev); }
.rp-ep.tag-prereq { border-left: 3px solid #909399; }
.rp-ep.tag-core { border-left: 3px solid var(--c-danger); }
.rp-ep.tag-optional { border-left: 3px solid var(--c-text-3); opacity: 0.85; }
.rp-ep-no { font-weight: 700; font-size: 13px; color: var(--c-primary); min-width: 40px; }
.rp-ep-title { flex: 1; font-size: 14px; }
.rp-ep-tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--c-bg-soft); color: var(--c-text-2); white-space: nowrap; }
.rp-ep-reason { font-size: 12px; color: var(--c-text-3); flex-basis: 100%; padding-left: 50px; }
.rp-quiz-entry { margin: 20px 0; }
.rp-q { margin-bottom: 16px; }
.rp-q-stem { font-weight: 600; margin-bottom: 8px; line-height: 1.6; }
.rp-rec { margin-top: 16px; }
.rp-actions { margin-top: 20px; text-align: center; }

@media (max-width: 768px) {
  .roadmap-page { padding: 12px 10px; }
  .rp-header h2 { font-size: 18px; }
  .rp-sub { font-size: 12px; }
  .rp-pick-row { gap: 6px; font-size: 13px; }
  .rp-pick-row .el-button { width: 100%; margin-top: 4px; }
  .rp-eps-preview { max-height: 200px; }
  .rp-ep-item { font-size: 12px; padding: 3px 6px; }
  .rp-ep { flex-wrap: wrap; padding: 8px 10px; }
  .rp-ep-no { min-width: 32px; font-size: 12px; }
  .rp-ep-title { font-size: 13px; flex-basis: 100%; order: 3; padding-left: 32px; }
  .rp-ep-tag { font-size: 10px; padding: 1px 6px; }
  .rp-ep-reason { padding-left: 0; font-size: 11px; }
  .rp-module-head { font-size: 14px; }
  .rp-q-stem { font-size: 14px; }
  .rp-quiz .el-radio { display: block; margin: 6px 0; padding: 8px; border: 1px solid var(--c-border); border-radius: 8px; }
  .rp-quiz .el-button { width: 100%; }
}
</style>
