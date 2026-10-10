// Real Keycloak auth-code/PKCE browser checks. Reads only ignored synthetic accounts.
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHmac, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const { AxeBuilder } = require('@axe-core/playwright');
const fixturePath = new URL('../.local-saas/bootstrap.json', import.meta.url);
const realmPath = new URL('../.local-saas/realm.json', import.meta.url);
const fixture = JSON.parse(await readFile(fixturePath, 'utf8'));
const origin = 'http://127.0.0.1:8000';
// Local privileged setup only provisions memberships; sign-in and switching still use real auth/CSRF.
const verification=JSON.parse(execFileSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),
  [fileURLToPath(new URL('./saas-local.py',import.meta.url)),'verification-workspace'],{encoding:'utf8'}));
function totp(secret) {
  // Keycloak's stored/enrollment value is raw UTF-8; its QR displays the base32 encoding.
  const bytes = Buffer.from(secret, 'utf8');
  const counter=Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));
  const hash=createHmac('sha1',bytes).update(counter).digest();
  const offset=hash[hash.length-1]&15;
  return ((hash.readUInt32BE(offset)&0x7fffffff)%1000000).toString().padStart(6,'0');
}
for(let attempt=0; attempt<60; attempt++) {
  try { if ((await fetch(origin+'/api/v1/version')).ok) break; } catch {}
  if(attempt===59) throw new Error('Local API did not start. Run the local setup/start recipe.');
  await new Promise(resolve=>setTimeout(resolve,500));
}
async function freshOtp(secret) {
  // Keycloak rejects reuse of a code, including one just used for enrollment.
  await new Promise(resolve=>setTimeout(resolve,30000-(Date.now()%30000)+250));
  return totp(secret);
}
const browser=await chromium.launch({headless:true});
const contexts=[];
async function signIn(username, viewport={width:1440,height:1000}) {
  const user=fixture.users.find(u=>u.username===username);
  const context=await browser.newContext({viewport});contexts.push(context);
  const page=await context.newPage();
  await page.goto(origin);
  await page.getByRole('link',{name:'Sign in securely'}).click();
  await page.locator('#username').fill(user.username);
  await page.locator('#password').fill(user.password);
  await page.locator('#kc-login').click();
  if (username==='operator') {
    // Only needed if a local operator must enroll. Capture its generated secret into ignored fixture.
    await page.locator('#totp, #otp').first().waitFor();
    if (await page.locator('#totp').count()) {
      fixture.otp_secret=await page.locator('#totpSecret').inputValue();
      await writeFile(fixturePath,JSON.stringify(fixture,null,2),{mode:0o600});
      const realm=JSON.parse(await readFile(realmPath,'utf8'));
      const operator=realm.users.find(u=>u.username==='operator');
      const otp=operator.credentials.find(c=>c.type==='otp');
      if(otp) otp.secretData=JSON.stringify({value:fixture.otp_secret});
      await writeFile(realmPath,JSON.stringify(realm,null,2),{mode:0o644});
      await page.locator('#totp').fill(await freshOtp(fixture.otp_secret));
      if (await page.locator('#userLabel').count()) await page.locator('#userLabel').fill('Synthetic test authenticator');
      await page.locator('form').getByRole('button', {name:/Submit|Save/}).first().click();
    } else {
      await page.locator('#otp').waitFor();
      await page.locator('#otp').fill(await freshOtp(fixture.otp_secret));
      await page.locator('#kc-login').click();
    }
  }
  await page.waitForURL(origin+'/app');
  await page.getByRole('button',{name:'Sign out'}).waitFor();
  if(username.endsWith('-a')) {
    const current=await (await context.request.get(origin+'/api/v1/session')).json();
    const switched=await context.request.post(origin+'/api/v1/session/workspace',{
      headers:{'Origin':origin,'X-CSRF-Token':current.csrf_token,'Idempotency-Key':randomUUID()},
      data:{workspace_id:verification.workspace_id},
    });
    assert.equal(switched.status(),200);
    assert.equal((await switched.json()).workspace_id,verification.workspace_id);
    await page.goto(origin+'/app');
    await page.getByRole('button',{name:'Sign out'}).waitFor();
  }
  return {page,context};
}
try {
  const a=await signIn('owner-a');
  const session=await a.context.request.get(origin+'/api/v1/session');assert.equal(session.status(),200);
  const s=await session.json();assert.equal(s.role,'owner');assert.equal(s.platform_admin,false);
  const cookies=await a.context.cookies();const cookie=cookies.find(c=>c.name==='dockling_session');assert(cookie.httpOnly);assert.equal(cookie.sameSite,'Lax');
  if(process.argv.includes('--phase4')) {
    await a.page.getByRole('link',{name:'AI connections',exact:true}).click();
    await a.page.getByRole('heading',{name:'AI connections',exact:true}).waitFor();
    await a.page.getByLabel('Connection name',{exact:true}).fill('Browser fictional provider');
    await a.page.getByLabel('OpenAI-compatible base URL',{exact:true}).fill('https://api.example.com/v1');
    await a.page.getByRole('button',{name:'Add connection',exact:true}).click();
    await a.page.getByRole('heading',{name:'Browser fictional provider',exact:true}).waitFor();
    await a.page.getByLabel('Your API key for Browser fictional provider',{exact:true}).fill('fake-browser-key-no-real-provider');
    await a.page.getByRole('button',{name:'Save API key',exact:true}).click();
    await a.page.getByText('Key saved securely',{exact:true}).waitFor();
    assert.equal(await a.page.getByLabel('Your API key for Browser fictional provider',{exact:true}).inputValue(),'');
    await a.page.getByLabel('Exact model ID',{exact:true}).fill('fictional-manual-model');
    await a.page.getByRole('button',{name:'Add model manually',exact:true}).click();
    await a.page.getByLabel('Model for Browser fictional provider',{exact:true}).selectOption('fictional-manual-model');
    const effort=a.page.getByLabel('Reasoning effort for Browser fictional provider',{exact:true});
    assert.deepEqual(await effort.locator('option').allTextContents(),['Highest supported','Provider default']);
    await a.page.getByRole('button',{name:'Save model choice',exact:true}).click();
    await a.page.getByText('fictional-manual-model · provider default',{exact:true}).waitFor();
    const list=await(await a.context.request.get(origin+'/api/v1/connections')).json();assert.equal(list.items.length,1);
    assert(!JSON.stringify(list).includes('fake-browser-key-no-real-provider'));
    await a.page.setViewportSize({width:375,height:1000});
    const axe=await new AxeBuilder({page:a.page}).analyze();assert.deepEqual(axe.violations.map(v=>v.id),[]);
    assert(await a.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await mkdir(new URL('../.local-saas/screenshots/',import.meta.url),{recursive:true});
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/connections-mobile.png',import.meta.url).pathname,fullPage:true});
    await a.page.setViewportSize({width:1440,height:1000});
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/connections-desktop.png',import.meta.url).pathname,fullPage:true});
    await a.page.getByText('Remove this connection',{exact:true}).click();
    await a.page.getByLabel('Revoke this connection and erase its saved key.',{exact:true}).check();
    await a.page.getByRole('button',{name:'Revoke connection',exact:true}).click();
    await a.page.getByText('Revoked',{exact:true}).waitFor();
    assert.equal((await(await a.context.request.get(origin+'/api/v1/connections')).json()).items[0].has_key,false);
    console.log('PASS: real owner connection → encrypted fictional key → manual model/provider-default picker → revoke/key erasure; no provider requests; mobile axe/layout.');
    await a.page.getByRole('link',{name:'Your jobs',exact:true}).click();
  }
  await a.page.getByRole('link',{name:'Create job'}).click();
  const name='Browser synthetic '+Date.now();
  await a.page.getByLabel('Job name').fill(name);
  await a.page.getByText('Conversion options',{exact:true}).click();
  await a.page.getByLabel('Date order',{exact:true}).selectOption('MDY');
  await a.page.getByLabel('Statement layout',{exact:true}).selectOption('generic');
  await a.page.getByRole('button',{name:'Save job'}).click();
  await a.page.getByRole('link',{name,exact:true}).waitFor();
  await a.page.getByRole('link',{name,exact:true}).click();
  await a.page.getByRole('heading',{name,exact:true}).waitFor();
  const id=a.page.url().split('/').at(-1);
  // Genuine files travel through authenticated storage and the restricted worker.
  const sample=new URL('../.local-saas/browser-fixtures/text.pdf',import.meta.url).pathname;
  await a.page.getByLabel('Choose statement files').setInputFiles(sample);
  await a.page.getByLabel('These are fictional test documents').check();
  await a.page.getByRole('button',{name:'Upload files',exact:true}).click();
  await a.page.getByText('text.pdf',{exact:true}).waitFor();
  await a.page.getByRole('button',{name:'Inspect documents',exact:true}).click();
  await a.page.getByRole('button',{name:'Convert statements',exact:true}).waitFor();
  await a.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Convert statements'&&!b.disabled),null,{timeout:90000});
  await a.page.getByRole('button',{name:'Convert statements',exact:true}).click();
  await a.page.getByText('Statement s0001 · 2 rows',{exact:true}).waitFor({timeout:90000});
  assert.equal(await a.page.getByRole('region',{name:'Extracted transactions'}).locator('tbody tr').count(),2);
  assert.equal((await (await a.context.request.get(origin+'/api/v1/jobs/'+id)).json()).source_checked,false);
  const inventory=await (await a.context.request.get(origin+'/api/v1/jobs/'+id+'/files')).json();
  const fileId=inventory.items[0].id;
  await a.page.getByRole('button',{name:'View source',exact:true}).click();
  await a.page.getByRole('img',{name:'Statement source page 1'}).waitFor();
  await a.page.waitForFunction(()=>document.querySelector('.pipeline-source')?.naturalWidth>0);
  await a.page.setViewportSize({width:375,height:1000});
  const resultAccessibility=await new AxeBuilder({page:a.page}).analyze();assert.deepEqual(resultAccessibility.violations.map(v=>v.id),[]);
  assert(await a.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await mkdir(new URL('../.local-saas/screenshots/',import.meta.url),{recursive:true});
  await a.page.screenshot({path:new URL('../.local-saas/screenshots/pipeline-mobile.png',import.meta.url).pathname,fullPage:true});
  await a.page.setViewportSize({width:1440,height:1000});
  await a.page.screenshot({path:new URL('../.local-saas/screenshots/pipeline-desktop.png',import.meta.url).pathname,fullPage:true});
  if (process.argv.includes('--phase3')) {
    await a.page.getByRole('button',{name:/Correct Synthetic purchase 000/}).click();
    await a.page.getByLabel('Description',{exact:true}).fill('Reviewed fictional purchase');
    await a.page.getByRole('button',{name:'Save correction',exact:true}).click();
    await a.page.getByText('Reviewed fictional purchase',{exact:true}).first().waitFor();
    await a.page.getByText('Account confirmation for OFX and merging',{exact:true}).click();
    await a.page.getByLabel('Your private account label').fill('Fictional browser account');
    await a.page.getByLabel('I checked that these statements belong to the same account.').check();
    const [accountSaved]=await Promise.all([a.page.waitForResponse(r=>r.url().endsWith('/account-group')&&r.status()===200),a.page.getByRole('button',{name:'Confirm account',exact:true}).click()]);
    const accountRevision=(await accountSaved.json()).revision;
    await a.page.waitForFunction(revision=>document.querySelector('[data-job-revision]')?.getAttribute('data-job-revision')===String(revision),accountRevision);
    await a.page.waitForFunction(()=>!document.querySelector('fieldset')?.matches(':disabled'));
    for(const label of ['Excel','CSV','QuickBooks (3 columns)','QuickBooks (4 columns)','Xero','OFX']) {console.log('Checking format:',label); await a.page.getByLabel(label,{exact:true}).check();}
    await a.page.getByLabel('Import date format',{exact:true}).selectOption('MM/DD/YYYY');
    const [optionsSaved]=await Promise.all([a.page.waitForResponse(r=>r.url().endsWith('/output-options')&&r.status()===200),a.page.getByRole('button',{name:'Save download options',exact:true}).click()]);
    const optionsRevision=(await optionsSaved.json()).revision;
    await a.page.waitForFunction(revision=>document.querySelector('[data-job-revision]')?.getAttribute('data-job-revision')===String(revision),optionsRevision);
    await a.page.waitForFunction(()=>!document.querySelector('fieldset')?.matches(':disabled'));
    const confirmations=a.page.getByLabel('I compared this row with the source.',{exact:true});
    assert.equal(await confirmations.count(),2);
    for(const box of await confirmations.all())await box.check();
    await a.page.getByRole('button',{name:'Confirm source check',exact:true}).click();
    await a.page.getByRole('button',{name:'Generate downloads',exact:true}).waitFor();
    await a.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Generate downloads'&&!b.disabled));
    await a.page.getByRole('button',{name:'Generate downloads',exact:true}).click();
    await a.page.getByRole('link',{name:'Download s0001.ofx',exact:true}).waitFor({timeout:90000});
    const manifest=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/exports')).json();assert.equal(manifest.items.length,6);
    await a.page.getByRole('button',{name:'Prepare delivery ZIP',exact:true}).click();
    await a.page.getByRole('link',{name:'Download reviewed-outputs.zip',exact:true}).waitFor({timeout:90000});
    const axe=await new AxeBuilder({page:a.page}).analyze();assert.deepEqual(axe.violations.map(v=>v.id),[]);
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/review-desktop.png',import.meta.url).pathname,fullPage:true});
    await a.page.setViewportSize({width:375,height:1000});
    assert(await a.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/review-mobile.png',import.meta.url).pathname,fullPage:true});
    await a.page.setViewportSize({width:1440,height:1000});
    console.log('PASS: browser correction → account confirmation → six current outputs → actual delivery ZIP; mobile layout and accessibility.');
  }
  const viewer=await signIn('viewer-a');await viewer.page.goto(origin+'/app/jobs/'+id);
  await viewer.page.getByText('Statement s0001 · 2 rows',{exact:true}).waitFor();
  assert.equal(await viewer.page.getByRole('button',{name:'Upload files',exact:true}).count(),0);
  assert.equal(await viewer.page.getByRole('button',{name:'Convert statements',exact:true}).count(),0);
  console.log('PASS: real PDF upload → isolated intake/conversion → two exact source-linked rows, private source PNG, viewer read-only and mobile accessibility/layout.');
  for (const [caseName, expectedRows] of [['different',6],['scan',2],['photo',2],['encrypted',2],['combined',2]]) {
    const headers={'Origin':origin,'X-CSRF-Token':s.csrf_token,'Idempotency-Key':randomUUID()};
    const created=await a.context.request.post(origin+'/api/v1/jobs',{headers,data:{name:'Browser '+caseName+' '+Date.now(),currency:'USD',date_order:'auto',outputs:['excel','csv'],combine:caseName==='combined'}});
    assert.equal(created.status(),201);const next=(await created.json()).id;
    const filename=caseName+(caseName==='photo'?'.png':'.pdf');
    const names=caseName==='combined'?['page-1.png','page-2-exif.jpg']:[filename];
    const sourceFiles=[];
    for(const [position, fileName] of names.entries()){
      const bytes=await readFile(new URL('../.local-saas/browser-fixtures/'+fileName,import.meta.url));
      const uploaded=await a.context.request.post(origin+'/api/v1/jobs/'+next+'/files',{headers:{...headers,'Idempotency-Key':randomUUID(),'Content-Type':'application/octet-stream','X-Expected-Revision':String(position+1),'X-File-Name':encodeURIComponent(fileName),'X-Synthetic-Confirmed':'true'},data:bytes});
      assert.equal(uploaded.status(),200);sourceFiles.push((await uploaded.json()).id);
    }
    await a.page.goto(origin+'/app/jobs/'+next);
    await a.page.getByRole('button',{name:'Inspect documents',exact:true}).click();
    if (caseName==='encrypted') {
      const password=a.page.getByLabel('PDF password for '+filename);await password.waitFor({timeout:90000});
      await password.fill('fictional-browser-password');
      await a.page.getByRole('button',{name:'Unlock and continue inspection',exact:true}).click();
    }
    await a.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Convert statements'&&!b.disabled),null,{timeout:90000});
    const [conversion]=await Promise.all([
      a.page.waitForResponse(response=>response.url()===origin+'/api/v1/jobs/'+next+'/operations' && response.request().method()==='POST'),
      a.page.getByRole('button',{name:'Convert statements',exact:true}).click(),
    ]);
    assert.equal(conversion.status(),202);
    await a.page.getByText('Statement s0001 · '+expectedRows+' rows',{exact:true}).waitFor({timeout:180000});
    const result=await (await a.context.request.get(origin+'/api/v1/jobs/'+next+'/rows')).json();
    assert.equal(result.items.length,expectedRows);
    assert(result.items.every(row=>sourceFiles.includes(row.file_id) && !row.source_reviewed));
    if(caseName==='combined')assert.deepEqual(result.items.map(row=>row.file_id),sourceFiles);
    assert.equal(result.items[0].credit,'20.00');assert.equal(result.items[1].debit,'2.00');
    for(const sourceFile of sourceFiles)assert.equal((await a.context.request.get(origin+'/api/v1/jobs/'+next+'/files/'+sourceFile+'/pages/1')).status(),200);
    console.log('PASS: '+caseName+' genuine input → '+expectedRows+' rows with exact amounts and source provenance.');
  }
  const b=await signIn('owner-b',{width:375,height:900});
  const forbidden=await b.context.request.get(origin+'/api/v1/jobs/'+id);assert.equal(forbidden.status(),404);
  assert.equal((await b.context.request.get(origin+'/api/v1/jobs/'+id+'/files/'+fileId+'/download')).status(),404);
  assert.equal((await b.context.request.get(origin+'/api/v1/jobs/'+id+'/files/'+fileId+'/pages/1')).status(),404);
  await b.page.goto(origin+'/app/jobs');await b.page.getByRole('heading',{name:'Your jobs'}).waitFor();
  assert.equal(await b.page.getByRole('link',{name,exact:true}).count(),0);
  const accessibility=await new AxeBuilder({page:b.page}).analyze();assert.deepEqual(accessibility.violations.map(v=>v.id),[]);
  assert(await b.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await mkdir(new URL('../.local-saas/screenshots/',import.meta.url),{recursive:true});
  await b.page.screenshot({path:new URL('../.local-saas/screenshots/jobs-mobile.png',import.meta.url).pathname,fullPage:true});
  await a.page.goto(origin+'/app/jobs');await a.page.getByRole('heading',{name:'Your jobs'}).waitFor();
  await a.page.screenshot({path:new URL('../.local-saas/screenshots/jobs-desktop.png',import.meta.url).pathname,fullPage:true});
  if(process.argv.includes('--phase3')) {
    await a.page.goto(origin+'/app/jobs/'+id);
    await a.page.getByLabel('I confirm permanent live data removal.').check();
    await a.page.getByRole('button',{name:'Remove live data',exact:true}).click();
    await a.page.getByText('Live removal verified',{exact:true}).waitFor({timeout:90000});
    const privacy=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/privacy')).json();
    assert.equal(privacy.deletion_state,'removed');assert.equal(privacy.certificate.worker_scratch_verified,true);
    assert.equal((await a.context.request.get(origin+'/api/v1/jobs/'+id+'/rows')).status(),404);
    console.log('PASS: real restricted worker removal, live certificate and blocked source/result access.');
  }
  await a.page.getByRole('button',{name:'Sign out'}).click();await a.page.getByRole('link',{name:'Sign in securely'}).waitFor();
  assert.equal((await a.context.request.get(origin+'/api/v1/session')).status(),401);
  let admin=await signIn('operator');
  let adminSession=await (await admin.context.request.get(origin+'/api/v1/session')).json();
  if (!adminSession.platform_admin) {
    // Enrollment itself is not an OTP authentication execution. Require another full sign-in.
    await admin.page.getByRole('button',{name:'Sign out'}).click();
    admin=await signIn('operator');adminSession=await (await admin.context.request.get(origin+'/api/v1/session')).json();
  }
  assert.equal(adminSession.platform_admin,true);assert.equal(adminSession.workspace_id,null);
  assert.equal((await admin.context.request.get(origin+'/api/v1/admin/health')).status(),200);
  assert.equal((await admin.context.request.get(origin+'/api/v1/jobs/'+id)).status(),404);
  console.log('PASS: real OIDC login/logout, opaque cookie, saved UI job, A/B isolation, mobile accessibility/layout and actual OTP admin with no customer membership.');
} catch (error) {
  console.log('Check failure:',error.name, String(error.stack).split('\n').filter(line=>/at .*saas-browser\.mjs:\d/.test(line)).join('\n'));
  for (const context of contexts) { const p=context.pages().at(-1); if(p) console.log('Diagnostic page',new URL(p.url()).pathname,await p.locator('input').evaluateAll(nodes=>nodes.map(n=>({id:n.id,name:n.name,type:n.type}))),await p.locator('button').allTextContents(), (await p.locator('#kc-page-title').count()) ? await p.locator('#kc-page-title').textContent() : ''); }
  throw new Error("Browser verification failed; inspect the sanitized page diagnostic and local service state.");
} finally {for(const c of contexts)await c.close();await browser.close();}
