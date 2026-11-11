// v0.4.1：用 UTF-8 渲染 USER_GUIDE.md（直接打开 .md 时浏览器不知道字符集 ⇒ 中文乱码）
function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function inline(s) {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return '\u0000' + (codes.length - 1) + '\u0000'; });
  s = esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => u.startsWith('#') ? `<a href="${u}">${t}</a>` : `<a href="${u}" target="_blank">${t}</a>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => '<code>' + esc(codes[+i]) + '</code>');
}
function cells(line) { return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim()); }
function render(md) {
  const L = md.replace(/\r\n/g, '\n').split('\n'); const out = []; let i = 0;
  while (i < L.length) {
    const t = L[i];
    if (/^```/.test(t)) { const b = []; i++; while (i < L.length && !/^```/.test(L[i])) b.push(L[i++]); i++;
      out.push('<pre><code>' + esc(b.join('\n')) + '</code></pre>'); continue; }
    let m = t.match(/^(#{1,6})\s+(.*)$/);
    if (m) { const id = m[2].replace(/`/g, '').trim().toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s/g, '-');
      out.push(`<h${m[1].length} id="${esc(id)}">${inline(m[2])}</h${m[1].length}>`); i++; continue; }
    if (/^\s*\|/.test(t) && i + 1 < L.length && /^\s*\|?\s*:?-{2,}/.test(L[i + 1])) {
      const h = cells(t); i += 2; const rows = [];
      while (i < L.length && /^\s*\|/.test(L[i])) rows.push(cells(L[i++]));
      out.push('<table><tr>' + h.map(c => '<th>' + inline(c) + '</th>').join('') + '</tr>' +
        rows.map(r => '<tr>' + r.map(c => '<td>' + inline(c) + '</td>').join('') + '</tr>').join('') + '</table>');
      continue; }
    if (/^\s*([-*+]|\d+\.)\s+/.test(t)) {
      const ordered = /^\s*\d+\./.test(t); const items = [];
      while (i < L.length && /^\s*([-*+]|\d+\.)\s+/.test(L[i])) {
        const ind = L[i].match(/^\s*/)[0].length;
        items.push(`<li style="margin-left:${ind * 0.6}em">` + inline(L[i].replace(/^\s*([-*+]|\d+\.)\s+/, '')) + '</li>'); i++; }
      out.push((ordered ? '<ol>' : '<ul>') + items.join('') + (ordered ? '</ol>' : '</ul>')); continue; }
    if (/^>\s?/.test(t)) { const b = []; while (i < L.length && /^>\s?/.test(L[i])) b.push(L[i++].replace(/^>\s?/, ''));
      out.push('<blockquote>' + inline(b.join(' ')) + '</blockquote>'); continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(t)) { out.push('<hr>'); i++; continue; }
    if (!t.trim()) { i++; continue; }
    const p = []; while (i < L.length && L[i].trim() && !/^(#{1,6}\s|```|\s*\||\s*([-*+]|\d+\.)\s|>)/.test(L[i])) p.push(L[i++]);
    if (!p.length) p.push(L[i++]);
    out.push('<p>' + inline(p.join(' ')) + '</p>');
  }
  return out.join('\n');
}
fetch(chrome.runtime.getURL('USER_GUIDE.md')).then(r => r.text())
  .then(md => { document.getElementById('doc').innerHTML = render(md); })
  .catch(e => { document.getElementById('doc').textContent = '说明加载失败：' + e; });
