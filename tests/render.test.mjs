// 渲染转义回归测试：笔记正文里的代码片段（printf("…")、&amount、a < b）
// 必须只转义一次，否则浏览器会把 &quot; / &amp; / &lt; 原样显示给用户。
// 运行：node --test tests/
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { renderMarkdownLite } from '../frontend/src/utils/latex.js'

const require = createRequire(import.meta.url)
const md = require('../extension/sidepanel/lib/markdown.js')

// 「转义两次」的特征串：&quot; → &amp;quot;、& → &amp;amp;、< → &amp;lt;
function assertNoDoubleEscape(html) {
  [['&amp;quot;', '&quot;'], ['&amp;amp;', '&amp;'], ['&amp;lt;', '&lt;'], ['&amp;gt;', '&gt;']]
    .forEach(function (pair) {
      assert.ok(
        html.indexOf(pair[0]) === -1,
        '出现了双重转义 ' + pair[0] + '（应为 ' + pair[1] + '）: ' + html
      )
    })
}

// 模拟浏览器解析 v-html / innerHTML 后的可见文本（只处理最常见的几个实体）
function decodeEntities(html) {
  return String(html)
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/<[^>]*>/g, '')
}

test('前端：行内代码里的引号只转义一次，解码后仍是真实引号', function () {
  const html = renderMarkdownLite('提示输入：`printf("请输入票面：");`')
  assertNoDoubleEscape(html)
  assert.match(html, /<code>printf\(&quot;请输入票面：&quot;\);<\/code>/)
  assert.equal(decodeEntities(html), '提示输入：printf("请输入票面：");')
})

test('前端：& 号只转义一次（scanf 的取地址符）', function () {
  const html = renderMarkdownLite('读取输入：`scanf("%d", &amount);`')
  assertNoDoubleEscape(html)
  assert.match(html, /&amp;amount/)
  assert.equal(decodeEntities(html), '读取输入：scanf("%d", &amount);')
})

test('前端：正文（非代码）里的引号、& 和 < 也正常', function () {
  const html = renderMarkdownLite('printf("x"); 且 price = a & b，判断 a < b')
  assertNoDoubleEscape(html)
  assert.equal(decodeEntities(html), 'printf("x"); 且 price = a & b，判断 a < b')
})

test('前端：围栏代码块原样输出，不丢字符', function () {
  const src = '```c\nprintf("%d", &amount);\n```'
  const html = renderMarkdownLite(src)
  assertNoDoubleEscape(html)
  assert.match(html, /<pre class="md-code-block"><code>/)
  assert.equal(decodeEntities(html).trim(), 'printf("%d", &amount);')
})

test('前端：表格单元格里的代码同样只转义一次', function () {
  const src = '| 语法 | 说明 |\n| --- | --- |\n| `scanf("%d", &a);` | 读取 |'
  const html = renderMarkdownLite(src)
  assertNoDoubleEscape(html)
  assert.match(html, /<td><code>scanf\(&quot;%d&quot;, &amp;a\);<\/code><\/td>/)
})

test('前端：行内代码里的 * 不会被当成强调', function () {
  const html = renderMarkdownLite('`a*b*c` 与 **粗体**')
  assert.match(html, /<code>a\*b\*c<\/code>/)
  assert.match(html, /<strong>粗体<\/strong>/)
})

test('前端：原始 HTML 被转义，不会注入', function () {
  const html = renderMarkdownLite('<img src=x onerror=alert(1)>')
  assert.ok(html.indexOf('<img') === -1)
  assert.match(html, /&lt;img/)
})

test('前端：标题、列表、公式仍然正常渲染', function () {
  const html = renderMarkdownLite('## 标题\n\n- 第一项\n- 第二项 `int amount;`')
  assert.match(html, /<h2 class="md-h2">标题<\/h2>/)
  assert.match(html, /<li>第一项<\/li>/)
  assert.match(html, /<li>第二项 <code>int amount;<\/code><\/li>/)
  assert.match(renderMarkdownLite('$x^2$'), /class="katex"/)
})

test('扩展：聊天 Markdown 渲染器同样只转义一次', function () {
  const html = md.renderChat('提示输入：`printf("x");` 与 &amount\n\n```c\nprintf("%d", &amount);\n```')
  assertNoDoubleEscape(html)
  assert.match(html, /<code>printf\(&quot;x&quot;\);<\/code>/)
  assert.match(html, /&amp;amount/)
  assert.match(html, /<pre class="md-code"/)
})

test('扩展：笔记正文走 BiliMarkdown.inline，引号/&/</> 正常', function () {
  const html = md.inline('提示输入：`printf("请输入票面：");`，读取 `scanf("%d", &amount);`，判断 a < b')
  assertNoDoubleEscape(html)
  assert.match(html, /<code>printf\(&quot;请输入票面：&quot;\);<\/code>/)
  assert.match(html, /<code>scanf\(&quot;%d&quot;, &amp;amount\);<\/code>/)
  assert.equal(decodeEntities(html), '提示输入：printf("请输入票面：");，读取 scanf("%d", &amount);，判断 a < b')
})

test('扩展：表格与转义安全性', function () {
  const html = md.renderChat('| a | b |\n| --- | --- |\n| `a & b` | a < b |')
  assertNoDoubleEscape(html)
  assert.match(html, /<td><code>a &amp; b<\/code><\/td>/)
  assert.ok(md.renderChat('<script>alert(1)</script>').indexOf('<script>') === -1)
})
