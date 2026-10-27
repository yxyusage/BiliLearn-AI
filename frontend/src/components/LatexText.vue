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
.latex-md :deep(.md-table) {
  border-collapse: collapse; margin: 10px 0; width: auto; max-width: 100%;
  font-size: 14px; overflow-x: auto; display: block;
}
.latex-md :deep(.md-table th), .latex-md :deep(.md-table td) {
  border: 1px solid var(--c-border, #d0d7de); padding: 6px 12px; text-align: left;
}
.latex-md :deep(.md-table th) { background: var(--c-bg-soft, #f6f8fa); font-weight: 600; }
.latex-md :deep(.md-h1), .latex-md :deep(.md-h2), .latex-md :deep(.md-h3), .latex-md :deep(.md-h4) {
  margin: 14px 0 6px; line-height: 1.4; font-weight: 600;
}
.latex-md :deep(.md-h1) { font-size: 1.5em; }
.latex-md :deep(.md-h2) { font-size: 1.3em; }
.latex-md :deep(.md-h3) { font-size: 1.15em; }
.latex-md :deep(.md-h4) { font-size: 1.05em; }
.latex-md :deep(.md-quote) {
  border-left: 3px solid var(--c-accent, #4f8ef7); padding: 4px 12px;
  margin: 8px 0; color: var(--c-text-2, #57606a); background: var(--c-bg-soft, #f6f8fa);
}
</style>
