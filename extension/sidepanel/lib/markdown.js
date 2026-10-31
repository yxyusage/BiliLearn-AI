/* BiliLearn-AI chat Markdown renderer (no third-party deps, CSP friendly). */
(function (global) {
  'use strict';

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/\x60/g, '&#96;');
  }

  function inline(text) {
    var tokens = [];
    function stash(html) {
      var key = '@@MD' + tokens.length + '@@';
      tokens.push(html);
      return key;
    }

    text = String(text == null ? '' : text);
    // Protect inline code first so * and $ inside code are not parsed.
    text = text.replace(/\x60([^\x60\n]+)\x60/g, function (_m, code) {
      return stash('<code>' + escapeHtml(code) + '</code>');
    });
    // Links: only http(s).
    text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, function (_m, label, href) {
      return stash('<a href="' + escapeAttr(href) + '" target="_blank" rel="noopener">' +
        escapeHtml(label) + '</a>');
    });
    // Inline math.
    text = text.replace(/\$([^$\n]+?)\$/g, function (_m, latex) {
      return stash('<span class="formula-inline" data-latex="' + escapeAttr(latex) + '"></span>');
    });
    text = text.replace(/\\\(([\s\S]+?)\\\)/g, function (_m, latex) {
      return stash('<span class="formula-inline" data-latex="' + escapeAttr(latex) + '"></span>');
    });

    text = escapeHtml(text);
    text = text.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');
    text = text.replace(/~~([^~\n]+?)~~/g, '<del>$1</del>');
    text = text.replace(/@@MD(\d+)@@/g, function (_m, index) {
      return tokens[Number(index)] || '';
    });
    return text.replace(/\n/g, '<br>');
  }

  function splitRow(line) {
    var value = String(line || '').trim();
    if (value.charAt(0) === '|') value = value.slice(1);
    if (value.charAt(value.length - 1) === '|') value = value.slice(0, -1);
    return value.split('|').map(function (cell) { return cell.trim(); });
  }

  function isTableStart(lines, index) {
    if (index + 1 >= lines.length) return false;
    if (String(lines[index]).indexOf('|') < 0) return false;
    var sep = String(lines[index + 1] || '').trim();
    return /^\|?[\s:|-]+\|?$/.test(sep) && sep.indexOf('-') >= 0;
  }

  function renderTable(lines, start) {
    var headers = splitRow(lines[start]);
    var rows = [];
    var i = start + 2;
    while (i < lines.length && String(lines[i]).trim() && String(lines[i]).indexOf('|') >= 0) {
      var cells = splitRow(lines[i]);
      while (cells.length < headers.length) cells.push('');
      rows.push(cells.slice(0, Math.max(headers.length, cells.length)));
      i += 1;
    }
    var html = '<div class="md-table-wrap"><table class="section-table md-table"><thead><tr>';
    headers.forEach(function (cell) { html += '<th>' + inline(cell) + '</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(function (row) {
      html += '<tr>';
      for (var c = 0; c < headers.length; c += 1) {
        html += '<td>' + inline(row[c] || '') + '</td>';
      }
      html += '</tr>';
    });
    return { html: html + '</tbody></table></div>', next: i };
  }

  function isBlockStart(line, lines, index) {
    var value = String(line || '');
    if (!value.trim()) return true;
    if (/^\s*(\x60{3,}|~{3,})\s*[\w-]*\s*$/.test(value)) return true;
    if (/^\s*@@MD\d+@@\s*$/.test(value)) return true;
    if (/^\s{0,3}#{1,6}\s+/.test(value)) return true;
    if (/^\s*>\s?/.test(value)) return true;
    if (/^\s*[-*_]{3,}\s*$/.test(value)) return true;
    if (/^\s*([-*+]|\d+[.)])\s+/.test(value)) return true;
    if (isTableStart(lines, index)) return true;
    return false;
  }

  function renderChat(markdown) {
    var text = String(markdown == null ? '' : markdown).replace(/\r\n?/g, '\n');
    text = text.replace(/<br\s*\/?>/gi, '\n');

    var displays = [];
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, function (_m, latex) {
      var key = '@@MD' + (displays.length + 10000) + '@@';
      displays.push(latex.trim());
      return '\n' + key + '\n';
    });
    text = text.replace(/\\\[([\s\S]*?)\\\]/g, function (_m, latex) {
      var key = '@@MD' + (displays.length + 10000) + '@@';
      displays.push(latex.trim());
      return '\n' + key + '\n';
    });

    var lines = text.split('\n');
    var out = [];
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (!line.trim()) { i += 1; continue; }

      var displayMatch = line.match(/^\s*@@MD(\d+)@@\s*$/);
      if (displayMatch) {
        var dIndex = Number(displayMatch[1]) - 10000;
        if (displays[dIndex] != null) {
          out.push('<div class="formula-display" data-latex="' + escapeAttr(displays[dIndex]) + '"></div>');
        }
        i += 1;
        continue;
      }

      var fence = line.match(/^\s*(\x60{3,}|~{3,})\s*([\w-]*)\s*$/);
      if (fence) {
        var marker = fence[1].charAt(0);
        var size = fence[1].length;
        var lang = (fence[2] || '').replace(/[^\w-]/g, '');
        var code = [];
        i += 1;
        while (i < lines.length) {
          var close = lines[i].match(/^\s*(\x60{3,}|~{3,})\s*$/);
          if (close && close[1].charAt(0) === marker && close[1].length >= size) { i += 1; break; }
          code.push(lines[i]);
          i += 1;
        }
        out.push('<pre class="md-code" data-lang="' + escapeAttr(lang) + '"><code>' +
          escapeHtml(code.join('\n')) + '</code></pre>');
        continue;
      }

      if (isTableStart(lines, i)) {
        var table = renderTable(lines, i);
        out.push(table.html);
        i = table.next;
        continue;
      }

      var heading = line.match(/^\s{0,3}(#{1,6})\s+(.*)$/);
      if (heading) {
        var level = Math.min(heading[1].length, 4);
        out.push('<h' + level + ' class="md-h md-h' + level + '">' + inline(heading[2]) + '</h' + level + '>');
        i += 1;
        continue;
      }

      if (/^\s*[-*_]{3,}\s*$/.test(line)) {
        out.push('<hr class="md-hr">');
        i += 1;
        continue;
      }

      if (/^\s*>\s?/.test(line)) {
        var quote = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          quote.push(lines[i].replace(/^\s*>\s?/, ''));
          i += 1;
        }
        out.push('<blockquote class="md-quote">' + inline(quote.join('\n')) + '</blockquote>');
        continue;
      }

      var listMatch = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
      if (listMatch) {
        var ordered = /^\d/.test(listMatch[1]);
        var items = [];
        while (i < lines.length) {
          var item = lines[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
          if (!item) break;
          items.push('<li>' + inline(item[2]) + '</li>');
          i += 1;
        }
        out.push('<' + (ordered ? 'ol' : 'ul') + ' class="md-list">' + items.join('') +
          '</' + (ordered ? 'ol' : 'ul') + '>');
        continue;
      }

      var paragraph = [line];
      i += 1;
      while (i < lines.length && !isBlockStart(lines[i], lines, i)) {
        paragraph.push(lines[i]);
        i += 1;
      }
      out.push('<p>' + inline(paragraph.join('\n')) + '</p>');
    }

    return out.join('\n');
  }

  var api = { renderChat: renderChat, escapeHtml: escapeHtml, inline: inline };
  global.BiliMarkdown = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
