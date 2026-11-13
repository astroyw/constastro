"""Exercise source-scoped careers, details, filtering and mobile in the real build."""
import asyncio,json,os
from collections import Counter
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    data=json.loads(Path('dist/data/site.json').read_text())
    counts=Counter(r.get('horse_id') for r in data['results'])
    nodes={h['id']:h for h in data['horses']['real']}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
        page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8083')+'/#caballos')
        async def open_horse(ident):
            await page.locator('#horse-search').fill(nodes[ident]['name'])
            await page.locator('#horse-search').press('Escape')
            await page.locator(f'button.horse-name-button[data-horse="{ident}"]').click()
            await page.locator('#horse-dialog[open] [data-campaign]').wait_for()
        await open_horse('ar-studbook:428095')
        panel=page.locator('[data-campaign]')
        assert 'Completa en esta fuente' in await panel.inner_text()
        assert 'Solo carreras oficiales de Argentina' in await panel.inner_text()
        assert await panel.locator('tbody tr').count()==min(20,counts['ar-studbook:428095'])
        first=panel.locator('tbody tr').first
        assert 'Césped' in await first.inner_text()
        await first.locator('summary').click()
        assert 'Tiempo del ganador' in await first.inner_text()
        assert 'Entrenador' in await first.inner_text()
        assert 'Premios publicados (ARS)' in await first.inner_text()
        assert await first.locator('a[href^="https://www.youtube.com/"]').count()==1
        await panel.locator('[data-campaign-year]').select_option('2025')
        expected=sum(r.get('horse_id')=='ar-studbook:428095' and r['date'].startswith('2025') for r in data['results'])
        assert await panel.locator('tbody tr').count()==expected
        await page.locator('#close-horse').click()
        long_id=next(i for i,n in counts.items() if i in nodes and n>20)
        await open_horse(long_id);assert await panel.locator('tbody tr').count()==20
        before=await panel.locator('tbody tr').first.inner_text()
        await panel.locator('[data-campaign-next]').click()
        assert before!=await panel.locator('tbody tr').first.inner_text()
        await page.locator('#close-horse').click()
        await open_horse('uy-studbook:103227')
        assert '7 actuaciones recuperadas / 7 declaradas' in await panel.inner_text()
        await panel.locator('summary').first.click()
        assert 'Tiempo individual oficial' in await panel.inner_text()
        assert 'de 8 participantes' in await panel.inner_text()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path='exports/campanas-actual.png',full_page=True)
        await page.locator('#close-horse').click()
        await open_horse('uy-studbook:38571')
        review=page.locator('details').filter(has=page.locator('summary',has_text='Ampliación documentada'))
        await review.locator('summary').click()
        assert 'Uruguay publica 1939 y Argentina 1930' in await review.inner_text()
        assert await review.locator('a[href^="https:"]').count()==4
        assert not errors,errors
        await browser.close()
        print('PASS: source totals, race details and citations, turf, years, pagination, Uruguay individual times, disputed pedigree date, mobile.')

if __name__=='__main__':asyncio.run(main())
