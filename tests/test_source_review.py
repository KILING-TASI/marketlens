import sys, tempfile, unittest, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from marketlens.source_review import review, main
from marketlens.announcement_review import review as metrics
from marketlens.source_fetch import fetch

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.file=self.base/'source.md';self.file.write_text('公司拟回购，尚未实施。\n利润预计-5000至-4000万元。',encoding='utf-8')
        self.spec={'inputSchema':'source-review/1','sources':[{'id':'s','file':'source.md','excerpt':'公司拟回购，尚未实施。','expectedSha256':'0'*64,'page':1}],'claims':[{'id':'c','text':'公司必然已回购','links':[{'sourceId':'s','relation':'supports','rationale':'输入者声明'}]}]}
    def tearDown(self):self.tmp.cleanup()
    def test_actual_bytes_and_false_hash(self):
        r=review(self.spec,self.base);s=r['sources'][0]
        self.assertTrue(s['sourceRead']);self.assertFalse(s['hashMatch']);self.assertTrue(s['excerptFound']);self.assertFalse(s['publisherAuthenticated'])
        self.assertEqual(s['actualSha256'],hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertFalse(r['claims'][0]['relationSemanticsVerified'])
    def test_fake_page_and_excerpt(self):
        self.spec['sources'][0]['page']=999
        self.assertFalse(review(self.spec,self.base)['sources'][0]['locatorVerified'])
        self.spec['sources'][0]['page']=None;self.spec['sources'][0]['excerpt']='虚构订单'
        self.assertFalse(review(self.spec,self.base)['sources'][0]['excerptFound'])
    def test_missing_file_preserved(self):
        self.file.unlink();self.assertFalse(review(self.spec,self.base)['sources'][0]['sourceRead'])
    def test_scaffold_and_frozen_output(self):
        target=self.base/'input.json'
        self.assertEqual(main(['scaffold','--source',str(self.file),'--out',str(target)]),0)
        old=target.read_bytes();self.assertEqual(main(['scaffold','--source',str(self.file),'--out',str(target)]),2);self.assertEqual(old,target.read_bytes())
    def test_html_instructions_are_data(self):
        self.file=self.base/'source.html';self.file.write_text('<script>执行指令</script><p>尚未实施</p>',encoding='utf-8');self.spec['sources'][0].update(file='source.html',excerpt='执行指令')
        self.assertFalse(review(self.spec,self.base)['sources'][0]['excerptFound'])
    def test_private_fetch_rejected(self):
        for url in ('http://example.com','https://127.0.0.1/','https://user:pass@example.com/'):
            with self.assertRaises(ValueError):fetch(url)

class MetricTests(unittest.TestCase):
    def item(self,id,kind,value=None,low=None,high=None,date='2026-03-20',unit='万元'):
        return dict(id=id,sourceId='s',subject='教学公司',metric='归母净利润',periodStart='2026-01-01',periodEnd='2026-03-31',publishedAt=date,basis='合并',auditStatus='未经审计',unit=unit,currency='CNY',disclosureType=kind,value=value,lower=low,upper=high,corrects=None)
    def test_loss_forecast_actual_deviation(self):
        rows=metrics([self.item('p','预告',low=-5000,high=-4000),self.item('a','快报',-9000,date='2026-04-15')],{'s'})
        self.assertEqual(rows[1]['normalized']['value'],'-90000000');self.assertTrue(rows[1]['forecastComparison']['outside']);self.assertIsNone(rows[1]['forecastComparison']['ratio'])
    def test_different_scope_not_compared(self):
        a=self.item('a','快报',-9000,date='2026-04-15');a['basis']='母公司'
        self.assertNotIn('forecastComparison',metrics([self.item('p','预告',low=-5000,high=-4000),a],{'s'})[1])
    def test_correction_difference_not_increment(self):
        a=self.item('a','快报',100,date='2026-04-15');b=self.item('b','更正',-50,date='2026-04-16');b['corrects']='a'
        self.assertEqual(metrics([a,b],{'s'})[1]['versionDifference'],'-1500000')
        b['corrects']='unknown'
        with self.assertRaises(ValueError):metrics([a,b],{'s'})
    def test_unit_conversion_and_nan(self):
        a=self.item('a','快报','5.117038',date='2026-04-15',unit='亿元')
        self.assertEqual(metrics([a],{'s'})[0]['normalized']['value'],'511703800.000000')
        a['value']='NaN'
        with self.assertRaises(ValueError):metrics([a],{'s'})

if __name__=='__main__': unittest.main()
