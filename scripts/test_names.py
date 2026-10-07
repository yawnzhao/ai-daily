"""Regression tests for the published EFS error and the shared-source gate."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_names
import check_page
import build_editorial_issue
import build_english_issue

ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-10-07'
CORRECT = 'Enterprise Frontier Safeguards'
WRONG = 'Enterprise Foundational Safeguards'
ENTRY = {'official_name':CORRECT,'abbreviation':'EFS','chinese_name':'企业前沿保障措施',
         'aliases':['Enterprise Safeguards'],'historical_names':['Enterprise Pilot Safeguards'],
         'source_url':'https://www.anthropic.com/news/cyber-verification-program',
         'source_excerpt':CORRECT+' (EFS)'}


class NamesTests(unittest.TestCase):
    def test_correct_occurrence_does_not_hide_wrong_occurrence(self):
        text = CORRECT+' (EFS). Later: '+WRONG+' (EFS).'
        errors = check_names.check_text(text,[ENTRY])
        self.assertTrue(any('缩写展开' in e for e in errors))
        self.assertTrue(any(WRONG in e for e in errors))

    def test_wrong_name_without_acronym_and_wrong_case(self):
        for text in [WRONG, 'Enterprise Frontier safeguards']:
            self.assertTrue(check_names.check_text(text,[ENTRY]),text)

    def test_unknown_named_declaration_and_abbreviation_need_source(self):
        for text in ['a plan called Fabric Safety Protocol', 'Fabric Safety Protocol (FSP)']:
            self.assertTrue(any('出处' in e or '原文记录' in e for e in check_names.check_text(text,[ENTRY])))

    def test_translations_aliases_history_and_ordinary_prose_are_valid(self):
        text = CORRECT+' (EFS). 企业前沿保障措施。 Enterprise Safeguards. Formerly Enterprise Pilot Safeguards (EFS). The verification program requires data retention.'
        self.assertEqual(check_names.check_text(text,[ENTRY]),[])
        self.assertTrue(any('历史名称' in e for e in check_names.check_text('Enterprise Pilot Safeguards',[ENTRY])))

    def test_reverse_expansion_is_checked(self):
        self.assertEqual(check_names.check_text('EFS ('+CORRECT+')',[ENTRY]),[])
        self.assertTrue(check_names.check_text('EFS ('+WRONG+')',[ENTRY]))

    def test_empty_or_bad_source_record_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'data/issues').mkdir(parents=True)
            p = root/f'data/issues/{DATE}.json'
            for entry in [{**ENTRY,'source_excerpt':'Different Program'}, {**ENTRY,'source_url':''}, {**ENTRY,'aliases':'not a list'}]:
                p.write_text(json.dumps({'official_names':{'efs':entry},'items':[]}))
                self.assertTrue(check_names.check_date(root,DATE))

    def test_new_issues_require_registry_legacy_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(check_names.check_date(tmp,'2026-09-07'),[])
            self.assertTrue(check_names.check_date(tmp,'2026-10-08'))

    def fixture(self, tmp):
        root = Path(tmp)
        files = ['data/issues/'+DATE+'.json','data/issues/en/'+DATE+'.json',
                 'daily/2026/'+DATE+'.md','daily/en/2026/'+DATE+'.md',
                 'ai-daily-digest-'+DATE+'.html','en/ai-daily-digest-'+DATE+'.html']
        for rel in files:
            p = root/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/rel,p)
        return root

    def test_same_wrong_translation_as_chinese_fails_original_source_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            for rel in ['daily/2026/'+DATE+'.md','daily/en/2026/'+DATE+'.md']:
                p = root/rel
                p.write_text(p.read_text().replace(CORRECT,WRONG))
            for lang in ['zh-CN','en']:
                self.assertTrue(check_names.check_date(root,DATE,lang,sources_only=True))

    def test_default_page_gate_catches_bad_english_page_with_good_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            p = root/'en'/('ai-daily-digest-'+DATE+'.html')
            self.assertIn(CORRECT,p.read_text())
            p.write_text(p.read_text().replace(CORRECT,WRONG,1))
            with patch.object(check_page,'ROOT',root):
                errors = check_page.check_issue(p,'en')
            self.assertTrue(any(WRONG in e for e in errors),errors)

    def test_both_builders_block_bad_source_before_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            for module,rel in [(build_editorial_issue,'daily/2026/'+DATE+'.md'),(build_english_issue,'daily/en/2026/'+DATE+'.md')]:
                p = root/rel
                good = p.read_text()
                p.write_text(good.replace(CORRECT,WRONG,1))
                with patch.object(module,'ROOT',root):
                    with self.assertRaisesRegex(ValueError,'名称|name'):
                        module.build(DATE)
                p.write_text(good)

    def test_corrected_issue_sources_and_pages_pass(self):
        self.assertEqual(check_names.check_date(ROOT,DATE),[])


if __name__ == '__main__':
    unittest.main()
