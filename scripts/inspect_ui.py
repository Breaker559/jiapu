from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).resolve().parent.parent/'test-results'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/?demo=1');page.wait_for_load_state('networkidle')
    page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True,animations="disabled")
    print(page.locator('h1').all_text_contents())
    print('buttons:',page.get_by_role('button').all_text_contents()[:30])
    print('overflow desktop:',page.evaluate('document.documentElement.scrollWidth > innerWidth'))
    page.get_by_role('button',name='世系图谱',exact=True).click();page.wait_for_timeout(600)
    page.screenshot(path=str(OUT/'tree-desktop.png'),full_page=True,animations="disabled")
    page.set_viewport_size({'width':390,'height':844});page.goto('http://127.0.0.1:8765/?demo=1');page.wait_for_load_state('networkidle')
    page.screenshot(path=str(OUT/'home-mobile.png'),full_page=True,animations="disabled")
    print('overflow mobile:',page.evaluate('document.documentElement.scrollWidth > innerWidth'))
    print('errors:',errors)
    browser.close()
