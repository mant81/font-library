"""Local browser QA for the public catalog, including project-subpath hosting."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def check():
    # Serve /_site/ rather than / to catch accidental origin-root asset URLs.
    handler=partial(SimpleHTTPRequestHandler,directory=str(ROOT))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    evidence=ROOT/'_workspace/pages-preview';evidence.mkdir(parents=True,exist_ok=True)
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            for width,height in [(1440,1100),(390,844)]:
                page=browser.new_page(viewport={'width':width,'height':height})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('response',lambda r:errors.append(f'HTTP {r.status}') if r.status>=400 else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/_site/',wait_until='networkidle')
                page.wait_for_function("document.querySelector('#font-state').textContent.includes('원형')")
                assert page.locator('.font-card').count()>=1
                assert page.locator('#apk-link').get_attribute('href').endswith('.apk')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal overflow'
                page.screenshot(path=str(evidence/f'catalog-{width}.png'),full_page=True)
                page.click('#seven')
                assert page.locator('#preview').evaluate('(el)=>getComputedStyle(el).fontSize')=='7px'
                assert 'Small' in page.locator('#preview').evaluate('(el)=>getComputedStyle(el).fontFamily')
                page.locator('#preview').fill('한글 English 0123')
                assert page.locator('#preview').input_value()=='한글 English 0123'
                page.click('#reset')
                assert '오늘의 작은 기록' in page.locator('#preview').input_value()
                page.close()
            browser.close()
    finally:server.shutdown()
    if errors:raise AssertionError(errors)
    (evidence/'validation.json').write_text(json.dumps({'status':'pass','viewports':[1440,390],
        'checks':['catalog','font-loading','project-subpath-assets','no-horizontal-overflow','7px-auto-small','input','reset','APK-link'],
        'errors':errors},indent=2)+'\n',encoding='utf-8')
    print('Pages browser QA PASS: desktop, mobile, 7px control and download links.')


if __name__=='__main__':check()
