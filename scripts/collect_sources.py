#!/usr/bin/env python3
"""按 config/sources.json 逐源检查，产出收据草稿。

用法：python3 scripts/collect_sources.py --until 2026-09-18T01:15:00Z --out data/runs/2026-09-18-sources.json

- rss 源：解析 feed，列出发现窗口内的条目（标题、链接、发布时间）。
- page 源：抓页面，提取页面上出现的日期，报告最新日期和窗口内的链接；提取不到日期记 partial。
- browser 源：脚本不处理，记为 pending，由人或 agent 用浏览器补查后改写收据。
- api / github-trending：由 agent 另行核验，这里只做可达性检查。

脚本只负责「每个源都被看过、看到了什么」，不做选稿判断。
"""
import argparse
import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en,zh;q=0.8'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def rss_items(text):
    root = ET.fromstring(text.encode('utf-8'))
    out = []
    for it in root.iter():
        tag = it.tag.split('}')[-1]
        if tag not in ('item', 'entry'):
            continue
        get = lambda name: next((c for c in it if c.tag.split('}')[-1] == name), None)
        title = (get('title').text or '').strip() if get('title') is not None else ''
        link_el = get('link')
        link = ''
        if link_el is not None:
            link = (link_el.text or '').strip() or link_el.attrib.get('href', '')
        when = None
        for name in ('pubDate', 'published', 'updated', 'date'):
            el = get(name)
            if el is not None and el.text:
                when = parse_date(el.text)
                if when:
                    break
        out.append({'title': html.unescape(title), 'url': link, 'published_at': when})
    return out


DATE_PATTERNS = [
    (re.compile(r'\b(20\d\d)-(\d\d)-(\d\d)'), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), (20\d\d)'),
     lambda m: (int(m[3]), MONTHS[m[1].lower()[:3]], int(m[2]))),
    (re.compile(r'\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)'),
     lambda m: (int(m[3]), MONTHS[m[2].lower()[:3]], int(m[1]))),
]


def page_dates(text):
    """页面上出现的日期，连同其前面最近的一个链接。"""
    found = []
    for pat, conv in DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                y, mo, d = conv(m)
                day = dt.date(y, mo, d)
            except (ValueError, KeyError):
                continue
            before = text[max(0, m.start() - 1500):m.start()]
            links = re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', before, re.S)
            link, label = (links[-1] if links else ('', ''))
            label = re.sub(r'<[^>]+>', ' ', label)
            found.append((day, link, re.sub(r'\s+', ' ', html.unescape(label)).strip()[:120]))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--until', required=True, help='采集截止时间（ISO，UTC）')
    ap.add_argument('--hours', type=int, help='发现窗口，默认取配置')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    cfg = json.loads((ROOT / 'config' / 'sources.json').read_text())
    until = parse_date(args.until)
    hours = args.hours or cfg['discovery_window_hours']
    since = until - dt.timedelta(hours=hours)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    receipts = []

    for s in cfg['sources']:
        r = {'source_id': s['id'], 'name': s['name'], 'core': s['core'], 'method': s['method'],
             'checked_at': now, 'checked_url': s.get('feed') or s['url'], 'status': 'failed',
             'evidence': '', 'items': []}
        try:
            if s['method'] == 'browser':
                r['status'] = 'pending'
                r['evidence'] = '脚本不处理，需浏览器补查'
            elif s['method'] == 'rss':
                code, text = fetch(s['feed'])
                items = rss_items(text)
                dated = [i for i in items if i['published_at']]
                newest = max((i['published_at'] for i in dated), default=None)
                hits = [i for i in dated if since <= i['published_at'] <= until]
                r['items'] = [{'title': i['title'], 'url': i['url'],
                               'published_at': i['published_at'].isoformat()} for i in hits]
                r['status'] = 'ok' if dated else 'partial'
                r['evidence'] = (f'feed HTTP {code}，共 {len(items)} 条，带日期 {len(dated)} 条，'
                                 f'最新 {newest.isoformat() if newest else "未知"}；窗口内 {len(hits)} 条')
            elif s['method'] in ('page', 'api'):
                url = s['url']
                if s['id'] == 'arxiv':
                    url += '?search_query=cat:cs.LG+OR+cat:cs.AI+OR+cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=5'
                code, text = fetch(url)
                found = page_dates(text) if s['method'] == 'page' else []
                if s['method'] == 'api' or s['id'] == 'github-trending':
                    r['status'] = 'ok'
                    r['evidence'] = f'HTTP {code}，可达；条目由主线程另行核验'
                elif not found:
                    r['status'] = 'partial'
                    r['evidence'] = f'HTTP {code}，页面上提取不到日期，无法判断窗口内有无新条目'
                else:
                    newest = max(f[0] for f in found)
                    hits = {(d, link, label) for d, link, label in found
                            if since.date() <= d <= until.date()}
                    r['items'] = [{'title': label, 'url': link, 'published_at': d.isoformat()}
                                  for d, link, label in sorted(hits, reverse=True)]
                    r['status'] = 'ok'
                    r['evidence'] = (f'HTTP {code}，页面日期 {len(found)} 处，最新 {newest}；'
                                     f'窗口内 {len(hits)} 条（按日期匹配，粒度到天）')
        except Exception as e:  # noqa: BLE001 — 每个源的失败都要记下来，不能中断其他源
            r['status'] = 'failed'
            r['evidence'] = f'{type(e).__name__}: {str(e)[:200]}'
        receipts.append(r)
        print(f"{r['status']:<8} {'核心' if s['core'] else '    '} {s['id']:<16} {r['evidence'][:110]}")

    done = [r for r in receipts if r['status'] != 'pending']
    ok = [r for r in done if r['status'] == 'ok']
    core_bad = [r['source_id'] for r in receipts if r['core'] and r['status'] not in ('ok',)]
    summary = {'window': [since.isoformat(), until.isoformat()], 'planned': len(receipts),
               'ok': len(ok), 'partial': sum(r['status'] == 'partial' for r in receipts),
               'failed': sum(r['status'] == 'failed' for r in receipts),
               'pending_browser': sum(r['status'] == 'pending' for r in receipts),
               'core_not_ok': core_bad}
    Path(args.out).write_text(json.dumps({'summary': summary, 'sources': receipts},
                                         ensure_ascii=False, indent=2))
    print(f"\n计划 {summary['planned']} 源：ok {summary['ok']} / partial {summary['partial']} / "
          f"failed {summary['failed']} / 待浏览器 {summary['pending_browser']}；核心源未达 ok：{core_bad or '无'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
