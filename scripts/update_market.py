"""Shared market publisher. Indexed snippets never become dated sale records."""
import json, os, re, sys, pathlib, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
ROOT=pathlib.Path(__file__).resolve().parents[1]
GROUPS={'797104363091043':'戰鬥陀螺X 大聯盟2.0','411150865948422':'戰鬥陀螺 BEYBLADE X 交易版全新／二手','1492428162434388':'戰鬥陀螺 BEYBLADE X 交易版','1240639167707723':'中部_戰鬥陀螺買賣／交流（台灣）'}
STATUSES=['成交','在售','收購','競標'];KINDS=['整顆','零件','組合','拆賣','頂重'];CONDITIONS=['沒寫','全新','拆檢','二手'];VERSIONS=['','日版','台版','亞版','美版','韓版','港版','泰版']
LIMIT=5_800_000

def instant(s):
    if not isinstance(s,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})',s): raise ValueError('時間需包含秒與時區')
    return datetime.fromisoformat(s.replace('Z','+00:00'))

def canonical(url):
    p=urllib.parse.urlsplit(url)
    m=re.fullmatch(r'/groups/(\d+)/(?:posts|permalink)/(\d+)/?',p.path)
    if p.scheme!='https' or p.hostname not in ('facebook.com','www.facebook.com') or p.port or p.username or p.password or not m or m[1] not in GROUPS:raise ValueError('不是指定社團原貼文')
    return f'https://www.facebook.com/groups/{m[1]}/posts/{m[2]}/',m[1]

def text(v,limit,required=True):
    if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):raise ValueError('缺少文字或超過長度限制')
    return v.strip()

def validate_post(p,models,now):
    url,gid=canonical(p['post_url']);published=instant(p['published_at'])
    if published>now:raise ValueError('發文日期在未來')
    if p.get('capture_method')!='original_post':raise ValueError('成交 feed 只接受原文記錄')
    items=p.get('listings');excerpt=text(p.get('excerpt'),20000)
    if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('商品列表無效')
    clean=[]
    for item in items:
        st=item['status'];kind=item.get('kind','整顆');cn=item.get('condition','沒寫');ver=item.get('version','')
        price=item['price_twd']
        if st not in STATUSES or kind not in KINDS or cn not in CONDITIONS or ver not in VERSIONS:raise ValueError('商品分類不支援')
        if type(price) is not int or not 1<=price<=1_000_000:raise ValueError('價格無效')
        x={k:item[k] for k in ['model','part_category','part_id','part_name'] if k in item}
        if kind=='零件' and item.get('part_category'):
            if item['part_category'] not in ['上蓋','固鎖','軸心','輔助戰刃','超越戰刃']:raise ValueError('零件分類無效')
            text(item.get('part_id'),100);text(item.get('part_name'),300)
        elif item.get('model') not in models:raise ValueError('商品型號不在圖鑑')
        x.update(price_twd=price,status=st,kind=kind,condition=cn,version=ver)
        if st=='成交':
            if item.get('sold_at') is not None:
                sold=instant(item['sold_at'])
                if sold<published or sold>now:raise ValueError('成交時間早於發文或在未來')
            # Price must be the seller-declared final price, not a retained asking price.
            if item.get('price_basis')!='seller_confirmed_final':raise ValueError('未確認成交價，不能使用原開價')
            x.update(sold_at=item.get('sold_at'),price_basis='seller_confirmed_final',evidence_excerpt=text(item.get('evidence_excerpt'),2000))
        clean.append(x)
    return dict(group_name=text(p.get('group_name',GROUPS[gid]),200),post_url=url,published_at=p['published_at'],excerpt=excerpt,capture_method='original_post',transaction_evidence=text(p.get('transaction_evidence',''),2000,False),listings=clean)

def request_json(url,payload=None,token=None):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.username or p.password:raise ValueError('feed 必須為不含帳密的 HTTPS URL')
    headers={'User-Agent':'BeybladeMarket/1.0','Accept':'application/json'}
    data=None
    if payload is not None:headers['Content-Type']='application/json';data=json.dumps(payload).encode()
    if token:headers['Authorization']='Bearer '+token
    with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers),timeout=35) as r:
        raw=r.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('資料超過大小限制')
        return json.loads(raw)

def merge_posts(old,new):
    # Provider entries are complete per-post replacements; handles amended price/status.
    result={x['post_url']:x for x in old}
    for x in new:result[x['post_url']]=x
    return sorted(result.values(),key=lambda x:x['post_url'])

