<template>
  <div class="quiz-card" :class="'q-' + (q.difficulty || 'basic')">
    <div class="q-head">
      <el-tag size="small" :type="tierType" effect="light">{{ tierLabel }}</el-tag>
      <el-tag size="small" effect="plain" type="info">{{ typeLabel }}</el-tag>
      <span v-if="q.type !== 'fill'" class="q-stem">{{ index + 1 }}. <LatexText :text="q.stem" /></span>
      <TimeLink v-if="q.time_stamp" :time="q.time_stamp" @jump="$emit('jump', q.time_stamp)" />
    </div>

    <div v-if="q.type === 'fill'" class="q-fill">
      <div class="q-stem fill-stem">
        <span class="fill-no">{{ index + 1 }}.</span>
        <template v-for="(seg, i) in stemSegments" :key="'seg' + i">
          <LatexText :text="seg" />
          <el-input
            v-if="i < blankCount"
            v-model="fillAnswers[i]"
            :disabled="revealed"
            class="fill-input"
            :class="slotClass(i)"
            size="small"
            :placeholder="'第 ' + (i + 1) + ' 空'"
            @keyup.enter="checkFill"
          />
        </template>
      </div>
    </div>

    <div v-if="q.type === 'single' && q.options.length" class="q-options">
      <div
        v-for="(opt, oi) in q.options"
        :key="oi"
        class="quiz-option-card"
        :class="[optionClass(optionKey(oi)), {selected: selected === optionKey(oi)}]"
        @click="!revealed && (selected = optionKey(oi))"
      >
        <span class="quiz-option-label">{{ optionKey(oi) }}</span>
        <span class="quiz-option-text"><LatexText :text="opt" /></span>
      </div>
    </div>

    <div v-else-if="q.type === 'judge'" class="q-options">
      <div
        class="quiz-option-card"
        :class="[optionClass('正确'), {selected: selected === '正确'}]"
        @click="!revealed && (selected = '正确')"
      >
        <span class="quiz-option-label">✓</span>
        <span class="quiz-option-text">正确</span>
      </div>
      <div
        class="quiz-option-card"
        :class="[optionClass('错误'), {selected: selected === '错误'}]"
        @click="!revealed && (selected = '错误')"
      >
        <span class="quiz-option-label">✗</span>
        <span class="quiz-option-text">错误</span>
      </div>
    </div>

    <div v-else class="q-text">
      <el-input
        v-model="textAnswer"
        type="textarea"
        :rows="3"
        resize="none"
        :disabled="revealed && q.type === 'calc'"
        :placeholder="q.type === 'proof' ? '先自己想一想、写一写（可以留空），再点开参考答案对照' : '写下你的答案或推导过程，点击「AI 批改」'"
      />
    </div>

    <div v-if="!revealed" class="q-actions">
      <el-button
        v-if="q.type === 'single' || q.type === 'judge'"
        size="small" type="primary" :disabled="!selected" @click="checkLocal"
      >提交答案</el-button>
      <el-button
        v-else-if="q.type === 'fill'"
        size="small" type="primary" :loading="loading"
        :disabled="!fillHasInput" @click="checkFill"
      >提交答案</el-button>
      <el-button
        v-else-if="q.type === 'calc'"
        size="small" type="primary" :loading="loading"
        :disabled="!(textAnswer || '').trim()" @click="judgeCalc"
      >AI 批改</el-button>
      <el-button
        v-else
        size="small" type="primary" plain @click="revealThink"
      >查看参考答案</el-button>
      <span class="q-hint">{{ actionHint }}</span>
      <el-button v-if="showVariant && q.type !== 'proof'" size="small" text type="primary" @click="$emit('variant', q)">✨ 变式题</el-button>
    </div>

    <div v-if="revealed && q.type !== 'proof'" class="q-feedback" :class="correct ? 'ok' : 'no'">
      <div class="fb-head">
        <el-tag :type="correct ? 'success' : 'danger'" size="small">
          {{ correct ? '✓ 回答正确' : '✘ 回答错误' }}
        </el-tag>
        <span v-if="q.answer" class="fb-answer">
          <b>参考答案：</b><LatexText :text="displayAnswer" />
        </span>
      </div>
      <div v-if="feedback" class="fb-body">
        <LatexText :text="feedback" markdown />
      </div>
      <div v-else-if="q.explanation" class="fb-body">
        <LatexText :text="q.explanation" markdown />
      </div>
      <div v-if="q.knowledge_point" class="fb-kp"><b>知识点：</b>{{ q.knowledge_point }}</div>
      <div class="fb-retry">
        <el-button link type="primary" size="small" @click="reset">再做一次</el-button>
      </div>
    </div>

    <div v-if="thinkShown" class="q-feedback think">
      <div class="think-title">📖 参考答案</div>
      <div v-if="q.answer" class="think-answer"><LatexText :text="q.answer" markdown /></div>
      <div v-if="q.explanation" class="think-explain">
        <b>解析：</b><LatexText :text="q.explanation" markdown />
      </div>
      <div v-if="q.knowledge_point" class="fb-kp"><b>知识点：</b>{{ q.knowledge_point }}</div>
      <div v-if="!assessed" class="think-actions">
        <span class="think-tip">对照后给自己评个价（不会自动判分）：</span>
        <el-button size="small" type="success" @click="selfAssess(true)">我掌握了</el-button>
        <el-button size="small" type="danger" plain @click="selfAssess(false)">还没掌握，加入错题本</el-button>
      </div>
      <div v-else class="think-done">
        <el-tag :type="assessedCorrect ? 'success' : 'warning'" size="small">
          {{ assessedCorrect ? '已标记掌握' : '已加入错题本，可在错题本中标记掌握' }}
        </el-tag>
        <el-button link type="primary" size="small" @click="reset">再想一次</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import TimeLink from './TimeLink.vue'
