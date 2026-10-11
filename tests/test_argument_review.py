import unittest,json,copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from marketlens.claim_evidence import review as dispatch
from marketlens.argument_review import review
from marketlens.competing_hypotheses import review as hypotheses
from marketlens.review_io import render,publish
def sample():return json.loads((ROOT/'references/examples/argument-teaching.json').read_text(encoding='utf-8'))
class Arguments(unittest.TestCase):
    def test_v1_full_result_unchanged(self):
        fixture=json.loads((ROOT/'tests/fixtures/claim-evidence-v1-baseline.json').read_text(encoding='utf-8'));self.assertEqual(dispatch(fixture['input']),fixture['result'])
    def test_proposal_not_counted_as_support(self):
        s=sample();l=s['claims'][0]['links'][0];l['relation']='supports';b=l['binding'];b.update(origin='ai',status='proposed',reviewedBy=None,reviewedAt=None,reviewBasis=None)
        r=review(s);self.assertEqual(r['records'][0]['status'],'insufficient');self.assertEqual(r['statusCounts']['declared-support'],0);self.assertEqual(r['proposedOrDeferredCount'],1)
    def test_review_is_a_declared_record_not_identity_certification(self):
        r=review(sample());l=r['records'][0]['admitted'][0];self.assertFalse(l['reviewIdentityVerified']);self.assertFalse(r['records'][0]['originalVerified']);self.assertFalse(r['records'][0]['argumentSemanticsVerified'])
    def test_late_and_backwards_binding(self):
        s=sample();s['claims'][0]['links'][0]['binding']['reviewedAt']='2026-10-12T12:00:00+08:00';r=review(s);self.assertEqual(r['records'][0]['status'],'insufficient')
        s=sample();s['claims'][0]['links'][0]['binding']['reviewedAt']='2026-10-09T12:00:00+08:00'
        with self.assertRaises(ValueError):review(s)
    def test_unknown_fields_and_nullable_reason(self):
        s=sample();s['claims'][0]['argument']['falsifier']['reason']=''
        with self.assertRaises(ValueError):review(s)
        s=sample();s['claims'][0]['argument']['theoryIds']=['UNKNOWN-BOOK']
        with self.assertRaises(ValueError):review(s)
        s=sample();s['claims'][0]['confidence']=0.99
        with self.assertRaises(ValueError):review(s)
    def test_reference_and_duplicate_checks_include_proposals(self):
        s=sample();l=s['claims'][0]['links'][0];l['evidenceId']='absent';l['binding'].update(status='proposed',reviewedBy=None,reviewedAt=None,reviewBasis=None)
        with self.assertRaises(ValueError):review(s)
        s=sample();s['claims'][0]['links']*=2
        with self.assertRaises(ValueError):review(s)
    def test_theory_id_does_not_upgrade_status(self):
        s=sample();baseline=review(s)['records'][0]['status'];s['claims'][0]['argument']['theoryIds']=['SPENCE-SIGNAL','ZHOUXG-LOGIC'];self.assertEqual(review(s)['records'][0]['status'],baseline)
    def test_render_escapes_and_shows_six_categories(self):
        s=sample();s['claims'][0]['argument']['warrant']['text']='<script>alert(1)</script>';page=render(review(s),'test');self.assertNotIn('<script>alert',page);self.assertIn('&lt;script&gt;',page);self.assertIn('只有局部支持',page);self.assertIn('只有背景资料',page);self.assertIn('未知：',page)
    def test_missing_metadata_is_not_manually_confirmed(self):
        s=sample();s['claims'][0]['links'][0]['binding']['reviewBasis']=None
        with self.assertRaises(ValueError):review(s)
class Hypotheses(unittest.TestCase):
    def sample(self):return json.loads((ROOT/'references/examples/hypotheses-teaching.json').read_text(encoding='utf-8'))
    def test_different_relations_not_truth_or_rank(self):
        r=hypotheses(self.sample());self.assertEqual(r['hypothesisMatrix'][0]['comparisonStatus'],'declared-difference');self.assertFalse(r['hypothesisMatrix'][0]['diagnosticityVerified']);self.assertNotIn('probability',r);self.assertNotIn('ranking',r)
    def test_missing_cell_keeps_null(self):
        s=self.sample();s['hypotheses'][1]['links']=[];r=hypotheses(s);self.assertIsNone(r['hypothesisMatrix'][0]['cells'][1]['relation']);self.assertEqual(r['hypothesisMatrix'][0]['comparisonStatus'],'incomplete')
    def test_same_declared_relation_not_diagnostic_certification(self):
        s=self.sample();s['hypotheses'][1]['links'][0]['relation']=s['hypotheses'][0]['links'][0]['relation'];r=hypotheses(s);self.assertEqual(r['hypothesisMatrix'][0]['comparisonStatus'],'same-declared-relation');self.assertFalse(r['hypothesisMatrix'][0]['diagnosticityVerified'])
if __name__=='__main__':unittest.main()
