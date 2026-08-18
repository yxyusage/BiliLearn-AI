import katex from 'katex'

export function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// 渲染 $...$ 与 $$...$$ 公式（纯文本其他部分原样转义）
export function renderLatex(s) {
  var text = String(s || '')
  var re = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g
  var out = ''
  var last = 0
  var m
  while ((m = re.exec(text))) {
    out += escapeHtml(text.slice(last, m.index))
    var code = m[1] !== undefined ? m[1] : m[2]
    var disp = m[1] !== undefined
    try {
      out += katex.renderToString(code, { displayMode: disp, throwOnError: false })
    } catch (e) {
      out += '<code>' + escapeHtml(code) + '</code>'
    }
    last = re.lastIndex
  }
  out += escapeHtml(text.slice(last))
  return out
}

function formatPlain(s) {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
}

// 轻量 markdown：**加粗** + 换行 + 公式
export function renderMarkdownLite(s) {
  var text = String(s || '')
  var re = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g
  var out = ''
  var last = 0
  var m
  while ((m = re.exec(text))) {
    out += formatPlain(text.slice(last, m.index))
    var code = m[1] !== undefined ? m[1] : m[2]
    var disp = m[1] !== undefined
    try {
      out += katex.renderToString(code, { displayMode: disp, throwOnError: false })
    } catch (e) {
      out += '<code>' + escapeHtml(code) + '</code>'
    }
    last = re.lastIndex
  }
  out += formatPlain(text.slice(last))
  return out
}

// 单条公式渲染（展示模式，用于公式卡片）
export function renderDisplayLatex(code) {
  try {
    return katex.renderToString(String(code || ''), { displayMode: true, throwOnError: false })
  } catch (e) {
    return '<code>' + escapeHtml(String(code || '')) + '</code>'
  }
}
