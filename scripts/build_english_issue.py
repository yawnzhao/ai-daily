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
    rendered = re.sub(r'\[([^\]]+)\]\((http://[^\s)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', rendered)
    rendered = re.sub(r'`([^`]+)`', r'<code>\1</code>', rendered)
    return re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', rendered)


def validate_archive_provenance(issue):
    """Keep normalized legacy inputs tied to the untouched published originals."""
    if not issue.get('archive_backfill'):
        return
    provenance = issue['archive_provenance']
    page = (ROOT / provenance['source_page']).read_text()
    main = re.search(r'<main id="main">(.*?)</main>', page, re.S)
    if not main or hashlib.sha256(main.group(1).encode()).hexdigest() != provenance['source_main_sha256']:
        raise ValueError('Archived Chinese page changed; source review required')
    if provenance.get('source_manuscript'):
        original = ROOT / provenance['source_manuscript']
        if hashlib.sha256(original.read_bytes()).hexdigest() != provenance['source_manuscript_sha256']:
            raise ValueError('Archived Chinese manuscript changed; source review required')


def build(date):
    import check_names
    errors = check_names.check_date(ROOT, date, lang='en', sources_only=True)
    if errors:
        raise ValueError('Original-source name review failed: ' + '; '.join(errors))
    issue = read_json(ROOT / f'data/issues/{date}.json')
    edition = read_json(ROOT / f'data/issues/en/{date}.json')
    validate_archive_provenance(issue)
    receipt_path = ROOT / f'data/runs/{date}-receipts.json'
    receipts = read_json(receipt_path) if receipt_path.exists() else {'sources': []}
    glossary = read_json(ROOT / 'config/glossary.en.json')
    manuscript = (ROOT / edition['canonical_markdown']).read_text()
    source_content = renderer.parse_manuscript((ROOT / issue['canonical_markdown']).read_text())
    content = renderer.parse_manuscript(manuscript)
    ids = [i['id'] for i in issue['items']]
    if list(content) != list(source_content) or set(source_content) != set(ids) or set(edition['items']) != set(ids):
        raise ValueError('English/Chinese item IDs or ordering differ')
    if edition['date'] != date or edition['language'] != 'en' or edition['status'] != 'published':
        raise ValueError('English edition is not ready for publication')
    for field, path in [('source_manuscript_sha256', issue['canonical_markdown']),
                        ('source_metadata_sha256', f'data/issues/{date}.json'),
                        ('translation_sha256', edition['canonical_markdown'])]:
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != edition[field]:
            raise ValueError('Review required after a source or translation change: ' + path)
    items = []
    by_id = {item['id']: item for item in issue['items']}
    for item_id in source_content:
        item = by_id[item_id]
        localized = edition['items'][item['id']]
        if set(localized) - LOCALIZED_FIELDS:
            raise ValueError('English overlay may only localize display fields')
        items.append({**item, **localized})
    groups = {key: [i for i in items if i['section'] == key]
              for key in ('featured', 'briefs', 'insight', 'discourse', 'papers', 'paper_briefs', 'opensource')}
    intro = manuscript.split('\n\n', 1)[1].split('\n## ', 1)[0].strip()
    parts = ['<div class="focus-box"><div class="label">' + esc(edition['title'])
             + '</div><div class="content">' + inline(intro) + '</div></div>']
    labels = [
        ('featured', '📰', 'Top Stories', f'{len(groups["featured"])} stories'
         + (f' + {len(groups["briefs"])} briefs' if groups['briefs'] else '')),
        ('insight', '🔍', 'Industry Insights', 'Editorial analysis' if issue.get('archive_backfill') else 'Conversation Spotlight'),
        ('papers', '📄', 'Research Briefs', f'{len(groups["papers"])} paper' + ('s' if len(groups['papers']) != 1 else '')),
        ('opensource', '⭐', 'Open Source Spotlight', f'{len(groups["opensource"])} project' + ('s' if len(groups['opensource']) != 1 else '')),
    ]
    for key, icon, label, tag in labels:
        block = (f'<section class="section" id="{key}"><div class="section-header">'
                 f'<span class="icon" aria-hidden="true">{icon}</span><h2>{label}</h2>'
                 f'<span class="tag">{tag}</span></div>')
        contexts = [i for i in items if i['section'] == key + '_context']
        for item in contexts:
            c = content[item['id']]
            block += ('<div class="focus-box" id="' + esc(item['id']) + '"><div class="label">' + inline(c['title']) + '</div><div class="content">' + ''.join('<p>' + inline(p) + '</p>' for p in c['paragraphs']) + '</div></div>')
        if key == 'opensource' and groups['opensource']:
            block += ('<div class="focus-box"><div class="label">Reading note</div>'
                      '<div class="content">' + ('Historical project descriptions; this backfill performed no fresh deployment tests. Stars refer to the original issue. ' if issue.get('archive_backfill') else 'Based on official documentation; no deployment tests were performed. ')
                      +
                      'Inclusion here is a tool-discovery recommendation, not a claim that each project was first released today.</div></div>')
        selected = groups[key] + (groups['briefs'] if key == 'featured' else groups['discourse'] if key == 'insight' else groups['paper_briefs'] if key == 'papers' else [])
        if not selected and not contexts:
            block += '<p>' + esc(edition.get('section_notes', {}).get(key, 'No separate items were recorded in this section of the original manuscript.')) + '</p>'
        for number, item in enumerate(selected, 1):
            if key == 'featured' and groups['briefs'] and item['id'] == groups['briefs'][0]['id']:
                block += '<div class="paper-also"><div class="paper-also-title">Briefs</div>'
            render_item = {**item, 'section': 'insight' if item['section'] == 'discourse' else 'briefs' if item['section'] == 'paper_briefs' else item['section']}
            rendered = renderer.render_item(render_item, content[item['id']],
                                            number - len(groups['featured']) if item['section'] == 'briefs' else number)
            rendered = re.sub(r'`([^`]+)`', r'<code>\1</code>', rendered)
            rendered = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', rendered)
            rendered = re.sub(r'\[([^\]]+)\]\((http://[^\s)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', rendered)
            block += rendered
        if key == 'featured' and groups['briefs']:
            block += '</div>'
        parts.append(block.replace('来源：', 'Source: ') + '</section>')

    summary = receipts.get('summary', {})
    gaps = [s for s in receipts['sources'] if s['status'] != 'ok']
    if set(edition['coverage_gaps']) != {s.get('name', s.get('source_id', s.get('id'))) for s in gaps}:
        raise ValueError('Translated coverage gaps do not match the source receipts')
    notes = manuscript.split('## Coverage Notes\n', 1)[1].strip()
    notes_html = ''.join('<p>' + inline(p) + '</p>' for p in notes.split('\n\n'))
    status_names = {'partial': 'Partially checked', 'failed': 'Access or collection failed', 'pending': 'Not yet checked'}
    rows = ''.join('<li><strong>' + esc(glossary['source_names'].get(s.get('name', s.get('source_id', s.get('id'))), s.get('name', s.get('source_id', s.get('id')))))
                   + '</strong> — ' + status_names[s['status']] + '. '
                   + esc(edition['coverage_gaps'][s.get('name', s.get('source_id', s.get('id')))]) + '</li>' for s in gaps)
    ok = summary.get('ok', sum(s['status'] == 'ok' for s in receipts['sources']))
    incomplete = summary.get('incomplete', bool(receipts['sources']) and (ok / len(receipts['sources']) < .9 or bool(summary.get('core_not_ok'))))
    status = 'Incomplete' if incomplete else 'Coverage threshold met'
    coverage_label = ('Historical coverage record' if issue.get('archive_backfill') else f'Coverage notes · {status}')
    parts.append('<details class="paper-observation" id="coverage"><summary class="label">' +
                 coverage_label + (f' · {ok}/{len(receipts["sources"])} checks recorded' if receipts['sources'] else ' · Receipts unavailable') +
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
        for zh_label, en_label in zip(renderer.CATALOG_LABELS, ('News', 'Concourse', 'Papers', 'Open source and releases')):
            catalog_html = catalog_html.replace('<h3 class="source-catalog-heading">' + zh_label,
                                                '<h3 class="source-catalog-heading">' + en_label)
        catalog_html = re.sub(r'(<h3 class="source-catalog-heading">.*? · \d+) 条</h3>', r'\1 links</h3>', catalog_html)
        catalog_html = catalog_html.replace('<div class="content">', '<div class="content"><p>Titles are retained from the Chinese edition; source names are shown in English. This discovery list includes material not read in full.</p>', 1)
        parts.append(catalog_html)
    filename = f'ai-daily-digest-{date}.html'
    parts.append('<div class="source">AI-assisted translation, checked against the Chinese edition. '
                 '<a href="../' + filename + '">Read the Chinese edition</a>.</div>')
    audio = ''
    episode_url = issue.get('episode_url') or issue.get('audio_episode_url')
    if episode_url and issue.get('audio_src'):
        seconds = round(issue.get('audio_duration_seconds') or issue.get('audio_duration') or 0)
        audio = ('<div class="audio-player"><div class="play-info"><div class="play-label">Audio · Chinese</div>'
                 '<div class="play-title"><a href="' + esc(episode_url)
                 + '" target="_blank" rel="noopener">Listen in Chinese →</a></div>'
                 f'<div class="play-meta">Issue {issue["vol"]}' + (f' · About {seconds // 60} min {seconds % 60} sec' if seconds else '') + ' · AI-generated audio</div></div></div>')
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
