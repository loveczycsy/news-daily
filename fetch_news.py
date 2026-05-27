#!/usr/bin/env python3
"""Fetch news data from all sources and save as JSON files for GitHub Pages."""
import json, urllib.request, urllib.parse, re, os, ssl, hashlib, time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read()

def fetch_json(url):
    return json.loads(fetch(url).decode('utf-8'))

def fetch_text(url):
    return fetch(url).decode('utf-8', errors='ignore')

def parse_rss(xml, src_name=''):
    items = []
    for m in re.finditer(r'<item>(.*?)</item>', xml, re.DOTALL):
        ix = m.group(1)
        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', _tag(ix, 'title'), flags=re.DOTALL).strip()
        link = _tag(ix, 'link').strip()
        desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', _tag(ix, 'description'), flags=re.DOTALL).strip()
        desc = re.sub(r'<[^>]+>', '', desc).strip()
        pub = _tag(ix, 'pubDate').strip() or _tag(ix, 'dc\\:date').strip()
        sn = src_name
        if not sn:
            if 'science.org' in link: sn = 'Science'
            elif 'chinanews.com' in link: sn = '中新网'
            elif 'people.com.cn' in link: sn = '人民网'
        if title:
            items.append({'title': title, 'link': link, 'desc': desc, 'publishTime': pub, 'sourceName': sn, 'source': 'rss'})
    return items

def parse_rss1(xml, src_name='Nature'):
    items = []
    for m in re.finditer(r'<item[^>]*>(.*?)</item>', xml, re.DOTALL):
        ix = m.group(1)
        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', _tag(ix, 'title'), flags=re.DOTALL).strip()
        link = _tag(ix, 'link').strip()
        desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', _tag(ix, 'content\\:encoded'), flags=re.DOTALL).strip()
        if not desc:
            desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', _tag(ix, 'description'), flags=re.DOTALL).strip()
        desc = re.sub(r'<[^>]+>', '', desc).strip()
        pub = _tag(ix, 'dc\\:date').strip() or _tag(ix, 'pubDate').strip()
        authors = re.findall(r'<dc:creator>(.*?)</dc:creator>', ix)
        author_str = ', '.join(a.strip() for a in authors[:3]) if authors else ''
        if title:
            items.append({'title': title, 'link': link, 'desc': (author_str + ' — ' + desc) if author_str else desc, 'publishTime': pub, 'sourceName': src_name, 'source': 'nature'})
    return items

def _tag(xml, name):
    m = re.search(r'<{0}[^>]*>(.*?)</{0}>'.format(name), xml, re.DOTALL)
    return m.group(1) if m else ''

def fetch_cankao():
    """Fetch all cankaoxiaoxi channels."""
    channels = ['diyi', 'junshi', 'zhongguo', 'guandian', 'kejiyy', 'yjxx', 'tiyujk']
    all_items = []
    for ch in channels:
        try:
            url = f'https://china.cankaoxiaoxi.com/json/channel/{ch}/list.json'
            raw = fetch_json(url)
            for d in raw.get('list', []):
                item = d.get('data', d)
                all_items.append({
                    'title': item.get('title', ''),
                    'link': item.get('url', ''),
                    'desc': item.get('description', '') or item.get('mTxt', ''),
                    'publishTime': item.get('publishTime', ''),
                    'sourceName': item.get('sourceName', '参考消息网'),
                    'source': 'cankaoxiaoxi'
                })
            print(f'  cankao/{ch}: {len(raw.get("list", []))} items')
        except Exception as e:
            print(f'  cankao/{ch}: FAIL - {e}')
    return all_items

def fetch_chinanews():
    """Fetch chinanews RSS feeds (used as 环球时报 source)."""
    cats = ['importnews', 'world', 'china', 'society', 'finance', 'life', 'jk', 'edu', 'fz']
    all_items = []
    for cat in cats:
        try:
            url = f'https://www.chinanews.com.cn/rss/{cat}.xml'
            xml = fetch_text(url)
            items = parse_rss(xml, '')
            all_items.extend(items)
            print(f'  chinanews/{cat}: {len(items)} items')
        except Exception as e:
            print(f'  chinanews/{cat}: FAIL - {e}')
    return all_items

