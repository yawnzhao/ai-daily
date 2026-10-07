#!/usr/bin/env python3
"""提交前检查日报页面：该有的 meta、导航、语义标签、外链写法有没有丢。

用法：python3 scripts/check_page.py                 # 检查全部页面
      python3 scripts/check_page.py 2026-09-18      # 只检查某一天
有问题时逐条打印并以退出码 1 结束。这些都是过去真出过的问题，不是风格偏好。
"""
import datetime
import argparse
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r'^ai-daily-digest-(\d{4}-\d{2}-\d{2})\.html$')
SECTIONS = ['每日精选', '行业洞见', '论文速递', '开源解读']


def check_issue(path, lang='zh-CN'):
    """检查一期日报页，返回问题列表。"""
    t = path.read_text()
    date = PAGE_RE.match(path.name).group(1)
    bad = []
    editorial = 'data-layout="editorial-v2"' in t
    audio = re.search(r'var AUDIO_SRC = "([^"]*)"', t)

    for pat, what in [
        (r'<meta name="description" content="[^"]{10,}">', 'meta description（分享和搜索都靠它）'),
        (r'<link rel="canonical" href="https://[^"]+">', 'canonical'),
        (r'<meta property="og:title" content="[^"]{5,}">', 'og:title'),
        (r'<meta property="og:url" content="https://[^"]+">', 'og:url'),
        (r'<meta name="twitter:card"', 'twitter:card'),
        (r'<link rel="icon"', 'favicon'),
        (r'<link rel="alternate" type="application/rss\+xml"', 'RSS 链接'),
        (r'<header class="masthead">' if editorial else r'<header class="header">', '<header> 语义标签'),
        (r'<main id="main">', '<main> 语义标签'),
        (r'data-nav="top"', '页眉导航块'),
        (r'data-nav="bottom"', '页尾导航块'),
    ]:
        if not re.search(pat, t):
            bad.append(f'缺少 {what}')

    if lang == 'en':
        if '<audio' in t or 'var AUDIO_SRC' in t:
            bad.append('英文版不应嵌入未提供的英文音频播放器')
        bad.extend(check_translation(path))
    elif not editorial:
        if audio and audio.group(1):
            for pattern, label in [(r'role="slider"','播放进度条的 role'), (r'aria-label="播放语音简报"','播放按钮的 aria-label')]:
                if not re.search(pattern,t): bad.append(f'缺少 {label}')
        elif '语音版制作中' not in t:
            bad.append('未发布音频时应显示制作中')
    else:
        match = re.search(r'<script type="application/json" id="daily-metadata">(.*?)</script>',t,re.S)
        try:
            metadata = json.loads(match.group(1)) if match else {}
            if metadata.get('date') != date or metadata.get('layout') != 'editorial-v2':
                bad.append('新版页面元数据与日期不一致')
            src = metadata.get('audio_src')
            if src:
                if not isinstance(src,str) or not src.startswith('https://') or f'src="{src}"' not in t:
                    bad.append('音频元数据与播放器不一致')
                if not re.search(r'<audio[^>]*controls[^>]*aria-label=',t):
                    bad.append('音频缺少可访问的播放控件')
            elif '<audio' in t or '语音版制作中' not in t:
                bad.append('未发布音频时应显示制作中，不应显示空播放器')
            for key, section in [('news','featured'),('papers','papers'),('oss','opensource')]:
                actual = len(re.findall(r'class="story '+section+r'-story"',t))
                if type(metadata.get(key)) is not int or metadata[key] != actual:
                    bad.append(f'{key} 数量与正文不一致')
        except (ValueError,TypeError):
            bad.append('新版页面元数据无法解析')
    if re.search(r'noindex|LOCAL PREVIEW|尚未替换线上|本地预览',t):
        bad.append('正式页面仍包含预览标记')

    if f'<time datetime="{date}">' not in t:
        bad.append(f'<time datetime="{date}"> 和文件名对不上')

    title = re.search(r'<title>(.*?)</title>', t)
    if not title:
        bad.append('没有 <title>')
    elif date not in title.group(1) or len(title.group(1)) < 20:
        bad.append(f'标题要带日期和当期主线，现在是：{title.group(1) if title else ""}')

    names = ['Top Stories', 'Industry Insights', 'Research Briefs', 'Open Source Spotlight'] if lang == 'en' else (['每日精选','行业观察','论文速递','开源解读'] if editorial else SECTIONS)
    for name in names:
        if f'<h2>{name}</h2>' not in t:
            bad.append(f'少了「{name}」板块')

    # 导航指向的页面必须真实存在
    for target in re.findall(r'<nav class="issue-nav[^>]*>(.*?)</nav>', t, re.S):
        for href in re.findall(r'href="([^"]+)"', target):
            if href == '#':
                continue
            base = ROOT / 'en' if lang == 'en' else ROOT
            if not (base / href).is_file():
                bad.append(f'导航指向不存在的页面：{href}')

    # 外链必须新标签页打开
    plain = re.findall(r'<a href="(https?://[^"]+)"(?![^>]*target=)', t)
    if plain:
        bad.append(f'{len(plain)} 条外链没写 target="_blank" rel="noopener"，第一条：{plain[0][:60]}')

    # 音频：有直链才说有语音版
    if audio and audio.group(1) and not audio.group(1).startswith('https://'):
        bad.append('AUDIO_SRC 不是 https 直链')

    import check_names
    try:
        bad.extend(check_names.check_date(ROOT, date, lang=lang))
    except (KeyError, ValueError, TypeError, OSError) as error:
        bad.append('名称检查无法完成：' + str(error))
    return bad


