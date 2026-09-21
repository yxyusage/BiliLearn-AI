import katex from 'katex'

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderTex(tex, display) {
  try {
    return katex.renderToString(String(tex).trim(), {
      throwOnError: true,
      displayMode: display,
      output: 'html',
      strict: false
    })
  } catch (e) {
    return null
  }
}

function fallback(original, tex, display) {
  return '<code class="latex-fail' + (display ? ' latex-fail-block' : '') + '" title="公式渲染失败，显示原文">' +
    escapeHtml(original) + '</code>'
}

const FORMULA_RE = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g

export function renderInlineLatex(text, opts) {
  opts = opts || {}
  if (text == null) return ''
  let html = escapeHtml(text)
  html = html.replace(FORMULA_RE, function (match, dd, bb, ddInline, pp) {
    const display = dd != null || bb != null
    const tex = dd != null ? dd : (bb != null ? bb : (ddInline != null ? ddInline : pp))
    const rendered = renderTex(tex, display)
    if (rendered) return rendered
    return fallback(match, tex, display)
  })
  if (opts.br !== false) html = html.replace(/\n/g, '<br>')
  return html
}

export function renderDisplayLatex(latex) {
  if (!latex || !String(latex).trim()) return ''
  const raw = String(latex).trim()
  const direct = renderTex(raw, true)
  if (direct) return direct

  const parts = raw.split(/\n{2,}|(?=\$\$)|(?<=\\\])/).map(function (s) { return s.trim() }).filter(Boolean)
  if (parts.length > 1) {
    const html = parts.map(function (p) {
      const one = renderTex(p.replace(/^\$\$|\$\$$/g, '').replace(/^\\\[|\\\]$/g, ''), true)
      return one || fallback(p, p, true)
    }).join('')
    if (html) return html
  }
  return fallback(raw, raw, true)
}

export function renderMarkdownLite(text) {
  if (!text) return ''
  let html = escapeHtml(text)

  const codeBlocks = []
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (m, lang, code) {
    codeBlocks.push({ lang: lang, code: code.replace(/\n$/, '') })
    return '\0CODE' + (codeBlocks.length - 1) + '\0'
  })

  html = html
    .replace(/&amp;nbsp;/g, '&nbsp;')
    .replace(/`([^`\n]+?)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')

  html = html.replace(FORMULA_RE, function (match, dd, bb, ddInline, pp) {
    const display = dd != null || bb != null
    const tex = dd != null ? dd : (bb != null ? bb : (ddInline != null ? ddInline : pp))
    const rendered = renderTex(tex, display)
    if (rendered) return rendered
    return fallback(match, tex, display)
  })

  const lines = html.split('\n')
  const out = []
  let inList = false
  let listOrdered = false
  let inCode = false
  let codeBuf = []
  function closeList() {
    if (inList) { out.push(listOrdered ? '</ol>' : '</ul>'); inList = false }
  }
  lines.forEach(function (line) {
    const cm = line.match(/^\0CODE(\d+)\0\s*$/)
    if (cm) {
      closeList()
      const b = codeBlocks[Number(cm[1])]
      out.push('<pre class="md-code-block"><code>' + escapeHtml(b.code) + '</code></pre>')
      return
    }
    const indentCode = line.match(/^ {4}(\S[\s\S]*)$/)
    if (indentCode && !inCode) {
      if (/^(?:public|private|protected|def |class |import |from |#include|func |fn |fun |return |if |for |while |var |let |const |int |void |\}|else|package )/.test(indentCode[1])) {
        closeList(); inCode = true; codeBuf = [indentCode[1]]; return
      }
    }
    if (inCode) {
      const c = line.match(/^ {4}(.*)$/)
      if (c && c[1].trim() !== '') { codeBuf.push(c[1]); return }
      out.push('<pre class="md-code-block"><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>')
      inCode = false
    }
    const ul = line.match(/^\s*[-*]\s+(.+)$/)
    const ol = line.match(/^\s*\d+[.、]\s*(.+)$/)
    if (ul || ol) {
      const ordered = !!ol
      const content = ul ? ul[1] : ol[1]
      if (!inList || listOrdered !== ordered) { closeList(); out.push(ordered ? '<ol>' : '<ul>'); inList = true; listOrdered = ordered }
      out.push('<li>' + content + '</li>')
      return
    }
    closeList()
    out.push(line)
  })
  closeList()
  if (inCode) out.push('<pre class="md-code-block"><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>')
  html = out.join('\n')

  html = html.replace(/^\n+/, '').replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>')
  html = html.replace(/\0CODE\d+\0/g, '')
  return html
}
