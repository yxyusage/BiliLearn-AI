<template>
  <div class="dict-card">
    <div class="dc-head">
      <span class="dc-no">{{ index + 1 }}</span>
      <el-button size="small" circle type="primary" plain title="听这句原声" @click="$emit('jump', item.time_stamp)">🔊</el-button>
      <span v-if="item.time_stamp" class="dc-time">{{ item.time_stamp }}</span>
      <span class="dc-tip">先听原声，再填写挖空的词</span>
    </div>

    <div class="dc-stem">
      <template v-for="(seg, i) in segments" :key="'s' + i">
        <span>{{ seg }}</span>
        <el-input
          v-if="i < blankCount"
          v-model="answers[i]"
          :disabled="revealed"
          class="dc-input"
          :class="slotClass(i)"
          size="small"
          :placeholder="'第 ' + (i + 1) + ' 空'"
          @keyup.enter="check"
        />
      </template>
    </div>

    <div v-if="!revealed" class="dc-actions">
      <el-button size="small" type="primary" :loading="loading" :disabled="!hasInput" @click="check">
        提交听写
      </el-button>
      <span class="dc-hint">填空即时判分，大小写、标点差异都不算错</span>
    </div>

    <div v-else class="dc-feedback" :class="correct ? 'ok' : 'no'">
      <el-tag :type="correct ? 'success' : 'danger'" size="small">
        {{ correct ? '✓ 全对' : '✘ 有错，对照下面的答案再听一遍' }}
      </el-tag>
      <div class="dc-answer">
        <b>参考答案：</b><span v-html="displayAnswer"></span>
      </div>
      <div v-if="item.translation" class="dc-line">💬 翻译：{{ item.translation }}</div>
      <div v-if="item.hint" class="dc-line">📌 {{ item.hint }}</div>
      <div class="dc-retry">
        <el-button link type="primary" size="small" @click="reset">再听一次</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'DictationCard',
  props: {
    item: { type: Object, required: true },
    noteId: { type: Number, required: true },
    index: { type: Number, default: 0 }
  },
  emits: ['jump', 'answered'],
  data() {
    return {
      answers: [],
      revealed: false,
      correct: false,
      perBlank: null,
      feedback: '',
      loading: false
    }
  },
  created() {
    this.answers = this.segments.slice(0, -1).map(function () { return '' })
  },
  computed: {
    segments() {
      return String(this.item.stem || '').split(/_{3,}/)
    },
    blankCount() {
      return Math.max(0, this.segments.length - 1)
    },
    hasInput() {
      return this.answers.some(function (a) { return (a || '').trim() })
    },
    displayAnswer() {
      var blanks = String(this.item.answer || '').split('|')
      var out = blanks.map(function (b, i) { return '第' + (i + 1) + '空：' + b.trim() })
      return out.join('<br/>')
    }
  },
  methods: {
    slotClass(i) {
      if (!this.revealed || !this.perBlank) return ''
      return this.perBlank[i] ? 'dc-right' : 'dc-wrong'
    },
    async check() {
      this.loading = true
      try {
        var res = await api.post('/quiz/judge', {
          note_id: this.noteId,
          stem: this.item.stem,
          qtype: 'fill',
          options: [],
          answer: this.item.answer || '',
          user_answer: JSON.stringify(this.answers.map(function (a) { return (a || '').trim() })),
          explanation: this.item.hint || '',
          difficulty: 'basic',
          time_stamp: this.item.time_stamp || ''
        })
        this.revealed = true
        this.correct = !!res.correct
        this.perBlank = res.per_blank || null
        this.feedback = res.feedback || ''
        this.$emit('answered', { correct: this.correct })
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.answers = this.segments.slice(0, -1).map(function () { return '' })
      this.revealed = false
      this.perBlank = null
      this.correct = false
    }
  }
}
</script>

<style scoped>
.dict-card {
  border: 1px solid var(--c-border); border-radius: 10px;
  padding: 12px 16px; margin-bottom: 12px; background: var(--c-bg-elev);
}
.dc-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.dc-no {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 20px; height: 20px; padding: 0 6px; border-radius: 6px;
  background: var(--c-primary); color: #fff; font-size: 12px; font-weight: 700;
}
html.dark .dc-no { color: #08231f; }
.dc-time { font-family: monospace; font-size: 12px; color: var(--c-text-3); }
.dc-tip { font-size: 12px; color: var(--c-text-3); }
.dc-stem { display: flex; align-items: center; flex-wrap: wrap; line-height: 2.2; font-size: 15px; color: var(--c-text); }
.dc-input { width: 130px; margin: 0 5px; vertical-align: middle; }
.dc-input.dc-right :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--c-success) inset; background: var(--c-success-soft); }
.dc-input.dc-wrong :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--c-danger) inset; background: var(--c-danger-soft); }
.dc-actions { margin-top: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.dc-hint { font-size: 12px; color: var(--c-text-3); }
.dc-feedback { border-radius: 8px; padding: 10px 12px; margin-top: 10px; font-size: 13px; line-height: 1.8; }
.dc-feedback.ok { background: var(--c-success-soft); border: 1px solid var(--c-success); }
.dc-feedback.no { background: var(--c-danger-soft); border: 1px solid var(--c-danger); }
.dc-answer { margin-top: 6px; color: var(--c-text); }
.dc-line { margin-top: 4px; color: var(--c-text-2); }
.dc-retry { margin-top: 4px; text-align: right; }
</style>
