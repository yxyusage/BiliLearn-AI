<template>
  <button class="time-link" :title="'跳转到视频 ' + time + '（点击后播放器自动定位）'" @click="$emit('jump', time)">
    <span class="tl-icon">▶</span>
    <span class="tl-time">{{ time }}</span>
  </button>
</template>

<script>
export default {
  name: 'TimeLink',
  props: {
    time: { type: String, default: '' }
  },
  emits: ['jump']
}
</script>

<style scoped>
.time-link {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 8px; margin-right: 2px;
  border: 1px solid var(--c-primary-border); border-radius: 999px;
  background: var(--c-primary-soft); color: var(--c-primary);
  font-size: 12px; font-family: Consolas, 'Courier New', monospace;
  cursor: pointer; line-height: 1.7; flex-shrink: 0;
  transition: all .15s ease; white-space: nowrap;
}
.time-link:hover { background: var(--c-primary); color: #fff; border-color: var(--c-primary); transform: translateY(-1px); }
html.dark .time-link:hover { color: #08231f; }
.tl-icon { font-size: 10px; }
</style>
