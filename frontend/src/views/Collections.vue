<template>
  <div class="collections">
    <!-- 任务列表 -->
    <el-card v-if="!jobId" shadow="never">
      <div class="col-head">
        <h2>合集批量任务</h2>
        <el-button size="small" @click="loadJobs">刷新</el-button>
      </div>
      <el-table :data="jobs" v-loading="loading" empty-text="还没有批量任务，去首页解析合集后点击「开始批量生成」">
        <el-table-column label="课程" min-width="220">
          <template #default="scope">
            <el-link type="primary" @click="$router.push('/collections/' + scope.row.id)">{{ scope.row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="学科" width="80">
          <template #default="scope">{{ subjectName(scope.row.subject) }}</template>
        </el-table-column>
        <el-table-column label="进度" min-width="170">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.total ? Math.round(scope.row.done_count * 100 / scope.row.total) : 0"
              :status="scope.row.status === 'done' ? 'success' : (scope.row.status === 'failed' ? 'exception' : undefined)"
            />
            <span class="progress-text">{{ scope.row.done_count }}/{{ scope.row.total }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag v-if="scope.row.status === 'running'" type="warning">进行中</el-tag>
            <el-tag v-else-if="scope.row.status === 'cancelling'" type="info">取消中</el-tag>
            <el-tag v-else-if="scope.row.status === 'cancelled'" type="info">已取消</el-tag>
            <el-tag v-else-if="scope.row.status === 'done'" type="success">完成</el-tag>
            <el-tag v-else-if="scope.row.status === 'partial'" type="warning">部分失败</el-tag>
            <el-tag v-else type="danger">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="图谱" width="80">
          <template #default="scope">
            <el-tag v-if="scope.row.has_map" type="info" size="small">已生成</el-tag>
            <span v-else style="color:var(--c-text-3)">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'running'"
              size="small" type="warning" text
              @click="cancelJob(scope.row)"
            >取消</el-button>
            <el-popconfirm title="删除该任务（不删除已生成笔记）？" @confirm="removeJob(scope.row)">
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 任务详情 -->
    <template v-else>
      <el-card shadow="never" class="detail-head" v-if="job">
        <div class="detail-title-row">
          <el-button size="small" text @click="$router.push('/collections')">← 返回列表</el-button>
          <h2 class="detail-title">{{ job.title }}</h2>
          <el-tag v-if="job.status === 'running'" type="warning">进行中（正在处理 P{{ job.current_page }}）</el-tag>
          <el-tag v-else-if="job.status === 'cancelling'" type="info">取消中（当前在处理的集完成后停止）</el-tag>
          <el-tag v-else-if="job.status === 'cancelled'" type="info">已取消</el-tag>
          <el-tag v-else-if="job.status === 'done'" type="success">全部完成</el-tag>
          <el-tag v-else-if="job.status === 'partial'" type="warning">部分失败</el-tag>
          <el-tag v-else type="danger">失败</el-tag>
          <el-button
            v-if="job.status === 'running'"
            size="small" type="warning" plain
            @click="cancelJob(job)"
          >取消任务</el-button>
        </div>
        <el-progress
          :percentage="job.total ? Math.round((job.done_count + job.failed_count) * 100 / job.total) : 0"
          :status="job.status === 'done' ? 'success' : (job.status === 'failed' ? 'exception' : undefined)"
        />
        <div class="progress-text">完成 {{ job.done_count }} / 失败 {{ job.failed_count }} / 共 {{ job.total }} 集</div>
        <div class="map-actions" v-if="job.done_count > 0">
          <el-button type="primary" size="small" :loading="mapLoading" @click="generateMap">
            {{ job.mindmap ? '重新生成全课程知识图谱' : '生成全课程知识图谱与考点地图' }}
          </el-button>
        </div>
      </el-card>

      <el-row :gutter="16" v-if="job">
        <el-col :xs="24" :md="10">
          <el-card shadow="never">
            <h4>各集处理结果</h4>
            <div class="result-list">
              <div v-for="(r, i) in job.results" :key="i" class="result-item">
                <span class="result-page">P{{ r.page }}</span>
                <el-link v-if="r.status === 'done'" type="primary" @click="openNote(r)">{{ r.title }}</el-link>
                <el-tooltip v-else-if="r.error" :content="r.error" placement="top" :show-after="200">
                  <span class="result-title result-failed">{{ r.title }}（失败，悬停看原因）</span>
                </el-tooltip>
                <span v-else class="result-title">{{ r.title }}</span>
                <el-tag v-if="r.status === 'done' && r.reused" type="info" size="small">复用</el-tag>
                <el-tag v-else-if="r.status === 'done'" type="success" size="small">完成</el-tag>
                <el-tag v-else type="danger" size="small">失败</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="14">
          <el-card shadow="never">
            <el-tabs v-model="mapTab">
              <el-tab-pane label="全课程知识图谱" name="kg">
                <MermaidView v-if="job.mindmap" :code="job.mindmap" @node-click="jumpNode" />
                <el-empty v-else description="点击上方按钮生成全课程知识图谱（自动梳理章节关联与前置后续关系）" />
              </el-tab-pane>
              <el-tab-pane label="考点地图" name="exam">
                <el-table v-if="job.exam_points && job.exam_points.length" :data="job.exam_points" size="small">
                  <el-table-column label="考点" min-width="160">
                    <template #default="scope">{{ scope.row.point }}</template>
                  </el-table-column>
                  <el-table-column label="重要程度" width="90">
                    <template #default="scope">
                      <el-tag :type="importanceType(scope.row.importance)" size="small">{{ scope.row.importance }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="位置" width="150">
                    <template #default="scope">
                      <el-link type="primary" class="ts-link" @click="jumpExam(scope.row)">
                        P{{ scope.row.page }} {{ scope.row.time_stamp }} ▶
                      </el-link>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-else description="生成知识图谱后自动汇总全课程考点" />
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import MermaidView from '../components/MermaidView.vue'

export default {
  name: 'CollectionsView',
  components: { MermaidView },
  data() {
    return {
      jobs: [],
      loading: false,
      job: null,
      mapTab: 'kg',
      mapLoading: false,
      timer: null
    }
  },
  computed: {
    jobId() {
      var id = this.$route.params.id
      return id ? Number(id) : 0
    }
  },
  created() {
    if (this.jobId) this.loadJob()
    else this.loadJobs()
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
  },
  watch: {
    jobId() {
      if (this.timer) { clearInterval(this.timer); this.timer = null }
      if (this.jobId) this.loadJob()
      else this.loadJobs()
    }
  },
  methods: {
    subjectName(s) {
      var names = { general: '通用', english: '英语', math: '数理', cs: '计算机', liberal: '文科' }
      return names[s] || s
    },
    importanceType(v) {
      if (v === '必考') return 'danger'
      if (v === '掌握') return 'warning'
      return 'info'
    },
    async loadJobs() {
      this.loading = true
      try {
        this.jobs = await api.get('/collections')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    async loadJob() {
      try {
        this.job = await api.get('/collections/' + this.jobId)
        if (this.job.status === 'running' || this.job.status === 'cancelling') {
          if (!this.timer) this.timer = setInterval(this.loadJob, 4000)
        } else if (this.timer) {
          clearInterval(this.timer)
          this.timer = null
        }
      } catch (e) {
        ElMessage.error(e.message)
        this.$router.push('/collections')
      }
    },
    async generateMap() {
      this.mapLoading = true
      try {
        var res = await api.post('/collections/' + this.jobId + '/map')
        this.job.mindmap = res.mindmap
        this.job.exam_points = res.exam_points || []
        ElMessage.success('知识图谱与考点地图已生成')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.mapLoading = false
      }
    },
    openNote(r) {
      this.$router.push('/note/' + r.note_id)
    },
    jumpNode(seconds, page) {
      var target = null
      if (page) {
        target = (this.job.results || []).find(function (x) { return x.page === page && x.status === 'done' })
      }
      if (!target) target = (this.job.results || []).find(function (x) { return x.status === 'done' })
      if (target) this.$router.push('/note/' + target.note_id + '?t=' + Math.floor(seconds))
    },
    jumpExam(row) {
      var target = (this.job.results || []).find(function (x) { return x.page === row.page && x.status === 'done' })
      if (target) {
        var sec = 0
        var parts = String(row.time_stamp || '').split(':')
        if (parts.length === 3) sec = parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseInt(parts[2], 10)
        this.$router.push('/note/' + target.note_id + '?t=' + sec)
      } else {
        ElMessage.warning('该集笔记尚未生成')
      }
    },
    async cancelJob(row) {
      try {
        await api.post('/collections/' + row.id + '/cancel')
        ElMessage.success('已请求取消，正在处理的集完成后停止')
        if (this.jobId) this.loadJob()
        else this.loadJobs()
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      }
    },
    async removeJob(row) {
      try {
        await api.delete('/collections/' + row.id)
        ElMessage.success('已删除')
        this.loadJobs()
      } catch (e) {
        ElMessage.error(e.message)
      }
    }
  }
}
</script>

<style scoped>
.col-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.col-head h2 { margin: 0; }
.progress-text { color: var(--c-text-3); font-size: 12px; margin-top: 4px; }
.detail-head { margin-bottom: 16px; }
.detail-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.detail-title { margin: 0; font-size: 17px; }
.map-actions { margin-top: 12px; }
.result-list { max-height: 420px; overflow-y: auto; }
.result-item { display: flex; align-items: center; gap: 8px; padding: 6px 2px; border-bottom: 1px dashed var(--c-border); font-size: 13px; }
.result-page { color: var(--c-primary); font-weight: 600; flex-shrink: 0; }
.result-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--c-text-2); }
.result-failed { color: var(--c-danger); cursor: help; }
h4 { margin: 0 0 10px; }
</style>
