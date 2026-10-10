import unittest,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from marketlens.citation_summary import summarize
class CitationTests(unittest.TestCase):
 def spec(self):return json.loads((ROOT/'examples/expansion-teaching/summary.json').read_text(encoding='utf-8'))
 def test_plan_not_execution(self):
  r=summarize(self.spec());self.assertEqual(r['rows'][0]['status'],'证据不足，不能确认');self.assertEqual(r['rows'][0]['citations'],[])
 def test_matching_plan_citable(self):
  s=self.spec();s['claims'][0]['type']='plan';r=summarize(s);self.assertEqual(r['rows'][0]['citations'][0]['stage'],'planned')
 def test_late_verification_excluded(self):
  s=self.spec();s['evidence'][0]['verified_at']='2027-01-01T11:00:00+08:00';self.assertEqual(len(summarize(s)['excluded']),1)