import LatexText from './LatexText.vue'

export default {
  name: 'QuizCard',
  components: { TimeLink, LatexText },
  props: {
    q: { type: Object, required: true },
    index: { type: Number, default: 0 },
    noteId: { type: Number, required: true },
    showVariant: { type: Boolean, default: false }
  },
  emits: ['jump', 'answered', 'variant'],
  data() {
    return {
      selected: '',
      textAnswer: '',
      fillAnswers: [],
      fillPerBlank: null,
      revealed: false,
      thinkShown: false,
      correct: false,
      feedback: '',
      loading: false,
      assessed: false,
      assessedCorrect: false
    }
  },
  created() {
    if (this.q.type === 'fill') {
      this.fillAnswers = this.stemSegments.slice(0, -1).map(function () { return '' })
    }
  },
  computed: {
    stemSegments() {
      return String(this.q.stem || '').split(/_{3,}/)
    },
    blankCount() {
      return Math.max(0, this.stemSegments.length - 1)
    },
    fillHasInput() {
      return this.fillAnswers.some(function (a) { return (a || '').trim() })
    },
    tierLabel() {
      var names = { basic: '基础', medium: '中档', advanced: '拔高' }
      return names[this.q.difficulty] || '基础'
    },
    tierType() {
      var types = { basic: 'info', medium: 'warning', advanced: 'danger' }
      return types[this.q.difficulty] || 'info'
    },
    typeLabel() {
      var names = { single: '单选题', judge: '判断题', fill: '填空题', calc: '计算题', proof: '思考卡' }
      return names[this.q.type] || '题目'
    },
    actionHint() {
      if (this.q.type === 'single' || this.q.type === 'judge') return '提交后即时判分，答错自动进入错题本'
      if (this.q.type === 'fill') return '填完提交即时判分，等价写法（如英文大小写）也判对'
      if (this.q.type === 'calc') return 'AI 会批改你的计算过程并讲解'
      return '先自己作答，再对照参考答案'
    },
    displayAnswer() {
      if (this.q.type === 'single' && this.q.options.length) {
        var idx = (this.q.answer || '').charCodeAt(0) - 65
        if (idx >= 0 && idx < this.q.options.length) return this.q.answer + '. ' + this.q.options[idx]
      }
      if (this.q.type === 'fill') {
        var blanks = String(this.q.answer || '').split('|')
        return blanks.map(function (b, i) {
          return '第' + (i + 1) + '空：' + b.trim()
        }).join('；')
      }
      return this.q.answer
    }
  },
  methods: {
    optionKey(i) {
      return String.fromCharCode(65 + i)
    },
    optionClass(key) {
      if (!this.revealed) return ''
      if (key === this.q.answer) return 'correct'
      if (key === this.selected && this.selected !== this.q.answer) return 'wrong'
      return ''
    },
    async record(correct) {
      try {
        await api.post('/quiz/record', {
          note_id: this.noteId,
          answers: [{
            qtype: this.q.type,
            question: this.q.stem,
            user_answer: this.q.type === 'single' || this.q.type === 'judge'
              ? (this.selected || '（未作答）') : (this.textAnswer || '（未作答）'),
            correct_answer: this.q.answer || '',
            explanation: this.q.explanation || '',
            feedback: this.feedback || '',
            difficulty: this.q.difficulty || '',
            time_stamp: this.q.time_stamp || '',
            correct: correct
          }]
        })
        this.$emit('answered', { correct: !!correct })
      } catch (e) {
        // 记录失败不影响答题体验
        console.warn('record failed', e)
      }
    },
    checkLocal() {
      if (this.q.type === 'single') {
        this.correct = this.selected === this.q.answer
      } else {
        this.correct = this.selected === this.q.answer
      }
      this.revealed = true
      this.feedback = this.q.explanation || ''
      this.record(this.correct)
    },
    async judgeCalc() {
      this.loading = true
      try {
        var res = await api.post('/quiz/judge', {
          note_id: this.noteId,
          stem: this.q.stem,
          qtype: 'calc',
          options: [],
          answer: this.q.answer || '',
          user_answer: this.textAnswer || '',
          explanation: this.q.explanation || '',
          knowledge_point: this.q.knowledge_point || '',
          difficulty: this.q.difficulty || '',
          time_stamp: this.q.time_stamp || ''
        })
        this.revealed = true
        this.correct = !!res.correct
        this.feedback = res.feedback || this.q.explanation || ''
        this.$emit('answered', { correct: !!res.correct })
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.loading = false
      }
    },
    slotClass(i) {
      if (!this.revealed || !this.fillPerBlank) return ''
      return this.fillPerBlank[i] ? 'slot-right' : 'slot-wrong'
    },
    async checkFill() {
      this.loading = true
      try {
        var answers = this.fillAnswers.map(function (a) { return (a || '').trim() })
        var res = await api.post('/quiz/judge', {
          note_id: this.noteId,
          stem: this.q.stem,
          qtype: 'fill',
          options: [],
          answer: this.q.answer || '',
          user_answer: JSON.stringify(answers),
          explanation: this.q.explanation || '',
          knowledge_point: this.q.knowledge_point || '',
          difficulty: this.q.difficulty || '',
          time_stamp: this.q.time_stamp || ''
        })
        this.revealed = true
        this.correct = !!res.correct
        this.fillPerBlank = res.per_blank || null
        this.feedback = res.feedback || this.q.explanation || ''
        this.$emit('answered', { correct: !!res.correct })
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.loading = false
      }
    },
    revealThink() {
      this.thinkShown = true
    },
    async selfAssess(mastered) {
      this.assessed = true
      this.assessedCorrect = mastered
      await this.record(mastered)
    },
    reset() {
      this.selected = ''
      this.textAnswer = ''
      this.fillAnswers = this.q.type === 'fill'
        ? this.stemSegments.slice(0, -1).map(function () { return '' })
        : []
      this.fillPerBlank = null
      this.revealed = false
      this.thinkShown = false
      this.correct = false
      this.feedback = ''
      this.assessed = false
      this.assessedCorrect = false
    }
  }
}
</script>

