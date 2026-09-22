<template>
  <div class="fav-page">
    <div class="fav-header">
      <h2>⭐ 收藏夹导入</h2>
      <p class="fav-sub">粘贴B站收藏夹链接，自动列出所有视频（支持单视频+合集混合），勾选后一键批量生成笔记</p>
    </div>

    <el-card v-if="!items.length" class="fav-input-card" shadow="never">
      <el-input v-model="url" placeholder="粘贴收藏夹链接，如 https://space.bilibili.com/123/favlist?fid=456" size="large" />
      <el-button type="primary" size="large" :loading="loading" @click="doParse">解析收藏夹</el-button>
      <el-alert v-if="hint" :title="hint" type="warning" :closable="false" style="margin-top:12px" />
    </el-card>

    <div v-if="items.length" class="fav-body">
      <div class="fav-toolbar">
        <el-checkbox :model-value="allSelected" :indeterminate="someSelected" @change="toggleAll">全选</el-checkbox>
        <span class="fav-count">已选 {{ selectedCount }} / {{ items.length }}</span>
        <el-button type="success" :loading="starting" :disabled="!selectedCount" @click="startGenerate">批量生成笔记</el-button>
        <el-button @click="reset">换个收藏夹</el-button>
      </div>

      <div class="fav-list">
        <div v-for="(item, i) in items" :key="item.bvid" class="fav-item" :class="{ selected: item.selected }">
          <el-checkbox v-model="item.selected" />
          <div class="fav-item-main">
            <div class="fav-item-title">{{ item.title }}</div>
            <div class="fav-item-meta">
              <el-tag size="small" :type="item.is_collection ? 'warning' : 'info'">{{ item.is_collection ? '合集' : '单视频' }}</el-tag>
              <span v-if="item.uploader" class="fav-up">UP：{{ item.uploader }}</span>
            </div>
            <div v-if="item.is_collection" class="fav-range">
              <span>范围：第</span>
              <el-input-number v-model="item.start_page" :min="1" size="small" style="width:80px" />
              <span>集到第</span>
              <el-input-number v-model="item.end_page" :min="0" size="small" style="width:80px" />
              <span>集（0=全部）</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'FavoritesView',
  data() {
    return {
      url: '', loading: false, starting: false,
      items: [], hint: ''
    }
  },
  computed: {
    selectedCount() { return this.items.filter(i => i.selected).length },
    allSelected() { return this.items.length > 0 && this.items.every(i => i.selected) },
    someSelected() { return this.selectedCount > 0 && !this.allSelected }
  },
  methods: {
    async doParse() {
      if (!this.url) { ElMessage.warning('请粘贴收藏夹链接'); return }
      this.loading = true
      this.hint = ''
      try {
        const r = await api.post('/favorites/parse', { url: this.url })
        this.items = (r.items || []).map(it => ({ ...it, start_page: 1, end_page: 0 }))
        if (!this.items.length) this.hint = '收藏夹为空或无法访问（私有收藏夹需在「设置」页填写B站Cookie）'
        else ElMessage.success('解析成功，共 ' + r.total + ' 个视频')
      } catch (e) {
        this.hint = e.message || '解析失败'
      } finally { this.loading = false }
    },
    toggleAll(val) {
      this.items.forEach(i => { i.selected = val })
    },
    async startGenerate() {
      const selected = this.items.filter(i => i.selected)
      if (!selected.length) { ElMessage.warning('请先勾选视频'); return }
      this.starting = true
      try {
        const payload = selected.map(i => ({
          bvid: i.bvid, title: i.title, is_collection: i.is_collection,
          start_page: i.start_page, end_page: i.end_page
        }))
        const r = await api.post('/favorites/start', { items: payload, subject: 'general' })
        const msg = '已启动：' + (r.collection_count || 0) + ' 个合集任务、' + (r.note_count || 0) + ' 个单视频'
        ElMessage.success(msg)
        if (r.collection_job_ids && r.collection_job_ids.length) {
          this.$router.push('/collections/' + r.collection_job_ids[0])
        } else {
          this.$router.push('/history')
        }
      } catch (e) { ElMessage.error(e.message) }
      finally { this.starting = false }
    },
    reset() {
      this.url = ''; this.items = []; this.hint = ''
    }
  }
}
</script>

<style scoped>
.fav-page { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.fav-header h2 { margin: 0 0 6px; font-size: 22px; }
.fav-sub { color: var(--c-text-3); font-size: 13px; margin: 0 0 18px; }
.fav-input-card :deep(.el-input) { margin-bottom: 12px; }
.fav-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.fav-count { color: var(--c-text-3); font-size: 13px; flex: 1; }
.fav-list { display: flex; flex-direction: column; gap: 8px; }
.fav-item { display: flex; gap: 10px; padding: 12px; border: 1px solid var(--c-border); border-radius: 10px; background: var(--c-bg-elev); transition: border-color .15s; }
.fav-item.selected { border-color: var(--c-primary); }
.fav-item-main { flex: 1; min-width: 0; }
.fav-item-title { font-size: 14px; font-weight: 600; color: var(--c-text); margin-bottom: 6px; word-break: break-all; }
.fav-item-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.fav-up { font-size: 12px; color: var(--c-text-3); }
.fav-range { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--c-text-2); flex-wrap: wrap; }
@media (max-width: 768px) {
  .fav-page { padding: 12px 10px; }
  .fav-header h2 { font-size: 18px; }
  .fav-toolbar .el-button { font-size: 12px; padding: 8px 12px; }
  .fav-item { padding: 10px; }
  .fav-item-title { font-size: 13px; }
}
</style>
