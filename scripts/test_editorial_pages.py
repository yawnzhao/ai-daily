"""Check the restored daily template, archive metadata and audio state."""
import re
import tempfile
import unittest
from pathlib import Path
import build_site
import check_page

ROOT = Path(__file__).resolve().parent.parent


class EditorialPagesTests(unittest.TestCase):
    def test_existing_edition_remains_readable(self):
        page = build_site.read_page(ROOT/'ai-daily-digest-2026-09-24.html')
        self.assertEqual(page['date'],'2026-09-24')
        self.assertEqual(page['vol'],'18')
        self.assertFalse(check_page.check_issue(ROOT/page['file']))

    def test_new_edition_counts_and_pending_audio_are_read_correctly(self):
        page = build_site.read_page(ROOT/'ai-daily-digest-2026-09-25.html')
        self.assertEqual((page['news'],page['papers'],page['oss']),('4','3','4'))
        self.assertFalse(page['audio'])
        self.assertFalse(check_page.check_issue(ROOT/page['file']))

    def test_validator_rejects_non_https_audio(self):
        text=(ROOT/'ai-daily-digest-2026-09-25.html').read_text().replace('var AUDIO_SRC = ""','var AUDIO_SRC = "http://example.com/audio.mp3"')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ai-daily-digest-2026-09-25.html';path.write_text(text)
            self.assertTrue(any('AUDIO_SRC' in e for e in check_page.check_issue(path)))

    def test_restored_edition_uses_original_styles_and_four_sections(self):
        text=(ROOT/'ai-daily-digest-2026-09-25.html').read_text()
        template=(ROOT/'templates/daily.html').read_text()
        self.assertEqual(re.search(r'<style>(.*?)</style>',text,re.S).group(1),
                         re.search(r'<style>(.*?)</style>',template,re.S).group(1))
        self.assertEqual(re.findall(r'<h2>(.*?)</h2>',text),check_page.SECTIONS)
        self.assertNotIn('editorial-v2',text)
        self.assertNotIn('<audio',text)

    def test_validator_rejects_preview_markers(self):
        text=(ROOT/'ai-daily-digest-2026-09-25.html').read_text().replace('</head>','<meta name="robots" content="noindex,nofollow"></head>')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ai-daily-digest-2026-09-25.html';path.write_text(text)
            self.assertTrue(any('预览标记' in e for e in check_page.check_issue(path)))


if __name__=='__main__': unittest.main()
