<template>
  <div class="quiz-card" :class="'q-' + (q.difficulty || 'basic')">
    <div class="q-head">
      <el-tag size="small" :type="tierType" effect="light">{{ tierLabel }}</el-tag>
      <span class="q-stem">{{ index + 1 }}. <LatexText :text="q.stem" /></span>
      <TimeLink v-if="q.time_stamp" :time="q.time_stamp" @jump="$emit('jump', q.time_stamp)" />
    </div>

    <div v-if="q.type === 'single' && q.options.length" class="q-options">
      <el-radio-group v-model="selected" :disabled="judged" :name="'quiz-' + index">
        <el-radio v-for="(opt, oi) in q.options" :key="oi" :value="opt" :name="'quiz-' + index" class="q-option">
          {{ opt }}
        </el-radio>
      </el-radio-group>
    </div>
    <div v-else class="q-text">
      <el-input
        v-model="textAnswer"
        type="textarea"
        :rows="2"
        resize="none"
        :disabled="judged"
        placeholder="写下你的答案/推导思路，点击「判断」让 AI 批改讲解"
      />
    </div>

    <div v-if="!judged" class="q-actions">
      <el-button size="small" type="primary" :loading="loading" :disabled="!canJudge" @click="judge">
        判断这道题
      </el-button>
      <span class="q-hint">{{ q.type === 'single' ? 'AI 会讲解每个选项的对错' : 'AI 会批改你的答案并讲解思路' }}</span>
    </div>

    <div v-if="judged" class="q-feedback" :class="correct ? 'ok' : 'no'">
      <div class="fb-head">
        <el-tag :type="correct ? 'success' : 'danger'" size="small">{{ correct ? '✓ 回答正确' : '✘ 回答错误' }}</el-tag>
        <span v-if="q.answer" class="fb-answer"><b>参考答案：</b>{{ q.answer }}</span>
      </div>
      <div v-if="feedback" class="fb-body">{{ feedback }}</div>
      <div v-if="q.knowledge_point" class="fb-kp"><b>知识点：</b>{{ q.knowledge_point }}</div>
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
    noteId: { type: Number, required: true }
  },
  emits: ['jump'],
  data() {
    return {
      selected: '',
      textAnswer: '',
      judged: false,
      correct: false,
      feedback: '',
      loading: false
    }
  },
  computed: {
    tierLabel() {
      var names = { basic: '基础', medium: '中档', advanced: '拔高' }
      return names[this.q.difficulty] || '基础'
    },
    tierType() {
      var types = { basic: 'info', medium: 'warning', advanced: 'danger' }
      return types[this.q.difficulty] || 'info'
    },
    canJudge() {
      if (this.q.type === 'single') return !!this.selected
      return !!(this.textAnswer || '').trim()
    }
  },
  methods: {
    async judge() {
      this.loading = true
      try {
        var res = await api.post('/quiz/judge', {
          note_id: this.noteId,
          stem: this.q.stem,
          qtype: this.q.type,
          options: this.q.options || [],
          answer: this.q.answer || '',
          user_answer: this.q.type === 'single' ? this.selected : (this.textAnswer || ''),
          explanation: this.q.explanation || '',
          knowledge_point: this.q.knowledge_point || '',
          difficulty: this.q.difficulty || '',
          time_stamp: this.q.time_stamp || ''
        })
        this.judged = true
        this.correct = res.correct
        this.feedback = res.feedback || ''
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.quiz-card {
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
  background: #fff;
  transition: box-shadow .2s;
}
.quiz-card:hover { box-shadow: 0 4px 14px rgba(31, 45, 61, 0.06); }
.q-basic { border-left: 4px solid #909399; }
.q-medium { border-left: 4px solid #e6a23c; }
.q-advanced { border-left: 4px solid #f56c6c; }
.q-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 10px; }
.q-stem { flex: 1; line-height: 1.7; color: #303133; font-size: 14px; }
.q-options { margin: 4px 0 6px; }
.q-option { display: block; margin: 6px 0; }
.q-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.q-hint { color: #909399; font-size: 12px; }
.q-feedback { border-radius: 8px; padding: 10px 12px; margin-top: 10px; }
.q-feedback.ok { background: #f0f9eb; border: 1px solid #e1f3d8; }
.q-feedback.no { background: #fef0f0; border: 1px solid #fde2e2; }
.fb-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.fb-answer { font-size: 13px; color: #606266; }
.fb-body { font-size: 13px; line-height: 1.8; color: #303133; white-space: pre-wrap; }
.fb-kp { margin-top: 6px; font-size: 12px; color: #909399; }
</style>
