"""Read-only checks for real earnings lists, pagination and late ranking responses."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
        page=await browser.new_page(viewport={'width':1440,'height':1100})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:8000/#rankings')
        await page.locator('[data-ranking="equibase-200"]').click()
        await page.get_by_role('button',name='Forever Young (JPN)',exact=True).wait_for()
        assert await page.locator('#ranking-rows tr').count()==200
        assert 'USD' in await page.locator('.ranking-earnings').first.inner_text()
        await page.locator('#ranking-search').fill('Forever Young')
        assert await page.locator('#ranking-rows tr').count()==1
        await page.get_by_role('button',name='Forever Young (JPN)',exact=True).click()
        await page.locator('#horse-title').filter(has_text='Forever Young').wait_for()
        assert await page.locator('.pedigree-node').count()==14
        assert 'Nacido en JPN' in await page.locator('.horse-meta').inner_text()
        await page.keyboard.press('Escape')
        await page.locator('[data-ranking="arg-100"]').click()
        await page.locator('#ranking-rows').wait_for()
        assert 'ARS' in await page.locator('.ranking-earnings').first.inner_text()
        assert '1992' in await page.locator('.ranking-header').inner_text()
        assert '14 / 14' in await page.locator('#ranking-rows tr').first.inner_text()
        await page.locator('#ranking-search').fill('  MIRINAQUE  ')
        await page.get_by_role('button',name='MIRIÑAQUE',exact=True).wait_for()
        assert await page.locator('#ranking-rows tr').count()==1
        await page.locator('#ranking-search').fill('')
        await page.locator('[data-ranking="bra-100"]').click()
        await page.locator('#ranking-detail .empty-state').wait_for()
        assert await page.locator('#ranking-rows').count()==0
        await page.locator('[data-ranking="uru-100"]').click()
        await page.get_by_role('button',name='PLUTO',exact=True).wait_for()
        assert 'UYU' in await page.locator('.ranking-earnings').first.inner_text()
        assert '14 / 14' in await page.locator('#ranking-rows tr').first.inner_text()
        await page.get_by_role('button',name='PLUTO',exact=True).click()
        await page.locator('#horse-title').filter(has_text='PLUTO').wait_for()
        assert await page.locator('.pedigree-node.unknown').count()==0
        await page.keyboard.press('Escape')
        await page.screenshot(path='exports/rankings.png',full_page=False)

        async def delay(route):
            await asyncio.sleep(.5)
            await route.continue_()
        await page.route('**/api/rankings/equibase-200',delay)
        await page.locator('[data-ranking="equibase-200"]').click()
        await page.locator('[data-ranking="bra-100"]').click()
        await page.locator('#ranking-detail .empty-state').wait_for()
        await page.wait_for_timeout(800)
        assert await page.locator('#ranking-rows').count()==0

        await page.locator('nav a[href="#caballos"]').click()
        await page.locator('.pagination').wait_for()
        assert await page.locator('.horse-table tbody tr').count()==50
        before=await page.locator('.horse-name-button').first.inner_text()
        await page.get_by_role('button',name='Siguiente',exact=True).click()
        assert before!=await page.locator('.horse-name-button').first.inner_text()
        await page.locator('#horse-search').fill('Electric Mud')
        await page.get_by_role('button',name='ELECTRIC MUD',exact=True).wait_for()
        assert await page.locator('.horse-table tbody tr').count()==1

        await page.set_viewport_size({'width':390,'height':844})
        await page.goto('http://127.0.0.1:8000/#rankings')
        await page.locator('[data-ranking="uru-100"]').click()
        await page.locator('#ranking-rows').wait_for()
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path='exports/rankings-mobile.png',full_page=False)
        assert not errors,errors
        await browser.close()
        print('PASS: 200 real Equibase positions, UYU/USD labels, birth country, pedigree, pending lists, late-response guard, 50-row pagination, search and mobile layout.')


if __name__=='__main__':
    Path('exports').mkdir(exist_ok=True)
    asyncio.run(main())
