#!/usr/bin/env python3
"""Build an issue with the original daily template and verified Markdown content."""
import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://yawnzhao.github.io/ai-daily'
def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    text = esc(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


def parse_manuscript(text):
    items = {}
    for match in re.finditer(r'<!-- item:([\w-]+) -->\s*\n### (.+?)\n(.*?)(?=<!-- item:|\n## |\Z)', text, re.S):
        item_id, title, body = match.groups()
        if item_id in items:
            raise ValueError('Duplicate manuscript ID: ' + item_id)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body.strip()) if p.strip()]
        items[item_id] = {'title': title, 'paragraphs': paragraphs}
    return items


def source(item):
    return (f'<a href="{esc(item["primary_url"])}" target="_blank" rel="noopener">'
            f'{esc(item["source_label"])}</a> · {esc(item["date_note"])}'
            f' · {esc(item["verification_scope"])}')


def paragraphs(content):
    return ''.join('<p>' + inline(p) + '</p>' for p in content['paragraphs'])


def render_item(item, content, number):
    title = inline(content['title'])
    body = paragraphs(content)
    item_id = esc(item['id'])
    section = item['section']
    if section == 'featured':
        badge = 'badge-infra' if item['id'] == 'dspark' else 'badge-model'
        return (f'<div class="news-item" id="{item_id}"><div class="news-head">'
                f'<span class="badge {badge}">{esc(item["topic"])}</span><h3>{title}</h3></div>'
                f'{body}<div class="source">来源：{source(item)}</div></div>')
    if section == 'briefs':
        return (f'<div class="paper-also-item" id="{item_id}"><span class="paper-also-num">{number:02d}</span>'
                f'<div><strong>{title}</strong>{body}<p>来源：{source(item)}</p></div></div>')
    if section == 'insight':
        return (f'<div class="insight-card" id="{item_id}"><div class="insight-banner">'
                f'<div class="meta">{esc(item["date_note"])}</div><h3>{title}</h3></div>'
                f'<div class="insight-body">{body}<p>来源：{source(item)}</p></div></div>')
    if section == 'papers':
        tags = ''.join('<span class="paper-tag">' + esc(tag) + '</span>'
                       for tag in (item['topic'], item['date_note'], item['verification_scope']))
        return (f'<div class="paper-item" id="{item_id}"><div class="paper-head">'
                f'<span class="paper-num">{number:02d}</span><span class="paper-title">{title}</span></div>'
                f'<div class="paper-tags">{tags}</div><div class="paper-body">{body}</div>'
                f'<a class="paper-link" href="{esc(item["primary_url"])}" target="_blank" rel="noopener">'
                f'{esc(item["source_label"])} →</a></div>')
    if section == 'opensource':
        rank = ' top' if number <= 3 else ''
        return (f'<div class="oss-item" id="{item_id}"><div class="oss-rank{rank}">{number}</div>'
                f'<div class="oss-content"><div class="oss-head"><span class="oss-name">'
                f'<a href="{esc(item["primary_url"])}" target="_blank" rel="noopener">{title}</a></span>'
                f'<span class="oss-license">{esc(item["license"])}</span></div>{body}</div></div>')
    raise ValueError('Unknown section: ' + section)


def render_coverage(receipts, manuscript):
    summary = receipts['summary']
    missing = [s['name'] for s in receipts['sources'] if s['status'] != 'ok']
    status = '采集不完整' if summary['incomplete'] else '本轮来源检查完成'
    notes = manuscript.split('## 采集说明', 1)[1].split('\n## ', 1)[0].strip()
    notes_html = ''.join('<p>' + inline(p) + '</p>' for p in re.split(r'\n\s*\n', notes) if p.strip())
    gap = '<p>待补齐：' + esc('、'.join(missing)) + '。不能据此判断这些来源没有新消息。</p>' if missing else ''
    return (f'<details class="paper-observation" id="coverage"><summary class="label">'
            f'采集说明 · {status} · {summary["ok"]}/{len(receipts["sources"])} 个来源完成检查</summary>'
            f'<div class="content">{notes_html}{gap}'
            f'<p>来源核验不等于独立实测；论文解读限于摘要与提交记录。</p></div></details>')


