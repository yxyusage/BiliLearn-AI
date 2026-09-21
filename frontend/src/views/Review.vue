<template>
  <div class="review-page" v-loading="loading">
    <div class="page-head">
      <h2 class="page-title">🧭 复习中心</h2>
      <p class="page-sub">按艾宾浩斯遗忘曲线安排复习节奏，错题自动归集，考前回来看看就够了。</p>
    </div>

    <div class="stat-row">
      <el-card shadow="never" class="stat-card stat-due" :class="{ pulse: dueCount > 0 }">
        <div class="stat-num">{{ dueCount }}</div>
        <div class="stat-label">今日待复习（含逾期）</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-wrong">
        <div class="stat-num">{{ activeWrong.length }}</div>
        <div class="stat-label">未掌握错题</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-done">
        <div class="stat-num">{{ doneCount }}</div>
        <div class="stat-label">已完成复习</div>
      </el-card>
    </div>

    <el-card shadow="never" class="panel-card">
      <el-tabs v-model="tab">
        <!-- 复习计划 -->
        <el-tab-pane name="plan">
          <template #label>📅 复习计划<span v-if="dueCount" class="tab-badge">{{ dueCount }}</span></template>
          <div class="panel-toolbar">
            <el-checkbox v-model="showAllPlan">显示全部（含未来安排与已完成）</el-checkbox>
            <el-button size="small" text @click="loadPlan">刷新</el-button>
          </div>
          <el-empty v-if="!plan.length" description="还没有复习计划，去笔记页点「生成复盘分析」即可自动安排" />
          <div v-else class="plan-list">
            <div
              v-for="item in shownPlan"
              :key="item.id"
              class="plan-item"
              :class="'plan-' + item.status"
            >
              <el-checkbox
                :model-value="item.done"
                :disabled="item.done"
                @change="toggleDone(item)"
              />
              <div class="plan-main">
                <div class="plan-content">{{ item.content }}</div>
                <div class="plan-meta">
                  <el-tag size="small" :type="statusTag(item.status)" effect="light">{{ statusLabel(item.status) }}</el-tag>
                  <span class="plan-note" @click="openNote(item)">📖 {{ item.note_title || '笔记 #' + item.note_id }}</span>
                  <span class="plan-date">到期 {{ item.due_date }}</span>
                </div>
              </div>
              <div class="plan-foot">
                <el-button size="small" type="primary" text @click="openNote(item)">去复习</el-button>
                <template v-if="!item.done">
                  <span class="rate-label">学完自评：</span>
                  <el-button-group size="small">
                    <el-button :disabled="ratingId === item.id" @click="rate(item, 1)">重来</el-button>
                    <el-button :disabled="ratingId === item.id" @click="rate(item, 2)">困难</el-button>
                    <el-button type="primary" plain :disabled="ratingId === item.id" @click="rate(item, 3)">良好</el-button>
                    <el-button type="success" plain :disabled="ratingId === item.id" @click="rate(item, 4)">简单</el-button>
                  </el-button-group>
                </template>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 全局错题本 -->
        <el-tab-pane name="wrong">
          <template #label>📝 错题本<span v-if="activeWrong.length" class="tab-badge danger">{{ activeWrong.length }}</span></template>
          <div class="panel-toolbar">
            <el-checkbox v-model="showMastered">包含已掌握</el-checkbox>
            <el-button size="small" text @click="loadWrong">刷新</el-button>
          </div>
          <el-empty v-if="!wrong.length" description="暂无错题记录，继续保持！" />
          <div v-else class="wrong-list">
            <div v-for="w in shownWrong" :key="w.id" class="wrong-item" :class="{ mastered: w.status === 'mastered' }">
              <div class="wrong-head">
                <el-tag size="small" type="danger" effect="plain">{{ qtypeName(w.qtype) }}</el-tag>
                <el-tag v-if="w.wrong_count > 1" size="small" type="warning" effect="dark">错 {{ w.wrong_count }} 次</el-tag>
                <el-tag v-if="w.status === 'mastered'" size="small" type="success" effect="plain">已掌握</el-tag>
                <span class="wrong-note" @click="openWrongNote(w)">📖 {{ w.note_title || '笔记 #' + w.note_id }}</span>
              </div>
              <div class="wrong-q"><b>题目：</b><LatexText :text="w.question" markdown /></div>
              <div class="wrong-a"><b>你的答案：</b><LatexText :text="w.user_answer || '（未作答）'" markdown /></div>
              <div class="wrong-a"><b>正确答案：</b><LatexText :text="w.correct_answer" markdown /></div>
              <div v-if="w.feedback" class="wrong-feedback"><b>讲解：</b><LatexText :text="w.feedback" markdown /></div>
              <div v-else-if="w.explanation" class="wrong-feedback"><b>解析：</b><LatexText :text="w.explanation" markdown /></div>
              <div class="wrong-foot">
                <el-button size="small" type="primary" plain @click="openWrongNote(w)">
                  🎬 {{ w.time_stamp ? '回到视频 ' + w.time_stamp : '打开笔记' }}
                </el-button>
                <el-button v-if="w.status !== 'mastered'" size="small" type="success" plain @click="master(w)">我已掌握</el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import { hmsToSeconds } from '../utils/time'
import LatexText from '../components/LatexText.vue'

