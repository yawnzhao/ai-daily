import importlib.util
from pathlib import Path
import unittest

import build_editorial_issue as builder
import synth_audio

ROOT = Path(__file__).resolve().parents[1]


class EditorialTrialTests(unittest.TestCase):
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
