#!/usr/bin/env python3
"""Build a published editorial-layout issue from its Markdown authority and metadata."""
import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://yawnzhao.github.io/ai-daily'
SECTIONS = [('featured', '01', '每日精选', '四条更新，把变化与使用条件一起读。'),
            ('briefs', '02', '还有两条', '值得知道，简短说明。'),
            ('insight', '03', '行业观察', '把产品更新放回实践中。'),
            ('papers', '04', '论文速递', '三篇摘要解读 · 已核对提交日，未复现实验。'),
            ('opensource', '05', '开源解读', '依据官方仓库说明整理 · 本期未进行部署实测。')]


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


def source_line(item):
    checked = dt.date.fromisoformat(item['checked_on'])
    checked_label = f'{checked.month} 月 {checked.day} 日'
    scope = item['verification_scope']
    precision = '发布日期只精确到日；未取得时分。' if item['date_precision'] == 'day' else ''
    if item['date_precision'] == 'unknown':
        precision = '未判定首次发布日期；本条属于工具发现。'
    return f'''<div class="source-line"><a href="{esc(item['primary_url'])}" target="_blank" rel="noopener noreferrer">{esc(item['source_label'])}<span aria-hidden="true"> ↗</span></a>
      <details class="source-detail"><summary>核验范围</summary><p>{esc(scope)}。本轮查阅于 {checked_label}。{esc(precision)} 本期补查发生在原稿之后。</p></details></div>'''


def diagram(item_id):
    if item_id == 'claude-tag':
        return '''<figure class="flow-figure"><figcaption>从个人资料，到频道回答</figcaption><ol><li><span>01</span>本人发起请求</li><li><span>02</span>读取有权访问的资料</li><li><span>03</span>审阅或自动筛查</li><li><span>04</span>发布后频道可见</li></ol><p>定时任务仍使用管理员配置的共享连接器。</p></figure>'''
    if item_id == 'dspark':
        return '''<figure class="speed-figure"><figcaption>两种“加速”，衡量的是不同范围</figcaption><div class="speed-row"><span>解码阶段</span><div class="speed-track"><span class="speed-decode"></span></div><strong>最高 3.13×</strong></div><div class="speed-row"><span>端到端</span><div class="speed-track"><span class="speed-total"></span></div><strong>最高 2.62×</strong></div><p>作者报告 · M5 Max / MLX · 各任务最大值，不代表每个任务都达到该速度。</p></figure>'''
    return ''


def render_item(item, content, number):
    section = item['section']
    parts = []
    for idx, paragraph in enumerate(content['paragraphs']):
        cl = 'lede' if idx == 0 and section == 'featured' else ''
        if paragraph.startswith(('**使用条件**', '**阅读边界**', '**要区分预测与实验结论**')):
            cl = 'boundary'
        parts.append(f'<p class="{cl}">{inline(paragraph)}</p>')
    badge = f'<span class="license">{esc(item["license"])}</span>' if 'license' in item else ''
    body = ''.join(parts)
    return f'''<article id="{item['id']}" class="story {section}-story">
      <div class="story-meta"><span class="story-number">{number:02d}</span><span>{esc(item['topic'])}</span>{badge}<span class="published">{esc(item['date_note'])}</span></div>
      <h3>{inline(content['title'])}</h3><div class="story-body">{body}</div>{diagram(item['id'])}{source_line(item)}</article>'''


