<template>
  <div class="history">
    <el-card shadow="never">
      <div class="history-head">
        <div class="history-filters">
          <el-select v-model="subjectFilter" size="small" style="width: 130px" @change="load">
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
        <div v-for="i in 5" :key="i" class="skeleton skeleton-card"></div>
      </div>
      <el-table v-else :data="filtered">
        <template #empty>
          <div class="empty-state">
            <div class="empty-icon">📚</div>
            <p class="empty-title">还没有笔记</p>
            <p class="empty-desc">粘贴 B 站视频链接，AI 自动生成带时间戳的结构化笔记</p>
            <el-button type="primary" @click="$router.push('/')">去生成第一份笔记</el-button>
          </div>
        </template>
        <el-table-column label="标题" min-width="240">
          <template #default="scope">
            <el-link type="primary" @click="open(scope.row)">{{ scope.row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="学科" width="90">
          <template #default="scope">{{ subjectName(scope.row.subject) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag v-if="scope.row.status === 'done'" type="success">已完成</el-tag>
            <el-tag v-else-if="scope.row.status === 'processing'" type="warning">生成中</el-tag>
            <el-tooltip v-else-if="scope.row.status === 'failed'" :content="scope.row.error || '生成失败'" placement="top">
              <el-tag type="danger">失败</el-tag>
            </el-tooltip>
            <el-tag v-else type="info">待处理</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="110">
          <template #default="scope">{{ humanize(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="open(scope.row)">查看</el-button>
            <el-button v-if="scope.row.status === 'failed'" size="small" type="warning" @click="retry(scope.row)">重试</el-button>
            <el-popconfirm title="确认删除这份笔记？" @confirm="remove(scope.row)">
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
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
      timer: null
    }
  },
  computed: {
    filtered() {
      var self = this
      return this.notes.filter(function (n) {
        if (self.subjectFilter !== 'all' && n.subject !== self.subjectFilter) return false
        if (self.statusFilter !== 'all' && n.status !== self.statusFilter) return false
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
        var res = await api.post('/notes/generate', {
          bvid: row.bvid,
          page: row.page || 1,
          subject: row.subject || 'general',
          title: row.title || ''
        })
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
</style>
