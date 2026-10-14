import {test,expect} from '@playwright/test';

test('private account workspaces, Gmail setup status, logout and expired session handling',async({page})=>{
 test.setTimeout(90000);
 const health=await(await page.request.get('/api/health')).json();test.skip(!health.auth_required,'Uses the authenticated QA server');
 const suffix=Date.now().toString();const a=`alice-${suffix}@example.invalid`,b=`bob-${suffix}@example.invalid`,password='Synthetic account test 729!';
 expect((await page.request.get('/api/events')).status()).toBe(401);
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
 await page.screenshot({path:'../../docs/sign-in-desktop.png',fullPage:true});
 async function register(email:string){await page.getByRole('button',{name:'Create a local account'}).click();await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Create account',exact:true}).click();await expect(page.getByRole('heading',{name:'Your money, in focus.'})).toBeVisible()}
 await register(a);await page.getByRole('button',{name:'Connect & import',exact:true}).click();
 await expect(page.getByRole('region',{name:'Gmail connection'})).toContainText('Google setup required');
 await page.getByRole('button',{name:'Load synthetic demo'}).click();await expect(page.getByRole('status')).toContainText('Synthetic demo loaded');
 const records=await(await page.request.get('/api/events')).json();expect(records.length).toBeGreaterThan(0);
 await page.screenshot({path:'../../docs/gmail-setup-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
 expect((await page.request.get('/api/events')).status()).toBe(401);
 await register(b);expect(await(await page.request.get('/api/events')).json()).toEqual([]);
 const csrf=(await(await page.request.get('/api/auth/me')).json()).csrf_token;
 const attack=await page.request.patch('/api/events/'+records[0].id,{headers:{'X-CSRF-Token':csrf},data:{field:'merchant',value:'Bob cannot change Alice',reason:'Synthetic isolation check'}});expect(attack.status()).toBe(404);
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await page.getByLabel('Email address').fill(a);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Your money, in focus.'})).toBeVisible();
 expect((await(await page.request.get('/api/events')).json()).length).toBe(records.length);
 await page.route('**/api/events',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Your session has expired. Please sign in again.'})}));
 await page.reload();await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Your money, in focus.'})).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'../../docs/sign-in-mobile.png',fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect(errors).toEqual([]);
});
