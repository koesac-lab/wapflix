#!/usr/bin/env python3
"""Optional shell checks: pip install playwright; playwright install chromium."""
import asyncio
import functools
import http.server
import threading
from pathlib import Path
from playwright.async_api import async_playwright

async def check():
    root = Path(__file__).resolve().parents[1]
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(root)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    count=0
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=await browser.new_page(reduced_motion='reduce')
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{server.server_port}/tests/fixtures/handset-shell.html')
            for width,height in ((280,640),(320,568),(375,812),(768,900),(1440,1000)):
                await page.set_viewport_size({'width':width,'height':height})
                for model in ('3210','3310','8210','6310','7110'):
                    await page.evaluate('(id)=>wapflixHandset.set(id)',model)
                    assert await page.locator('.handset-head').count()==1
                    assert await page.locator('.brand').inner_text()=='NOKIA'
                    assert await page.locator('.phone .legend').count()==0
                    assert await page.locator('.phone .handset-model').count()==0
                    assert await page.locator('.handset-controls').count()==1
                    assert await page.locator('.keypad [data-key]').count()==12
                    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,model,'overflow')
                    assert await page.evaluate("document.getElementById('display')===originalCanvas&&document.getElementById('left')===originalLeft&&document.getElementById('back')===originalBack")
                    assert await page.evaluate("[...document.querySelectorAll('.keypad button')].every((b,i)=>b.onclick===originalKeyHandlers[i])")
                    assert await page.locator('.handset-slider-cover').is_visible()==(model=='7110')
                    assert await page.evaluate("""()=>{
                      const nodes=[...document.querySelectorAll('.handset-controls button,.keypad button')];
                      const rs=nodes.map(n=>n.getBoundingClientRect());
                      return rs.every((a,i)=>a.width>20&&a.height>20&&rs.every((b,j)=>i===j||Math.min(a.right,b.right)-Math.max(a.left,b.left)<1||Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<1));
                    }"""),(width,model,'overlapping controls')
                    await page.evaluate('events.length=0')
                    await page.locator('#left').click()
                    await page.locator('#back').click()
                    assert await page.evaluate('events')==['select','back' if model in ('3210','3310') else 'context-right']
                    if model in ('3210','3310'):
                        await page.locator('#back').evaluate("n=>n.setAttribute('aria-label','OPTIONS')")
                        assert await page.locator('#back').get_attribute('aria-label')=='Back (C)'
                    await page.locator('.handset-up,.roller-up').click()
                    await page.locator('.handset-down,.roller-down').click()
                    assert (await page.evaluate('events'))[-2:]==['2','8']
                    for value in '123456789*0#':
                        await page.locator(f'.keypad [data-key="{value}"]').click()
                        assert (await page.evaluate('events'))[-1]==value
                    await page.locator('.handset-power').click()
                    assert (await page.evaluate('events'))[-1]=='#'
                    assert await page.locator('.handset-power').get_attribute('aria-pressed')=='true'
                    if model not in ('3210','3310'):
                        await page.locator('.handset-call').click()
                        assert (await page.evaluate('events'))[-1]=='select'
                        await page.locator('.handset-end').click()
                        assert (await page.evaluate('events'))[-1]=='*'
                    if model=='7110':
                        assert await page.evaluate("document.querySelector('.handset-slider-cover').getBoundingClientRect().top>=document.querySelector('.keypad').getBoundingClientRect().bottom")
                        await page.locator('.roller-press').click()
                        assert (await page.evaluate('events'))[-1]=='select'
                        await page.locator('.handset-roller').dispatch_event('wheel',{'deltaY':40})
                        assert (await page.evaluate('events'))[-1]=='8'
                        before=await page.locator('.handset-slider-cover').bounding_box()
                        await page.locator('.handset-slider-cover').click()
                        assert await page.locator('.keypad').evaluate('(n)=>n.inert')
                        assert not await page.locator('.keypad [data-key="5"]').is_visible()
                        after=await page.locator('.handset-slider-cover').bounding_box()
                        assert abs(before['height']-after['height'])<1,'Cover must translate, not resize'
                        await page.locator('.handset-slider-cover').click()
                        assert not await page.locator('.keypad').evaluate('(n)=>n.inert')
                    count+=1
            await page.locator('.handset-picker select').select_option('8210')
            await page.reload()
            assert await page.evaluate('wapflixHandset.current()')=='NOKIA 8210'
            await page.evaluate('events.length=0')
            await page.locator('.handset-picker select').focus()
            await page.keyboard.press('ArrowDown')
            assert 'document-shortcut' not in await page.evaluate('events')
            for _ in range(25): await page.evaluate('wapflixHandset.cycle()')
            assert await page.locator('.handset-head').count()==1
            assert await page.locator('.handset-picker').count()==1
            assert await page.locator('.handset-help').count()==1
            assert not errors,errors
            await page.evaluate("wapflixHandset.set('7110')")
            await page.emulate_media(reduced_motion='no-preference')
            await page.locator('.handset-slider-cover').click()
            await page.wait_for_timeout(280)
            assert await page.locator('.handset-slider-cover').get_attribute('aria-expanded')=='false'
            await page.locator('.handset-slider-cover').click()
            await page.wait_for_timeout(280)
            assert await page.locator('.handset-slider-cover').get_attribute('aria-expanded')=='true'
            await page.set_viewport_size({'width':320,'height':568})
            await page.wait_for_timeout(100)
            assert await page.evaluate("document.querySelector('.handset-slider-cover').getBoundingClientRect().top>=document.querySelector('.keypad').getBoundingClientRect().bottom")
            touch=await browser.new_context(viewport={'width':375,'height':812},has_touch=True,reduced_motion='reduce')
            touch_page=await touch.new_page()
            await touch_page.goto(f'http://127.0.0.1:{server.server_port}/tests/fixtures/handset-shell.html')
            await touch_page.evaluate("wapflixHandset.set('7110')")
            await touch_page.locator('.roller-press').tap()
            assert (await touch_page.evaluate('events'))[-1]=='select'
            await touch_page.locator('.handset-slider-cover').tap()
            assert await touch_page.locator('.keypad').evaluate('(n)=>n.inert')
            await touch_page.locator('.handset-slider-cover').tap()
            assert not await touch_page.locator('.keypad').evaluate('(n)=>n.inert')
            await touch.close()
            await page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('denied')}})")
            await page.reload()
            assert await page.evaluate('wapflixHandset.current()')=='NOKIA 3310'
            await page.evaluate('wapflixHandset.cycle()')
            assert await page.evaluate('wapflixHandset.current()')=='NOKIA 8210'
            assert not errors,errors
            await browser.close()
    finally:
        server.shutdown();server.server_close()
    print(f'PASS: {count} handset/viewport combinations; original DOM/handlers, numeric controls, labels, power, roller, rigid slide, persistence, blocked storage and picker isolation.')

if __name__=='__main__': asyncio.run(check())
