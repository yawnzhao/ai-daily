#!/usr/bin/env python3
"""Build an issue with the original daily template and verified Markdown content."""
import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://yawnzhao.github.io/ai-daily'
def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    text = esc(text)
    text = re.sub(r'\[([^\]]+)\]\((https://[^\s)]+)\)',
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
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
    missing = [s for s in receipts['sources'] if s['status'] != 'ok']
    status = '采集不完整' if summary['incomplete'] else '本轮来源检查完成'
    notes = manuscript.split('## 采集说明', 1)[1].split('\n## ', 1)[0].strip()
    notes_html = ''.join('<p>' + inline(p) + '</p>' for p in re.split(r'\n\s*\n', notes) if p.strip())
    gap = ''
    if missing:
        labels = {'partial': '已检查部分内容，覆盖或日期待核',
                  'failed': '访问或抓取失败', 'pending': '尚未完成检查'}
        rows = ''.join('<li><strong>' + esc(s['name']) + '</strong>：'
                       + esc(labels.get(s['status'], '检查未完成')) + '。'
                       + esc(s.get('evidence') or '尚无足够检查证据。') + '</li>'
                       for s in missing)
        gap = ('<p><strong>检查尚未完成的来源</strong>：下列状态表示检查缺口，'
               '不能据此认定近期无更新；“已完整检查且无新增”另行记录。</p><ul>' + rows + '</ul>')
    return (f'<details class="paper-observation" id="coverage"><summary class="label">'
            f'采集说明 · {status} · {summary["ok"]}/{len(receipts["sources"])} 个来源完成检查</summary>'
            f'<div class="content">{notes_html}{gap}'
            f'<p>来源核验不等于独立实测；论文阅读范围按各条说明，未复现。</p></div></details>')


def catalog_kind(entry, issue):
    item = next((i for i in issue['items'] if i['primary_url'].rstrip('/') == entry['url'].rstrip('/')), None)
    if item:
        return {'featured': 0, 'briefs': 0, 'insight': 1, 'discourse': 1,
                'papers': 2, 'paper_briefs': 2, 'opensource': 3}[item['section']]
    explicit = entry.get('catalog_kind')
    if explicit in ('news', 'discourse', 'paper', 'code'):
        return ('news', 'discourse', 'paper', 'code').index(explicit)
    parsed = urlsplit(entry['url'])
    host = (parsed.hostname or '').removeprefix('www.')
    if entry.get('source_id') == 'concourse' or re.match(r'^Podcast\s*:', entry.get('title', ''), re.I):
        return 1
    if (host in ('arxiv.org', 'openreview.net', 'doi.org')
            or (host == 'huggingface.co' and parsed.path.startswith('/papers/'))
            or entry.get('source_id') in ('hf-daily-papers', 'arxiv', 'openreview')):
        return 2
    return 3 if host == 'github.com' else 0

def catalog_entries_for_display(entries, issue, content):
    """Keep discovery evidence intact; curate only the public presentation."""
    if issue['date'] < '2026-10-05':
        return entries
    selected = {i['primary_url'].rstrip('/'): i for i in issue['items']}
    positions = {item_id: n for n, item_id in enumerate(content)}

    def is_selected(entry):
        return entry['url'].rstrip('/') in selected


    def timestamp(entry):
        try:
            value = dt.datetime.fromisoformat(entry.get('published_at', '').replace('Z', '+00:00'))
            return value.replace(tzinfo=value.tzinfo or dt.timezone(dt.timedelta(hours=8))).timestamp()
        except (ValueError, TypeError, AttributeError):
            return float('-inf')

    visible = []
    for entry in entries:
        review = entry.get('catalog_review', {})
        # Public-list decisions do not delete discovery evidence or overrule adoption.
        if review.get('action') == 'defer' and not is_selected(entry):
            if not review.get('reason') or not review.get('scope'):
                raise ValueError('Catalog deferral needs a reason and review scope: ' + entry['url'])
            continue
        parsed = urlsplit(entry['url'])
        routine_commit = ((parsed.hostname or '').removeprefix('www.') == 'github.com'
                          and re.match(r'^/[^/]+/[^/]+/commits?(?:/|$)', parsed.path))
        reviewed_exception = (entry.get('catalog_news_reason')
                              and entry.get('verification_scope') not in
                              (None, '', 'list', 'pending', 'pending_verification'))
        if routine_commit and not (is_selected(entry) or reviewed_exception):
            continue
        visible.append(entry)
    # event_key is assigned only after editorial review, never from a company name.
    # Prefer adopted evidence or a version release over other links to that event.
    representatives = {}
    def event_priority(entry):
        return (is_selected(entry), bool(entry.get('catalog_event_representative')),
                '/releases/' in urlsplit(entry['url']).path)
    for entry in visible:
        key = entry.get('event_key')
        if key and (key not in representatives or event_priority(entry) > event_priority(representatives[key])):
            representatives[key] = entry
    visible = [e for e in visible if not e.get('event_key') or is_selected(e)
               or representatives[e['event_key']] is e]
    def order(entry):
        item = selected.get(entry['url'].rstrip('/'))
        if item:
            return (catalog_kind(entry, issue), 0, positions.get(item['id'], len(positions)))
        return (catalog_kind(entry, issue), 1, -timestamp(entry))
    return sorted(visible, key=order)


CATALOG_LABELS = ('新闻资讯', '话语场', '论文速递', '开源项目与版本更新')


def source_catalog_rows(issue, content):
    path = issue.get('source_catalog_path')
    if not path:
        if issue['date'] >= '2026-10-04':
            raise ValueError('Missing source catalog; save discovered candidates before publishing')
        return []
    catalog = json.loads((ROOT / path).read_text())
    if catalog['date'] != issue['date']:
        raise ValueError('Source catalog date mismatch')
    selected = {i['primary_url'].rstrip('/'): i for i in issue['items']}
    rows = []
    seen = set()
    for entry in catalog['items']:
        url = entry['url']
        if not url.startswith('https://') or url in seen:
            raise ValueError('Invalid or duplicate catalog URL: ' + url)
        seen.add(url)
    public_names = {}
    if issue['date'] >= '2026-10-05':
        config = json.loads((ROOT / 'config/sources.json').read_text())
        public_names = {s['id']: s['display_name'] for s in config['sources'] if s.get('display_name')}
    for entry in catalog_entries_for_display(catalog['items'], issue, content):
        url = entry['url']
        item = selected.get(url.rstrip('/'))
        if item:
            original = entry.get('original_title')
            if not original:
                raise ValueError('Missing original title for selected item: ' + item['id'])
            title = content[item['id']]['title']
        else:
            original = entry.get('original_title') or entry['title']
            title = entry.get('title_zh') or original
            if (issue['date'] >= '2026-10-05' and re.search(r'[A-Za-z]', original)
                    and not re.search(r'[\u3400-\u9fff]', original)
                    and not re.search(r'[\u3400-\u9fff]', entry.get('title_zh', ''))):
                raise ValueError('Missing Chinese catalog title: ' + url)
        name = entry['source']
        if issue['date'] >= '2026-10-05':
            name = public_names.get(entry.get('source_id'), re.sub(r'[（(]试用[）)]', '', name).strip())
        rows.append(dict(entry=entry, title=title, original=original, source=name,
                         adopted=bool(item), kind=catalog_kind(entry, issue)))
    return rows


def render_source_catalog(issue, content):
    rows = source_catalog_rows(issue, content)
    if not issue.get('source_catalog_path'):
        return ''
    blocks = []
    grouped = issue['date'] >= '2026-10-05'
    groups = range(4) if grouped else [None]
    for group in groups:
        entries = [r for r in rows if group is None or r['kind'] == group]
        if not entries:
            continue
        if grouped:
            blocks.append('<h3 class="source-catalog-heading">' + CATALOG_LABELS[group]
                          + ' · ' + str(len(entries)) + ' 条</h3>')
        blocks.append('<ul class="source-catalog-list" aria-label="资讯标题与来源">')
        for row in entries:
            title = esc(row['title'])
            if row['original'] != row['title']:
                title += '<span class="source-catalog-original">' + esc(row['original']) + '</span>'
            blocks.append('<li><a href="' + esc(row['entry']['url']) + '" target="_blank" rel="noopener">'
                          + title + '</a><span class="source-catalog-name">'
                          + esc(row['source']) + '</span></li>')
        blocks.append('</ul>')
    return ('<details class="paper-observation source-catalog" id="source-catalog">'
            '<summary class="label">资讯源 <span class="source-catalog-count">'
            + str(len(rows)) + ' 条</span></summary><div class="content">'
            + ''.join(blocks) + '</div></details>')


def render_source_catalog_markdown(issue, content):
    """Reading export of the same curated rows; JSON remains the machine input."""
    rows = source_catalog_rows(issue, content)
    def cell(value):
        return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;').replace('\n', ' ')
    lines = ['# ' + issue['date'] + ' 资讯源', '',
             '展示条目：' + str(len(rows)) + '。与当期网页共用筛选、分类和排序；每类正文采用项在前，其余按发布时间倒序。', '',
             '本清单含未读全文的候选，收录或标题翻译不表示完成核验。跨日汇总应读取结构化数据并按规范原文链接或论文 ID 去重。', '',
             '结构化数据：[' + issue['source_catalog_path'] + '](../../../' + issue['source_catalog_path'] + ')。', '']
    for group, label in enumerate(CATALOG_LABELS):
        entries = [r for r in rows if r['kind'] == group]
        if not entries:
            continue
        lines += ['## ' + label + ' · ' + str(len(entries)) + ' 条', '',
                  '| 标题（点击原文） | 来源 | 发布时间（原记录） | 日期精度 | 正文采用 |',
                  '| --- | --- | --- | --- | --- |']
        for row in entries:
            entry = row['entry']
            title = cell(row['title'])
            if row['original'] != row['title']:
                title += '<br>' + cell(row['original'])
            lines.append('| [' + title + '](<' + entry['url'] + '>) | ' + cell(row['source'])
                         + ' | ' + cell(entry.get('published_at') or '未知')
                         + ' | ' + cell(entry.get('date_precision') or '未记录')
                         + ' | ' + ('是' if row['adopted'] else '否') + ' |')
        lines.append('')
    return '\n'.join(lines)


def build(date):
    import check_names
    errors = check_names.check_date(ROOT, date, lang='zh-CN', sources_only=True)
    if errors:
        raise ValueError('名称核对未通过：' + '; '.join(errors))
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
            block += '<div class="paper-also"><div class="paper-also-title">其他动态</div>'
            block += ''.join(render_item(item, content[item['id']], n + 1) for n, item in enumerate(groups['briefs']))
            block += '</div>'
        sections.append(block + '</div>')
    day = dt.date.fromisoformat(date)
    day_human = f'{day.year}年{day.month}月{day.day}日'
    values = {'TITLE': esc(f'AI 日报 {date} · {issue["title"]}'), 'DESC': esc(issue['description']),
              'CANONICAL': BASE + '/ai-daily-digest-' + date + '.html', 'DATE': date,
              'DATE_HUMAN': day_human, 'WEEKDAY': ['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][day.weekday()],
              'VOL': str(issue['vol']), 'NEWS_COUNT': str(len(groups['featured']) + len(groups['briefs'])),
              'PAPER_COUNT': str(len(groups['papers'])), 'OSS_COUNT': str(len(groups['opensource'])),
              'WINDOW_HOURS': str(issue['window_hours']), 'AUDIO_SRC': esc(audio),
              'CONTENT': '\n'.join(sections) + '\n' + render_coverage(receipts, manuscript)
                         + '\n' + render_source_catalog(issue, content)}
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
        # Preserve published episode details when rebuilding the same audio.
        previous_audio = re.search(r'var AUDIO_SRC = "([^"]*)"', previous)
        if audio and previous_audio and html.unescape(previous_audio.group(1)) == audio:
            previous_meta = re.search(r'<div class="play-meta">.*?</div>', previous, re.S)
            if previous_meta:
                page = re.sub(r'<div class="play-meta">.*?</div>',
                              lambda _: previous_meta.group(0), page, count=1, flags=re.S)
        for mark in ('top', 'bottom'):
            pattern = r'(<nav class="issue-nav[^"]*" aria-label="日报导航" data-nav="' + mark + r'">).*?(</nav>)'
            found = re.search(pattern, previous, re.S)
            if found:
                page = re.sub(pattern, lambda _: found.group(0), page, flags=re.S)
    output.write_text(page)
    if date >= '2026-10-05' and issue.get('source_catalog_path'):
        catalog_output = ROOT / 'daily/sources' / date[:4] / (date + '.md')
        catalog_output.parent.mkdir(parents=True, exist_ok=True)
        catalog_output.write_text(render_source_catalog_markdown(issue, content))
    print(f'Built {output.name}: original daily UI; {len(issue["items"])} items; audio {"available" if audio else "pending"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('date', help='Issue date, YYYY-MM-DD')
    parser.add_argument('--lang', choices=['zh-CN', 'en'], default='zh-CN')
    args = parser.parse_args()
    if args.lang == 'en':
        from build_english_issue import build as build_english
        build_english(args.date)
    else:
        build(args.date)
