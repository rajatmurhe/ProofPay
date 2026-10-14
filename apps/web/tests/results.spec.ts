import {test,expect} from '@playwright/test';

test('quality results, repaired parsing, import feedback, error recovery and deletion',async({page,request})=>{
 test.setTimeout(90000);
 expect((await (await request.get('/api/health')).json()).single_user).toBe(true);
 await request.delete('/api/data');
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await page.getByRole('button',{name:'View quality check results'}).click();
 const report=page.getByRole('region',{name:'Quality check results'});
 await expect(report.getByRole('heading',{name:'How the message checks performed'})).toBeVisible();
 await expect(report).toContainText('50 made-up messages');
 await expect(report).not.toContainText('"macro_f1"');
 await report.getByText('More about these checks').click();
 await expect(report).toContainText('have not been verified');
 await page.getByLabel('Message content').fill('Card statement: total due INR 2400. minimum due INR 120. due by 2026-12-04');
 await page.getByRole('button',{name:'Analyse message'}).click();
 await expect(page.getByRole('region',{name:'Latest import results'})).toContainText('1 financial message was saved');
 await page.getByRole('button',{name:'Bills & refunds',exact:true}).click();
 await expect(page.locator('.bill-row')).toContainText('₹2,400');
 await expect(page.locator('.bill-row')).toContainText('₹120');
 await expect(page.locator('.bill-row')).toContainText('4 Dec');
 await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await page.getByLabel('Import files').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{private-invalid')});
 await expect(page.locator('main').getByRole('alert')).toBeVisible();
 await expect(page.locator('main').getByRole('alert')).not.toContainText('private-invalid');
 await page.getByLabel('Message content').fill('UPI payment of INR 82.50 declined on 2026-10-05.');
 await page.getByRole('button',{name:'Analyse message'}).click();
 await expect(page.getByRole('status')).toContainText('Message processed');
 await expect(page.locator('main').getByRole('alert')).toHaveCount(0);
 await page.getByRole('button',{name:'View financial activity',exact:true}).click();
 await expect(page.locator('tbody')).toContainText('₹82.50');await expect(page.locator('tbody')).toContainText('failed');
 await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await page.getByLabel('Message content').fill('OTP 923781 for payment INR 82.50');
 await page.getByRole('button',{name:'Analyse message'}).click();
 const outcome=page.getByRole('region',{name:'Latest import results'});
 await expect(outcome).toContainText('No new financial records were saved');
 await expect(outcome).toContainText('Security codes skipped');
 expect(await (await request.get('/api/export')).text()).not.toContain('923781');
 await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:'../../docs/import-results-desktop.png',fullPage:true});
 for(const view of ['Overview','Financial activity','Bills & refunds','Needs attention','Connect & import']){
  await page.getByRole('button',{name:view,exact:true}).click();await page.setViewportSize({width:360,height:800});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),view+' overflow').toBe(true);
 }
 await page.screenshot({path:'../../docs/import-results-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Delete my financial data'}).click();
 await page.getByRole('button',{name:'Confirm deletion'}).click();
 await expect(page.getByRole('status')).toContainText('Your financial data was deleted');
 expect(await (await request.get('/api/events')).json()).toEqual([]);
 expect(await (await request.get('/api/jobs')).json()).toEqual([]);
 expect(errors).toEqual([]);
});

