import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import patch

import build_editorial_issue as builder
import synth_audio

ROOT = Path(__file__).resolve().parents[1]


class EditorialTrialTests(unittest.TestCase):
    def test_catalog_groups_news_discourse_papers_code_with_adopted_first_in_each(self):
        def entry(url, date='2026-10-04', **extra):
            return dict(url=url, published_at=date, **extra)
        code = entry('https://github.com/example/tool')
        paper = entry('https://arxiv.org/abs/2610.00001')
        old_news = entry('https://example.com/old', '2026-10-01')
        new_news = entry('https://example.com/new')
        selected_paper = entry('https://arxiv.org/abs/2610.00002')
        selected_news = entry('https://example.com/adopted')
        undated = entry('https://example.com/undated', None)
        podcast = entry('https://example.com/podcast', catalog_kind='discourse')
        adopted_talk = entry('https://example.com/talk')
        entries = [code, paper, old_news, selected_paper, undated, podcast, new_news, selected_news, adopted_talk]
        issue = {'date': '2026-10-05', 'items': [
            {'id': 'paper', 'section': 'papers', 'primary_url': selected_paper['url']},
            {'id': 'talk', 'section': 'insight', 'primary_url': adopted_talk['url']},
            {'id': 'news', 'section': 'featured', 'primary_url': selected_news['url']}]}
        result = builder.catalog_entries_for_display(entries, issue, {'news': {}, 'talk': {}, 'paper': {}})
        self.assertEqual(result, [selected_news, new_news, old_news, undated, adopted_talk, podcast, selected_paper, paper, code])
        self.assertEqual(entries[0], code)  # Input collection stays in its original order.
        self.assertEqual(builder.catalog_entries_for_display(entries, {**issue, 'date': '2026-10-04'}, {}), entries)

    def test_catalog_filters_commit_noise_without_losing_adopted_or_reviewed_evidence(self):
        def commit(suffix, **extra):
            return dict(url='https://github.com/example/tool/commit/' + suffix, **extra)
        routine = commit('routine', selected=True)  # Stale candidate flag is not adoption.
        adopted = commit('adopted', event_key='release')
        reviewed = commit('reviewed', catalog_news_reason='Verified security change', verification_scope='diff')
        unreviewed = commit('unreviewed', catalog_news_reason='Maybe useful', verification_scope='list')
        release = dict(url='https://github.com/example/tool/releases/tag/v1', event_key='release')
        story = dict(url='https://example.com/story', event_key='other-release')
        other_release = dict(url='https://github.com/example/tool/releases/tag/v2', event_key='other-release')
        issue = {'date': '2026-10-05', 'items': [{'id': 'chosen', 'section': 'opensource', 'primary_url': adopted['url']}]}
        result = builder.catalog_entries_for_display([routine, release, story, other_release, adopted, reviewed, unreviewed], issue, {'chosen': {}})
        self.assertEqual(result, [adopted, other_release, reviewed])

    def test_public_catalog_labels_count_bilingual_titles_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/sources.json').write_text(json.dumps({'sources': [
                {'id': 'techcrunch-ai', 'name': 'TechCrunch AI（试用）', 'display_name': 'TechCrunch'}]}))
            (root / 'catalog.json').write_text(json.dumps({'date': '2026-10-05', 'items': [
                {'url': 'https://github.com/example/tool/commit/noise', 'title': 'Routine fix', 'source': 'DeepSeek'},
                {'url': 'https://example.com/story', 'title': 'Original title', 'original_title': 'Original title',
                 'source_id': 'techcrunch-ai', 'source': 'TechCrunch AI（试用）'}]}))
            issue = {'date': '2026-10-05', 'source_catalog_path': 'catalog.json', 'items': [
                {'id': 'chosen', 'section': 'featured', 'primary_url': 'https://example.com/story'}]}
            with patch.object(builder, 'ROOT', root):
                output = builder.render_source_catalog(issue, {'chosen': {'title': '中文标题'}})
            self.assertIn('1 条', output)
            self.assertIn('>TechCrunch</span>', output)
            self.assertIn('中文标题', output)
            self.assertIn('Original title', output)
            self.assertIn('href="https://example.com/story"', output)
            self.assertNotIn('试用', output)
            self.assertNotIn('/commit/', output)

    def test_dictionary_preserves_readable_text_and_other_polyphones(self):
        dictionary = synth_audio.load_dictionary(ROOT / 'config/tts-pronunciation.json')
        text = '学校先校对文字，再校验数据并校听录音。'
        request = synth_audio.make_request(text, 'test-voice', dictionary)
        self.assertEqual(request['text'], text)
        rules = dict(rule.split('/', 1) for rule in request['pronunciation_dict']['tone'])
        self.assertEqual(rules['校对'], '(jiao4)(dui4)')
        self.assertEqual(rules['校验'], '(jiao4)(yan4)')
        self.assertEqual(rules['宏碁'], '(hong2)(ji1)')
        self.assertNotIn('校', rules)
        self.assertNotIn('学校', rules)

    def test_partial_failed_pending_do_not_become_no_updates(self):
        receipt = {'summary': {'ok': 0, 'incomplete': True}, 'sources': [
            {'name': 'Microsoft', 'status': 'partial', 'evidence': '日期范围不足'},
            {'name': 'Example', 'status': 'pending', 'evidence': '需浏览器'},
            {'name': 'Unavailable', 'status': 'failed', 'evidence': '连接失败'}]}
        output = builder.render_coverage(receipt, '## 采集说明\n已作部分检查。')
        self.assertIn('已检查部分内容', output)
        self.assertIn('尚未完成检查', output)
        self.assertIn('访问或抓取失败', output)
        self.assertNotIn('待补齐：', output)
        self.assertNotIn('论文解读限于摘要', output)

    def test_inline_links_work_without_executing_html(self):
        output = builder.inline('[节目](https://example.com/a?x=1&y=2) <script>bad()</script>')
        self.assertIn('href="https://example.com/a?x=1&amp;y=2"', output)
        self.assertIn('rel="noopener"', output)
        self.assertNotIn('<script>', output)


if __name__ == '__main__':
    unittest.main()
