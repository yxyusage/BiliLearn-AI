<template>
  <div class="note-detail" v-loading="loading">
    <!-- 生成中 -->
    <div v-if="status === 'processing'" class="status-box">
      <el-result icon="info" title="AI 正在生成笔记">
        <template #sub-title>
          <p class="stage-text">{{ stageText || '正在初始化...' }}</p>
          <p class="stage-tip">通常需要 1-5 分钟（无字幕转写会更久）。进度按实际耗时计算，切换页面/刷新后再回来也不会重置。</p>
          <el-progress :percentage="progressPercent" />
        </template>
        <template #extra>
          <el-button @click="$router.push('/history')">去历史笔记查看</el-button>
        </template>
      </el-result>
    </div>

    <!-- 失败 -->
    <div v-else-if="status === 'failed'" class="status-box">
      <el-result icon="error" title="笔记生成失败">
        <template #sub-title><p class="err-text">{{ error }}</p></template>
        <template #extra>
          <el-button type="primary" :loading="retrying" @click="retryGenerate">重新生成</el-button>
          <el-popconfirm title="删除这条失败记录？" @confirm="deleteNote">
            <template #reference>
              <el-button type="danger" plain>删除记录</el-button>
            </template>
          </el-popconfirm>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </template>
      </el-result>
    </div>

    <!-- 完成 -->
    <template v-else-if="status === 'done'">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-radio-group v-model="layoutMode" size="small">
            <el-radio-button value="split">左右分栏</el-radio-button>
            <el-radio-button value="top">视频置顶</el-radio-button>
          </el-radio-group>
          <span v-if="layoutMode === 'split'" class="drag-tip">↔ 拖动中间分隔条调整视频宽度</span>
        </div>
        <div class="toolbar-actions">
          <el-button size="small" @click="download('markdown')">导出 Markdown</el-button>
          <el-button size="small" @click="download('pdf')">导出 PDF</el-button>
          <el-button v-if="hasWords" size="small" @click="download('anki')">Anki 卡片</el-button>
          <el-button v-if="hasWords" size="small" @click="download('anki.csv')">CSV</el-button>
          <el-button size="small" type="primary" plain @click="chatVisible = true">💬 AI 答疑</el-button>
        </div>
      </div>

      <div ref="splitLayout" class="layout" :class="[layoutMode, { dragging: dragging }]">
        <div class="video-panel" :style="videoPanelStyle">
          <div class="sticky-video">
            <VideoPlayer ref="player" :bvid="bvid" :page="page" />
            <div class="meta-line">
              <el-tag size="small" type="info" effect="plain">{{ bvid }}</el-tag>
              <span class="note-title">{{ title }}</span>
            </div>
          </div>
        </div>

        <div v-if="layoutMode === 'split'" class="split-divider" @mousedown="startDrag">
          <div class="divider-dot">⠿</div>
        </div>

        <div class="content-panel">
          <el-card shadow="never" class="tabs-card">
            <el-tabs v-model="activeTab">
              <!-- 笔记 + 内嵌自测 -->
              <el-tab-pane label="笔记" name="note">
                <div v-if="summary" class="summary-box"><LatexText :text="summary" /></div>

                <div v-if="chapters.length > 1" class="chapter-nav">
                  <span class="chapter-nav-label">📑 目录：</span>
                  <el-tag
                    v-for="(ch, ci) in chapters"
                    :key="ci"
                    size="small"
                    class="chapter-nav-item"
                    @click="scrollToChapter(ci)"
                  >{{ ci + 1 }}. {{ ch.title }}</el-tag>
                </div>

                <div v-if="!quizQuestions.length" class="quiz-entry">
                  <el-button size="small" type="primary" :loading="quizGenerating" @click="generateQuiz">
                    ✨ 生成本课自测题（嵌入各章节，逐题 AI 批改）
                  </el-button>
                  <span class="gen-tip">生成后每道题带「判断」按钮，AI 立即批改讲解</span>
                </div>

                <div v-for="(ch, ci) in chapters" :key="ci" :id="'chapter-' + ci" class="chapter">
                  <h3 class="chapter-title">{{ ch.title }}</h3>
                  <div v-for="(p, pi) in ch.points" :key="pi" class="point" :class="{ important: p.important }">
                    <TimeLink v-if="p.time_stamp" :time="p.time_stamp" @jump="jump" />
                    <LatexText class="point-content" :text="p.content" />
                    <el-tag v-if="p.important" size="small" type="danger" effect="dark">重点</el-tag>
                  </div>
                  <div v-if="chapterQuestions[ci] && chapterQuestions[ci].length" class="chapter-quiz">
                    <div class="chapter-quiz-head">📝 本章自测（{{ chapterQuestions[ci].length }} 题）</div>
                    <QuizCard
                      v-for="q in chapterQuestions[ci]"
                      :key="q.index"
                      :q="q"
                      :index="q.index"
                      :note-id="noteId"
                      @jump="jump"
                    />
                  </div>
                </div>
                <div v-if="unmatchedQuestions.length" class="chapter-quiz">
                  <div class="chapter-quiz-head">📝 综合自测（{{ unmatchedQuestions.length }} 题）</div>
                  <QuizCard
                    v-for="q in unmatchedQuestions"
                    :key="q.index"
                    :q="q"
                    :index="q.index"
                    :note-id="noteId"
                    @jump="jump"
                  />
                </div>
              </el-tab-pane>

              <!-- 思维导图 -->
              <el-tab-pane label="思维导图" name="mindmap">
                <MermaidView v-if="mindmap" :code="mindmap" @node-click="jumpBySeconds" />
                <el-empty v-else description="本次生成未输出脑图" />
              </el-tab-pane>

              <!-- 公式板书（数理/计算机专项） -->
              <el-tab-pane label="公式板书" name="formulas">
                <div v-if="!formulasList.length" class="formula-entry">
                  <el-empty description="提取视频关键帧，AI 识别板书/课件公式并转为 LaTeX">
                    <div class="formula-gen">
                      <el-select v-model="visionProvider" size="small" style="width: 200px">
                        <el-option label="通义千问 qwen-vl-plus" value="qwen" />
                        <el-option label="Kimi 视觉模型" value="kimi" />
                      </el-select>
                      <el-button type="primary" size="small" :loading="formulasLoading" @click="generateFormulas">
                        提取板书公式
                      </el-button>
                    </div>
                    <p class="gen-tip">需要视觉模型 Key（通义千问免费额度可用 qwen-vl-plus），首次需下载视频流，约 1-3 分钟</p>
                  </el-empty>
                </div>
                <div v-else class="formula-box">
                  <div class="formula-toolbar">
                    <el-button size="small" :loading="formulasLoading" @click="generateFormulas">重新提取</el-button>
                    <span class="gen-tip">识别到 {{ formulasList.length }} 条公式，LaTeX 可直接复制到 Typora/Word/Overleaf</span>
                  </div>
                  <el-row :gutter="12">
                    <el-col v-for="(img, ii) in formulaImages" :key="ii" :xs="12" :sm="8" :md="6">
                      <div class="frame-card">
                        <el-image :src="img" fit="contain" :preview-src-list="formulaImages" :initial-index="ii" class="frame-img" />
                        <div class="frame-label">关键帧 {{ ii + 1 }}</div>
                      </div>
                    </el-col>
                  </el-row>
                  <div v-if="formulaNotes.length" class="formula-notes">
                    <span class="fn-label">📌 板书要点：</span>
                    <el-tag v-for="(n, ni) in formulaNotes" :key="ni" size="small" effect="plain" class="fn-tag">{{ n }}</el-tag>
                  </div>
                  <div v-for="(f, fi) in formulasList" :key="fi" class="formula-card">
                    <div class="formula-latex"><LatexText :text="f.latex" display /></div>
                    <div v-if="f.description" class="formula-desc">{{ f.description }}</div>
                    <el-button size="small" text type="primary" @click="copyLatex(f.latex)">复制 LaTeX</el-button>
                  </div>
                </div>
              </el-tab-pane>

              <!-- 生词（英语专项） -->
              <el-tab-pane v-if="subject === 'english'" label="生词" name="words">
                <div v-if="wordList.length">
                  <el-table :data="wordList" size="small">
                    <el-table-column label="单词" width="130">
                      <template #default="scope"><b>{{ scope.row.word }}</b></template>
                    </el-table-column>
                    <el-table-column label="音标" width="130">
                      <template #default="scope">{{ scope.row.phonetic }}</template>
                    </el-table-column>
                    <el-table-column label="释义" min-width="140">
                      <template #default="scope">{{ scope.row.meaning }}</template>
                    </el-table-column>
                    <el-table-column label="原句" min-width="200">
                      <template #default="scope">{{ scope.row.sentence }}</template>
                    </el-table-column>
                    <el-table-column label="时间" width="120">
                      <template #default="scope">
                        <TimeLink v-if="scope.row.time_stamp" :time="scope.row.time_stamp" @jump="jump" />
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-if="pronList.length" class="pron-box">
                    <h4>语音现象（连读 / 弱读 / 失去爆破）</h4>
                    <div v-for="(p, pi) in pronList" :key="pi" class="pron-item">
                      <el-tag size="small" type="warning">{{ p.phenomenon }}</el-tag>
                      <span class="pron-sentence">{{ p.sentence }}</span>
                      <TimeLink v-if="p.time_stamp" :time="p.time_stamp" @jump="jump" />
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无生词数据" />
              </el-tab-pane>

              <!-- 复盘 -->
              <el-tab-pane label="复盘" name="review">
                <div v-if="wrongList.length" class="wrong-box">
                  <h4>错题本（{{ wrongList.length }}）</h4>
                  <div v-for="(w, wi) in wrongList" :key="wi" class="wrong-item">
                    <div><b>题目：</b>{{ w.question }}</div>
                    <div><b>你的答案：</b>{{ w.user_answer || '（未作答）' }}</div>
                    <div><b>正确答案：</b>{{ w.correct_answer }}</div>
                    <div v-if="w.feedback" class="wrong-feedback"><b>AI 讲解：</b>{{ w.feedback }}</div>
                    <div v-if="w.time_stamp" class="weak-line">
                      <b>对应视频片段：</b>
                      <TimeLink :time="w.time_stamp" @jump="jump" />
                    </div>
                  </div>
                </div>

                <div v-if="!reviewData">
                  <el-empty description="基于错题生成薄弱点分析与复习计划">
                    <el-button type="primary" :loading="reviewLoading" @click="generateReview">生成复盘分析</el-button>
                  </el-empty>
                </div>
                <div v-else>
                  <el-alert
                    v-if="reviewData.summary"
                    :title="reviewData.summary"
                    type="success"
                    :closable="false"
                    show-icon
                    style="margin-bottom: 12px"
                  />
                  <div v-if="reviewData.weak_points && reviewData.weak_points.length">
                    <h4>薄弱知识点</h4>
                    <div v-for="(w, wi) in reviewData.weak_points" :key="wi" class="weak-item">
                      <div class="weak-head">
                        <span class="weak-point">{{ w.point }}</span>
                        <el-tag
                          :type="w.priority === 'high' ? 'danger' : (w.priority === 'medium' ? 'warning' : 'info')"
                          size="small"
                        >{{ priorityName(w.priority) }}</el-tag>
                      </div>
                      <div v-if="w.reason" class="weak-line"><b>错题表现：</b>{{ w.reason }}</div>
                      <div v-if="w.suggestion" class="weak-line"><b>复习建议：</b>{{ w.suggestion }}</div>
                      <div v-if="w.replay_timestamps && w.replay_timestamps.length" class="weak-line">
                        <b>复习片段：</b>
                        <TimeLink
                          v-for="(t, ti) in w.replay_timestamps"
                          :key="ti"
                          :time="t"
                          @jump="jump"
                        />
                      </div>
                    </div>
                  </div>
                  <el-alert
                    v-else
                    title="暂无错题记录，继续保持！"
                    type="success"
                    :closable="false"
                    show-icon
                    style="margin-bottom: 12px"
                  />
                  <h4 v-if="planList.length">艾宾浩斯复习计划</h4>
                  <el-table v-if="planList.length" :data="planList" size="small">
                    <el-table-column prop="content" label="复习内容" min-width="160" />
                    <el-table-column prop="due_date" label="复习日期" width="120" />
                    <el-table-column label="状态" width="90">
                      <template #default="scope">
                        <el-checkbox :model-value="scope.row.done" @change="togglePlan(scope.row)">完成</el-checkbox>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </div>
      </div>

      <!-- AI 答疑抽屉 -->
      <el-drawer v-model="chatVisible" title="💬 AI 答疑（基于本笔记）" size="440px">
        <div class="chat-wrap">
          <div class="chat-actions">
            <el-button size="small" text @click="clearChat">清空对话</el-button>
          </div>
          <div ref="chatBody" class="chat-body">
            <div v-if="!chatMessages.length" class="chat-empty">
              <p>针对这份笔记提问，例如：</p>
              <el-tag
                v-for="(s, si) in quickQuestions"
                :key="si"
                class="quick-q"
                effect="plain"
                @click="quickAsk(s)"
              >{{ s }}</el-tag>
            </div>
            <div v-for="(m, i) in chatMessages" :key="i" class="chat-msg" :class="m.role">
              <div class="chat-bubble">
                <template v-if="m.role === 'assistant'">
                  <template v-for="(part, pi) in parseAssistant(m.content)" :key="pi">
                    <div v-if="part.type === 'text'" class="chat-text" v-html="part.html"></div>
                    <MermaidView v-else :code="part.code" compact />
                  </template>
                </template>
                <template v-else>{{ m.content }}</template>
              </div>
            </div>
            <div v-if="chatLoading" class="chat-msg assistant">
              <div class="chat-bubble typing">思考中...</div>
            </div>
          </div>
          <div class="chat-input">
            <el-input
              v-model="chatInput"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="输入你的问题，回车发送"
              @keydown.enter.exact.prevent="sendChat"
            />
            <el-button type="primary" :loading="chatLoading" @click="sendChat">发送</el-button>
          </div>
        </div>
      </el-drawer>
    </template>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import { hmsToSeconds } from '../utils/time'
