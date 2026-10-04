#!/usr/bin/env python3
"""从各期日报页重建首页、RSS、sitemap，并回写每期的上下期导航。

用法：python3 scripts/build_site.py        # 重建并写回
      python3 scripts/build_site.py --check # 只检查，有差异就退出码 1

只读取每期页面已有的信息（日期、期号、统计数字、description、音频直链），
不改正文。每天写完当期页面后跑一次，首页和导航就不会和事实脱节。
"""
import argparse
import datetime
import email.utils
import html
import json
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


def read_page(path, lang='zh-CN'):
    t = path.read_text()
    date = PAGE_RE.match(path.name).group(1)
    d = datetime.date.fromisoformat(date)
    if lang == 'en':
        issue = json.loads((ROOT / 'data/issues' / (date + '.json')).read_text())
        edition = json.loads((ROOT / 'data/issues/en' / (date + '.json')).read_text())
        if edition['status'] != 'published' or edition['date'] != date:
            raise ValueError(f'{path}: English edition is not published')
        counts = {key: sum(i['section'] == key for i in issue['items'])
                  for key in ('featured', 'briefs', 'papers', 'opensource')}
        return {'file': path.name, 'date': date, 'weekday': d.strftime('%A'),
                'human': d.strftime('%B ') + str(d.day) + d.strftime(', %Y'),
                'vol': str(issue['vol']), 'desc': esc(edition['description']),
                'news': str(counts['featured'] + counts['briefs']), 'papers': str(counts['papers']),
                'oss': str(counts['opensource']), 'audio': bool(issue.get('audio_src') and (issue.get('episode_url') or issue.get('audio_episode_url'))),
                'text': t, 'published_at': edition['published_at']}
    metadata_match = re.search(r'<script type="application/json" id="daily-metadata">(.*?)</script>', t, re.S)
    if metadata_match:
        metadata = json.loads(metadata_match.group(1))
        if metadata.get('layout') != 'editorial-v2' or metadata.get('date') != date:
            raise ValueError(f'{path.name}: editorial metadata layout/date mismatch')
        for key in ('vol', 'news', 'papers', 'oss'):
            if type(metadata.get(key)) is not int or metadata[key] < 0:
                raise ValueError(f'{path.name}: invalid {key}')
        audio = metadata.get('audio_src')
        if audio is not None and (not isinstance(audio, str) or not audio.startswith('https://')):
            raise ValueError(f'{path.name}: invalid audio URL')
        return {'file': path.name, 'date': date, 'weekday': WEEKDAYS[d.weekday()],
                'human': f'{d.year}年{d.month}月{d.day}日', 'vol': str(metadata['vol']),
                'desc': need(r'<meta name="description" content="(.*?)">', t, path.name, 'description'),
                'news': str(metadata['news']), 'papers': str(metadata['papers']), 'oss': str(metadata['oss']),
                'audio': bool(audio), 'text': t}
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


def nav_html(pages, i, bottom=False, lang='zh-CN', english_files=()):
    older = pages[i + 1] if i + 1 < len(pages) else None
    newer = pages[i - 1] if i > 0 else None
    def link(p, label):
        return f'<a href="{p["file"]}">{label} · {p["date"][5:]}</a>' if p else ''
    switch = ''
    filename = pages[i]['file']
    if lang == 'en':
        switch = (f'<a href="../{filename}" lang="zh-CN">中文</a>'
                  '<a href="#" lang="en" aria-current="page">English</a>')
    elif filename in english_files:
        switch = ('<a href="#" lang="zh-CN" aria-current="page">中文</a>'
                  f'<a href="en/{filename}" lang="en">English</a>')
    previous, next_label, all_issues = ('Previous', 'Next', 'All issues') if lang == 'en' else ('上一期', '下一期', '全部日报')
    if bottom:
        return (switch + f'{link(older, previous)}{link(newer, next_label)}'
                + f'<span class="spacer"></span><a href="index.html">{all_issues} →</a>')
    return (switch + f'<a href="index.html">← {all_issues}</a><span class="spacer"></span>'
            + f'{link(older, previous)}{link(newer, next_label)}')