def build(date):
    issue = json.loads((ROOT / 'data/issues' / (date + '.json')).read_text())
    receipts = json.loads((ROOT / 'data/runs' / (date + '-receipts.json')).read_text())
    manuscript = (ROOT / issue['canonical_markdown']).read_text()
    content = parse_manuscript(manuscript)
    if issue['date'] != date or set(content) != {i['id'] for i in issue['items']}:
        raise ValueError('Issue date or manuscript IDs do not match metadata')
    groups = {key: [i for i in issue['items'] if i['section'] == key]
              for key in ('featured', 'briefs', 'insight', 'papers', 'opensource')}
    if len(groups['featured']) > 5:
        raise ValueError('Too many featured items')
    for item in issue['items']:
        if item['verified_primary_url'] != item['primary_url'] or not item['primary_url'].startswith('https://'):
            raise ValueError('Unverified source: ' + item['id'])
    checked = sum(s['status'] == 'ok' for s in receipts['sources'])
    if checked != receipts['summary']['ok'] or checked / len(receipts['sources']) != receipts['summary']['success_rate']:
        raise ValueError('Coverage summary differs from source records')
    audio = issue.get('audio_src') or ''
    if audio and not audio.startswith('https://'):
        raise ValueError('Audio URL must be HTTPS')
    sections = []
    labels = [('featured', '📰', '每日精选', f'{len(groups["featured"])} 条核心资讯'),
              ('insight', '🔍', '行业洞见', '深度分析'),
              ('papers', '📄', '论文速递', f'{len(groups["papers"])} 篇论文'),
              ('opensource', '⭐', '开源解读', f'{len(groups["opensource"])} 个仓库')]
    for key, icon, name, tag in labels:
        block = (f'<div class="section" id="{key}"><div class="section-header">'
                 f'<span class="icon">{icon}</span><h2>{name}</h2><span class="tag">{tag}</span></div>')
        if key == 'featured':
            block += ('<div class="focus-box"><div class="label">今日焦点</div>'
                      f'<div class="content">{esc(issue["description"])}</div></div>')
        if key == 'opensource':
            block += ('<div class="focus-box"><div class="label">阅读说明</div>'
                      '<div class="content">依据官方仓库说明整理，未进行部署实测。'
                      '本期作为工具发现，不表示项目在当日首次发布。</div></div>')
        block += ''.join(render_item(item, content[item['id']], n + 1) for n, item in enumerate(groups[key]))
        if key == 'featured' and groups['briefs']:
            block += '<div class="paper-also"><div class="paper-also-title">另两条动态</div>'
            block += ''.join(render_item(item, content[item['id']], n + 1) for n, item in enumerate(groups['briefs']))
            block += '</div>'
        sections.append(block + '</div>')
    day = dt.date.fromisoformat(date)
    day_human = f'{day.year}年{day.month}月{day.day}日'
    values = {'TITLE': esc(f'AI 日报 {date} · {issue["title"]}'), 'DESC': esc(issue['description']),
              'CANONICAL': BASE + '/ai-daily-digest-' + date + '.html', 'DATE': date,
              'DATE_HUMAN': day_human, 'WEEKDAY': ['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][day.weekday()],
              'VOL': str(issue['vol']), 'NEWS_COUNT': str(len(groups['featured'])),
              'PAPER_COUNT': str(len(groups['papers'])), 'OSS_COUNT': str(len(groups['opensource'])),
              'WINDOW_HOURS': str(issue['window_hours']), 'AUDIO_SRC': esc(audio),
              'CONTENT': '\n'.join(sections) + '\n' + render_coverage(receipts, manuscript)}
    page = (ROOT / 'templates/daily.html').read_text()
    for key, value in values.items():
        page = page.replace('{{' + key + '}}', value)
    if re.search(r'\{\{[A-Z_]+\}\}', page):
        raise ValueError('Unfilled template fields')
    if not audio:
        # Keep the original audio card, without nonfunctional playback controls.
        note = ('<!-- ===== Audio Player ===== -->\n<div class="audio-player"><div class="play-info">'
                f'<div class="play-label">语音简报</div><div class="play-title">AI 日报 · {day_human}</div>'
                '<div class="play-meta">语音版制作中 · <a href="https://www.xiaoyuzhoufm.com/podcast/6aa034c1002d4e51bf4b4f31" '
                'target="_blank" rel="noopener">前往小宇宙节目页</a></div></div></div>\n'
                '<script>var AUDIO_SRC = "";</script>\n\n')
        page = re.sub(r'<!-- ===== Audio Player ===== -->.*?(?=<main id="main">)', lambda _: note, page, flags=re.S)
    output = ROOT / ('ai-daily-digest-' + date + '.html')
    if output.exists():
        previous = output.read_text()
        for mark in ('top', 'bottom'):
            pattern = r'(<nav class="issue-nav[^"]*" aria-label="日报导航" data-nav="' + mark + r'">).*?(</nav>)'
            found = re.search(pattern, previous, re.S)
            if found:
                page = re.sub(pattern, lambda _: found.group(0), page, flags=re.S)
    output.write_text(page)
    print(f'Built {output.name}: original daily UI; {len(issue["items"])} items; audio {"available" if audio else "pending"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('date', help='Issue date, YYYY-MM-DD')
    build(parser.parse_args().date)

