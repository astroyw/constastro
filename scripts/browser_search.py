"""Check the interactive preview's autocomplete and campaign coverage display."""
import asyncio,os
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
  page=await browser.new_page(viewport={'width':1440,'height':1000})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8083')+'/#compatibilidad')
  sire=page.locator('#sire-search');await sire.fill('in')
  assert await page.locator('#sire-search-options').is_hidden()
  await sire.fill('inv');await page.locator('#sire-search-options [role=option]').first.wait_for()
  await sire.press('ArrowDown');await sire.press('Enter')
  assert await page.locator('#sire').input_value()
  await page.locator('#dam-search').fill('china inv')
  await page.locator('#dam-search-options [role=option]').first.click()
  assert await page.locator('#dam').input_value()
  await page.get_by_role('button',name='Analizar parentesco').click()
  await page.locator('.affinity-grid').wait_for()
  assert await page.locator('.affinity-grid article').count()==5
  assert 'escala 1–100' in await page.locator('.affinity-panel').inner_text()
  assert (await page.locator('.affinity-grid').inner_text()).count('Confianza: Sin evaluar')==5
  assert (await page.locator('.affinity-grid').inner_text()).count('Sin datos suficientes')==5
  await sire.fill('zzz');assert await page.locator('#sire').input_value()==''
  assert await page.locator('.result-analysis').count()==0
  await page.locator('#sire').select_option('uy-studbook:49882')
  assert 'INVASOR' in await sire.input_value()
  global_input=page.locator('#global-search');await global_input.fill('inv')
  await page.locator('#global-search-options [role=option]').first.wait_for()
  assert await page.locator('#global-search-options [role=option]').count()>=2
  await global_input.press('ArrowDown');await global_input.press('Enter')
  await page.locator('#horse-dialog[open]').wait_for();await page.keyboard.press('Escape')
  await page.goto(os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8083')+'/#caballos')
  await page.locator('#horse-search').fill('inv')
  await page.locator('#horse-search-options [role=option]').first.wait_for()
  await page.locator('#horse-search-options [role=option]').first.click()
  await page.locator('#horse-dialog[open]').wait_for();await page.keyboard.press('Escape')
  await page.set_viewport_size({'width':390,'height':844})
  await page.goto(os.environ.get('STATIC_SITE_URL','http://127.0.0.1:8083')+'/#compatibilidad')
  await page.locator('#sire-search').fill('inv')
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await page.screenshot(path='exports/compatibilidad-busqueda.png',full_page=True)
  assert not errors,errors
  await browser.close();print('PASS: suggestions, keyboard/mouse, sex filters, selection invalidation, global/library search, five honest coverage cards, mobile.')

if __name__=='__main__':asyncio.run(main())
