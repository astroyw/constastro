"""Verify the Netlify edition on a plain file server, with no Python API."""
import asyncio
import io
import json
import os
from pathlib import Path
import sys

from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.genetics import analyze

BASE=os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8080')


async def main():
    data=json.loads((ROOT/'dist'/'data'/'site.json').read_text())
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
        page=await browser.new_page(viewport={'width':1440,'height':1100})
        errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        await page.goto(BASE+'/#inicio')
        await page.locator('.stats-grid').wait_for()
        assert str(len(data['horses']['real'])) in (await page.locator('.stat .number').first.inner_text()).replace('.','')
        summary=data['stats']['real']['historical_review']
        assert f"{summary['complete']} árboles completos" in await page.locator('#historical-review-summary').inner_text()
        await page.screenshot(path=str(ROOT/'exports'/'previsualizacion-actual.png'),full_page=True)
        await page.goto(BASE+'/#rankings')
        for ident,count in (('equibase-200',200),('arg-100',100),('uru-100',100)):
            await page.locator(f'[data-ranking="{ident}"]').click()
            await page.locator('#ranking-rows').wait_for()
            assert await page.locator('#ranking-rows tr').count()==count
        await page.get_by_role('button',name='PLUTO',exact=True).click()
        await page.locator('#horse-title').filter(has_text='PLUTO').wait_for()
        assert await page.locator('.pedigree-node').count()==14
        assert await page.locator('.pedigree-node.unknown').count()==0
        await page.keyboard.press('Escape')
        await page.locator('[data-ranking="bra-100"]').click()
        await page.locator('#ranking-detail .empty-state').wait_for()
        await page.goto(BASE+'/#caballos')
        await page.locator('.pagination').wait_for()
        assert await page.locator('#main .horse-table tbody tr').count()==50
        await page.locator('#horse-search').fill('Electric Mud')
        await page.locator('#horse-search').press('Escape')  # Close suggestions before choosing the table row.
        await page.get_by_role('button',name='ELECTRIC MUD',exact=True).click()
        await page.locator('#horse-title').filter(has_text='ELECTRIC MUD').wait_for()
        assert await page.locator('.pedigree-node.unknown').count()==0
        await page.keyboard.press('Escape')
        await page.goto(BASE+'/#compatibilidad')
        await page.locator('#sire').select_option('uy-studbook:49882')
        dams=await page.locator('#dam option').evaluate_all('(items)=>items.map(e=>e.value).filter(Boolean)')
        await page.locator('#dam').select_option(dams[0])
        expected=analyze('uy-studbook:49882',dams[0],data['horses']['real'])
        await page.get_by_role('button',name='Analizar parentesco').click()
        await page.locator('.coefficient').wait_for()
        text=(await page.locator('.coefficient').inner_text()).replace('%','').replace(',','.').strip()
        assert abs(float(text)-expected['coefficient'])<0.0001
        await page.goto(BASE+'/#resultados')
        await page.locator('.result-panel').first.wait_for()
        assert await page.locator('.result-panel tbody tr').count()==sum(r['country']=='URU' for r in data['results'])
        await page.locator('#result-date').fill('2026-10-18')
        await page.wait_for_function("document.querySelectorAll('.result-panel tbody tr').length===6")
        await page.locator('#result-date').fill('2026-01-01')
        await page.locator('#results-content .empty-state').wait_for()
        await page.goto(BASE+'/#datos')
        await page.get_by_role('heading',name='Una base para explorar').wait_for()
        assert await page.locator('form').count()==1  # Global search only; no import forms.
        async with page.expect_download() as download_info:
            await page.get_by_role('link',name='Descargar Excel completo',exact=True).click()
        download=await download_info.value
        assert download.suggested_filename=='Linaje_pedigrees.xlsx'
        from openpyxl import load_workbook
        workbook=load_workbook(io.BytesIO(Path(await download.path()).read_bytes()),read_only=True)
        assert sum(1 for _ in workbook['Caballos'].rows)==len(data['horses']['real'])+1
        assert sum(1 for _ in workbook['Ganancias'].rows)==401
        assert 'Ramas pendientes' in workbook.sheetnames
        assert sum(1 for _ in workbook['Ramas pendientes'].rows)>1
        workbook.close()
        await page.locator('#mode-button').click()
        await page.get_by_role('link',name='Descargar Excel de ejemplo',exact=True).wait_for()
        async with page.expect_download() as demo_info:
            await page.get_by_role('link',name='Descargar Excel de ejemplo',exact=True).click()
        assert (await demo_info.value).suggested_filename=='Linaje_DEMOSTRACION.xlsx'
        await page.goto(BASE+'/#compatibilidad')
        await page.get_by_role('button',name='Analizar parentesco').click()
        await page.locator('.coefficient').wait_for()
        demo_expected=analyze('demo-faro','demo-brisa',data['horses']['demo'])
        demo_text=(await page.locator('.coefficient').inner_text()).replace('%','').replace(',','.').strip()
        assert abs(float(demo_text)-demo_expected['coefficient'])<0.0001
        await page.locator('#mode-button').click()
        await page.goto(BASE+'/#fuentes')
        await page.locator('.source-card').first.wait_for()
        assert 'HTTP 403' in await page.locator('.reference-check').inner_text()
        assert 'No se importaron datos' in await page.locator('.reference-check').inner_text()
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto(BASE+'/#rankings')
        await page.locator('#ranking-rows').wait_for()
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path=str(ROOT/'exports'/'netlify-mobile.png'))
        assert not errors,errors
        assert not [url for url in requests if '/api/' in url],requests
        assert len([url for url in requests if '/data/site.json' in url])==(0 if await page.locator('#linaje-data').count() else 1)
        await browser.close()
        print('PASS: Netlify edition, expanded records, 400 positions, 14 ancestors, Wright parity, results, real/demo Excel, mobile, no backend requests.')


if __name__=='__main__':asyncio.run(main())