<style scoped>
.quiz-card {
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
  background: var(--c-bg-elev);
  transition: box-shadow .2s;
}
.quiz-card:hover { box-shadow: 0 4px 14px rgba(31, 45, 61, 0.06); }
.q-basic { border-left: 4px solid var(--c-text-3); }
.q-medium { border-left: 4px solid var(--c-accent); }
.q-advanced { border-left: 4px solid var(--c-danger); }
.q-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.q-stem { flex: 1; min-width: 200px; line-height: 1.7; color: var(--c-text); font-size: 14px; }
.q-options { margin: 4px 0 6px; }
.q-option { display: flex; align-items: flex-start; margin: 6px 0; padding: 4px 8px; border-radius: 6px; }
.opt-key { font-weight: 600; margin-right: 2px; }
.q-option.opt-right { background: var(--c-success-soft); }
.q-option.opt-wrong { background: var(--c-danger-soft); }
.q-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.q-hint { color: var(--c-text-3); font-size: 12px; }
.q-feedback { border-radius: 8px; padding: 10px 12px; margin-top: 10px; }
.q-feedback.ok { background: var(--c-success-soft); border: 1px solid var(--c-success); }
.q-feedback.no { background: var(--c-danger-soft); border: 1px solid var(--c-danger); }
.q-feedback.think { background: var(--c-bg-soft); border: 1px solid var(--c-border); }
.fb-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.fb-answer { font-size: 13px; color: var(--c-text-2); }
.fb-body { font-size: 13px; line-height: 1.8; color: var(--c-text); }
.fb-kp { margin-top: 6px; font-size: 12px; color: var(--c-text-3); }
.fb-retry { margin-top: 4px; text-align: right; }
.think-title { font-weight: 600; color: var(--c-primary); margin-bottom: 6px; }
.think-answer { font-size: 14px; line-height: 1.8; color: var(--c-text); }
.think-explain { margin-top: 6px; font-size: 13px; line-height: 1.8; color: var(--c-text-2); }
.think-actions { margin-top: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.think-tip { font-size: 12px; color: var(--c-text-3); }
.think-done { margin-top: 10px; display: flex; align-items: center; gap: 12px; }
.q-fill { margin: 4px 0 6px; }
.fill-stem { display: flex; align-items: center; flex-wrap: wrap; line-height: 2.2; }
.fill-no { font-weight: 600; margin-right: 6px; color: var(--c-text); }
.fill-input { width: 124px; margin: 0 5px; vertical-align: middle; }
.fill-input.slot-right :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--c-success) inset; background: var(--c-success-soft); }
.fill-input.slot-wrong :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--c-danger) inset; background: var(--c-danger-soft); }

/* 手机端刷题：选项大按钮、点击热区 ≥44px，减少打字 */
@media (max-width: 768px) {
  .quiz-card { padding: 12px; margin-bottom: 12px; }
  .q-stem { font-size: 15px; min-width: 0; }
  .q-options :deep(.el-radio) {
    display: flex; align-items: center;
    padding: 12px 12px; margin: 8px 0; min-height: 48px;
    border: 1px solid var(--c-border); border-radius: 10px;
    background: var(--c-bg-elev); width: 100%;
  }
  .q-options :deep(.el-radio__label) { flex: 1; font-size: 15px; line-height: 1.5; }
  .q-options :deep(.el-radio__input) { flex-shrink: 0; }
  .q-option.opt-right { background: var(--c-success-soft); border-color: var(--c-success); }
  .q-option.opt-wrong { background: var(--c-danger-soft); border-color: var(--c-danger); }
  .fill-input { width: 130px; }
  .q-actions :deep(.el-button) { min-height: 40px; }
}
</style>
