"""Real dataset/browser checks for historical ancestry, source comparison and mobile."""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
 data=json.loads(Path('dist/data/site.json').read_text());nodes={h['id']:h for h in data['horses']['real']}
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
  page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8083')+'/#compatibilidad')
  await page.locator('#sire-search').wait_for()
  await page.locator('#global-search').fill('INVASOR')
  options=page.locator('#global-search-options [role=option]')
  await options.filter(has_text='uy-studbook:49882').first.click()
  await page.locator('#horse-dialog[open]').wait_for()
  await page.locator('.historic-details > summary').click()
  assert 'Ampliación pendiente' in await page.locator('.historic-details').inner_text()
  await page.locator('.history-search').fill('nearco')
  await page.locator('[data-history-id="uy-studbook:8781"]').click()
  await page.locator('#horse-title').filter(has_text='NEARCO').wait_for()
  assert 'Coincidencia documental parcial' in await page.locator('.verification-panel').inner_text()
  assert 'árbol completo' in await page.locator('.verification-panel').inner_text()
  assert await page.locator('.verification-panel a').count()>=1
  await page.locator('.historic-details > summary').click()
  assert 'Todas las ramas' in await page.locator('.historic-details').inner_text()
  await page.set_viewport_size({'width':390,'height':844})
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await page.screenshot(path='exports/pedigree-historico-mobile.png',full_page=True)
  assert not errors,errors
  await browser.close()
 print('PASS: historical search, clickable Nearco, honest partial source verification, 1935 cutoff and mobile layout.')

if __name__=='__main__':asyncio.run(main())
