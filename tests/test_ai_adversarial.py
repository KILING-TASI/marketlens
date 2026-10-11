import sys,json,copy,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from marketlens.source_review import review
from marketlens.evidence_compare import compare
ROOT=Path(__file__).resolve().parents[1]/'references/examples'

class AIAdversarial(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'evidence-depth.json').read_text(encoding='utf-8'));self.spec.pop('asOf')
    def row(self):return review(self.spec,ROOT)
    def test_future_review_is_not_completed(self):
        self.spec['claims'][0]['checks'][0]['reviewedAt']='2099-01-01T00:00:00+08:00'
        self.assertEqual(self.row()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_review_before_source_is_not_completed(self):
        self.spec['claims'][0]['checks'][0]['reviewedAt']='2025-01-01T00:00:00+08:00'
        self.assertEqual(self.row()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_negation_cannot_be_laundered_as_support(self):
        self.spec['claims'][0]['checks'][1]['finding']='supports'
        result=self.row()['claims'][0]['aspectChecks'][1]
        self.assertEqual(result['finding'],'supports');self.assertEqual(result['effectiveFinding'],'unknown');self.assertTrue(result['riskQuestions'])
    def test_partial_denial_cannot_be_laundered(self):
        self.spec['claims'][0]['checks'][2]['finding']='supports'
        self.assertEqual(self.row()['claims'][0]['aspectChecks'][2]['effectiveFinding'],'unknown')
    def test_link_cannot_inject_certification(self):
        self.spec['claims'][0]['links'][0]['programCertified']=True
        with self.assertRaises(ValueError):self.row()
    def test_future_search_rejected(self):
        self.spec['searchLog'][0]['checkedAt']='2099-01-01T00:00:00+08:00'
        with self.assertRaises(ValueError):self.row()
    def test_search_before_publication_rejected(self):
        self.spec['searchLog'][0].update(status='found',sourceIds=['s1'],checkedAt='2025-01-01T00:00:00+08:00')
        with self.assertRaises(ValueError):self.row()
    def test_basic_date_rejected_consistently(self):
        self.spec['announcementMetrics']=self.spec['announcementMetrics'][:1];self.spec['announcementMetrics'][0]['periodStart']='20260101'
        with self.assertRaises(ValueError):self.row()
    def test_wrong_metric_number_is_visible(self):
        self.spec['announcementMetrics'][0].update(lower=1000,upper=2000,evidenceExcerpt='初次预告区间为-1000万元至0万元。')
        row=self.row()['announcementMetrics'][0]
        self.assertFalse(row['sourceEvidenceCheck']['numericMentionMatch']['lower']);self.assertTrue(row['warnings'])
    def test_repeat_checks_do_not_invent_content_changes(self):
        old=self.row();new=self.row();self.assertEqual(compare(old,new)['sourceChanges'],[]);self.assertEqual(compare(old,new)['affectedClaims'],[])
    def test_malformed_unit_is_value_error(self):
        self.spec['announcementMetrics'][0]['unit']=[]
        with self.assertRaises(ValueError):self.row()
    def test_future_and_invalid_publication_not_upgraded(self):
        for date in ('2099-01-01','昨天'):
            self.spec['sources'][0]['publishedAt']=date
            self.assertEqual(self.row()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')

if __name__=='__main__':unittest.main()
