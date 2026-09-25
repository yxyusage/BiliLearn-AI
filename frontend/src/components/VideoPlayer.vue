<template>
  <div class="video-player">
    <iframe :src="src" scrolling="no" frameborder="0" allowfullscreen="true" @load="onLoad"></iframe>
    <el-tooltip placement="bottom-end" effect="dark">
      <template #content>
        登录 B 站账号后可在播放器右下角调节倍速与清晰度。<br />
        未登录时部分功能受限，点击会跳转 B 站登录页。
      </template>
      <span class="vp-hint">💡 登录B站可调倍速/清晰度</span>
    </el-tooltip>
    <div v-if="loading" class="vp-loading">
      <span class="vp-spinner"></span>
      <span>视频跳转中…</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VideoPlayer',
  props: {
    bvid: { type: String, required: true },
    page: { type: Number, default: 1 }
  },
  data() {
    return {
      currentTime: 0,
      loading: false,
      timer: null,
      lastJump: -999
    }
  },
  computed: {
    src() {
      var url = 'https://player.bilibili.com/player.html?bvid=' + this.bvid + '&page=' + (this.page || 1) + '&high_quality=1&danmaku=0&as_wide=1&wide_screen_mode=1'
      if (this.currentTime > 0) {
        url += '&t=' + Math.floor(this.currentTime) + '&autoplay=1'
      }
      return url
    }
  },
  beforeUnmount() {
    if (this.timer) clearTimeout(this.timer)
  },
  methods: {
    jumpTo(seconds) {
      var target = Math.floor(Number(seconds) || 0)
      if (this.timer) clearTimeout(this.timer)
      this.timer = setTimeout(() => {
        this.currentTime = target
        this.lastJump = target
        this.loading = true
      }, 350)
    },
    onLoad() {
      this.loading = false
    }
  }
}
</script>

<style scoped>
.video-player { position: relative; padding-top: 56.25%; width: 100%; background: #000; border-radius: 10px; overflow: hidden; }
.video-player iframe { position: absolute; left: 0; top: 0; width: 100%; height: 100%; border: 0; }
.vp-hint {
  position: absolute; right: 10px; bottom: 10px; z-index: 3;
  background: rgba(0, 0, 0, .55); color: #fff; font-size: 12px;
  padding: 3px 10px; border-radius: 999px; cursor: help; opacity: 0;
  transition: opacity .2s; pointer-events: none;
}
.video-player:hover .vp-hint { opacity: 1; pointer-events: auto; }
.vp-loading {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  gap: 10px; align-items: center; justify-content: center;
  background: rgba(0,0,0,.55); color: #fff; font-size: 14px; z-index: 2;
}
.vp-spinner {
  width: 28px; height: 28px; border: 3px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: vp-spin .8s linear infinite;
}
@keyframes vp-spin { to { transform: rotate(360deg); } }
</style>