export default {
  name: 'ReviewView',
  components: { LatexText },
  data() {
    return {
      loading: false,
      tab: 'plan',
      plan: [],
      wrong: [],
      showAllPlan: false,
      showMastered: false,
      ratingId: 0
    }
  },
  computed: {
    dueCount() {
      return this.plan.filter(function (p) { return p.status === 'overdue' || p.status === 'today' }).length
    },
    doneCount() {
      var today = new Date().toISOString().slice(0, 10)
      return this.plan.filter(function (p) { return p.done || p.last_reviewed === today }).length
    },
    shownPlan() {
      if (this.showAllPlan) return this.plan
      return this.plan.filter(function (p) { return p.status === 'overdue' || p.status === 'today' })
    },
    activeWrong() {
      return this.wrong.filter(function (w) { return w.status !== 'mastered' })
    },
    shownWrong() {
      if (this.showMastered) return this.wrong
      return this.activeWrong
    }
  },
  created() {
    this.loadPlan()
    this.loadWrong()
  },
  methods: {
    async loadPlan() {
      try {
        this.plan = await api.get('/review/plan?due_only=false')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async loadWrong() {
      this.loading = true
      try {
        this.wrong = await api.get('/quiz/wrong/all?active_only=0&limit=300')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    async rate(item, rating) {
      this.ratingId = item.id
      try {
        var res = await api.post('/review/plan/' + item.id + '/rate', { rating: rating })
        item.done = res.done
        item.due_date = res.due_date
        item.status = res.status
        item.last_reviewed = new Date().toISOString().slice(0, 10)
        var names = { 1: '重来', 2: '困难', 3: '良好', 4: '简单' }
        ElMessage.success('已按「' + names[rating] + '」重新排期：下次 ' + res.due_date + ' 复习')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.ratingId = 0
      }
    },
    async toggleDone(item) {
      try {
        var res = await api.post('/review/plan/' + item.id + '/toggle')
        item.done = res.done
        item.status = res.done ? 'done' : 'upcoming'
        ElMessage.success(res.done ? '已完成本次复习' : '已取消完成')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async master(w) {
      try {
        await api.post('/quiz/wrong/' + w.id + '/master')
        w.status = 'mastered'
        ElMessage.success('已标记掌握')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    openNote(item) {
      this.$router.push('/note/' + item.note_id)
    },
    openWrongNote(w) {
      var t = w.time_stamp ? hmsToSeconds(w.time_stamp) : 0
      this.$router.push('/note/' + w.note_id + (t > 0 ? '?t=' + t : ''))
    },
    statusLabel(s) {
      return { overdue: '已逾期', today: '今日到期', upcoming: '待复习', done: '已完成' }[s] || s
    },
    statusTag(s) {
      return { overdue: 'danger', today: 'warning', upcoming: 'info', done: 'success' }[s] || 'info'
    },
    qtypeName(t) {
      var names = { single: '单选题', judge: '判断题', fill: '填空题', calc: '计算题', proof: '思考卡' }
      return names[t] || '题目'
    }
  }
}
</script>

<style scoped>
.review-page { max-width: 960px; margin: 0 auto; }
.page-head { margin-bottom: 16px; }
.page-title { margin: 0 0 6px; font-size: 22px; color: var(--c-text); }
.page-sub { margin: 0; color: var(--c-text-2); font-size: 13px; }

.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px; }
.stat-card { border-radius: 12px; text-align: center; padding: 8px 0; }
.stat-num { font-size: 32px; font-weight: 800; line-height: 1.2; }
.stat-label { font-size: 13px; color: var(--c-text-2); margin-top: 4px; }
.stat-due .stat-num { color: var(--c-accent); }
.stat-wrong .stat-num { color: var(--c-danger); }
.stat-done .stat-num { color: var(--c-success); }
.stat-card.pulse { border-color: var(--c-accent-border); }

.panel-card { border-radius: 12px; }
.panel-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.tab-badge {
  display: inline-block; min-width: 18px; padding: 0 5px; margin-left: 5px;
  border-radius: 999px; background: var(--c-accent); color: #fff; font-size: 11px; line-height: 17px; text-align: center;
}
.tab-badge.danger { background: var(--c-danger); }

.plan-list { display: flex; flex-direction: column; gap: 8px; }
.plan-item {
  display: flex; align-items: center; gap: 12px;
  border: 1px solid var(--c-border-light); border-radius: 10px; padding: 10px 14px;
  background: var(--c-bg-elev);
}
.plan-item.plan-overdue { border-left: 4px solid var(--c-danger); }
.plan-item.plan-today { border-left: 4px solid var(--c-accent); }
.plan-item.plan-done { opacity: .62; }
.plan-main { flex: 1; min-width: 0; }
.plan-content { font-size: 14px; color: var(--c-text); margin-bottom: 4px; }
.plan-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--c-text-3); }
.plan-foot { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rate-label { font-size: 12px; color: var(--c-text-3); }
.plan-note { color: var(--c-primary); cursor: pointer; }
.plan-note:hover { text-decoration: underline; }

.wrong-list { display: flex; flex-direction: column; gap: 10px; }
.wrong-item {
  border-left: 3px solid var(--c-danger); background: var(--c-danger-soft);
  padding: 10px 14px; border-radius: 8px; font-size: 13px; line-height: 1.8;
}
.wrong-item.mastered { border-left-color: var(--c-success); opacity: .62; }
.wrong-head { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; flex-wrap: wrap; }
.wrong-note { color: var(--c-primary); cursor: pointer; font-size: 12px; margin-left: auto; }
.wrong-note:hover { text-decoration: underline; }
.wrong-q, .wrong-a { margin: 2px 0; color: var(--c-text); }
.wrong-feedback { margin-top: 2px; color: var(--c-text); }
.wrong-foot { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }

@media (max-width: 700px) {
  .stat-row { grid-template-columns: 1fr; }
}
</style>