test('refund review, accept, undo and propose from the refund record',async({page,request})=>{
 test.setTimeout(90000);
 expect((await (await request.get('/api/health')).json()).single_user).toBe(true);
 await request.delete('/api/data');
 await request.post('/api/imports',{data:{messages:[
  {body:'Paid INR 900 at Cafe on 2026-10-01 txn ref QA-BUY'},
  {body:'Refund INR 200 credited at Cafe on 2026-10-02 refund ref QA-REF'},
 ]}});
 await page.goto('/');await page.getByRole('button',{name:'Financial activity',exact:true}).click();
 await page.locator('.record-name').filter({hasText:'Refund'}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByRole('button',{name:'Accept link'}).click();
 await expect(dialog.getByRole('button',{name:'Undo link'})).toBeVisible();
 let records=await(await request.get('/api/events')).json();expect(records.find((e:any)=>e.subtype==='purchase').net_minor).toBe(70000);
 await dialog.getByRole('button',{name:'Undo link'}).click();
 await expect(dialog).toContainText('undone');
 records=await(await request.get('/api/events')).json();expect(records.find((e:any)=>e.subtype==='purchase').net_minor).toBe(90000);
 await dialog.getByText('Propose a relationship',{exact:true}).click();
 const target=records.find((e:any)=>e.subtype==='purchase');
 await dialog.getByLabel('Related record',{exact:true}).selectOption(target.id);
 await dialog.getByRole('button',{name:'Propose link',exact:true}).click();
 await expect(dialog.getByRole('button',{name:'Accept link'})).toBeVisible();
 await dialog.getByRole('button',{name:'Reject',exact:true}).click();await expect(dialog).toContainText('rejected');
 await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 await expect(page.getByRole('button',{name:/Purchase spending/})).toContainText('₹900');
 const colour=await page.getByRole('button',{name:'Import messages',exact:true}).evaluate(el=>getComputedStyle(el).backgroundColor);
 expect(colour).toBe('rgb(9, 100, 175)');
});

test('JSON and CSV uploads, currency, source, date and search filters, and exports',async({page,request})=>{
 test.setTimeout(90000);
 expect((await (await request.get('/api/health')).json()).single_user).toBe(true);
 await request.delete('/api/data');await page.goto('/');
 await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await page.getByLabel('Import files').setInputFiles([
  {name:'messages.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify([{body:'Paid INR 200 at Metro on 2026-10-01 txn ref QA-METRO',source:'sms'},{body:'Paid USD 12 at Cafe on 2026-10-03',source:'paste'}]))},
  {name:'messages.csv',mimeType:'text/csv',buffer:Buffer.from('body,source,source_id\n"Paid INR 300 at Cafe on 2026-10-02",sms,qa-csv\n')},
 ]);
 await expect(page.getByRole('region',{name:'Latest import results'})).toContainText('3 financial messages were saved');
 await page.getByRole('button',{name:'Financial activity',exact:true}).click();
 await expect(page.locator('tbody tr')).toHaveCount(2);
 await page.getByLabel('Currency',{exact:true}).selectOption('USD');await expect(page.locator('tbody tr')).toHaveCount(1);await expect(page.locator('tbody')).toContainText('$12');
 await page.getByLabel('Currency',{exact:true}).selectOption('INR');
 await page.getByLabel('Source',{exact:true}).selectOption('email');await expect(page.getByRole('heading',{name:'No records here yet'})).toBeVisible();
 await page.getByLabel('Source',{exact:true}).selectOption('all');
 await page.getByLabel('Search financial activity').fill('Metro');await expect(page.locator('tbody tr')).toHaveCount(1);await expect(page.locator('tbody')).toContainText('₹200');
 await page.getByLabel('Search financial activity').fill('');
 await page.getByText('All dates',{exact:true}).click();await page.getByLabel('From',{exact:true}).fill('2026-10-02');await page.getByLabel('To',{exact:true}).fill('2026-10-02');
 await expect(page.locator('tbody tr')).toHaveCount(1);await expect(page.locator('tbody')).toContainText('₹300');await page.getByRole('button',{name:'Clear dates'}).click();await page.getByText('All dates',{exact:true}).click();
 await expect(page.locator('tbody tr')).toHaveCount(2);
 const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('link',{name:'CSV',exact:true}).click()]);
 expect(download.suggestedFilename()).toBe('proofpay-activity.csv');
 const exported=await(await request.get('/api/export?format=json')).json();expect(exported).toHaveLength(3);
 await page.getByRole('button',{name:'Overview',exact:true}).click();await expect(page.getByRole('button',{name:/Purchase spending/})).toContainText('₹500');
 await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:'../../docs/filters-desktop.png',fullPage:true});
});