def card(p, lang='zh-CN'):
    if lang == 'en':
        chips = [f'{p["news"]} news items', f'{p["papers"]} paper' + ('s' if p['papers'] != '1' else ''),
                 f'{p["oss"]} open-source project' + ('s' if p['oss'] != '1' else '')]
        if p['audio']:
            chips.append('Audio · Chinese')
        chip_html = ''.join(f'<span class="chip">{c}</span>' for c in chips)
        return f'''<a class="episode" href="{p['file']}">
  <div class="vol"><div class="num">{p['vol'].zfill(2)}</div><div class="label">VOL</div></div>
  <div class="info"><div class="title"><time datetime="{p['date']}">AI Daily Digest · {p['human']} · {p['weekday']}</time></div>
    <div class="desc">{p['desc']}</div><div class="meta">{chip_html}</div></div>
  <div class="go">Read →</div>
</a>'''
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

    english = [read_page(p, 'en') for p in (ROOT / 'en').glob('ai-daily-digest-*.html') if PAGE_RE.match(p.name)]
    english.sort(key=lambda p: p['date'], reverse=True)
    english_files = {p['file'] for p in english}
    chinese_files = {p['file'] for p in pages}
    if english_files - chinese_files:
        sys.exit('English edition has no corresponding Chinese issue')
    outputs = {}
    collections = [('zh-CN', pages, '')] + ([('en', english, 'en/')] if english else [])
    for lang, issues, prefix in collections:
        base = BASE + ('/en' if lang == 'en' else '')
        # Navigation stays within the selected language's published issues.
        for i, p in enumerate(issues):
            t = p['text']
            for bottom, mark in ((False, 'top'), (True, 'bottom')):
                pat = re.compile(r'(<nav class="issue-nav[^"]*" aria-label="[^"]+" data-nav="%s">).*?(</nav>)' % mark, re.S)
                if not pat.search(t):
                    sys.exit(f'{prefix}{p["file"]}: missing {mark} navigation')
                t = pat.sub(lambda m: m.group(1) + nav_html(issues, i, bottom, lang, english_files) + m.group(2), t)
            if p['file'] in english_files:
                alternates = (f'<link rel="alternate" hreflang="zh-CN" href="{BASE}/{p["file"]}">\n'
                              f'<link rel="alternate" hreflang="en" href="{BASE}/en/{p["file"]}">\n')
                t = re.sub(r'<link rel="alternate" hreflang="[^"]+"[^>]*>\n?', '', t)
                t = t.replace('</head>', alternates + '</head>')
            outputs[prefix + p['file']] = t

        template_name = 'index.en.html' if lang == 'en' else 'index.html'
        tpl = (ROOT / 'templates' / template_name).read_text()
        language_link = ('<a href="../index.html" lang="zh-CN">中文</a>' if lang == 'en'
                         else '<a href="en/index.html" lang="en">English</a>' if english else '')
        tpl = tpl.replace('<div class="subscribe">', '<div class="subscribe">' + language_link, 1)
        if english:
            alternates = (f'<link rel="alternate" hreflang="zh-CN" href="{BASE}/">\n'
                          f'<link rel="alternate" hreflang="en" href="{BASE}/en/">\n')
            tpl = tpl.replace('</head>', alternates + '</head>')
        outputs[prefix + 'index.html'] = (tpl.replace('{{TOTAL}}', str(len(issues)))
                                        .replace('{{FIRST_DATE}}', issues[-1]['human'])
                                        .replace('{{DESC}}', issues[0]['desc'])
                                        .replace('{{CARDS}}', '\n\n'.join(card(p, lang) for p in issues)))

        feed_items = []
        dates = []
        for p in issues:
            if lang == 'en':
                pub = datetime.datetime.fromisoformat(p['published_at'].replace('Z', '+00:00'))
            else:
                pub = datetime.datetime.fromisoformat(p['date']).replace(hour=8, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
            if pub.tzinfo is None:
                raise ValueError('Publication timestamp must include a timezone')
            dates.append(pub)
            name = 'AI Daily Digest' if lang == 'en' else 'AI 日报'
            feed_items.append(f'''  <item>
    <title>{name} · {p['human']} {p['weekday']}</title>
    <link>{base}/{p['file']}</link>
    <guid isPermaLink="true">{base}/{p['file']}</guid>
    <pubDate>{email.utils.format_datetime(pub)}</pubDate>
    <description>{esc(html.unescape(p['desc']))}</description>
  </item>''')
        feed_title = 'AI Daily Digest · English' if lang == 'en' else 'AI 日报'
        feed_desc = 'Daily AI news · Insights / Research / Open Source' if lang == 'en' else 'AI 领域每日资讯 · 新闻 / 洞见 / 论文 / 开源'
        outputs[prefix + 'feed.xml'] = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{feed_title}</title>
  <link>{base}/</link>
  <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>{feed_desc}</description>
  <language>{lang}</language>
  <lastBuildDate>{email.utils.format_datetime(max(dates))}</lastBuildDate>
{chr(10).join(feed_items)}
</channel>
</rss>
'''

    def sitemap_entry(url, modified, pair=None):
        alternatives = ''
        if pair:
            alternatives = ''.join(f'<xhtml:link rel="alternate" hreflang="{language}" href="{href}"/>' for language, href in pair)
        return f'  <url><loc>{url}</loc><lastmod>{modified}</lastmod>{alternatives}</url>\n'
    home_pair = [('zh-CN', BASE + '/'), ('en', BASE + '/en/')] if english else None
    urls = sitemap_entry(BASE + '/', pages[0]['date'], home_pair)
    if english:
        urls += sitemap_entry(BASE + '/en/', english[0]['date'], home_pair)
    for lang, issues, prefix in collections:
        for p in issues:
            pair = [('zh-CN', BASE + '/' + p['file']), ('en', BASE + '/en/' + p['file'])] if p['file'] in english_files else None
            urls += sitemap_entry(BASE + '/' + prefix + p['file'], p['date'], pair)
    outputs['sitemap.xml'] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
                              + urls + '</urlset>\n')
    outputs['robots.txt'] = f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n'

    changed = []
    for name, content in outputs.items():
        path = ROOT / name
        if not path.exists() or path.read_text() != content:
            changed.append(name)
            if not args.check:
                path.write_text(content)

    audio_missing = [p['date'] for p in pages if not p['audio']]
    print(f'{len(pages)} 期中文 / {len(english)} 期英文 · 最新 {pages[0]["date"]}（第 {pages[0]["vol"]} 期）')
    print(f'语音版待补：{", ".join(audio_missing) if audio_missing else "无"}')
    if args.check:
        print('需要重建：' + (', '.join(changed) if changed else '无，全部是最新的'))
        return 1 if changed else 0
    print('已更新：' + (', '.join(changed) if changed else '无（内容已是最新）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
