"""Check the interactive preview's autocomplete and campaign coverage display."""
import asyncio,os,json,subprocess
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
  assert 'escala 0–100' in await page.locator('.affinity-panel').inner_text()
  assert all(0<=int(s.split('/')[0])<=100 for s in await page.locator('.affinity-grid strong').all_inner_texts())
  assert 'Sin datos suficientes' not in await page.locator('.affinity-grid').inner_text()
  assert await page.locator('.affinity-grid meter[min="0"]').count()==5
  await page.locator('#sire').select_option('ar-studbook:428095')
  await page.locator('#dam').select_option('ar-studbook:422102')
  await page.get_by_role('button',name='Analizar parentesco').click()
  await page.locator('.affinity-grid').wait_for()
  expected=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import fs from 'node:fs'; import {performance} from './static/performance.js'; const d=JSON.parse(fs.readFileSync('dist/data/site.json','utf8')); console.log(JSON.stringify(performance('ar-studbook:428095','ar-studbook:422102',d.horses.real,d.results).map(p=>p.score)));"],text=True))
  assert await page.locator('.affinity-grid strong').all_inner_texts()==[f'{s} / 100' for s in expected]
  assert any(s!=50 for s in expected),expected
  await page.locator('.affinity-grid article').first.locator('details > summary').click()
  assert 'Rama paterna' in await page.locator('.affinity-grid article').first.inner_text()
  assert await page.locator('.affinity-grid a[href^="https://www.studbook.org.ar/"]').count()>0
  await page.locator('#mode-button').click()
  await page.get_by_role('button',name='Analizar parentesco').click()
  await page.locator('.affinity-grid').wait_for()
  assert await page.locator('.affinity-grid strong').all_inner_texts()==['50 / 100']*5
  assert (await page.locator('.affinity-grid').inner_text()).count('Confianza: Sin evidencia')==5
  await page.locator('#mode-button').click()
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
  await page.locator('#sire-search').press('Escape')
  await page.locator('#sire').select_option('ar-studbook:428095')
  await page.locator('#dam').select_option('ar-studbook:422102')
  await page.get_by_role('button',name='Analizar parentesco').click()
  await page.locator('.affinity-grid').wait_for()
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await page.screenshot(path='exports/compatibilidad-indices.png',full_page=True)
  assert not errors,errors
  await browser.close();print('PASS: searches and invalidation, five numeric indices, real campaigns and citations, explicit neutral prior in demo, desktop/mobile layout.')

if __name__=='__main__':asyncio.run(main())
