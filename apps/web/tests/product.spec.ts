import {test,expect} from '@playwright/test';
import path from 'node:path';
test('mixed demo, source filters, safe import, export and desktop/mobile layout',async({page,request})=>{
 test.setTimeout(90000);const h=await request.get('/api/health');expect((await h.json()).single_user).toBe(true);
 await request.delete('/api/data');await page.goto('/');await page.getByRole('button',{name:'Connect & import',exact:true}).click();await page.getByRole('button',{name:'Load synthetic demo'}).click();await expect(page.getByRole('status')).toContainText('Synthetic demo loaded');
 await expect(page.getByText('Security codes skipped',{exact:true})).toBeVisible();
 await page.getByLabel('Import files').setInputFiles(path.resolve('../../data/synthetic/purchase.eml'));await expect(page.getByRole('status')).toContainText('Import processed');
 await page.getByLabel('Message content').fill('My secret dinner is at 9 pm. Code 773391.');await page.getByRole('button',{name:'Analyse message'}).click();await expect(page.getByRole('status')).toContainText('Message processed');
 const dump=await (await request.get('/api/export')).text();expect(dump).not.toContain('773391');expect(dump).not.toContain('739182');
 await page.getByRole('button',{name:'Overview',exact:true}).click();await expect(page.getByRole('heading',{name:'Your money, in focus.'})).toBeVisible();
 await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:'../../docs/desktop.png'});
 await page.getByRole('button',{name:/Purchase spending/}).click();await expect(page.getByText('Showing purchases')).toBeVisible();
 await page.getByRole('button',{name:'Needs attention',exact:false}).first().click();await expect(page.getByRole('heading',{name:'A little context goes a long way.'})).toBeVisible();
 await page.getByRole('button',{name:'Overview',exact:true}).click();await page.setViewportSize({width:390,height:844});await page.screenshot({path:'../../docs/mobile.png'});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
