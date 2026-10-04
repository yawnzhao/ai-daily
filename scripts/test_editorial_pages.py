"""Check the restored daily template, archive metadata and audio state."""
import re
import tempfile
import unittest
from pathlib import Path
import build_site
import check_page

ROOT = Path(__file__).resolve().parent.parent


class EditorialPagesTests(unittest.TestCase):
    def test_english_issue_uses_shared_counts_and_passes_validation(self):
        path = ROOT / 'en/ai-daily-digest-2026-10-04.html'
        page = build_site.read_page(path, 'en')
        self.assertEqual((page['news'], page['papers'], page['oss']), ('6', '1', '2'))
        self.assertFalse(check_page.check_issue(path, 'en'))

    def test_english_navigation_does_not_link_untranslated_issues(self):
        pages = [build_site.read_page(p, 'en') for p in sorted((ROOT / 'en').glob('ai-daily-digest-*.html'), reverse=True)]
        oldest = build_site.nav_html(pages, len(pages) - 1, lang='en')
        self.assertNotIn('Previous', oldest)
        self.assertIn('Next', oldest)
        self.assertNotIn('href="#featured"', oldest)

    def test_translation_validator_rejects_missing_item_and_changed_catalog_title(self):
        original = (ROOT / 'en/ai-daily-digest-2026-10-04.html').read_text()
        variants = [(original.replace('id="frontier-academy"', 'id="wrong-id"'), '缺少条目'),
                    (original.replace('Anthropic 投入1亿美元', 'Changed catalog title'), '来源目录标题')]
        for text, expected in variants:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'ai-daily-digest-2026-10-04.html'
                path.write_text(text)
                self.assertTrue(any(expected in e for e in check_page.check_translation(path)))

    def test_existing_edition_remains_readable(self):
        page = build_site.read_page(ROOT/'ai-daily-digest-2026-09-24.html')
        self.assertEqual(page['date'],'2026-09-24')
        self.assertEqual(page['vol'],'18')
        self.assertFalse(check_page.check_issue(ROOT/page['file']))

    def test_published_edition_counts_and_audio_are_read_correctly(self):
        page = build_site.read_page(ROOT/'ai-daily-digest-2026-09-25.html')
        self.assertEqual((page['news'],page['papers'],page['oss']),('4','3','4'))
        self.assertTrue(page['audio'])
        self.assertFalse(check_page.check_issue(ROOT/page['file']))

    def test_validator_rejects_non_https_audio(self):
        text=re.sub(r'var AUDIO_SRC = "[^"]*"', 'var AUDIO_SRC = "http://example.com/audio.mp3"',
                    (ROOT/'ai-daily-digest-2026-09-25.html').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ai-daily-digest-2026-09-25.html';path.write_text(text)
            self.assertTrue(any('AUDIO_SRC' in e for e in check_page.check_issue(path)))

    def test_restored_edition_uses_original_styles_and_four_sections(self):
        text=(ROOT/'ai-daily-digest-2026-09-25.html').read_text()
        template=(ROOT/'templates/daily.html').read_text()
        self.assertEqual(re.search(r'<style>(.*?)</style>',text,re.S).group(1),
                         re.search(r'<style>(.*?)</style>',template,re.S).group(1).split('  /* Collapsed source catalog. */')[0])
        self.assertEqual(re.findall(r'<h2>(.*?)</h2>',text),check_page.SECTIONS)
        self.assertNotIn('editorial-v2',text)
        self.assertIn('<audio',text)

    def test_validator_rejects_preview_markers(self):
        text=(ROOT/'ai-daily-digest-2026-09-25.html').read_text().replace('</head>','<meta name="robots" content="noindex,nofollow"></head>')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ai-daily-digest-2026-09-25.html';path.write_text(text)
            self.assertTrue(any('预览标记' in e for e in check_page.check_issue(path)))


if __name__=='__main__': unittest.main()