import { renderMarkdownLite } from '../utils/latex'
import VideoPlayer from '../components/VideoPlayer.vue'
import MermaidView from '../components/MermaidView.vue'
import QuizCard from '../components/QuizCard.vue'
import TimeLink from '../components/TimeLink.vue'
import LatexText from '../components/LatexText.vue'

export default {
  name: 'NoteDetailView',
  components: { VideoPlayer, MermaidView, QuizCard, TimeLink, LatexText },
  data() {
    return {
      noteId: 0,
      loading: false,
      timer: null,
      startedAt: 0,
      tick: 0,
      stageText: '',
      status: 'pending',
      error: '',
      retrying: false,
      bvid: '',
      page: 1,
      title: '',
      subject: 'general',
      summary: '',
      chapters: [],
      mindmap: '',
      activeTab: 'note',
      // 布局
      layoutMode: 'split',
      leftWidth: 52,
      dragging: false,
      // 自测
      quizQuestions: [],
      chapterQuestions: [],
      unmatchedQuestions: [],
      quizGenerating: false,
      wrongList: [],
      // 生词
      wordList: [],
      pronList: [],
      // 公式板书
      formulasList: [],
      formulaImages: [],
      formulaNotes: [],
      formulasLoading: false,
      visionProvider: 'qwen',
      // 复盘
      reviewData: null,
      reviewLoading: false,
      planList: [],
      // 答疑
      chatVisible: false,
      chatMessages: [],
      chatInput: '',
      chatLoading: false,
      jumpedQuery: false,
      quickQuestions: [
        '这段视频主要讲了什么？',
        '帮我总结重点，并划出考点',
        '用更通俗的方式解释第一个知识点'
      ]
    }
  },
  computed: {
    progressPercent() {
      var t = this.elapsedSeconds
      var transcribing = this.stageText.indexOf('转写') >= 0
      if (transcribing) return Math.min(35, 5 + Math.round(t / 2))
      return Math.min(90, 35 + Math.round(t / 3))
    },
    elapsedSeconds() {
      if (this.startedAt) {
        return Math.max(0, Math.floor((Date.now() - this.startedAt) / 1000))
      }
      return this.tick
    },
    hasWords() {
      return this.subject === 'english' && this.wordList.length > 0
    },
    videoPanelStyle() {
      if (this.layoutMode === 'split') return { width: this.leftWidth + '%' }
      return {}
    }
  },
  created() {
    this.noteId = Number(this.$route.params.id)
    var saved = localStorage.getItem('bililearn-layout')
    if (saved === 'top' || saved === 'split') this.layoutMode = saved
    var w = parseFloat(localStorage.getItem('bililearn-video-width'))
    if (w >= 30 && w <= 75) this.leftWidth = w
    this.load()
  },
  beforeUnmount() {
    this.stopPolling()
    this.stopDrag()
  },
  methods: {
    async load() {
      this.loading = true
      try {
        var data = await api.get('/notes/' + this.noteId)
        this.applyNote(data)
        if (data.status === 'processing') this.startPolling()
        else this.stopPolling()
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    applyNote(data) {
      this.status = data.status
      this.error = data.error || ''
      if (data.status === 'processing' && data.error) this.stageText = data.error
      if (data.created_at) {
        var iso = String(data.created_at)
        if (iso.indexOf('+') < 0 && !iso.endsWith('Z')) iso += 'Z'
        var ts = new Date(iso).getTime()
        if (!isNaN(ts)) this.startedAt = ts
      }
      this.bvid = data.bvid
      this.page = data.page
      this.title = data.title
      this.subject = data.subject
      this.summary = data.summary
      this.mindmap = data.mindmap
      var note = data.note || {}
      this.chapters = note.chapters || []
      this.quizQuestions = ((data.quizzes && data.quizzes.questions) || []).map(function (q, i) {
        return Object.assign({ index: i }, q)
      })
      this.assignQuestions()
      var words = data.words || {}
      this.wordList = words.words || []
      this.pronList = words.pronunciations || []
      var formulas = data.formulas || {}
      this.formulasList = formulas.formulas || []
      this.formulaNotes = formulas.notes || []
      this.reviewData = (data.review && data.review.weak_points !== undefined) ? data.review : null
      this.planList = (this.reviewData && this.reviewData.plan) ? this.reviewData.plan : []
      if (data.status === 'done') {
        this.loadWrong()
        if (!this.jumpedQuery) {
          this.jumpedQuery = true
          var t = parseFloat(this.$route.query.t)
          if (t > 0) this.jumpBySeconds(t)
        }
      }
    },
    assignQuestions() {
      var self = this
      this.chapterQuestions = this.chapters.map(function () { return [] })
      this.unmatchedQuestions = []
      this.quizQuestions.forEach(function (q) {
        if (!q.time_stamp) { self.unmatchedQuestions.push(q); return }
        var sec = hmsToSeconds(q.time_stamp)
        var best = -1
        var bestDist = Infinity
        for (var i = 0; i < self.chapters.length; i++) {
          var pts = (self.chapters[i] && self.chapters[i].points) || []
          if (!pts.length) continue
          var first = hmsToSeconds(pts[0].time_stamp)
          var last = hmsToSeconds(pts[pts.length - 1].time_stamp)
          if (sec >= first && sec <= last) { best = i; break }
          var d = Math.min(Math.abs(sec - first), Math.abs(sec - last))
          if (d < bestDist) { bestDist = d; best = i }
        }
        if (best >= 0) self.chapterQuestions[best].push(q)
        else self.unmatchedQuestions.push(q)
      })
    },
    scrollToChapter(ci) {
      var el = document.getElementById('chapter-' + ci)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    startPolling() {
      if (this.timer) return
      this.timer = setInterval(this.poll, 3000)
    },
    stopPolling() {
      if (this.timer) {
        clearInterval(this.timer)
        this.timer = null
      }
    },
    async poll() {
      try {
        var st = await api.get('/notes/' + this.noteId + '/status')
        if (st.status === 'done') {
          this.stopPolling()
          await this.load()
        } else if (st.status === 'failed') {
          this.stopPolling()
          this.status = 'failed'
          this.error = st.error || ''
        } else {
          this.tick += 3
          if (st.error) this.stageText = st.error
        }
      } catch (e) {
        /* 忽略轮询错误 */
      }
    },
    async loadWrong() {
      try {
        this.wrongList = await api.get('/quiz/' + this.noteId + '/wrong')
      } catch (e) {
        this.wrongList = []
      }
    },
    jump(hms) {
      if (this.$refs.player) this.$refs.player.jumpTo(hmsToSeconds(hms))
    },
    jumpBySeconds(sec) {
      if (this.$refs.player) this.$refs.player.jumpTo(sec)
    },
    download(type) {
      window.open('/api/export/' + this.noteId + '/' + type, '_blank')
    },
    async retryGenerate() {
      if (!this.bvid) return
      this.retrying = true
      try {
        var res = await api.post('/notes/generate', {
          bvid: this.bvid,
          page: this.page || 1,
          subject: this.subject || 'general',
          title: this.title || ''
        })
        this.$router.replace('/note/' + res.id)
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.retrying = false
      }
    },
    async deleteNote() {
      try {
        await api.delete('/notes/' + this.noteId)
        ElMessage.success('已删除')
        this.$router.push('/history')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async generateQuiz() {
      this.quizGenerating = true
      try {
        var res = await api.post('/quiz/generate', { note_id: this.noteId })
        this.quizQuestions = (res.questions || []).map(function (q, i) {
          return Object.assign({ index: i }, q)
        })
        this.assignQuestions()
        ElMessage.success('已生成 ' + this.quizQuestions.length + ' 道自测题，嵌入各章节下方')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.quizGenerating = false
      }
    },
    async generateFormulas() {
      this.formulasLoading = true
      try {
        var res = await api.post('/notes/' + this.noteId + '/formulas', { provider: this.visionProvider })
        this.formulasList = res.formulas || []
        this.formulaImages = res.images || []
        this.formulaNotes = res.notes || []
        if (this.formulasList.length) ElMessage.success('已识别 ' + this.formulasList.length + ' 条公式')
        else ElMessage.warning('关键帧中未识别到公式（该视频可能以动画/口述为主）')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.formulasLoading = false
      }
    },
    async copyLatex(text) {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success('LaTeX 已复制')
      } catch (e) {
        ElMessage.error('复制失败')
      }
    },
    async generateReview() {
      this.reviewLoading = true
      try {
        var res = await api.post('/review/analyze', { note_id: this.noteId })
        this.reviewData = res
        this.planList = res.plan || []
        ElMessage.success('复盘分析完成')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.reviewLoading = false
      }
    },
    async togglePlan(row) {
      try {
        var res = await api.post('/review/plan/' + row.id + '/toggle')
        row.done = res.done
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    priorityName(p) {
      var names = { high: '高优先级', medium: '中优先级', low: '低优先级' }
      return names[p] || p
    },
    // 拖拽分栏
    startDrag(e) {
      e.preventDefault()
      this.dragging = true
      document.addEventListener('mousemove', this.onDrag)
      document.addEventListener('mouseup', this.stopDrag)
    },
    onDrag(e) {
      var el = this.$refs.splitLayout
      if (!el) return
      var rect = el.getBoundingClientRect()
      var pct = ((e.clientX - rect.left) / rect.width) * 100
      this.leftWidth = Math.min(75, Math.max(30, Math.round(pct)))
    },
    stopDrag() {
      if (!this.dragging) return
      this.dragging = false
      document.removeEventListener('mousemove', this.onDrag)
      document.removeEventListener('mouseup', this.stopDrag)
      localStorage.setItem('bililearn-video-width', String(this.leftWidth))
      localStorage.setItem('bililearn-layout', this.layoutMode)
    },
    // AI 答疑
    async sendChat() {
      var msg = (this.chatInput || '').trim()
      if (!msg || this.chatLoading) return
      this.chatInput = ''
      this.chatMessages.push({ role: 'user', content: msg })
      this.chatLoading = true
      this.scrollChatBottom()
      try {
        var history = this.chatMessages.slice(-9, -1)
        var res = await api.post('/notes/' + this.noteId + '/chat', { message: msg, history: history })
        this.chatMessages.push({ role: 'assistant', content: res.reply })
      } catch (e) {
        this.chatMessages.push({ role: 'assistant', content: '⚠️ ' + e.message })
      } finally {
        this.chatLoading = false
        this.scrollChatBottom()
      }
    },
    quickAsk(text) {
      this.chatInput = text
      this.sendChat()
    },
    parseAssistant(content) {
      var fence = String.fromCharCode(96)
      var regex = new RegExp(fence + 'mermaid\\n([\\s\\S]*?)' + fence, 'g')
      var parts = []
      var last = 0
      var m
      while ((m = regex.exec(content))) {
        if (m.index > last) parts.push({ type: 'text', html: renderMarkdownLite(content.slice(last, m.index)) })
        parts.push({ type: 'mermaid', code: m[1].trim() })
        last = m.index + m[0].length
      }
      if (last < content.length) parts.push({ type: 'text', html: renderMarkdownLite(content.slice(last)) })
      if (!parts.length) parts.push({ type: 'text', html: renderMarkdownLite(content) })
      return parts
    },
    clearChat() {
      this.chatMessages = []
      this.chatInput = ''
    },
    scrollChatBottom() {
      var self = this
      this.$nextTick(function () {
        if (self.$refs.chatBody) self.$refs.chatBody.scrollTop = self.$refs.chatBody.scrollHeight
      })
    }
  },
  watch: {
    layoutMode(val) {
      localStorage.setItem('bililearn-layout', val)
    }
  }
}
</script>

<style scoped>
.status-box { max-width: 560px; margin: 60px auto; }
.stage-text { color: #409eff; font-weight: 600; }
.stage-tip { color: #909399; font-size: 13px; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  margin-bottom: 12px; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px; padding: 8px 14px;
}
.toolbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.drag-tip { color: #909399; font-size: 12px; }

/* 布局：分栏模式下笔记面板独立滚动，视频面板固定不动 */
.layout.split {
  display: flex; align-items: stretch;
  height: calc(100vh - 162px); overflow: hidden;
}
.layout.top { display: block; }
.layout.dragging { user-select: none; }
.video-panel { min-width: 0; }
.layout.split .video-panel {
  flex-shrink: 0; padding-right: 10px;
  height: 100%; overflow-y: auto;
}
.layout.top .video-panel {
  position: sticky; top: 0; z-index: 20; background: #f2f4f8;
  padding: 8px 0 4px; margin-bottom: 12px;
}
.layout.top .sticky-video { max-width: 900px; margin: 0 auto; }
.meta-line { margin: 10px 0 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.note-title { font-size: 15px; font-weight: 600; color: #303133; }

.split-divider {
  flex-shrink: 0; width: 16px; cursor: col-resize;
  display: flex; align-items: center; justify-content: center;
  position: relative; color: #909399; user-select: none; align-self: stretch;
}
.split-divider::before {
  content: ''; position: absolute; left: 7px; top: 0; bottom: 0;
  width: 2px; background: #dcdfe6; border-radius: 2px;
  transition: background .15s;
}
.split-divider:hover::before,
.layout.dragging .split-divider::before { background: #409eff; }
.divider-dot {
  position: relative; z-index: 1;
  width: 22px; height: 28px; border-radius: 8px;
  background: #fff; border: 1px solid #dcdfe6;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: #909399; cursor: col-resize;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .1); transition: all .15s;
}
.layout.dragging .divider-dot,
.split-divider:hover .divider-dot { border-color: #409eff; color: #409eff; }

.content-panel { flex: 1; min-width: 0; }
.layout.split .content-panel { height: 100%; overflow-y: auto; padding: 2px 6px 24px 2px; }
.content-panel::-webkit-scrollbar { width: 8px; }
.content-panel::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 4px; }
.content-panel::-webkit-scrollbar-thumb:hover { background: #c0c4cc; }
html.dark .content-panel::-webkit-scrollbar-thumb { background: #3d4148; }
.tabs-card { border-radius: 10px; }

/* 笔记 */
.summary-box {
  background: #ecf5ff; border-left: 4px solid #409eff;
  padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; color: #303133;
}
.chapter-nav { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chapter-nav-label { font-size: 13px; color: #606266; }
.chapter-nav-item { cursor: pointer; transition: all .15s; }
.chapter-nav-item:hover { color: #409eff; border-color: #409eff; }
.chapter { margin-bottom: 22px; }
.chapter-title { margin: 8px 0; font-size: 16px; border-left: 3px solid #409eff; padding-left: 8px; }
.point { display: flex; align-items: flex-start; gap: 6px; padding: 6px 4px; border-bottom: 1px dashed #ebeef5; }
.point.important { background: #fdf6ec; border-radius: 4px; }
.point-content { flex: 1; line-height: 1.8; }
.quiz-entry { margin-bottom: 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.chapter-quiz { margin: 10px 0 6px; }
.chapter-quiz-head {
  font-size: 13px; font-weight: 600; color: #409eff;
  background: #ecf5ff; border-radius: 6px; padding: 6px 10px; margin-bottom: 10px;
}

/* 公式板书 */
.formula-entry { padding: 8px 0; }
.formula-gen { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.formula-toolbar { margin-bottom: 14px; display: flex; align-items: center; flex-wrap: wrap; }
.frame-card { margin-bottom: 10px; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; }
.frame-img { width: 100%; height: 110px; background: #000; }
.frame-label { padding: 4px 8px; font-size: 12px; color: #909399; text-align: center; }
.formula-card {
  background: #fafcff; border: 1px solid #e4e7ed; border-left: 3px solid #409eff;
  border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;
}
.formula-latex {
  font-family: 'Cambria Math', 'Times New Roman', serif;
  font-size: 15px; color: #1f2d3d; overflow-x: auto; white-space: pre-wrap;
  word-break: break-all; margin-bottom: 6px;
}
.formula-desc { font-size: 13px; color: #606266; line-height: 1.7; }
.formula-notes { margin: 10px 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.fn-label { font-size: 13px; color: #606266; }
.fn-tag { cursor: default; }

/* 生词 */
.pron-box { margin-top: 20px; }
.pron-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px dashed #ebeef5; flex-wrap: wrap; }
.pron-sentence { color: #606266; flex: 1; min-width: 200px; }

/* 复盘 */
.wrong-box { margin-bottom: 20px; }
.wrong-item {
  border-left: 3px solid #f56c6c; background: #fef0f0; padding: 10px 12px;
  margin-bottom: 10px; border-radius: 4px; font-size: 13px; line-height: 1.8;
}
.wrong-feedback { margin-top: 4px; color: #303133; }
.weak-item { border: 1px solid #ebeef5; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.weak-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.weak-point { font-weight: 600; }
.weak-line { font-size: 13px; line-height: 1.8; color: #606266; }
h4 { margin: 16px 0 8px; }

/* 答疑抽屉 */
:deep(.el-drawer__body) { height: 100%; padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.chat-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 2px 16px 14px; }
.chat-actions { display: flex; justify-content: flex-end; margin-bottom: 4px; flex-shrink: 0; }
.chat-body { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 4px; }
.chat-empty { color: #909399; font-size: 13px; line-height: 2; padding: 12px; }
.quick-q { cursor: pointer; margin: 4px 6px 4px 0; }
.chat-msg { display: flex; margin-bottom: 10px; }
.chat-msg.user { justify-content: flex-end; }
.chat-bubble {
  max-width: 86%; min-width: 0; padding: 9px 12px; border-radius: 10px; font-size: 13px; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word; overflow-x: auto;
}
.chat-msg.user .chat-bubble { background: #409eff; color: #fff; border-bottom-right-radius: 2px; }
.chat-msg.assistant .chat-bubble { background: #f4f4f5; color: #303133; border-bottom-left-radius: 2px; }
.chat-bubble.typing { color: #909399; }
.chat-text { line-height: 1.7; }
.chat-bubble .mermaid-view { margin: 6px 0; }
.chat-input { display: flex; gap: 8px; align-items: flex-end; padding-top: 10px; border-top: 1px solid #ebeef5; flex-shrink: 0; }
.chat-input .el-textarea { flex: 1; }

/* 窄屏自动降级为视频置顶 */
@media (max-width: 900px) {
  .layout.split { flex-direction: column; height: auto; overflow: visible; }
  .layout.split .video-panel { width: 100% !important; position: static; padding-right: 0; height: auto; overflow: visible; }
  .layout.split .content-panel { height: auto; overflow: visible; }
  .split-divider { display: none; }
}
</style>
