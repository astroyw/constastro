"""Read-only regression checks for delayed responses, country filters and horse campaigns."""
import asyncio
from urllib.parse import parse_qs,urlsplit

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
        context=await browser.new_context(viewport={'width':1440,'height':1000})
        await context.add_init_script("localStorage.setItem('linaje-demo','true')")
        page=await context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        async def slow_cross(route):
            await asyncio.sleep(.6)
            await route.fulfill(status=200,content_type='application/json',body='{"coefficient":0,"coverage":0,"known_slots":0,"total_slots":28,"shared_ancestors":[],"method":"Fixture","limitations":"Fixture"}')
        await page.route('**/api/compatibility',slow_cross)
        await page.goto('http://127.0.0.1:8000/#compatibilidad')
        await page.locator('#cross-form button').click()
        await page.locator('nav a[href="#datos"]').click()
        await page.locator('#uy-search').wait_for()
        await page.wait_for_timeout(800)
        assert await page.locator('#uruguay-import').is_visible()

        async def slow_old_results(route):
            country=parse_qs(urlsplit(route.request.url).query).get('country',[''])[0]
            if country=='URU':
                await asyncio.sleep(.6)
                await route.fulfill(status=500,content_type='application/json',body='{"detail":"Error de una consulta anterior"}')
            else:
                await route.continue_()
        await page.route('**/api/results?**',slow_old_results)
        await page.locator('nav a[href="#resultados"]').click()
        await page.locator('[data-country="ARG"]').click()
        await page.locator('.result-panel').first.wait_for()
        await page.wait_for_timeout(800)
        assert await page.locator('#results-content .result-panel').count()==9
        assert await page.locator('#results-content .error-message').count()==0
        await page.locator('#mode-button').click()
        await page.locator('#mode-label').filter(has_text='Datos reales').wait_for()
        await page.locator('nav a[href="#caballos"]').click()
        await page.locator('#horse-search').fill('Electric Mud')
        await page.get_by_role('button',name='ELECTRIC MUD',exact=True).click()
        await page.locator('#horse-title').filter(has_text='ELECTRIC MUD').wait_for()
        assert await page.locator('[data-campaign] tbody tr').count()>=9
        assert not errors,errors
        await browser.close()
        print('PASS: delayed analysis survives navigation; stale result failures cannot replace current results; linked campaign displays nine starts; no JS errors.')


if __name__=='__main__':asyncio.run(main())
