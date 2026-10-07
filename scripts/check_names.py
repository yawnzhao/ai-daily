#!/usr/bin/env python3
"""Check source-backed formal names shared by both editions; never rewrite prose."""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FROM = '2026-10-08'
WORD = re.compile(r'[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*')
CAP = r'(?!(?:Formerly|Previously|Historical)\b)[A-Z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*'
EXPANSION = re.compile(r'(?P<name>(?:' + CAP + r'[ \t]+){1,7}' + CAP + r')\s*[(（](?P<abbr>[A-Z][A-Z0-9]{1,7})[)）]')
REVERSE = re.compile(r'(?P<abbr>[A-Z][A-Z0-9]{1,7})\s*[(（](?P<name>(?:' + CAP + r'[ \t]+){1,7}' + CAP + r')[)）]')
NAMED = re.compile(r'\b(?:called|named|known as)\s+[“\"]?(?P<name>' + CAP + r'(?:[ \t]+' + CAP + r'){0,6})')
HISTORY = re.compile(r'formerly|previously (?:called|named)|historical name|旧称|原名|历史名称|曾称', re.I)


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(text)).translate(str.maketrans({'‐':'-','‑':'-'})).split())


class ItemText(HTMLParser):
    def __init__(self, ids):
        super().__init__()
        self.ids, self.items, self.stack, self.active = set(ids), {}, [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.active is None and attrs.get('id') in self.ids:
            self.active = attrs['id']
            self.items[self.active] = []
            self.stack = [tag]
        elif self.active is not None and tag not in {'br','img','hr','input','meta','link'}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.active is not None and tag in self.stack:
            while self.stack:
                current = self.stack.pop()
                if current == tag:
                    break
            if not self.stack:
                self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.items[self.active].append(data)


def plain_markdown(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    return text.replace('**', '').replace('`', '')


def check_text(text, names):
    """Catch conflicting occurrences, even when the correct name is also present."""
    errors = []
    text = normalize(text)
    allowed = set()
    historical = set()
    by_abbr = {}
    historical_by_abbr = {}
    for entry in names:
        forms = [entry['official_name']] + entry.get('aliases', [])
        if entry.get('chinese_name'):
            forms.append(entry['chinese_name'])
        allowed.update(normalize(f) for f in forms)
        historical.update(normalize(f) for f in entry.get('historical_names', []))
        if entry.get('abbreviation'):
            by_abbr[entry['abbreviation']] = {normalize(f) for f in forms}
            historical_by_abbr[entry['abbreviation']] = {normalize(f) for f in entry.get('historical_names', [])}
    for pattern in (EXPANSION, REVERSE):
        for match in pattern.finditer(text):
            name, abbr = match.group('name'), match.group('abbr')
            if abbr not in by_abbr:
                errors.append('正式名称/缩写无对应原文记录：' + name + ' (' + abbr + ')')
            elif name not in by_abbr[abbr]:
                labeled_history = name in historical_by_abbr[abbr] and HISTORY.search(text[max(0,match.start()-80):match.start()])
                if not labeled_history:
                    errors.append('缩写展开不一致：' + name + ' (' + abbr + ')')
    for match in NAMED.finditer(text):
        if match.group('name') not in allowed | historical:
            errors.append('具名表述无出处记录：' + match.group('name'))
    for historic in historical:
        for match in re.finditer(re.escape(historic), text):
            if not HISTORY.search(text[max(0, match.start()-80):match.start()]):
                errors.append('历史名称未标明原语境：' + historic)
    tokens = list(WORD.finditer(text))
    for name in allowed:
        target = WORD.findall(name)
        if not target:
            continue
        n = len(target)
        for at in range(len(tokens)-n+1):
            segment = tokens[at:at+n]
            phrase = text[segment[0].start():segment[-1].end()]
            words = [m.group() for m in segment]
            if any(not re.fullmatch(r'\s+', text[a.end():b.start()]) for a,b in zip(segment,segment[1:])):
                continue  # Do not join names across punctuation or Chinese explanations.
            if words[0].casefold() != target[0].casefold() and SequenceMatcher(None,words[0].lower(),target[0].lower()).ratio() < .8:
                continue  # A normal sentence ending is not a renamed product.
            # Lowercase descriptions are not declarations of a formal name.
            if not words[0][0].isupper() and not any(c.isdigit() for c in words[0]):
                continue
            if phrase in allowed | historical:
                continue
            equal = [a.casefold() == b.casefold() for a,b in zip(words,target)]
            mismatch = [i for i, same in enumerate(equal) if not same]
            near = not mismatch
            if len(mismatch) == 1:
                i = mismatch[0]
                near = (n >= 3 or (n == 2 and (any(c.isdigit() for c in target[i]) or SequenceMatcher(None, words[i].lower(), target[i].lower()).ratio() >= .8)))
            if n == 1:
                near = (words[0][:3].lower() == target[0][:3].lower() and SequenceMatcher(None, words[0].lower(), target[0].lower()).ratio() >= .85)
            if near:
                errors.append('正式名称拼写不一致：' + phrase + '；原文为 ' + name)
    return sorted(set(errors))


def check_date(root, date, lang='all', sources_only=False):
    root = Path(root)
    path = root / f'data/issues/{date}.json'
    if not path.exists():
        return [] if date < REQUIRED_FROM else ['缺少当期名称元数据']
    issue = json.loads(path.read_text())
    if 'official_names' not in issue:
        return [] if date < REQUIRED_FROM else ['缺少共用 official_names 原文名称记录']
    registry = issue['official_names']
    errors = []
    if not isinstance(registry, dict):
        return ['official_names 必须按稳定 ID 保存一份共用记录']
    for key, entry in registry.items():
        if not isinstance(entry, dict) or not all(entry.get(k) for k in ('official_name','source_url','source_excerpt')):
            errors.append('名称记录缺少正式名称或出处：' + key)
            continue
        string_fields = ('official_name','source_url','source_excerpt','abbreviation','chinese_name')
        if any(entry.get(k) is not None and not isinstance(entry[k],str) for k in string_fields) or any(not isinstance(entry.get(k,[]),list) or any(not isinstance(v,str) for v in entry.get(k,[])) for k in ('aliases','historical_names')):
            errors.append('名称记录字段类型不正确：' + key)
            continue
        quote = normalize(entry['source_excerpt'])
        if normalize(entry['official_name']) not in quote or (entry.get('abbreviation') and entry['abbreviation'] not in quote):
            errors.append('原文片段不支持名称/缩写：' + key)
        if not entry['source_url'].startswith('https://'):
            errors.append('名称出处须为原始 HTTPS 链接：' + key)
    if errors:
        return errors
    items = {i['id']:i for i in issue['items']}
    for key, item in items.items():
        if not isinstance(item.get('official_name_ids'),list) or any(not isinstance(k,str) or k not in registry for k in item.get('official_name_ids', [])):
            errors.append('条目缺少名称引用或引用不存在：' + key)
    if errors:
        return errors
    languages = ['zh-CN','en'] if lang == 'all' else [lang]
    for language in languages:
        if language == 'en':
            ep = root / f'data/issues/en/{date}.json'
            if not ep.exists():
                continue
            manuscript = root / json.loads(ep.read_text())['canonical_markdown']
        else:
            manuscript = root / issue['canonical_markdown']
        if not manuscript.exists():
            errors.append('缺少源稿：' + str(manuscript.relative_to(root)))
            continue
        # Use the existing item IDs; do not inspect the unreviewed source catalog.
        import build_editorial_issue as renderer
        blocks = renderer.parse_manuscript(manuscript.read_text())
        for key, item in items.items():
            if key not in blocks:
                continue  # Structural validation already handles missing IDs.
            names = [registry[k] for k in item['official_name_ids']]
            block = blocks[key]
            text = plain_markdown(block['title'] + '\n' + '\n'.join(block['paragraphs']))
            errors.extend(str(manuscript.relative_to(root)) + '/' + key + ': ' + e for e in check_text(text,names))
        if not sources_only:
            hp = root / (('en/' if language == 'en' else '') + f'ai-daily-digest-{date}.html')
            if hp.exists():
                parser = ItemText(items)
                page_text = hp.read_text()
                parser.feed(page_text)
                for key, parts in parser.items.items():
                    names = [registry[k] for k in items[key]['official_name_ids']]
                    errors.extend(str(hp.relative_to(root)) + '/' + key + ': ' + e for e in check_text(' '.join(parts),names))
    script = root / f'daily/scripts/{date}.txt'
    if lang in ('all','zh-CN') and script.exists():
        errors.extend(str(script.relative_to(root)) + ': ' + e for e in check_text(script.read_text(),list(registry.values())))
    return sorted(set(errors))


def write_report(root, dates, report_path, sources_only=False):
    root = Path(root)
    results = {date:check_date(root,date,sources_only=sources_only) for date in dates}
    files = [p for date in dates for p in [root/f'daily/{date[:4]}/{date}.md',root/f'daily/en/{date[:4]}/{date}.md',root/f'data/issues/{date}.json'] if p.exists()]
    report = {'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'registered names, spelling variants, explicit expansions and named declarations; not a general fact/claim endorsement','sources_only':sources_only,'results':results,'input_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    p = Path(report_path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date')
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--report',help='Private run receipt path; not rendered into reader content')
    args = parser.parse_args()
    errors = check_date(ROOT,args.date,sources_only=args.sources_only)
    if args.report:
        write_report(ROOT,[args.date],args.report,args.sources_only)
    for error in errors:
        print(error)
    print('名称检查：' + ('需编辑核对后再发布' if errors else '通过'))
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
