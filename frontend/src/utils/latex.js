import katex from 'katex'

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function unescapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
}

function renderTex(tex, display) {
  try {
    return katex.renderToString(unescapeHtml(String(tex)).trim(), {
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

// 行内渲染：整段只做一次 HTML 转义。
// 行内代码 / 公式先用占位符抽走，避免内容里的 * & " 被二次转义或被当成 Markdown。
function renderInline(text) {
  let src = String(text == null ? '' : text)
  const tokens = []

  function stash(html) {
    const key = '\u0001' + tokens.length + '\u0001'
    tokens.push(html)
    return key
  }

  src = src.replace(/\x60([^\x60\n]+?)\x60/g, function (_m, code) {
    return stash('<code>' + escapeHtml(code) + '</code>')
  })
  src = src.replace(FORMULA_RE, function (match, dd, bb, ddInline, pp) {
    const display = dd != null || bb != null
    const tex = dd != null ? dd : (bb != null ? bb : (ddInline != null ? ddInline : pp))
    const rendered = renderTex(tex, display)
    return stash(rendered || fallback(match, tex, display))
  })

  let html = escapeHtml(src)
  html = html
    .replace(/&amp;nbsp;/g, '&nbsp;')
    .replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
    .replace(/~~([^~\n]+?)~~/g, '<del>$1</del>')
  html = html.replace(/\u0001(\d+)\u0001/g, function (_m, index) { return tokens[Number(index)] || '' })
  return html.replace(/\n/g, '<br>')
}

function splitRow(line) {
  var s = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return s.split('|').map(function (c) { return c.trim() })
}

export function renderMarkdownLite(text) {
  if (!text) return ''
  const source = String(text).replace(/\r\n?/g, '\n')

  // 围栏代码块先整块抽出，正文按行处理；这一步全程使用原文，
  // 只有真正写进 HTML 时才转义一次（转义两次会把 " 变成 &quot;、& 变成 &amp;）。
  const codeBlocks = []
  const staged = source.replace(/\x60{3}[ \t]*([\w-]*)[ \t]*\n([\s\S]*?)\x60{3}/g, function (_m, lang, code) {
    codeBlocks.push({ lang: lang, code: code.replace(/\n$/, '') })
    return '\n\u0001CODE' + (codeBlocks.length - 1) + '\u0001\n'
  })

  const lines = staged.split('\n')
  const out = []
  let inList = false
  let listOrdered = false
  let inCode = false
  let codeBuf = []
  let inQuote = false

  function closeList() {
    if (inList) { out.push(listOrdered ? '</ol>' : '</ul>'); inList = false }
  }
  function closeQuote() {
    if (inQuote) { out.push('</blockquote>'); inQuote = false }
  }

  var i = 0
  while (i < lines.length) {
    var line = lines[i]

    var cm = line.match(/^\u0001CODE(\d+)\u0001\s*$/)
    if (cm) {
      closeList(); closeQuote()
      var b = codeBlocks[Number(cm[1])]
      out.push('<pre class="md-code-block"><code>' + escapeHtml(b.code) + '</code></pre>')
      i++; continue
    }

    var heading = line.match(/^(#{1,4})\s+(.+)$/)
    if (heading) {
      closeList(); closeQuote()
      var level = heading[1].length
      out.push('<h' + level + ' class="md-h' + level + '">' + renderInline(heading[2]) + '</h' + level + '>')
      i++; continue
    }

    var quote = line.match(/^>\s?(.*)$/)
    if (quote) {
      closeList()
      if (!inQuote) { out.push('<blockquote class="md-quote">'); inQuote = true }
      out.push(renderInline(quote[1]))
      i++; continue
    } else {
      closeQuote()
    }

    var tableRow = line.match(/^\|(.+)\|\s*$/)
    if (tableRow) {
      closeList()
      var sepRow = (i + 1 < lines.length) ? lines[i + 1] : ''
      var isSep = /^\|[\s:|-]+\|\s*$/.test(sepRow)
      if (isSep) {
        var headerCells = splitRow(line)
        var rows = []
        var j = i + 2
        while (j < lines.length) {
          var r = lines[j]
          var rm = r.match(/^\|(.+)\|\s*$/)
          if (!rm) break
          rows.push(splitRow(r))
          j++
        }
        var t = '<table class="md-table"><thead><tr>'
        headerCells.forEach(function (c) { t += '<th>' + renderInline(c) + '</th>' })
        t += '</tr></thead><tbody>'
        rows.forEach(function (row) {
          t += '<tr>'
          row.forEach(function (c) { t += '<td>' + renderInline(c) + '</td>' })
          t += '</tr>'
        })
        t += '</tbody></table>'
        out.push(t)
        i = j; continue
      }
    }

    var ul = line.match(/^\s*[-*]\s+(.+)$/)
    var ol = line.match(/^\s*\d+[.、]\s*(.+)$/)
    if (ul || ol) {
      closeQuote()
      var ordered = !!ol
      var content = ul ? ul[1] : ol[1]
      if (!inList || listOrdered !== ordered) { closeList(); out.push(ordered ? '<ol>' : '<ul>'); inList = true; listOrdered = ordered }
      out.push('<li>' + renderInline(content) + '</li>')
      i++; continue
    }
    closeList()

    var indentCode = line.match(/^ {4}(\S[\s\S]*)$/)
    if (indentCode && !inCode) {
      if (/^(?:public|private|protected|def |class |import |from |#include|func |fn |fun |return |if |for |while |var |let |const |int |void |\}|else|package )/.test(indentCode[1])) {
        inCode = true; codeBuf = [indentCode[1]]; i++; continue
      }
    }
    if (inCode) {
      var c = line.match(/^ {4}(.*)$/)
      if (c && c[1].trim() !== '') { codeBuf.push(c[1]); i++; continue }
      out.push('<pre class="md-code-block"><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>')
      inCode = false
      continue
    }

    out.push(renderInline(line))
    i++
  }
  closeList(); closeQuote()
  if (inCode) out.push('<pre class="md-code-block"><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>')

  // 逐行输出：行与行之间保留换行（与旧实现一致的视觉间距）
  return out.join('<br>\n')
}
