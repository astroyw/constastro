"""Read-only browser smoke test against the running development server."""
import argparse
import io
import shutil
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:8000')
args=parser.parse_args()
out=Path(__file__).resolve().parents[1]/'exports'
out.mkdir(exist_ok=True)

with sync_playwright() as p:
    executable=shutil.which('chromium')
    browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
    context=browser.new_context(viewport={'width':1440,'height':1080},accept_downloads=True)
    context.add_init_script("localStorage.setItem('linaje-demo','true')")
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.base_url)
    page.get_by_role('heading',name='Cada campeón tiene una historia.').wait_for()
    assert page.locator('.demo-banner').is_visible()
    page.screenshot(path=str(out/'panorama.png'),full_page=True)

    page.locator('nav a[href="#caballos"]').click()
    page.locator('#horse-search').fill('Faro Oriental')
    page.get_by_role('button',name='Faro Oriental',exact=True).click()
    page.locator('#horse-title').filter(has_text='Faro Oriental').wait_for()
    assert page.locator('.pedigree-node').count()==14
    assert page.locator('.pedigree-node[data-col="3"]').count()==8
    page.screenshot(path=str(out/'pedigree.png'),full_page=True)
    page.keyboard.press('Escape')

    page.locator('nav a[href="#compatibilidad"]').click()
    page.locator('#cross-form button[type="submit"]').click()
    page.locator('.coefficient').wait_for()
    assert '3,125' in page.locator('.coefficient').inner_text()
    assert '100%' in page.locator('.analysis-metrics').inner_text()
    page.screenshot(path=str(out/'compatibilidad.png'),full_page=True)

    page.locator('nav a[href="#resultados"]').click()
    page.wait_for_function("document.querySelector('#results-content .empty-state, #results-content .result-panel') !== null")
    assert page.locator('.country-chip').count()==9
    page.locator('[data-country="JPN"]').click()
    page.locator('.results-heading h2').filter(has_text='Japón').wait_for()
    page.locator('#results-content .empty-state').wait_for()

    page.locator('nav a[href="#fuentes"]').click()
    page.locator('#source-country').select_option('URU')
    page.wait_for_function("document.querySelectorAll('.source-card').length === 2")

    page.locator('nav a[href="#datos"]').click()
    with page.expect_download() as download_info:
        page.get_by_role('link',name='Descargar Excel de ejemplo').click()
    download=download_info.value
    download.save_as(str(out/'Linaje_DEMOSTRACION.xlsx'))
    wb=load_workbook(out/'Linaje_DEMOSTRACION.xlsx')
    assert wb['Caballos'].max_row==30
    assert len(wb.sheetnames)==7

    page.locator('#mode-button').click()
    page.locator('#mode-label').filter(has_text='Datos reales').wait_for()
    page.locator('nav a[href="#caballos"]').click()
    assert page.locator('.demo-banner').count()==0
    assert page.locator('[data-horse^="demo-"]').count()==0
    page.locator('#mode-button').click()
    page.locator('#mode-label').filter(has_text='Demostración').wait_for()

    phone=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    phone.add_init_script("localStorage.setItem('linaje-demo','true')")
    mobile=phone.new_page()
    mobile.on('pageerror',lambda e:errors.append(str(e)))
    mobile.goto(args.base_url)
    mobile.get_by_role('heading',name='Cada campeón tiene una historia.').wait_for()
    assert mobile.evaluate('document.body.scrollWidth <= innerWidth')
    mobile.screenshot(path=str(out/'movil.png'),full_page=True)
    mobile.locator('#mobile-menu').click()
    mobile.locator('nav a[href="#caballos"]').click()
    mobile.locator('#horse-search').fill('Faro Oriental')
    mobile.get_by_role('button',name='Faro Oriental',exact=True).click()
    mobile.locator('#horse-title').filter(has_text='Faro Oriental').wait_for()
    assert mobile.evaluate('document.body.scrollWidth <= innerWidth')
    assert not errors,errors
    print('PASS: desktop/mobile navigation, search, 14 ancestors, Wright 3.125%, coverage, country/source filters, XLSX download, real/demo separation; no JS errors.')
    browser.close()
