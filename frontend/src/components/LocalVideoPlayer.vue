<template>
  <div class="local-player">
    <video
      v-if="available"
      ref="video"
      class="lp-video"
      :src="src"
      controls
      preload="metadata"
      playsinline
      @loadedmetadata="onLoaded"
    ></video>
    <div v-else class="lp-missing">
      <div class="lp-missing-icon">⚠️</div>
      <div class="lp-missing-title">本地视频不可用</div>
      <div class="lp-missing-desc">文件可能已被移动、重命名或删除，笔记内容仍可正常阅读与导出</div>
      <div v-if="name" class="lp-missing-name">{{ name }}</div>
    </div>
    <div class="lp-meta">
      <span class="lp-badge">本地视频</span>
      <span class="lp-name" :title="name">{{ name }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LocalVideoPlayer',
  props: {
    src: { type: String, default: '' },
    name: { type: String, default: '' },
    available: { type: Boolean, default: true }
  },
  data() {
    return {
      pendingSeek: null
    }
  },
  methods: {
    // 与 VideoPlayer 保持同一套对外接口，笔记里的时间戳/脑图节点可直接调用
    jumpTo(seconds) {
      var target = Math.max(0, Number(seconds) || 0)
      var video = this.$refs.video
      if (!video) return
      if (video.readyState === 0) {
        this.pendingSeek = target
        return
      }
      this._seek(video, target)
    },
    _seek(video, target) {
      try {
        video.currentTime = target
        if (video.paused) {
          var p = video.play()
          if (p && p.catch) p.catch(function () { /* 自动播放被拦截时忽略 */ })
        }
      } catch (e) { /* 元数据未就绪时忽略 */ }
    },
    onLoaded() {
      if (this.pendingSeek === null) return
      var video = this.$refs.video
      var target = this.pendingSeek
      this.pendingSeek = null
      if (video) this._seek(video, target)
    }
  }
}
</script>

<style scoped>
.local-player {
  position: relative;
  width: 100%;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
}
.lp-video { display: block; width: 100%; max-height: 68vh; background: #000; }
.lp-missing {
  padding: 40px 20px; text-align: center; color: #fff;
  background: #1c1f24;
}
.lp-missing-icon { font-size: 32px; margin-bottom: 8px; }
.lp-missing-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.lp-missing-desc { font-size: 12px; opacity: .7; line-height: 1.7; }
.lp-missing-name { margin-top: 8px; font-size: 12px; opacity: .6; word-break: break-all; }
.lp-meta {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; background: var(--c-bg-soft);
  border-top: 1px solid var(--c-border);
}
.lp-badge {
  flex-shrink: 0; font-size: 11px; padding: 1px 8px; border-radius: 999px;
  background: var(--c-primary-soft); color: var(--c-primary);
}
.lp-name {
  font-size: 12px; color: var(--c-text-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
</style>
