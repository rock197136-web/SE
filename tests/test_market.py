import sys,json,tempfile,pathlib,os,unittest
from unittest.mock import patch
from datetime import datetime, timezone
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import update_market as m
NOW=datetime(2026,10,6,15,0,tzinfo=timezone.utc)
def post():
 return {'post_url':'https://www.facebook.com/groups/1492428162434388/posts/123456789/','published_at':'2026-10-01T12:00:00+08:00','capture_method':'original_post','excerpt':'測試原文','listings':[{'model':'UX-03','status':'成交','condition':'二手','price_twd':800,'sold_at':'2026-10-05T12:00:00+08:00','price_basis':'seller_confirmed_final','evidence_excerpt':'賣家確認800元成交'}]}
class MarketTests(unittest.TestCase):
 def test_sold_requires_final_price_and_date(self):
  p=post();m.validate_post(p,{'UX-03'},NOW)
  for field in ['price_basis','evidence_excerpt']:
   p=post();del p['listings'][0][field]
   with self.assertRaises((ValueError,KeyError)):m.validate_post(p,{'UX-03'},NOW)
 def test_sold_date_optional(self):
  p=post();del p['listings'][0]['sold_at'];m.validate_post(p,{'UX-03'},NOW)
 def test_no_future_sales(self):
  p=post();p['listings'][0]['sold_at']='2026-12-01T00:00:00Z'
  with self.assertRaises(ValueError):m.validate_post(p,{'UX-03'},NOW)
 def test_index_is_not_sale(self):
  results=m.index_refs([{'url':post()['post_url'],'title':'已售出','description':'UX03 $800 Other posts 假資料'}],NOW)
  self.assertRegex(results[0]['captured_at'],r'\d{2}:\d{2}:\d{2}\+00:00$');self.assertEqual(results[0]['status'],'未分類');self.assertIsNone(results[0]['published_at']);self.assertNotIn('假資料',results[0]['excerpt'])
 def test_post_update_replaces_price(self):
  p=post();x=post();x['listings'][0]['price_twd']=850
  r=m.merge_posts([p],[x]);self.assertEqual(len(r),1);self.assertEqual(r[0]['listings'][0]['price_twd'],850)
 def test_failure_retains_history(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'data').mkdir();(root/'data/models.json').write_text('["UX-03"]')
   old={'posts':[post()],'references':[],'collection':{'last_verified_fetch_at':'2026-10-01T00:00:00Z'}};(root/'data/snapshot.json').write_text(json.dumps(old))
   with patch.dict(os.environ,{'MARKET_FEED_URLS':'https://example.org/feed.json','FIRECRAWL_API_KEY':'','FIRECRAWL_SEARCH_ENABLED':'0'}),patch.object(m,'request_json',side_effect=OSError('failed')):
    result=m.update(root)
   self.assertEqual(result['posts'],old['posts']);self.assertEqual(result['collection']['status'],'error');self.assertEqual(result['collection']['last_verified_fetch_at'],old['collection']['last_verified_fetch_at'])
 def test_valid_feed_enters_shared_file(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'data').mkdir();(root/'data/models.json').write_text('["UX-03"]');(root/'data/snapshot.json').write_text('{"posts":[],"references":[]}')
   with patch.dict(os.environ,{'MARKET_FEED_URLS':'https://example.org/feed.json','FIRECRAWL_API_KEY':'','FIRECRAWL_SEARCH_ENABLED':'0'}),patch.object(m,'request_json',return_value={'posts':[post()]}):
    result=m.update(root)
   self.assertEqual(result['collection']['status'],'ok');self.assertEqual(len(result['posts']),1)
if __name__=='__main__':unittest.main()
