<template>
  <span class="latex-text" :class="{ 'latex-display': display, 'latex-md': markdown }" v-html="html"></span>
</template>

<script>
import { renderDisplayLatex, renderInlineLatex, renderMarkdownLite } from '../utils/latex'

export default {
  name: 'LatexText',
  props: {
    text: { type: String, default: '' },
    display: { type: Boolean, default: false },
    markdown: { type: Boolean, default: false }
  },
  computed: {
    html() {
      if (!this.text) return ''
      if (this.markdown) return renderMarkdownLite(this.text)
      if (this.display) return renderDisplayLatex(this.text)
      return renderInlineLatex(this.text)
    }
  }
}
</script>

<style scoped>
.latex-text { line-height: 1.8; word-break: break-word; }
.latex-text :deep(.katex) { font-size: 1.05em; }
.latex-display { display: block; overflow-x: auto; padding: 6px 0; }
.latex-md { display: block; }
.latex-md :deep(ul), .latex-md :deep(ol) { margin: 6px 0; padding-left: 22px; }
.latex-md :deep(li) { margin: 3px 0; }
.latex-md :deep(.md-code-block) {
  background: var(--c-bg-soft); border: 1px solid var(--c-border); border-radius: 6px;
  padding: 10px 12px; overflow-x: auto; margin: 8px 0; font-size: 13px; line-height: 1.6;
}
.latex-md :deep(code) {
  background: var(--c-bg-soft); border-radius: 4px; padding: 1px 5px;
  font-family: Consolas, Monaco, monospace; font-size: 0.92em;
}
.latex-md :deep(.md-code-block code) { background: none; padding: 0; }
.latex-md :deep(.latex-fail) {
  background: var(--c-accent-soft); color: var(--c-accent); border-radius: 4px;
  padding: 0 5px; font-family: Consolas, Monaco, monospace; font-size: 0.92em;
}
.latex-md :deep(.latex-fail-block) { display: block; padding: 8px 10px; margin: 6px 0; white-space: pre-wrap; }
</style>
