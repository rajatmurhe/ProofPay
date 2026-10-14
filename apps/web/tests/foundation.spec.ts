import {test,expect} from '@playwright/test';
test('golden journey, evidence, correction, refund progress and idempotency',async({page,request})=>{
 test.setTimeout(90000);
 const h=await request.get('/api/health');expect((await h.json()).single_user).toBe(true);
 await request.delete('/api/data');await page.goto('/');await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await page.getByText('Step through the ₹1,499').click();
 await page.getByRole('button',{name:'1. Purchase + email'}).click();await expect(page.getByRole('status')).toContainText('purchase');
 await page.getByRole('button',{name:'2. Refund initiated'}).click();await expect(page.getByRole('status')).toContainText('initiated');
 let events=await (await request.get('/api/events')).json();expect(events.find((e:any)=>e.subtype==='purchase').net_minor).toBe(149900);
 await page.getByRole('button',{name:'3. Refund received'}).click();await expect(page.getByRole('status')).toContainText('received');
 await page.getByRole('button',{name:'Financial activity',exact:true}).click();await page.getByRole('button',{name:/Amazon Shopping/}).click();
 await expect(page.getByRole('dialog')).toContainText('Net purchase ₹1,000');await expect(page.getByRole('dialog')).toContainText('2 sources');
 await page.getByLabel('Corrected value').fill('Amazon corrected');await page.getByLabel('Reason',{exact:true}).fill('Synthetic test correction');await page.getByRole('button',{name:'Save correction'}).click();
 await expect(page.getByRole('heading',{name:'Amazon corrected',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Close record'}).click();
 await request.post('/api/demo?stage=purchase');events=await(await request.get('/api/events')).json();expect(events.filter((e:any)=>e.subtype==='purchase')).toHaveLength(1);
});