def index_refs(results,now):
    out=[]
    for item in results:
        try:url,gid=canonical(item['url'])
        except (ValueError,KeyError,TypeError):continue
        title=item.get('title','');excerpt=item.get('description','')
        if not isinstance(title,str) or not isinstance(excerpt,str) or not title.strip() or not excerpt.strip():continue
        # Adjacent "other posts" prices don't belong to the indexed source post.
        excerpt=re.split(r'Other posts|其他貼文',excerpt,flags=re.I)[0].strip()
        if not excerpt:continue
        out.append(dict(group_id=gid,group_name=GROUPS[gid],post_url=url,title=title[:300],excerpt=excerpt[:2000],status='未分類',capture_method='search_index',published_at=None,captured_at=now.isoformat(timespec='seconds'),collected_on=now.astimezone(timezone(timedelta(hours=8))).date().isoformat(),verification='unverified'))
    return out

def update(root=ROOT):
    now=datetime.now(timezone.utc);path=root/'data/snapshot.json';old=json.loads(path.read_text())
    models=set(json.loads((root/'data/models.json').read_text()));posts=old.get('posts',[]);refs={x['post_url']:x for x in old.get('references',[])}
    feed_urls=[x.strip() for x in os.environ.get('MARKET_FEED_URLS','').splitlines() if x.strip()]
    verified_ok=0;search_ok=0;errors=[];new_urls=set();before=set(refs)
    for n,url in enumerate(feed_urls):
        try:
            source=request_json(url);items=source['posts']
            if not isinstance(items,list) or len(items)>5000:raise ValueError('feed 過大')
            seen=set();accepted=[]
            for item in items:
                x=validate_post(item,models,now)
                if x['post_url'] in seen:raise ValueError('同 feed 原文重複')
                seen.add(x['post_url']);accepted.append(x)
            new_urls.update(x['post_url'] for x in accepted if x['post_url'] not in {p['post_url'] for p in posts})
            posts=merge_posts(posts,accepted);verified_ok+=1
        except Exception as exc:errors.append({'source':f'feed_{n+1}','reason':type(exc).__name__})
    key=os.environ.get('FIRECRAWL_API_KEY','').strip()
    search_enabled=os.environ.get('FIRECRAWL_SEARCH_ENABLED','1')!='0'
    if search_enabled:
        for gid in GROUPS:
            try:
                result=request_json('https://api.firecrawl.dev/v2/search',{'query':f'site:facebook.com/groups/{gid} 陀螺 出售 全新 二手','limit':20 if key else 3,'sources':['web'],'domainTools':False},key)
                if not result.get('success'):raise ValueError('搜尋服務失敗')
                body=result.get('data',{});web=body.get('web',[]) if isinstance(body,dict) else body
                if not isinstance(web,list):raise ValueError('搜尋格式無效')
                for ref in index_refs(web,now):refs[ref['post_url']]=ref
                search_ok+=1
            except Exception as exc:errors.append({'source':f'group_{gid}','reason':type(exc).__name__})
    # Retain prior confirmed records on feed failure; refresh age from true event timestamps.
    prior=old.get('collection',{})
    result={'schema_version':2,'captured_at':now.isoformat(timespec='seconds'),'posts':posts,'references':list(refs.values())[-2000:],'collection':{'status':'ok' if not errors and (verified_ok or search_ok) else 'partial' if verified_ok or search_ok else 'error' if errors else 'pending','last_attempt_at':now.isoformat(timespec='seconds'),'last_verified_fetch_at':now.isoformat(timespec='seconds') if verified_ok else prior.get('last_verified_fetch_at'),'verified_feed_configured':bool(feed_urls),'verified_feeds_ok':verified_ok,'reference_groups_ok':search_ok,'last_reference_fetch_at':now.isoformat(timespec='seconds') if search_ok else prior.get('last_reference_fetch_at'),'new_posts':len(new_urls),'new_references':len(set(refs)-before),'errors':errors}}
    if len(posts)>5000 or sum(len(p['listings']) for p in posts)>20000:raise ValueError('原文或商品總數超限，保留原檔')
    encoded=json.dumps(result,ensure_ascii=False,indent=2)
    if len(encoded.encode())>LIMIT:raise ValueError('快照過大，保留原檔')
    temp=path.with_suffix('.tmp');temp.write_text(encoded);temp.replace(path)
    (root/'snapshot.json').write_text(encoded)
    print(json.dumps({'status':result['collection']['status'],'posts':len(posts),'references':len(refs),'feed_ok':verified_ok,'search_ok':search_ok},ensure_ascii=False))
    return result
if __name__=='__main__':update()
