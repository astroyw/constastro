"""Verify the shareable preview, using only the managed CA for a temporary browser."""
import asyncio,base64,hashlib,os,subprocess
from pathlib import Path
from playwright.async_api import async_playwright

def browser_options():
    options={'executable_path':'/usr/bin/chromium','headless':True}
    proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    if proxy:options['proxy']={'server':proxy,'bypass':'127.0.0.1,localhost'}
    ca=Path('/usr/local/share/ca-certificates/environment-proxy-ca.crt')
    if proxy and ca.exists():
        # No persistent trust-store change and no blanket ignore_https_errors.
        # Scope this temporary Chromium process to the provided proxy CA key.
        key=subprocess.check_output(['openssl','x509','-in',str(ca),'-pubkey','-noout'])
        der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=key)
        pin=base64.b64encode(hashlib.sha256(der).digest()).decode()
        options['args']=['--ignore-certificate-errors-spki-list='+pin]
    return options

async def main():
    url=os.environ['PUBLIC_PREVIEW_URL']
    async with async_playwright() as p:
        browser=await p.chromium.launch(**browser_options())
        page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(url,timeout=45000)
        frame=page.frame_locator('#linaje-preview')
        await frame.locator('.stats-grid').wait_for(timeout=60000)
        print('Public preview loaded:',await frame.locator('.stat .number').first.inner_text(),flush=True)
        await frame.locator('a[data-route="caballos"]').click()
        await frame.locator('#horse-search').fill('ACENTO FINAL');await frame.locator('#horse-search').press('Escape')
        await frame.get_by_role('button',name='ACENTO FINAL',exact=True).click()
        await frame.locator('[data-campaign]').wait_for()
        assert 'Completa en esta fuente' in await frame.locator('[data-campaign]').inner_text()
        await frame.locator('#close-horse').click()
        await frame.locator('a[data-route="compatibilidad"]').click()
        await frame.locator('#sire').select_option('ar-studbook:428095')
        await frame.locator('#dam').select_option('ar-studbook:422102')
        await frame.get_by_role('button',name='Analizar parentesco').click()
        await frame.locator('.affinity-grid').wait_for();assert await frame.locator('.affinity-grid article').count()==5
        await frame.locator('a[data-route="datos"]').click()
        async with page.expect_download(timeout=60000) as pending:
            await frame.get_by_role('link',name='Descargar Excel completo',exact=True).click()
        download=await pending.value;assert download.suggested_filename=='Linaje_pedigrees.xlsx'
        assert (await download.failure()) is None
        await page.set_viewport_size({'width':390,'height':844})
        await frame.locator('#mobile-menu').click()
        await frame.locator('a[data-route="inicio"]').click()
        await frame.locator('.stats-grid').wait_for()
        assert await frame.locator('html').evaluate('e=>e.scrollWidth<=innerWidth')
        await page.screenshot(path='exports/preview-publica-mobile.png',full_page=True)
        assert not errors,errors
        await browser.close()
        print('PASS: shareable preview navigation, campaigns, five computed indices, Excel download, mobile and no JavaScript errors.',flush=True)

if __name__=='__main__':asyncio.run(main())