def check_translation(path):
    import build_editorial_issue as renderer
    import build_english_issue
    date = PAGE_RE.match(path.name).group(1)
    t = path.read_text()
    bad = []
    if not (ROOT / path.name).is_file():
        return ['英文版缺少对应中文页面']
    try:
        issue = json.loads((ROOT / f'data/issues/{date}.json').read_text())
        build_english_issue.validate_archive_provenance(issue)
        edition = json.loads((ROOT / f'data/issues/en/{date}.json').read_text())
        en = renderer.parse_manuscript((ROOT / edition['canonical_markdown']).read_text())
        zh = renderer.parse_manuscript((ROOT / issue['canonical_markdown']).read_text())
        ids = [i['id'] for i in issue['items']]
        if list(en) != list(zh) or set(zh) != set(ids) or set(edition['items']) != set(ids):
            bad.append('中英条目 ID、顺序或翻译字段不一致')
        if edition.get('status') != 'published' or not edition.get('published_at'):
            bad.append('英文版缺少正式发布状态与时间')
        for key, filename in [('source_manuscript_sha256', issue['canonical_markdown']),
                              ('source_metadata_sha256', f'data/issues/{date}.json'),
                              ('translation_sha256', edition['canonical_markdown'])]:
            if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != edition[key]:
                bad.append('原稿或译稿变更后尚未复核：' + filename)
        for item in issue['items']:
            localized = edition['items'].get(item['id'], {})
            if set(localized) - build_english_issue.LOCALIZED_FIELDS:
                bad.append('英文元数据重复保存或覆盖事实字段：' + item['id'])
            if t.count('id="' + item['id'] + '"') != 1 or html.escape(item['primary_url'], quote=True) not in t:
                bad.append('英文正文缺少条目或原始链接：' + item['id'])
            for url in item.get('source_urls', []):
                if html.escape(url, quote=True) not in t:
                    bad.append('英文正文缺少原刊的补充来源链接：' + item['id'])
        if '<html lang="en">' not in t or 'noindex' in t or 'English edition · Preview' in t:
            bad.append('英文语言标记或正式发布标记不正确')
        canonical = f'{renderer.BASE}/en/{path.name}'
        for required in (f'<link rel="canonical" href="{canonical}">',
                         f'<meta property="og:url" content="{canonical}">',
                         f'href="{renderer.BASE}/en/feed.xml"',
                         f'hreflang="zh-CN" href="{renderer.BASE}/{path.name}"',
                         f'hreflang="en" href="{canonical}"'):
            if required not in t:
                bad.append('英文 SEO 或 RSS 地址不一致：' + required)
        zh_page = (ROOT / path.name).read_text()
        if f'href="en/{path.name}"' not in zh_page or f'href="../{path.name}"' not in t:
            bad.append('中英语言切换不是双向的')
        episode_url = issue.get('episode_url') or issue.get('audio_episode_url')
        audio = bool(issue.get('audio_src') and episode_url)
        if audio != ('Listen in Chinese' in t) or (audio and episode_url not in t):
            bad.append('中文音频入口与原版状态不一致')
        counts = {'news items': sum(i['section'] in ('featured', 'briefs') for i in issue['items']),
                  'papers': sum(i['section'] == 'papers' for i in issue['items']),
                  'open-source projects': sum(i['section'] == 'opensource' for i in issue['items'])}
        for label, count in counts.items():
            if count == 1 and label in ('papers', 'open-source projects'):
                label = label[:-1]
            if f'<span class="num">{count}</span>{label}' not in t:
                bad.append('英文页头统计与中文元数据不符：' + label)
        source_catalog = renderer.render_source_catalog(issue, zh)
        matches = re.findall(r'<ul class="source-catalog-list"[^>]*>(.*?)</ul>', t, re.S)
        if bool(source_catalog) != bool(matches):
            bad.append('中英来源目录是否存在不一致')
        elif matches:
            original = ''.join(re.findall(r'<ul class="source-catalog-list"[^>]*>(.*?)</ul>', source_catalog, re.S))
            names = json.loads((ROOT / 'config/glossary.en.json').read_text())['source_names']
            expected = re.sub(r'<span class="source-catalog-name">(.*?)</span>',
                              lambda m: '<span class="source-catalog-name">' + html.escape(names.get(html.unescape(m.group(1)), html.unescape(m.group(1))), quote=True) + '</span>', original)
            if expected != ''.join(matches):
                bad.append('来源目录标题、链接、顺序或英文来源名称与中文版不一致')
            labels = re.findall(r'<span class="source-catalog-name">(.*?)</span>', ''.join(matches))
            if any(re.search(r'[\u3400-\u9fff]', s) for s in labels):
                bad.append('来源名称仍含未翻译中文')
        for nav in re.findall(r'<nav\b[^>]*>(.*?)</nav>', t, re.S):
            if any('href="#' + section + '"' in nav for section in ('featured', 'insight', 'papers', 'opensource')):
                bad.append('英文菜单不应添加栏目跳转')
    except (KeyError, ValueError, OSError, TypeError) as exc:
        bad.append('英文对照数据无法读取：' + str(exc))
    return bad


