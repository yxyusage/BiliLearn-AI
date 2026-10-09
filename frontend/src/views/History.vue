<template>
  <div class="history">
    <el-card shadow="never">
      <div class="history-head">
        <div class="history-filters">
          <el-input v-model="searchKeyword" size="small" placeholder="搜索笔记标题/摘要" style="width: 200px" clearable @input="onSearch" />
          <el-select v-model="subjectFilter" size="small" style="width: 110px" @change="load">
            <el-option label="全部学科" value="all" />
            <el-option label="通用" value="general" />
            <el-option label="英语" value="english" />
            <el-option label="数理" value="math" />
            <el-option label="计算机" value="cs" />
            <el-option label="文科" value="liberal" />
          </el-select>
          <el-radio-group v-model="statusFilter" size="small" @change="load">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="done">已完成</el-radio-button>
            <el-radio-button value="processing">生成中</el-radio-button>
            <el-radio-button value="failed">失败</el-radio-button>
          </el-radio-group>
        </div>
        <el-button size="small" @click="load">刷新</el-button>
      </div>

      <div v-if="loading" class="skeleton-wrap">
        <div v-for="i in 6" :key="i" class="skeleton skeleton-card" style="height:100px"></div>
      </div>
      <div v-else-if="filtered.length === 0" class="empty-state-v2">
        <div class="empty-illustration">📚</div>
        <p class="empty-title-v2">还没有笔记</p>
        <p class="empty-desc-v2">粘贴 B 站视频链接，AI 自动生成带时间戳的结构化笔记</p>
        <el-button type="primary" @click="$router.push('/')">去生成第一份笔记</el-button>
      </div>
      <div v-else class="note-grid">
        <div
          v-for="(n, i) in filtered"
          :key="n.id"
          class="note-card-h stagger-item"
          :style="{animationDelay: (i * 50) + 'ms'}"
        >
          <div class="note-card-thumb" @click="open(n)">🎬</div>
          <div class="note-card-info" @click="open(n)">
            <div class="note-card-title">{{ n.title }}</div>
            <div class="note-card-meta">
              <span>{{ subjectName(n.subject) }}</span>
              <el-tag v-if="n.source === 'local'" size="small" effect="plain" type="success">本地视频</el-tag>
              <span>{{ humanize(n.created_at) }}</span>
              <el-tag v-if="n.status === 'done'" type="success" size="small">已完成</el-tag>
              <el-tag v-else-if="n.status === 'processing'" type="warning" size="small">生成中</el-tag>
              <el-tooltip v-else-if="n.status === 'failed'" :content="n.error || '生成失败'" placement="top">
                <el-tag type="danger" size="small">失败</el-tag>
              </el-tooltip>
              <el-tag v-else type="info" size="small">待处理</el-tag>
              <el-dropdown v-if="n.status === 'done'" trigger="click" @command="(cmd) => setLearningStatus(n, cmd)">
                <el-tag :type="learningTagType(n.learning_status)" size="small" effect="plain" style="cursor:pointer">
                  {{ learningLabel(n.learning_status) }} ▾
                </el-tag>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="unlearned">未学</el-dropdown-item>
                    <el-dropdown-item command="learning">学习中</el-dropdown-item>
                    <el-dropdown-item command="completed">已完成</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div class="note-card-actions">
            <el-button v-if="n.status === 'failed' || n.status === 'pending'" size="small" type="warning" @click.stop="retry(n)">重试</el-button>
            <el-popconfirm title="确认删除？" @confirm="remove(n)">
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'HistoryView',
  data() {
    return {
      notes: [],
      loading: false,
      subjectFilter: 'all',
      statusFilter: 'all',
      searchKeyword: '',
      searchTimer: null,
      timer: null
    }
  },
  computed: {
    filtered() {
      var self = this
      var kw = this.searchKeyword.trim().toLowerCase()
      return this.notes.filter(function (n) {
        if (self.subjectFilter !== 'all' && n.subject !== self.subjectFilter) return false
        if (self.statusFilter !== 'all' && n.status !== self.statusFilter) return false
        if (kw) {
          var title = (n.title || '').toLowerCase()
          var summary = (n.summary || '').toLowerCase()
          if (title.indexOf(kw) < 0 && summary.indexOf(kw) < 0) return false
        }
        return true
      })
    }
  },
  created() {
    this.load()
    // 存在生成中的任务时每 6 秒自动刷新
    this.timer = setInterval(this.autoRefresh, 6000)
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
  },
  methods: {
    subjectName(s) {
      var names = { general: '通用', english: '英语', math: '数理', cs: '计算机', liberal: '文科' }
      return names[s] || s
    },
    learningLabel(s) {
      var labels = { unlearned: '未学', learning: '学习中', completed: '已学完' }
      return labels[s] || '未学'
    },
    learningTagType(s) {
      var types = { unlearned: 'info', learning: 'warning', completed: 'success' }
      return types[s] || 'info'
    },
    onSearch() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(async () => {
        if (this.searchKeyword.trim()) {
          try {
            this.notes = await api.get('/notes/search?q=' + encodeURIComponent(this.searchKeyword.trim()) + '&limit=100')
          } catch (e) { /* 忽略 */ }
        } else {
          this.load()
        }
      }, 300)
    },
    async setLearningStatus(note, status) {
      try {
        await api.put('/notes/' + note.id + '/learning-status', { status: status })
        note.learning_status = status
        ElMessage.success('已标记为「' + this.learningLabel(status) + '」')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    humanize(iso) {
      if (!iso) return ''
      var d = new Date(String(iso))
      if (!iso.endsWith('Z') && iso.indexOf('+') < 0) d = new Date(String(iso) + 'Z')
      if (isNaN(d.getTime())) return ''
      var diff = Math.floor((Date.now() - d.getTime()) / 1000)
      if (diff < 60) return '刚刚'
      if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
      if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
      return Math.floor(diff / 86400) + ' 天前'
    },
    async load() {
      this.loading = true
      try {
        this.notes = await api.get('/notes?limit=100')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    async autoRefresh() {
      if (this.notes.some(function (n) { return n.status === 'processing' })) {
        try {
          this.notes = await api.get('/notes?limit=100')
        } catch (e) {
          /* 忽略 */
        }
      }
    },
    open(row) {
      this.$router.push('/note/' + row.id)
    },
    async retry(row) {
      try {
        var res
        if (row.source === 'local') {
          if (!row.local_path) {
            ElMessage.error('这条笔记没有记录本地文件路径，请回首页重新选择文件')
            return
          }
          res = await api.post('/local/generate', {
            path: row.local_path,
            subject: row.subject || 'general',
            title: row.title || ''
          })
        } else {
          res = await api.post('/notes/generate', {
            bvid: row.bvid,
            page: row.page || 1,
            subject: row.subject || 'general',
            title: row.title || ''
          })
        }
        ElMessage.success('已重新开始生成')
        this.$router.push('/note/' + res.id)
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async remove(row) {
      try {
        await api.delete('/notes/' + row.id)
        ElMessage.success('已删除')
        this.load()
      } catch (e) {
        ElMessage.error(e.message)
      }
    }
  }
}
</script>

<style scoped>
.history-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }
.history-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.empty-state { padding: 40px 20px; text-align: center; }
.empty-icon { font-size: 48px; margin-bottom: 12px; opacity: .6; }
.empty-title { font-size: 16px; font-weight: 600; color: var(--c-text); margin: 0 0 6px; }
.empty-desc { font-size: 13px; color: var(--c-text-3); margin: 0 0 16px; }
.skeleton-wrap { padding: 8px 0; }
.note-grid { display: flex; flex-direction: column; gap: 10px; }
.note-card-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
</style>
