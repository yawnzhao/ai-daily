#!/usr/bin/env python3
"""提交前检查日报页面：该有的 meta、导航、语义标签、外链写法有没有丢。

用法：python3 scripts/check_page.py                 # 检查全部页面
      python3 scripts/check_page.py 2026-09-18      # 只检查某一天
有问题时逐条打印并以退出码 1 结束。这些都是过去真出过的问题，不是风格偏好。
"""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r'^ai-daily-digest-(\d{4}-\d{2}-\d{2})\.html$')
SECTIONS = ['每日精选', '行业洞见', '论文速递', '开源解读']


def check_issue(path):
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

    if not editorial:
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

    for name in (['每日精选','行业观察','论文速递','开源解读'] if editorial else SECTIONS):
        if f'<h2>{name}</h2>' not in t:
            bad.append(f'少了「{name}」板块')

    # 导航指向的页面必须真实存在
    for target in re.findall(r'<nav class="issue-nav[^>]*>(.*?)</nav>', t, re.S):
        for href in re.findall(r'href="([^"]+)"', target):
            if not (ROOT / href).exists():
                bad.append(f'导航指向不存在的页面：{href}')

    # 外链必须新标签页打开
    plain = re.findall(r'<a href="(https?://[^"]+)"(?![^>]*target=)', t)
    if plain:
        bad.append(f'{len(plain)} 条外链没写 target="_blank" rel="noopener"，第一条：{plain[0][:60]}')

    # 音频：有直链才说有语音版
    if audio and audio.group(1) and not audio.group(1).startswith('https://'):
        bad.append('AUDIO_SRC 不是 https 直链')

    return bad


def check_index():
    t = (ROOT / 'index.html').read_text()
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
    return bad


def main():
    argv = sys.argv[1:]
    pages = sorted(p for p in ROOT.glob('ai-daily-digest-*.html') if PAGE_RE.match(p.name))
    if argv:
        pages = [p for p in pages if PAGE_RE.match(p.name).group(1) in argv]
        if not pages:
            sys.exit(f'没有这些日期的页面：{" ".join(argv)}')

    problems = {}
    for p in pages:
        bad = check_issue(p)
        if bad:
            problems[p.name] = bad
    if not argv:
        bad = check_index()
        if bad:
            problems['index.html'] = bad

    if not problems:
        print(f'检查 {len(pages)} 个页面{"" if argv else " + 首页"}：全部通过')
        return 0
    for name, bad in problems.items():
        print(f'\n{name}')
        for b in bad:
            print(f'  - {b}')
    print(f'\n共 {sum(len(v) for v in problems.values())} 处问题，修好再提交。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