def render_coverage(receipts, manuscript, issue):
    summary = receipts['summary']
    sources = receipts['sources']
    labels = {'ok':'已检查','partial':'待补齐','failed':'抓取失败','pending':'待检查'}
    rows = ''.join(f'<tr><th scope="row"><a href="{esc(r["configured_url"])}" target="_blank" rel="noopener noreferrer">{esc(r["name"])}</a></th><td><span class="status-{r["status"]}">{labels[r["status"]]}</span></td><td>{esc(r["note"])}</td></tr>' for r in sources)
    count = len(sources)
    missing = [r['name'] for r in sources if r['status'] != 'ok']
    status = '采集不完整' if summary['incomplete'] else '本轮来源检查完成'
    gap = '仍待补齐：' + '、'.join(missing) + '。这些来源不能据此判断为没有新消息。' if missing else '本轮配置来源均已完成检查。'
    notes = manuscript.split('## 采集说明',1)[1].split('\n## ',1)[0].strip()
    notes_html = ''.join('<p>'+inline(p)+'</p>' for p in re.split(r'\n\s*\n',notes) if p.strip())
    arxiv = summary.get('arxiv_metadata_records')
    paper_note = f'<p>arXiv 发现窗口取得 {arxiv} 条唯一元数据，精选条目另读摘要；这不表示读完了 {arxiv} 篇全文。</p>' if arxiv else ''
    audio = issue.get('audio_src')
    if audio:
        audio_html = f'<audio controls preload="none" aria-label="本期语音简报" src="{esc(audio)}"></audio>'
    else:
        audio_html = '<p class="audio-note">语音版制作中 · <a href="https://www.xiaoyuzhoufm.com/podcast/6aa034c1002d4e51bf4b4f31" target="_blank" rel="noopener noreferrer">前往小宇宙节目页 ↗</a></p>'
    return f'''<section id="coverage" class="coverage"><div class="section-heading"><div><span class="section-number">06</span><h2>来源与采集说明</h2></div><p>把没有覆盖到的地方也交代清楚。</p></div>
      <div class="coverage-summary"><strong>{status}</strong><span>{summary['ok']} / {count} 个源完成检查 · {count-summary['ok']} 个待补齐</span></div>
      <p>本轮完成比例为 {summary['success_rate']:.0%}。{esc(gap)}</p>{notes_html}{paper_note}
      <details class="receipt-details"><summary>展开 {count} 个来源的检查记录<span aria-hidden="true">＋</span></summary><div class="table-scroll"><table><caption>本轮来源检查；“已检查”不表示所有条目都进行了独立实测。</caption><thead><tr><th scope="col">来源</th><th scope="col">状态</th><th scope="col">检查结果</th></tr></thead><tbody>{rows}</tbody></table></div></details>{audio_html}</section>'''


