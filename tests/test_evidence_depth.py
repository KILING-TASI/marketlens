import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from marketlens.source_review import review
from marketlens.evidence_details import scan
from marketlens.announcement_review import review as metrics
from marketlens.review_io import render

class Depth(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.content='教学子公司公告：拟向客户甲供货，尚未交付。\n表头：金额单位万元，未经审计。\n公司否认与客户乙签约，不否认其他客户。\n脚注：上述为预计金额，不能保证收入。\n外资与险资可能介入；稳赚不赔属于待核表述。'
        (self.base/'a.md').write_text(self.content,encoding='utf-8')
        self.spec=dict(inputSchema='source-review/2',sources=[dict(id='a',file='a.md',sourceUrl='https://example.com/original',publishedAt='2026-10-10',expectedSha256=hashlib.sha256((self.base/'a.md').read_bytes()).hexdigest(),excerpt='拟向客户甲供货',page=None)],claims=[dict(id='c',text='教学母公司是否已交付？',links=[])])
    def tearDown(self):self.tmp.cleanup()
    def check(self,aspect='stage',excerpt='尚未交付',finding='contradicts'):
        return dict(aspect=aspect,expected='已交付',sourceId='a',excerpt=excerpt,finding=finding,rationale='原文只披露预计供货，未交付',reviewer='教学复核声明者',reviewedAt='2026-10-11T10:00:00+08:00')
    def test_context_keeps_negation_and_footnote(self):
        r=review(self.spec,self.base);c=r['sources'][0]['contexts'][0]
        self.assertIn('尚未交付',c['after']);self.assertIn('单位万元',c['after']);self.assertIn('脚注',c['after'])
    def test_full_text_without_excerpt(self):
        self.spec['sources'][0]['excerpt']=None;r=review(self.spec,self.base)
        words=[a['matched'] for a in r['sources'][0]['fullTextAlerts']]
        self.assertIn('外资',words);self.assertIn('稳赚不赔',words)
        self.assertFalse(r['sources'][0]['excerptFound'])
    def test_regulator_not_actor_hint(self):
        self.assertNotIn('actor-boundary',[w['code'] for w in scan('本公告已向监管机构报备')])
        self.assertIn('actor-boundary',[w['code'] for w in scan('险资与量化私募买入')])
    def test_duplicate_text_keeps_byte_hashes(self):
        (self.base/'b.md').write_text(self.content+' \n',encoding='utf-8')
        self.spec['sources'].append(dict(id='b',file='b.md'))
        r=review(self.spec,self.base);self.assertEqual(len(r['artifactGroups']),2);self.assertEqual(r['normalizedTextGroups'],[['a','b']])
        self.assertNotEqual(r['sources'][0]['actualSha256'],r['sources'][1]['actualSha256'])
    def test_declared_url_never_looks_visited(self):
        r=review(self.spec,self.base);self.assertEqual(r['sources'][0]['urlCheck']['status'],'not-visited')
        page=render(r,'test');self.assertIn('https://example.com/original',page);self.assertIn('不代表主张证实',page)
    def test_actual_download_mismatch_blocks_opinion(self):
        self.spec['claims'][0]['checks']=[self.check()]
        with patch('marketlens.source_fetch.fetch',return_value=(b'different file',{'finalUrl':'https://example.com/final'})):
            r=review(self.spec,self.base,True)
        self.assertFalse(r['sources'][0]['urlCheck']['bytesMatch']);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_actual_download_equal_not_authenticated(self):
        with patch('marketlens.source_fetch.fetch',return_value=((self.base/'a.md').read_bytes(),{'finalUrl':'https://example.com/original'})):
            r=review(self.spec,self.base,True)
        self.assertTrue(r['sources'][0]['urlCheck']['bytesMatch']);self.assertFalse(r['sources'][0]['publisherAuthenticated'])
    def test_unavailable_url_preserved(self):
        with patch('marketlens.source_fetch.fetch',side_effect=OSError('network blocked')):r=review(self.spec,self.base,True)
        self.assertEqual(r['sources'][0]['urlCheck']['status'],'unavailable')
    def test_field_level_opinion_and_fake_quote(self):
        self.spec['claims'][0]['checks']=[self.check(),self.check('amount','收入已确认')]
        r=review(self.spec,self.base);checks=r['claims'][0]['aspectChecks']
        self.assertEqual(checks[0]['effectiveFinding'],'contradicts');self.assertEqual(checks[1]['effectiveFinding'],'unknown')
        self.assertFalse(r['claims'][0]['relationSemanticsVerified'])
    def test_parent_subsidiary_identity_not_guessed(self):
        self.spec['claims'][0]['checks']=[self.check('identity','教学子公司','partial')]
        r=review(self.spec,self.base);self.assertIn('身份',render(r,'test'));self.assertIn('身份认证',r['answerSummary']['cannotConfirm'])
    def test_day_precision_same_day_not_intraday(self):
        self.spec['asOf']='2026-10-10T12:00:00+08:00';self.spec['claims'][0]['checks']=[self.check()]
        r=review(self.spec,self.base);self.assertIsNone(r['sources'][0]['timeCheck']['availableAtCutoff']);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_late_publication_not_usable(self):
        self.spec['asOf']='2026-10-09T12:00:00+08:00';self.spec['claims'][0]['checks']=[self.check()]
        r=review(self.spec,self.base);self.assertFalse(r['sources'][0]['timeCheck']['availableAtCutoff']);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_search_no_find_not_counterevidence_absence(self):
        self.spec['searchLog']=[dict(query='后续澄清',scope='所列两条公开入口',status='searched-no-find',checkedAt='2026-10-11T10:00:00+08:00',sourceIds=[],reason='未找到，不代表不存在')]
        r=review(self.spec,self.base);self.assertIn('未找到不等于没有反证',render(r,'test'))
    def test_missing_search_reference_rejected(self):
        self.spec['searchLog']=[dict(query='澄清',scope='入口',status='found',checkedAt='2026-10-11T10:00:00+08:00',sourceIds=['missing'],reason='声明')]
        with self.assertRaises(ValueError):review(self.spec,self.base)
    def test_denial_chain_does_not_erase_history(self):
        (self.base/'b.md').write_text('否认客户乙订单',encoding='utf-8');self.spec['sources'].append(dict(id='b',file='b.md'))
        self.spec['sourceRelations']=[dict(**{'from':'b','to':'a','type':'denial','reason':'仅否认客户乙，不撤销客户甲相关披露'})]
        r=review(self.spec,self.base);self.assertEqual(len(r['sources']),2);self.assertEqual(r['sourceRelations'][0]['type'],'denial')
    def test_injection_is_escaped_and_not_action(self):
        self.spec['sources'][0]['excerpt']='<img src=x onerror=alert(1)>'
        r=review(self.spec,self.base);page=render(r,'test');self.assertNotIn('<img src=x',page);self.assertFalse(r['sources'][0]['excerptFound'])
    def test_computed_flags_cannot_be_supplied(self):
        self.spec['sources'][0]['publisherAuthenticated']=True
        with self.assertRaises(ValueError):review(self.spec,self.base)
    def test_empty_extracted_text_not_full_coverage(self):
        (self.base/'a.md').write_text('',encoding='utf-8')
        r=review(self.spec,self.base);self.assertEqual(r['sources'][0]['extractionCoverage']['emptyPages'],[1]);self.assertFalse(r['sources'][0]['excerptFound'])
    def test_changes_point_to_affected_claims(self):
        from marketlens.evidence_compare import compare
        self.spec['claims'][0]['links']=[dict(sourceId='a',relation='partial',rationale='教学声明')]
        old=review(self.spec,self.base);frozen=copy.deepcopy(old)
        (self.base/'a.md').write_text('后续更正，未交付',encoding='utf-8');new=review(self.spec,self.base)
        diff=compare(old,new);self.assertEqual(diff['affectedClaims'][0]['id'],'c');self.assertEqual(old,frozen)

class Ranges(unittest.TestCase):
    def item(self,id,low,high,kind='预告',value=None):
        return dict(id=id,sourceId='a',subject='教学公司',metric='净利润',periodStart='2026-01-01',periodEnd='2026-03-31',publishedAt='2026-04-15',basis='合并',auditStatus='未经审计',unit='万元',currency='CNY',disclosureType=kind,value=value,lower=low,upper=high,corrects=None)
    def test_disjoint_negative_intervals(self):
        a=self.item('a',-1000,0);b=self.item('b',-5000,-4000,'更正');b['corrects']='a'
        r=metrics([a,b],{'a'})[1];self.assertFalse(r['forecastComparison']['overlap']);self.assertTrue(r['warnings']);self.assertIsNone(r['forecastComparison']['ratio'])
    def test_overlap_changes_still_visible(self):
        r=metrics([self.item('a',-1000,0),self.item('b',-500,500,'更正')],{'a'})[1]
        self.assertTrue(r['forecastComparison']['overlap']);self.assertTrue(r['forecastComparison']['partlyOutside']);self.assertTrue(r['warnings'])
    def test_point_conflicts_with_own_interval(self):
        r=metrics([self.item('a',-5000,-4000,'快报',100)],{'a'})[0];self.assertTrue(r['warnings'])
    def test_cross_basis_link_not_direct_correction(self):
        a=self.item('a',-1000,0);b=self.item('b',-5000,-4000,'更正');b.update(basis='母公司',relatedVersionId='a',scopeChangeReason='合并与母公司口径不同')
        r=metrics([a,b],{'a'})[1];self.assertEqual(r['relatedVersion']['numericComparison'],'not-performed');self.assertNotIn('forecastComparison',r)
        b['corrects']='a'
        with self.assertRaises(ValueError):metrics([a,b],{'a'})
    def test_large_exponent_bounded(self):
        with self.assertRaises(ValueError):metrics([self.item('a',None,None,'快报','1e999999')],{'a'})
    def test_year_report_uses_latest_forecast_revision(self):
        a=self.item('a',-1000,0);b=self.item('b',-5000,-4000,'更正');b['corrects']='a';c=self.item('c',None,None,'年报',-4500)
        r=metrics([a,b,c],{'a'})[2];self.assertEqual(r['forecastComparison']['forecastId'],'b');self.assertFalse(r['forecastComparison']['outside'])

if __name__=='__main__':unittest.main()
