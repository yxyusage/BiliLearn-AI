<template>
  <span class="latex-text" :class="{ 'latex-display': display }" v-html="html"></span>
</template>

<script>
import { renderDisplayLatex, renderLatex } from '../utils/latex'

export default {
  name: 'LatexText',
  props: {
    text: { type: String, default: '' },
    display: { type: Boolean, default: false }
  },
  computed: {
    html() {
      if (!this.text) return ''
      if (this.display) return renderDisplayLatex(this.text)
      return renderLatex(this.text)
    }
  }
}
</script>

<style scoped>
.latex-text { line-height: 1.8; }
.latex-text :deep(.katex) { font-size: 1.05em; }
.latex-display { display: block; overflow-x: auto; padding: 6px 0; }
</style>
