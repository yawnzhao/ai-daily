#!/usr/bin/env python3
"""从各期日报页重建首页、RSS、sitemap，并回写每期的上下期导航。

用法：python3 scripts/build_site.py        # 重建并写回
      python3 scripts/build_site.py --check # 只检查，有差异就退出码 1

只读取每期页面已有的信息（日期、期号、统计数字、description、音频直链），
不改正文。每天写完当期页面后跑一次，首页和导航就不会和事实脱节。
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://yawnzhao.github.io/ai-daily'
WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
PAGE_RE = re.compile(r'^ai-daily-digest-(\d{4}-\d{2}-\d{2})\.html$')


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))


def need(pattern, text, page, what, group=1):
    m = re.search(pattern, text)
    if not m:
        sys.exit(f'{page}: 读不到{what}，模板被改过？先修页面再跑本脚本。')
    return m.group(group)


def read_page(path):
    t = path.read_text()
    date = PAGE_RE.match(path.name).group(1)
    d = datetime.date.fromisoformat(date)
    # 用标签做键。若先用数字做键，资讯数和开源数相同（例如都是 4）时会互相覆盖，首页就会显示 0 条精选。
    stats = {label: num for num, label in re.findall(
        r'<span class="num">(\d+)</span>(条资讯|篇论文|个开源项目)', t)}
    return {
        'file': path.name,
        'date': date,
        'weekday': WEEKDAYS[d.weekday()],
        'human': f'{d.year}年{d.month}月{d.day}日',
        'vol': need(r'第\s*(\d+)\s*期', t, path.name, '期号'),
        'desc': need(r'<meta name="description" content="(.*?)">', t, path.name, 'description'),
        'news': stats.get('条资讯', '0'),
        'papers': stats.get('篇论文', '0'),
        'oss': stats.get('个开源项目', '0'),
        'audio': bool(need(r'var AUDIO_SRC = "([^"]*)"', t, path.name, 'AUDIO_SRC 变量')),
        'text': t,
    }


def nav_html(pages, i, bottom=False):
    older = pages[i + 1] if i + 1 < len(pages) else None
    newer = pages[i - 1] if i > 0 else None
    def link(p, label):
        return f'<a href="{p["file"]}">{label} · {p["date"][5:]}</a>' if p else ''
    if bottom:
        return (f'{link(older, "上一期")}{link(newer, "下一期")}'
                '<span class="spacer"></span><a href="index.html">全部日报 →</a>')
    return ('<a href="index.html">← 全部日报</a><span class="spacer"></span>'
            f'{link(older, "上一期")}{link(newer, "下一期")}')


def card(p):
    chips = [f'{p["news"]} 条精选', f'{p["papers"]} 篇论文', f'{p["oss"]} 个开源项目']
    chips = ''.join(f'<span class="chip">{c}</span>' for c in chips)
    chips += ('<span class="chip">语音版 · 小宇宙</span>' if p['audio']
              else '<span class="chip chip-pending">语音版制作中</span>')
    return f'''<a class="episode" href="{p['file']}">
  <div class="vol"><div class="num">{p['vol'].zfill(2)}</div><div class="label">VOL</div></div>
  <div class="info">
    <div class="title"><time datetime="{p['date']}">AI 日报 · {p['human']} {p['weekday']}</time></div>
    <div class="desc">{p['desc']}</div>
    <div class="meta">
      {chips}
    </div>
  </div>
  <div class="go">阅读 →</div>
</a>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对，不写文件')
    args = ap.parse_args()

    pages = [read_page(p) for p in ROOT.glob('ai-daily-digest-*.html') if PAGE_RE.match(p.name)]
    if not pages:
        sys.exit('没找到任何日报页面。')
    pages.sort(key=lambda p: p['date'], reverse=True)

    outputs = {}

    # 1. 每期页面的上下期导航
    for i, p in enumerate(pages):
        t = p['text']
        for bottom, mark in ((False, 'top'), (True, 'bottom')):
            pat = re.compile(r'(<nav class="issue-nav[^"]*" aria-label="日报导航" data-nav="%s">).*?(</nav>)' % mark, re.S)
            if not pat.search(t):
                sys.exit(f'{p["file"]}: 缺少 data-nav="{mark}" 的导航块，请按 templates/daily.html 补上。')
            t = pat.sub(lambda m: m.group(1) + nav_html(pages, i, bottom) + m.group(2), t)
        outputs[p['file']] = t

    # 2. 首页
    tpl = (ROOT / 'templates' / 'index.html').read_text()
    outputs['index.html'] = (tpl
                             .replace('{{TOTAL}}', str(len(pages)))
                             .replace('{{DESC}}', pages[0]['desc'])
                             .replace('{{CARDS}}', '\n\n'.join(card(p) for p in pages)))

    # 3. RSS
    items = []
    for p in pages:
        pub = datetime.datetime.fromisoformat(p['date']).replace(hour=8)
        items.append(f'''  <item>
    <title>AI 日报 · {p['human']} {p['weekday']}</title>
    <link>{BASE}/{p['file']}</link>
    <guid isPermaLink="true">{BASE}/{p['file']}</guid>
    <pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S')} +0200</pubDate>
    <description>{esc(p['desc'])}</description>
  </item>''')
    newest = datetime.datetime.fromisoformat(pages[0]['date']).replace(hour=8)
    outputs['feed.xml'] = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>AI 日报</title>
  <link>{BASE}/</link>
  <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>AI 领域每日资讯 · 新闻 / 洞见 / 论文 / 开源</description>
  <language>zh-CN</language>
  <lastBuildDate>{newest.strftime('%a, %d %b %Y %H:%M:%S')} +0200</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
'''

    # 4. sitemap / robots
    urls = ''.join(f'  <url><loc>{BASE}/{p["file"]}</loc><lastmod>{p["date"]}</lastmod></url>\n' for p in pages)
    outputs['sitemap.xml'] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                              f'  <url><loc>{BASE}/</loc><lastmod>{pages[0]["date"]}</lastmod></url>\n'
                              f'{urls}</urlset>\n')
    outputs['robots.txt'] = f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n'

    changed = []
    for name, content in outputs.items():
        path = ROOT / name
        if not path.exists() or path.read_text() != content:
            changed.append(name)
            if not args.check:
                path.write_text(content)

    audio_missing = [p['date'] for p in pages if not p['audio']]
    print(f'{len(pages)} 期 · 最新 {pages[0]["date"]}（第 {pages[0]["vol"]} 期）')
    print(f'语音版待补：{", ".join(audio_missing) if audio_missing else "无"}')
    if args.check:
        print('需要重建：' + (', '.join(changed) if changed else '无，全部是最新的'))
        return 1 if changed else 0
    print('已更新：' + (', '.join(changed) if changed else '无（内容已是最新）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
