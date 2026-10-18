#!/usr/bin/env python3
# Optional browser regression checks: pip install playwright; playwright install chromium.
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
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    count = 0
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{server.server_port}/tests/fixtures/handset-shell.html')
            for width in (320, 375, 768, 1440):
                await page.set_viewport_size({'width':width,'height':900})
                for model in ('3210','3310','8210','6310','7110'):
                    await page.evaluate('(id)=>wapflixHandset.set(id)',model)
                    assert await page.locator('.handset-controls').count() == 1
                    assert await page.locator('#left').count() == 1
                    assert await page.locator('#back').count() == 1
                    assert await page.locator('.keypad [data-key]').count() == 12
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width,model,'overflow')
                    assert await page.locator('.handset-slider-cover').is_visible() == (model=='7110')
                    assert await page.evaluate("""() => {
                      const nodes=[...document.querySelectorAll('.handset-controls button,.keypad button')];
                      const rs=nodes.map(n=>n.getBoundingClientRect());
                      return rs.every((a,i)=>a.width>20&&a.height>20&&rs.every((b,j)=>i===j||Math.min(a.right,b.right)-Math.max(a.left,b.left)<1||Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<1));
                    }"""), (width,model,'overlapping controls')
                    await page.evaluate('events.length=0')
                    await page.locator('#left').click()
                    await page.locator('#back').click()
                    if model in ('3210','3310'):
                        await page.locator('#back').evaluate("n=>n.setAttribute('aria-label','OPTIONS')")
                        assert await page.locator('#back').get_attribute('aria-label') == 'Back (C)'
                    expected = ['select','back' if model in ('3210','3310') else 'context-right']
                    assert await page.evaluate('events') == expected
                    await page.locator('.handset-up,.roller-up').click()
                    await page.locator('.handset-down,.roller-down').click()
                    assert (await page.evaluate('events'))[-2:] == ['2','8']
                    for value in ('4','5','6','0','*','#'):
                        await page.locator(f'.keypad [data-key="{value}"]').click()
                        assert (await page.evaluate('events'))[-1] == value
                    await page.evaluate('document.getElementById("lcd").classList.remove("dim")')
                    if model not in ('3210','3310'):
                        await page.locator('.handset-call').click()
                        assert (await page.evaluate('events'))[-1] == 'select'
                        await page.locator('.handset-end').click()
                        assert (await page.evaluate('events'))[-1] == '*'
                    if model=='7110':
                        await page.locator('.roller-press').click()
                        assert (await page.evaluate('events'))[-1] == 'select'
                        await page.locator('.handset-roller').dispatch_event('wheel',{'deltaY':40})
                        assert (await page.evaluate('events'))[-1] == '8'
                        await page.locator('.handset-slider-cover').click()
                        assert await page.locator('.keypad').evaluate('(n)=>n.inert')
                        assert not await page.locator('.keypad [data-key="5"]').is_visible()
                        await page.locator('.handset-slider-cover').click()
                        assert not await page.locator('.keypad').evaluate('(n)=>n.inert')
                    count += 1
            await page.locator('.handset-picker select').select_option('8210')
            await page.reload()
            assert await page.evaluate('wapflixHandset.current()') == 'NOKIA 8210'
            await page.evaluate('events.length=0')
            await page.locator('.handset-picker select').focus()
            await page.keyboard.press('ArrowDown')
            assert 'document-shortcut' not in await page.evaluate('events')
            for _ in range(20): await page.evaluate('wapflixHandset.cycle()')
            assert await page.locator('.handset-controls').count()==1
            assert await page.locator('.handset-picker').count()==1
            assert not errors, errors
            await page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('denied')}})")
            await page.reload()
            assert await page.evaluate('wapflixHandset.current()')=='NOKIA 3310'
            await page.evaluate('wapflixHandset.cycle()')
            assert await page.evaluate('wapflixHandset.current()')=='NOKIA 8210'
            assert not errors, errors
            await browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(f'PASS: {count} handset/viewport combinations; controls, slider, roller, persistence, denied storage and selector isolation.')

if __name__=='__main__': asyncio.run(check())