def build(date):
    issue = json.loads((ROOT / 'data/issues' / (date+'.json')).read_text())
    receipts = json.loads((ROOT / 'data/runs' / (date+'-receipts.json')).read_text())
    manuscript = (ROOT / issue['canonical_markdown']).read_text()
    content = parse_manuscript(manuscript)
    if issue['date'] != date or set(content) != {i['id'] for i in issue['items']}:
        raise ValueError('Issue date or manuscript IDs do not match metadata')
    counts = {key:sum(i['section']==key for i in issue['items']) for key in ('featured','papers','opensource')}
    if counts['featured'] > 5: raise ValueError('Too many featured items')
    for item in issue['items']:
        if item['verified_primary_url'] != item['primary_url'] or not item['primary_url'].startswith('https://'):
            raise ValueError('Unverified source: '+item['id'])
    checked = sum(s['status']=='ok' for s in receipts['sources'])
    if checked != receipts['summary']['ok'] or checked / len(receipts['sources']) != receipts['summary']['success_rate']:
        raise ValueError('Coverage summary differs from source records')
    day = dt.date.fromisoformat(date)
    canonical = BASE + '/ai-daily-digest-' + date + '.html'
    metadata = {'layout':'editorial-v2','date':date,'vol':issue['vol'],'news':counts['featured'],
                'papers':counts['papers'],'oss':counts['opensource'],'audio_src':issue.get('audio_src')}
    if metadata['audio_src'] is not None and not metadata['audio_src'].startswith('https://'):
        raise ValueError('Audio URL must be HTTPS')
    metadata_json = json.dumps(metadata,ensure_ascii=False).replace('<','\\u003c')
    public_meta = f'''<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="AI 日报 {date} · {esc(issue['title'])}">
<meta property="og:description" content="{esc(issue['description'])}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="创学空间 · AI 日报">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="AI 日报" href="{BASE}/feed.xml">
<script type="application/json" id="daily-metadata">{metadata_json}</script>'''
    nav = ''.join(f'<a href="#{key}"><span>{number}</span>{name}</a>' for key,number,name,_ in SECTIONS)
    nav += '<a href="#coverage"><span>06</span>来源说明</a>'
    sections = []
    for key,number,name,description in SECTIONS:
        items = [i for i in issue['items'] if i['section']==key]
        if not items: continue
        if key == 'featured': description = f'{len(items)} 条更新，把变化与使用条件一起读。'
        if key == 'papers': description = f'{len(items)} 篇摘要解读 · 已核对提交日，未复现实验。'
        articles = ''.join(render_item(item,content[item['id']],n+1) for n,item in enumerate(items))
        sections.append(f'<section id="{key}" class="editorial-section {key}-section"><div class="section-heading"><div><span class="section-number">{number}</span><h2>{name}</h2></div><p>{description}</p></div><div class="section-stories">{articles}</div></section>')
    points = []
    for point in issue['overview']:
        if point['target'] not in content: raise ValueError('Unknown overview target')
        text = '<br>'.join(esc(line) for line in point['text'].splitlines())
        points.append(f'<a href="#{point["target"]}"><span>{esc(point["label"])}</span><strong>{text}</strong><span aria-hidden="true">↗</span></a>')
    overview = '<section id="overview" class="overview" aria-labelledby="overview-title"><div class="overview-label"><span class="smallcaps">THE SHORT LIST</span><h2 id="overview-title">先看三个要点</h2></div><div class="overview-items">'+''.join(points)+'</div></section>'
    publication_day = dt.date.fromisoformat(issue['focus_date'])
    hero = esc(issue['hero_lines'][0])+'<br><em>'+esc(issue['hero_lines'][1])+'</em>'
    values = {'DATE':date,'DATE_DOTS':date.replace('-','.'),'TITLE':esc(issue['title']),
        'DESC':esc(issue['description']),'VOL':str(issue['vol']),'VOL_PAD':str(issue['vol']).zfill(3),
        'WEEKDAY':['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][day.weekday()],
        'NEWS':str(counts['featured']),'PAPERS':str(counts['papers']),'OSS':str(counts['opensource']),
        'NEWS_PAD':str(counts['featured']).zfill(2),'PAPERS_PAD':str(counts['papers']).zfill(2),'OSS_PAD':str(counts['opensource']).zfill(2),
        'HERO':hero,'HERO_DESCRIPTION':esc(issue['hero_description']),
        'WINDOW_LABEL':f'关注 {publication_day.month} 月 {publication_day.day} 日发布<br>与近期研究、工具发现',
        'PUBLIC_META':public_meta,'OVERVIEW':overview,'NAV':nav,'MAIN':''.join(sections),
        'COVERAGE':render_coverage(receipts,manuscript,issue),'ADDED_NOTE':'<br>'.join(esc(n) for n in issue['added_note'])}
    page = (ROOT / 'templates/editorial.html').read_text()
    for key,value in values.items(): page=page.replace('__'+key+'__',value)
    if re.search(r'__[A-Z_]+__',page): raise ValueError('Unfilled template fields')
    output = ROOT / ('ai-daily-digest-'+date+'.html')
    # Retain generated archive navigation when rebuilding only this issue.
    if output.exists():
        previous = output.read_text()
        for mark in ('top','bottom'):
            pattern = r'(<nav class="issue-nav[^"]*" aria-label="日报导航" data-nav="'+mark+r'">).*?(</nav>)'
            found = re.search(pattern,previous,re.S)
            if found: page=re.sub(pattern,lambda _:found.group(0),page,flags=re.S)
    output.write_text(page)
    print(f'Built {output.name}: {len(issue["items"])} items; audio {"available" if issue.get("audio_src") else "pending"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('date',help='Issue date, YYYY-MM-DD')
    args = parser.parse_args()
    build(args.date)