def check_index(lang='zh-CN'):
    base = ROOT / 'en' if lang == 'en' else ROOT
    t = (base / 'index.html').read_text()
    bad = []
    if re.search(r'\.episode \.info \.desc \{[^}]*white-space: nowrap', t):
        bad.append('首页摘要又变回 nowrap，会在手机上把卡片撑到屏幕外')
    if not re.search(r'\.episode \{[^}]*text-decoration: none', t):
        bad.append('首页卡片缺 text-decoration: none，整张卡会带下划线')
    if 'align-items: flex-start' in t:
        bad.append('手机端媒体查询里的 align-items 要用 stretch，flex-start 会让卡片不撑满')

    # 首页声称有语音版的，页面里必须真有直链
    for m in re.finditer(r'<a class="episode" href="(ai-daily-digest-[\d-]+\.html)">(.*?)</a>', t, re.S):
        page, block = m.group(1), m.group(2)
        if lang == 'en':
            page_text = (base / page).read_text()
            if ('Audio · Chinese' in block) != ('Listen in Chinese' in page_text):
                bad.append(f'{page}：英文首页与中文音频入口不一致')
            continue
        claims_audio = '语音版 · 小宇宙' in block
        page_text = (ROOT / page).read_text()
        metadata_match = re.search(r'<script type="application/json" id="daily-metadata">(.*?)</script>',page_text,re.S)
        if metadata_match:
            has_audio = bool(json.loads(metadata_match.group(1)).get('audio_src'))
        else:
            src = re.search(r'var AUDIO_SRC = "([^"]*)"',page_text)
            has_audio = bool(src and src.group(1))
        if claims_audio and not has_audio:
            bad.append(f'{page}：首页写了「语音版 · 小宇宙」，但页面里没有音频直链')
        if has_audio and not claims_audio:
            bad.append(f'{page}：页面已有音频，首页还标着制作中')
    if lang == 'en':
        expected = sorted(p.name for p in base.glob('ai-daily-digest-*.html'))
        linked = re.findall(r'<a class="episode" href="([^"]+)">', t)
        if sorted(linked) != expected:
            bad.append('英文首页与已发布英文期次不一致')
        feed = ET.parse(base / 'feed.xml').getroot()
        links = [x.text.rsplit('/', 1)[-1] for x in feed.findall('./channel/item/link')]
        if links != linked or feed.findtext('./channel/language') != 'en':
            bad.append('英文 RSS 期次、顺序或语言与首页不一致')
    return bad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dates', nargs='*')
    parser.add_argument('--lang', choices=['zh-CN', 'en', 'all'], default='all')
    parser.add_argument('--name-report', help='名称核对收据的私有运行路径')
    args = parser.parse_args()
    problems = {}
    count = 0
    checked_dates = set()
    languages = ['zh-CN', 'en'] if args.lang == 'all' else [args.lang]
    for lang in languages:
        base = ROOT / 'en' if lang == 'en' else ROOT
        pages = sorted(p for p in base.glob('ai-daily-digest-*.html') if PAGE_RE.match(p.name))
        if args.dates:
            pages = [p for p in pages if PAGE_RE.match(p.name).group(1) in args.dates]
        count += len(pages)
        for p in pages:
            checked_dates.add(PAGE_RE.match(p.name).group(1))
            bad = check_issue(p, lang)
            if bad:
                problems[str(p.relative_to(ROOT))] = bad
        if not args.dates and pages:
            bad = check_index(lang)
            if bad:
                problems[str((base / 'index.html').relative_to(ROOT))] = bad
    if not count:
        sys.exit('没有对应语言或日期的页面')

    if args.name_report:
        import check_names
        check_names.write_report(ROOT, sorted(checked_dates), args.name_report)

    if not problems:
        print(f'检查 {count} 个页面{"" if args.dates else " + 首页"}：全部通过')
        return 0
    for name, bad in problems.items():
        print(f'\n{name}')
        for b in bad:
            print(f'  - {b}')
    print(f'\n共 {sum(len(v) for v in problems.values())} 处问题，修好再提交。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
