<template>
  <div class="video-player">
    <iframe :src="src" scrolling="no" frameborder="0" allowfullscreen="true"></iframe>
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
    return { currentTime: 0 }
  },
  computed: {
    src() {
      // high_quality=1 提升画质；danmaku=0 关闭弹幕保持画面干净
      var url = 'https://player.bilibili.com/player.html?bvid=' + this.bvid + '&page=' + (this.page || 1) + '&high_quality=1&danmaku=0'
      if (this.currentTime > 0) {
        url += '&t=' + Math.floor(this.currentTime) + '&autoplay=1'
      }
      return url
    }
  },
  methods: {
    jumpTo(seconds) {
      this.currentTime = seconds
    }
  }
}
</script>

<style scoped>
.video-player { position: relative; padding-top: 56.25%; width: 100%; background: #000; border-radius: 8px; overflow: hidden; }
.video-player iframe { position: absolute; left: 0; top: 0; width: 100%; height: 100%; border: 0; }
</style>