def fetch_nature():
    """Fetch Nature RSS feeds."""
    sources = [
        ('https://www.nature.com/nature.rss', 'Nature'),
        ('https://feeds.nature.com/nbt/rss/current', 'Nat. Biotechnol.'),
        ('https://feeds.nature.com/nbt/rss/aop', 'Nat. Biotechnol.'),
        ('https://www.nature.com/nchem.rss', 'Nat. Chem.'),
        ('https://feeds.nature.com/nchem/rss/aop', 'Nat. Chem.'),
    ]
    all_items = []
    for url, name in sources:
        try:
            xml = fetch_text(url)
            items = parse_rss1(xml, name)
            all_items.extend(items)
            print(f'  nature/{name}: {len(items)} items')
        except Exception as e:
            print(f'  nature/{name}: FAIL - {e}')
    return all_items

def fetch_science():
    """Fetch Science RSS feeds."""
    urls = [
        'https://feeds.science.org/rss/science.xml',
        'https://feeds.science.org/rss/science-aop.xml',
    ]
    all_items = []
    for url in urls:
        try:
            xml = fetch_text(url)
            items = parse_rss(xml, 'Science')
            all_items.extend(items)
            print(f'  science/{url.split("/")[-1]}: {len(items)} items')
        except Exception as e:
            print(f'  science: FAIL - {e}')
    return all_items

def save_data(name, items):
    path = os.path.join(DATA_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'items': items, 'updated': datetime.utcnow().isoformat() + 'Z'}, f, ensure_ascii=False, indent=1)
    print(f'Saved {name}.json: {len(items)} items')

if __name__ == '__main__':
    print(f'Fetching news data at {datetime.utcnow().isoformat()}Z')
    
    print('\n--- 参考消息 ---')
    save_data('cankao', fetch_cankao())
    
    print('\n--- 环球时报 ---')
    save_data('huanqiu', fetch_chinanews())
    
    print('\n--- Nature ---')
    nature_items = fetch_nature()
    # Split by sub-source
    for sub in ['Nature', 'Nat. Biotechnol.', 'Nat. Chem.']:
        sub_items = [i for i in nature_items if i.get('sourceName') == sub]
        key = {'Nature': 'nature', 'Nat. Biotechnol.': 'nbt', 'Nat. Chem.': 'nchem'}[sub]
        save_data(key, sub_items)
    
    print('\n--- Science ---')
    save_data('science', fetch_science())
    
    print('\n--- 小红书·资本论 ---')
    save_data('xhs', fetch_xhs_user())
    
    print('\nDone!')

def fetch_xhs_user(user_id='602598343'):
    """Fetch Xiaohongshu user notes via web page scraping."""
    import re as _re
    items = []
    try:
        url = f'https://www.xiaohongshu.com/user/profile/{user_id}'
        html = fetch_text(url)
        m = _re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>', html, _re.DOTALL)
        if m:
            raw = _re.sub(r'\bundefined\b', 'null', m.group(1))
            data = json.loads(raw)
            user_data = data.get('user', {})
            notes = user_data.get('notes', [])
            if isinstance(notes, list):
                for note_group in notes:
                    if isinstance(note_group, list):
                        for note in note_group:
                            if isinstance(note, dict):
                                nc = note.get('note_card', note)
                                title = nc.get('title', nc.get('display_title', ''))
                                nid = nc.get('note_id', note.get('id', ''))
                                if title and nid:
                                    items.append({
                                        'title': title,
                                        'link': f'https://www.xiaohongshu.com/explore/{nid}',
                                        'desc': nc.get('desc', ''),
                                        'publishTime': nc.get('time', ''),
                                        'sourceName': '资本论',
                                        'source': 'xhs'
                                    })
        if not items:
            items.append({
                'title': '资本论·小红书主页',
                'link': f'https://www.xiaohongshu.com/user/profile/{user_id}',
                'desc': '小红书博主「资本论」- 商业财经 · 科普 · 民生资讯',
                'publishTime': '',
                'sourceName': '小红书',
                'source': 'xhs'
            })
        print(f'  xhs/资本论: {len(items)} items')
    except Exception as e:
        print(f'  xhs/资本论: FAIL - {e}')
        items = [{'title':'资本论·小红书','link':f'https://www.xiaohongshu.com/user/profile/{user_id}','desc':'点击查看小红书主页','publishTime':'','sourceName':'小红书','source':'xhs'}]
    return items
