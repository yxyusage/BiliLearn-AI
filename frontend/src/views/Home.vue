<template>
  <div class="home">
    <el-card class="hero-card" shadow="never">
      <h2 class="hero-title">视频输入 → 笔记生成 → 自测检验 → 薄弱复盘 → 体系化复习</h2>
      <p class="hero-sub">粘贴B站视频/合集链接，自动提取字幕，生成带时间戳的分学科结构化笔记</p>
      <div class="input-row">
        <el-input
          v-model="url"
          size="large"
          placeholder="例如：https://www.bilibili.com/video/BV1GJ411x7h7 或合集链接"
          clearable
          @keyup.enter="parseVideo"
        />
        <el-button type="primary" size="large" :loading="parsing" @click="parseVideo">解析视频</el-button>
      </div>
      <div class="subject-row">
        <span class="subject-label">课程类型：</span>
        <el-radio-group v-model="subject">
          <el-radio-button value="general">通用</el-radio-button>
          <el-radio-button value="english">英语</el-radio-button>
          <el-radio-button value="math">数理</el-radio-button>
          <el-radio-button value="cs">计算机</el-radio-button>
          <el-radio-button value="liberal">文科</el-radio-button>
        </el-radio-group>
        <span class="subject-desc">{{ subjectDesc }}</span>
      </div>
    </el-card>

    <el-card v-if="videoInfo" class="video-card" shadow="never">
      <div class="video-head">
        <div class="video-title">{{ videoInfo.title }}</div>
        <div class="video-meta">
          <el-tag size="small">{{ videoInfo.bvid }}</el-tag>
          <el-tag v-if="videoInfo.uploader" size="small" type="info">UP：{{ videoInfo.uploader }}</el-tag>
          <el-tag size="small" :type="videoInfo.subtitle_available ? 'success' : 'warning'">
            {{ videoInfo.subtitle_available ? '已获取字幕（' + videoInfo.subtitle_count + ' 条）' : '未检测到官方字幕' }}
          </el-tag>
        </div>
      </div>

      <el-alert
        v-if="videoInfo.hint"
        :title="videoInfo.hint"
        type="warning"
        :closable="false"
        show-icon
        style="margin: 10px 0"
      />

      <div v-if="videoInfo.pages && videoInfo.pages.length > 1" class="page-select">
        <span class="subject-label">合集共 {{ videoInfo.pages.length }} P，本次处理：</span>
        <el-select v-model="selectedPage" style="width: 340px" filterable>
          <el-option
            v-for="p in videoInfo.pages"
            :key="p.page"
            :label="p.page + '. ' + p.title"
            :value="p.page"
          />
        </el-select>
        <el-tag size="small" type="info" style="margin-left: 8px">单P处理模式</el-tag>
      </div>

      <div v-if="videoInfo.pages && videoInfo.pages.length > 1" class="batch-box">
        <span class="subject-label">📚 批量生成（后台异步逐集处理）：</span>
        <span class="subject-label">前</span>
        <el-input-number v-model="batchCount" :min="1" :max="videoInfo.pages.length" size="small" style="width: 110px" />
        <span class="subject-label">集 / 共 {{ videoInfo.pages.length }} 集</span>
        <el-button size="small" type="warning" :loading="batchStarting" @click="startBatch">开始批量生成</el-button>
        <span class="gen-tip">已生成的集自动复用缓存不重复计费；可关闭页面，在「合集任务」查看进度</span>
      </div>

      <el-collapse v-if="videoInfo.subtitles && videoInfo.subtitles.length" class="sub-collapse">
        <el-collapse-item :title="'字幕预览（共 ' + videoInfo.subtitle_count + ' 条，点击展开）'" name="subs">
          <div class="sub-list">
            <div v-for="(s, i) in videoInfo.subtitles" :key="i" class="sub-line">
              <span class="sub-time">{{ formatTime(s.start) }}</span>
              <span class="sub-text">{{ s.text }}</span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <div class="gen-row">
        <el-button
          type="success"
          size="large"
          :loading="generating"
          :disabled="!videoInfo.subtitle_available && !videoInfo.whisper_enabled"
          @click="generateNote"
        >
          生成{{ subjectName }}笔记
        </el-button>
        <span class="gen-tip">
          {{ videoInfo.subtitle_available ? '生成约需 1-5 分钟' : '已开启本地语音转写，将先转写再生成，耗时较长' }}
          ，可关闭页面，稍后从「历史笔记」查看
        </span>
      </div>
    </el-card>

    <el-card v-if="recentNotes.length" class="recent-card lift-card" shadow="never">
      <div class="recent-head">
        <h3>最近笔记</h3>
        <el-link type="primary" @click="$router.push('/history')">查看全部 →</el-link>
      </div>
      <div class="recent-list">
        <div v-for="n in recentNotes" :key="n.id" class="recent-item" @click="$router.push('/note/' + n.id)">
          <el-tag size="small" :type="n.status === 'done' ? 'success' : (n.status === 'failed' ? 'danger' : 'warning')">
            {{ n.status === 'done' ? '已完成' : (n.status === 'failed' ? '失败' : '生成中') }}
          </el-tag>
          <span class="recent-title">{{ n.title }}</span>
        </div>
      </div>
    </el-card>

    <el-card class="feature-card lift-card" shadow="never">
      <h3>核心能力</h3>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8" v-for="f in features" :key="f.title">
          <div class="feature-item">
            <div class="feature-icon">{{ f.icon }}</div>
            <div class="feature-title">{{ f.title }}</div>
            <div class="feature-desc">{{ f.desc }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import { secondsToHms } from '../utils/time'

export default {
  name: 'HomeView',
  created() {
    this.loadRecent()
  },
  data() {
    return {
      url: '',
      subject: 'general',
      parsing: false,
      generating: false,
      videoInfo: null,
      selectedPage: 1,
      recentNotes: [],
      batchCount: 3,
      batchStarting: false,
      features: [
        { icon: '⏱️', title: '全链路时间戳', desc: '知识点/公式/题目/错题全部绑定视频时间点，点击直达复习片段' },
        { icon: '🎓', title: '分学科模板', desc: '英语/数理/计算机/文科专属笔记逻辑，告别通用化总结' },
        { icon: '📝', title: '学习闭环', desc: '阶梯自测 → 错题本 → AI 薄弱复盘 → 艾宾浩斯复习计划' }
      ]
    }
  },
  computed: {
    subjectName() {
      var names = { general: '通用', english: '英语', math: '数理', cs: '计算机', liberal: '文科' }
      return names[this.subject] || '通用'
    },
    subjectDesc() {
      var descs = {
        general: '通用课程结构化笔记',
        english: '听力原文精校 + 生词提取 + 语音现象标注 + Anki 导出',
        math: '定理结构化整理 + 公式 LaTeX + 易错点辨析',
        cs: '代码片段提取 + 逻辑拆解 + 拓展练手',
        liberal: '核心概念 → 理论框架 → 案例分析 → 考点分级汇总'
      }
      return descs[this.subject] || ''
    }
  },
  methods: {
    formatTime(seconds) {
      return secondsToHms(seconds)
    },
    async loadRecent() {
      try {
        this.recentNotes = await api.get('/notes?limit=3')
      } catch (e) {
        this.recentNotes = []
      }
    },
    async parseVideo() {
      if (!this.url.trim()) {
        ElMessage.warning('请输入B站视频链接')
        return
      }
      this.parsing = true
      this.videoInfo = null
      try {
        var res = await api.post('/video/parse', { url: this.url.trim() })
        this.videoInfo = res
        this.selectedPage = res.pages && res.pages.length ? res.pages[0].page : 1
        if (res.subtitle_available) ElMessage.success('解析成功，已获取 ' + res.subtitle_count + ' 条字幕')
        else if (res.hint) ElMessage.warning(res.hint)
        else ElMessage.warning('解析成功，但未检测到官方字幕')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.parsing = false
      }
    },
    async generateNote() {
      this.generating = true
      try {
        var res = await api.post('/notes/generate', {
          bvid: this.videoInfo.bvid,
          page: this.selectedPage || 1,
          subject: this.subject,
          title: this.videoInfo.title || ''
        })
        this.$router.push({ path: '/note/' + res.id, query: { fresh: '1' } })
      } catch (e) {
        ElMessage.error(e.message)
        this.generating = false
      }
    },
    async startBatch() {
      this.batchStarting = true
      try {
        var res = await api.post('/collections/start', {
          bvid: this.videoInfo.bvid,
          subject: this.subject,
          max_pages: this.batchCount,
          title: this.videoInfo.title || ''
        })
        ElMessage.success('批量任务已启动，共 ' + res.total + ' 集')
        this.$router.push('/collections/' + res.id)
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.batchStarting = false
      }
    }
  }
}
</script>

<style scoped>
.hero-card { margin-bottom: 16px; border-radius: 16px; border: none; background: linear-gradient(135deg, #eef4ff 0%, #f6f1ff 100%); }
html.dark .hero-card { background: linear-gradient(135deg, #1a2233 0%, #221a30 100%); }
.hero-title { margin: 4px 0 8px; font-size: 20px; }
.hero-sub { color: #909399; margin: 0 0 16px; }
.input-row { display: flex; gap: 10px; }
.input-row .el-input { flex: 1; }
.subject-row { margin-top: 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.subject-label { color: #606266; font-size: 14px; }
.subject-desc { color: #909399; font-size: 12px; margin-left: 6px; }
.video-card { margin-bottom: 16px; }
.video-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.video-title { font-size: 16px; font-weight: 600; color: #303133; }
.video-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.page-select { margin: 12px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.batch-box { margin: 10px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; background: #fdf6ec; border: 1px solid #faecd8; border-radius: 8px; padding: 10px 12px; }
.sub-collapse { margin: 12px 0; }
.sub-list { max-height: 220px; overflow-y: auto; border: 1px solid #ebeef5; border-radius: 6px; padding: 6px 10px; background: #fafafa; }
.sub-line { display: flex; gap: 10px; padding: 2px 0; font-size: 13px; }
.sub-time { color: #409eff; flex-shrink: 0; font-family: monospace; }
.sub-text { color: #606266; }
.gen-row { margin-top: 16px; display: flex; align-items: center; }
.recent-card { margin-bottom: 16px; }
.recent-head { display: flex; align-items: center; justify-content: space-between; }
.recent-head h3 { margin: 0 0 10px; }
.recent-list { display: flex; flex-direction: column; gap: 6px; }
.recent-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; transition: background .15s; }
.recent-item:hover { background: #f5f7fa; }
.recent-title { font-size: 14px; color: #303133; }
.feature-card h3 { margin-top: 0; }
.feature-item { text-align: center; padding: 12px 6px; }
.feature-icon {
  width: 56px; height: 56px; border-radius: 50%;
  background: #eef4ff; display: flex; align-items: center; justify-content: center;
  margin: 0 auto 10px; font-size: 26px;
}
html.dark .feature-icon { background: #1d2a3a; }
.feature-title { font-weight: 600; margin: 6px 0; }
.feature-desc { color: #909399; font-size: 12px; line-height: 1.6; }
</style>
