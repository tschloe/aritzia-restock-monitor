import os, re, json, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
URL='https://www.aritzia.com/intl/en/product/the-super-puff%E2%84%A2/126362.html?color=29661'
SIZES=['XS','S']
STATE=Path('state.json')
def notify(title,body):
    payload=json.dumps({'device_key':os.environ['BARK_KEY'],'title':title,'body':body,'url':URL}).encode()
    req=urllib.request.Request('https://api.day.app/push',data=payload,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if json.load(r).get('code') != 200: raise RuntimeError('Bark rejected push')

def main():
    if os.getenv('TEST_PUSH')=='true': notify('Aritzia monitor test','Push connection works'); return
    old=json.loads(STATE.read_text()) if STATE.exists() else {}
    new=dict(old)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(locale='en-US')
        for size in SIZES:
            response=page.goto(URL,wait_until='domcontentloaded',timeout=45000)
            if response is None or response.status>=400: raise RuntimeError('Page unavailable; stop and review access')
            page.wait_for_timeout(5000)
            if '/intl/' not in page.url or 'color=29661' not in page.url: raise RuntimeError('Region or color not confirmed')
            if not re.search(r'Mochi Pink',page.locator('body').inner_text(),re.I): raise RuntimeError('Target color not confirmed')
            # Conservative: require unique semantic size control and explicit purchase or sold-out signal.
            control=page.get_by_role('button',name=re.compile(r'^'+size+r'$',re.I))
            if control.count()!=1: raise RuntimeError(f'{size}: size control not uniquely identified; inspect DOM')
            if not control.is_enabled(): raise RuntimeError(f'{size}: disabled control; stock status not verified')
            control.click(timeout=5000)
            page.wait_for_timeout(2000)
            bag=page.get_by_role('button',name=re.compile(r'^Add to Bag$',re.I))
            out=page.get_by_role('button',name=re.compile(r'Notify Me|Email Me|Sold Out',re.I))
            available=bag.count()==1 and bag.is_visible() and bag.is_enabled()
            unavailable=out.count()==1 and out.is_visible()
            if available==unavailable: raise RuntimeError(f'{size}: ambiguous stock signals')
            status='available' if available else 'unavailable'
            print(size,status)
            if available and old.get(size)!=status: notify('Aritzia possible restock',f'126362 / 29661 / {size}: Add to Bag enabled. Verify color and delivery country.')
            new[size]=status
            STATE.write_text(json.dumps(new,indent=2)+'\n')
        browser.close()
if __name__=='__main__': main()
