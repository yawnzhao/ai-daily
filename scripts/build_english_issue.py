#!/usr/bin/env python3
"""Render the English translation while retaining the Chinese issue's factual record."""
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path

import build_editorial_issue as renderer

ROOT = Path(__file__).resolve().parents[1]
BASE = renderer.BASE
LOCALIZED_FIELDS = {'topic', 'source_label', 'date_note', 'verification_scope', 'license'}
esc = renderer.esc


def read_json(path):
    return json.loads(path.read_text())


def inline(text):
    rendered = renderer.inline(text)
    rendered = re.sub(r'`([^`]+)`', r'<code>\1</code>', rendered)
    return re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', rendered)


def build(date):
    issue = read_json(ROOT / f'data/issues/{date}.json')
    edition = read_json(ROOT / f'data/issues/en/{date}.json')
    receipts = read_json(ROOT / f'data/runs/{date}-receipts.json')
    glossary = read_json(ROOT / 'config/glossary.en.json')
    manuscript = (ROOT / edition['canonical_markdown']).read_text()
    source_content = renderer.parse_manuscript((ROOT / issue['canonical_markdown']).read_text())
    content = renderer.parse_manuscript(manuscript)
    ids = [i['id'] for i in issue['items']]
    if list(content) != ids or list(source_content) != ids or set(edition['items']) != set(ids):
        raise ValueError('English/Chinese item IDs or ordering differ')
    if edition['date'] != date or edition['language'] != 'en' or edition['status'] != 'published':
        raise ValueError('English edition is not ready for publication')
    for field, path in [('source_manuscript_sha256', issue['canonical_markdown']),
                        ('source_metadata_sha256', f'data/issues/{date}.json'),
                        ('translation_sha256', edition['canonical_markdown'])]:
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != edition[field]:
            raise ValueError('Review required after a source or translation change: ' + path)
    items = []
    for item in issue['items']:
        localized = edition['items'][item['id']]
        if set(localized) - LOCALIZED_FIELDS:
            raise ValueError('English overlay may only localize display fields')
        items.append({**item, **localized})
    groups = {key: [i for i in items if i['section'] == key]
              for key in ('featured', 'briefs', 'insight', 'papers', 'opensource')}
    intro = manuscript.split('\n\n', 1)[1].split('\n## ', 1)[0].strip()
    parts = ['<div class="focus-box"><div class="label">' + esc(edition['title'])
             + '</div><div class="content">' + inline(intro) + '</div></div>']
    labels = [
        ('featured', '📰', 'Top Stories', f'{len(groups["featured"])} stories'
         + (f' + {len(groups["briefs"])} briefs' if groups['briefs'] else '')),
        ('insight', '🔍', 'Industry Insights', 'Conversation Spotlight'),
        ('papers', '📄', 'Research Briefs', f'{len(groups["papers"])} paper' + ('s' if len(groups['papers']) != 1 else '')),
        ('opensource', '⭐', 'Open Source Spotlight', f'{len(groups["opensource"])} project' + ('s' if len(groups['opensource']) != 1 else '')),
    ]
    for key, icon, label, tag in labels:
        block = (f'<section class="section" id="{key}"><div class="section-header">'
                 f'<span class="icon" aria-hidden="true">{icon}</span><h2>{label}</h2>'
                 f'<span class="tag">{tag}</span></div>')
        if key == 'opensource':
            block += ('<div class="focus-box"><div class="label">Reading note</div>'
                      '<div class="content">Based on official documentation; no deployment tests were performed. '
                      'Inclusion here is a tool-discovery recommendation, not a claim that each project was first released today.</div></div>')
        selected = groups[key] + (groups['briefs'] if key == 'featured' else [])
        for number, item in enumerate(selected, 1):
            if key == 'featured' and groups['briefs'] and item['id'] == groups['briefs'][0]['id']:
                block += '<div class="paper-also"><div class="paper-also-title">Briefs</div>'
            rendered = renderer.render_item(item, content[item['id']],
                                            number - len(groups['featured']) if item['section'] == 'briefs' else number)
            rendered = re.sub(r'`([^`]+)`', r'<code>\1</code>', rendered)
            rendered = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', rendered)
            block += rendered
        if key == 'featured' and groups['briefs']:
            block += '</div>'
        parts.append(block.replace('来源：', 'Source: ') + '</section>')

    summary = receipts['summary']
    gaps = [s for s in receipts['sources'] if s['status'] != 'ok']
    if set(edition['coverage_gaps']) != {s['name'] for s in gaps}:
        raise ValueError('Translated coverage gaps do not match the source receipts')
    notes = manuscript.split('## Coverage Notes\n', 1)[1].strip()
    notes_html = ''.join('<p>' + inline(p) + '</p>' for p in notes.split('\n\n'))
    status_names = {'partial': 'Partially checked', 'failed': 'Access or collection failed', 'pending': 'Not yet checked'}
    rows = ''.join('<li><strong>' + esc(glossary['source_names'].get(s['name'], s['name']))
                   + '</strong> — ' + status_names[s['status']] + '. '
                   + esc(edition['coverage_gaps'][s['name']]) + '</li>' for s in gaps)
    status = 'Incomplete' if summary['incomplete'] else 'Source checks complete'
    parts.append('<details class="paper-observation" id="coverage"><summary class="label">'
                 f'Coverage notes · {status} · {summary["ok"]}/{len(receipts["sources"])} sources checked'
                 '</summary><div class="content">' + notes_html
                 + ('<p><strong>Coverage gaps</strong> reflect incomplete checks; they do not establish that a source had no updates.</p><ul>' + rows + '</ul>' if gaps else '')
                 + '<p>Reviewing a source does not constitute independent testing. '
                 'Paper-reading scope is stated with each item; experiments were not reproduced.</p></div></details>')

    # Render the same catalog as the Chinese edition; only source names are localized.
    catalog_html = renderer.render_source_catalog(issue, source_content)
    if catalog_html:
        catalog_html = re.sub(r'<span class="source-catalog-name">(.*?)</span>',
                              lambda m: '<span class="source-catalog-name">'
                              + esc(glossary['source_names'].get(html.unescape(m.group(1)), html.unescape(m.group(1)))) + '</span>',
                              catalog_html)
        catalog_html = catalog_html.replace('>资讯源 ', '>Sources &amp; discoveries ').replace(' 条</span>', ' links</span>')
        catalog_html = catalog_html.replace('aria-label="资讯标题与来源"', 'aria-label="Original titles and sources"')
        catalog_html = catalog_html.replace('<div class="content">', '<div class="content"><p>Titles are retained from the Chinese edition; source names are shown in English. This discovery list includes material not read in full.</p>', 1)
        parts.append(catalog_html)
    filename = f'ai-daily-digest-{date}.html'
    parts.append('<div class="source">AI-assisted translation, checked against the Chinese edition. '
                 '<a href="../' + filename + '">Read the Chinese edition</a>.</div>')
    audio = ''
    if issue.get('episode_url') and issue.get('audio_src'):
        seconds = round(issue.get('audio_duration_seconds') or issue['audio_duration'])
        audio = ('<div class="audio-player"><div class="play-info"><div class="play-label">Audio · Chinese</div>'
                 '<div class="play-title"><a href="' + esc(issue['episode_url'])
                 + '" target="_blank" rel="noopener">Listen in Chinese →</a></div>'
                 f'<div class="play-meta">Issue {issue["vol"]} · About {seconds // 60} min {seconds % 60} sec · AI-generated audio</div></div></div>')
    day = dt.date.fromisoformat(date)
    values = {'TITLE': esc(f'AI Daily Digest · {date} · {edition["title"]}'),
              'DESC': esc(edition['description']), 'CANONICAL': BASE + '/en/' + filename,
              'DATE': date, 'DATE_HUMAN': day.strftime('%B ') + str(day.day) + day.strftime(', %Y'),
              'WEEKDAY': day.strftime('%A'), 'VOL': str(issue['vol']),
              'NEWS_COUNT': str(len(groups['featured']) + len(groups['briefs'])),
              'PAPER_COUNT': str(len(groups['papers'])), 'OSS_COUNT': str(len(groups['opensource'])),
              'WINDOW_HOURS': str(issue['window_hours']), 'CONTENT': '\n'.join(parts), 'CHINESE_AUDIO': audio}
    page = (ROOT / 'templates/daily.en.html').read_text()
    for key, value in values.items():
        page = page.replace('{{' + key + '}}', value)
    page = page.replace('<span class="num">1</span>papers', '<span class="num">1</span>paper')
    page = page.replace('<span class="num">1</span>open-source projects', '<span class="num">1</span>open-source project')
    if re.search(r'\{\{[A-Z_]+\}\}', page):
        raise ValueError('Unfilled English template fields')
    output = ROOT / 'en' / filename
    if output.exists():
        previous = output.read_text()
        for mark in ('top', 'bottom'):
            pattern = r'(<nav class="issue-nav[^"]*" aria-label="Issue navigation" data-nav="' + mark + r'">).*?(</nav>)'
            found = re.search(pattern, previous, re.S)
            if found:
                page = re.sub(pattern, lambda _: found.group(0), page, flags=re.S)
    output.parent.mkdir(exist_ok=True)
    output.write_text(page)
    print(f'Built en/{filename}: {len(items)} translated items')
