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
    const axe=await new AxeBuilder({page:a.page}).analyze();if(axe.violations.length) console.log('Accessibility failures',JSON.stringify(axe.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))));assert.deepEqual(axe.violations.map(v=>v.id),[]);
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
  if(process.argv.includes('--phase4-owner')) {
    await a.page.getByRole('link',{name:'Preferences',exact:true}).click();
    await a.page.getByRole('heading',{name:'Workspace preferences',exact:true}).waitFor();
    await a.page.getByLabel('Currency',{exact:true}).fill('EUR');
    await a.page.getByRole('button',{name:'Save preferences',exact:true}).click();
    await a.page.getByText('Preferences saved for future jobs.',{exact:true}).waitFor();
    await a.page.setViewportSize({width:375,height:1000});
    assert.deepEqual((await new AxeBuilder({page:a.page}).analyze()).violations.map(v=>v.id),[]);
    assert(await a.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await a.page.getByLabel('Currency',{exact:true}).fill('USD');
    await a.page.getByRole('button',{name:'Save preferences',exact:true}).click();
    await a.page.getByText('Preferences saved for future jobs.',{exact:true}).waitFor();
    await a.page.setViewportSize({width:1440,height:1000});
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
  await a.page.getByText('text.pdf',{exact:true}).first().waitFor();
  await a.page.getByRole('button',{name:'Inspect documents',exact:true}).click();
  await a.page.getByRole('button',{name:'Convert statements',exact:true}).waitFor();
  await a.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Convert statements'&&!b.disabled),null,{timeout:90000});
  await a.page.getByRole('button',{name:'Convert statements',exact:true}).click();
  await a.page.getByText('Statement s0001 · 2 rows',{exact:true}).waitFor({timeout:90000});
  await a.page.getByRole('region',{name:'Extracted transactions'}).locator('tbody tr').nth(1).waitFor();
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
  if(process.argv.includes('--phase4-owner')) {
    await a.page.getByText('Build a private layout scaffold',{exact:true}).click();
    await a.page.getByRole('button',{name:'Create private scaffold',exact:true}).click();
    const download=a.page.getByRole('link',{name:'Download private-profile-scaffold.json',exact:true});
    await download.waitFor({timeout:90000});
    const report=await a.context.request.get(origin+await download.getAttribute('href'));
    assert.equal(report.status(),200);assert((await report.json()).page_1_words.length>0);
    await a.page.getByText('Allow temporary support access',{exact:true}).click();
    await a.page.getByLabel('Why support is needed',{exact:true}).fill('Synthetic browser support permission test');
    await a.page.getByRole('button',{name:'Grant temporary access',exact:true}).click();
    await a.page.getByRole('button',{name:'Revoke support access',exact:true}).waitFor();
    await a.page.getByRole('button',{name:'Revoke support access',exact:true}).click();
    await a.page.getByText(/results · Revoked · Revision/).waitFor();
    console.log('PASS: real owner preferences, scoped parser-generated private scaffold/download and named expiring support grant/revoke.');
  }
  if(process.argv.includes('--phase4-ai')) {
    // This switch must run against scripts/saas-fake-ai-server.py. Its provider factory
    // has no public transport fallback. Production app settings expose no fake mode.
    async function aiWrite(path,body) {
      const session=await(await a.context.request.get(origin+'/api/v1/session')).json();
      const response=await a.context.request.post(origin+path,{headers:{'Origin':origin,'X-CSRF-Token':session.csrf_token,'Idempotency-Key':randomUUID()},data:body});
      assert(response.ok(),await response.text()); return response.json();
    }
    const provider=await aiWrite('/api/v1/connections',{name:'Fictional browser AI',base_url:'https://api.example.com/v1',requires_key:false});
    await aiWrite('/api/v1/connections/'+provider.id+'/models/manual',{expected_revision:1,model_id:'fictional-browser-ai'});
    await aiWrite('/api/v1/connections/'+provider.id+'/selection',{expected_revision:2,model_id:'fictional-browser-ai',effort:'highest'});
    await aiWrite('/api/v1/connections/'+provider.id+'/terms',{expected_revision:3,confirmed:true,terms_version:'https://example.com/terms/fictional'});
    await aiWrite('/api/v1/connections/'+provider.id+'/models',{expected_revision:4});
    const picked=await aiWrite('/api/v1/connections/'+provider.id+'/selection',{expected_revision:5,model_id:'fictional-browser-ai',effort:'highest'});assert.equal(picked.effort,'max');
    await a.page.reload();
    await a.page.getByRole('heading',{name:'Optional AI assistance',exact:true}).waitFor();
    await a.page.getByText('Set or renew job permission',{exact:true}).click();
    await a.page.getByLabel('AI provider for this job',{exact:true}).selectOption(provider.id);
    await a.page.getByLabel('Client permission note',{exact:true}).fill('Fictional client permits masked cells for this test.');
    await a.page.getByLabel('Names to mask',{exact:true}).fill('Fictional Client');
    await a.page.getByLabel('I have permission to send these minimized cells to this provider under suitable terms.',{exact:true}).check();
    await a.page.getByRole('button',{name:'Save job permission',exact:true}).click();
    await a.page.getByText('Current',{exact:true}).waitFor();
    await a.page.getByRole('group',{name:'Pages for this AI request (up to 5)',exact:true}).getByRole('checkbox').first().check();
    await a.page.getByRole('button',{name:'Request AI assistance',exact:true}).click();
    await a.page.getByText('Saved; full AI source review required',{exact:true}).waitFor({timeout:30000});
    const status=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/ai')).json();
    assert.equal(status.pages_used,1);assert.equal(status.requests_used,1);assert.equal(status.consent.valid,false);
    const currentRows=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/rows')).json();
    assert(currentRows.items.every(r=>r.engine==='ai'&&r.fixed_by==='ai'&&!r.source_reviewed));
    await a.page.setViewportSize({width:375,height:1000});
    const axe=await new AxeBuilder({page:a.page}).analyze();if(axe.violations.length) console.log('Accessibility failures',JSON.stringify(axe.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))));assert.deepEqual(axe.violations.map(v=>v.id),[]);
    assert(await a.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/ai-mobile.png',import.meta.url).pathname,fullPage:true});
    await a.page.setViewportSize({width:1440,height:1000});
    await a.page.screenshot({path:new URL('../.local-saas/screenshots/ai-desktop.png',import.meta.url).pathname,fullPage:true});
    console.log('PASS: real owner job consent → reserved fictional AI request → atomic untrusted row revision → full AI-source gate; mobile axe/layout; no public model traffic.');
  }
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
    assert.equal(await confirmations.count(),process.argv.includes('--phase4-ai') ? 4 : 2);
    for(const box of await confirmations.all())await box.check();
    for(let i=0;i<(process.argv.includes('--phase4-ai') ? 2 : 1);i++) {
      await a.page.getByRole('button',{name:'Confirm source check',exact:true}).first().click();
      await a.page.waitForFunction(expected=>[...document.querySelectorAll('button')].filter(b=>b.textContent==='Source check recorded').length===expected,i+1);
    }
    await a.page.getByRole('button',{name:'Generate downloads',exact:true}).waitFor();
    await a.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Generate downloads'&&!b.disabled));
    await a.page.getByRole('button',{name:'Generate downloads',exact:true}).click();
    await a.page.getByRole('link',{name:'Download s0001.ofx',exact:true}).waitFor({timeout:90000});
    const manifest=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/exports')).json();assert.equal(manifest.items.length,6);
    await a.page.getByRole('button',{name:'Prepare delivery ZIP',exact:true}).click();
    await a.page.getByRole('link',{name:'Download reviewed-outputs.zip',exact:true}).waitFor({timeout:90000});
    const axe=await new AxeBuilder({page:a.page}).analyze();if(axe.violations.length) console.log('Accessibility failures',JSON.stringify(axe.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))));assert.deepEqual(axe.violations.map(v=>v.id),[]);
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
  let delegatedGrant=null;
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
    if(caseName==='combined' && process.argv.includes('--phase4-owner')) {
      const operators=await(await a.context.request.get(origin+'/api/v1/support-operators')).json();
      const current=await(await a.context.request.get(origin+'/api/v1/jobs/'+next)).json();
      const granted=await a.context.request.post(origin+'/api/v1/jobs/'+next+'/support-grants',{headers:{...headers,'Idempotency-Key':randomUUID()},data:{expected_revision:current.revision,actor_id:operators.items[0].id,scopes:['results','source'],minutes:30,reason:'Synthetic assigned support UI test'}});
      assert.equal(granted.status(),201);delegatedGrant=await granted.json();
    }

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
  assert.equal(adminSession.platform_admin,true);
  const memberships=await(await admin.context.request.get(origin+'/api/v1/workspaces')).json();
  assert(memberships.items.every(w=>w.name==='Private synthetic diagnostics'));
  assert.equal((await admin.context.request.get(origin+'/api/v1/admin/health')).status(),200);
  assert.equal((await admin.context.request.get(origin+'/api/v1/jobs/'+id)).status(),404);
  if(process.argv.includes('--phase4-owner')) {
    await admin.page.getByRole('link',{name:'Service health',exact:true}).click();
    await admin.page.getByRole('heading',{name:'Live services',exact:true}).waitFor();
    await admin.page.getByText('Edit supported configuration (advanced)',{exact:true}).click();
    await admin.page.getByLabel('Reason for change',{exact:true}).fill('Synthetic browser unchanged draft verification');
    await admin.page.getByRole('button',{name:'Save configuration draft',exact:true}).click();
    await admin.page.getByText('Draft saved. Active configuration is unchanged.',{exact:true}).waitFor();

    assert(delegatedGrant);
    await admin.page.getByRole('button',{name:'Open approved transaction rows',exact:true}).click();
    await admin.page.getByRole('table',{name:'Owner-approved transaction rows',exact:true}).locator('tbody tr').nth(1).waitFor();
    await admin.page.getByRole('button',{name:'Show approved files',exact:true}).click();
    const sourceLink=admin.page.getByRole('link',{name:/Download (original|normalized|page) \d/}).first();
    await sourceLink.waitFor();assert.equal((await admin.context.request.get(origin+await sourceLink.getAttribute('href'))).status(),200);
    const returningOwner=await signIn('owner-a');
    const ownerSession=await(await returningOwner.context.request.get(origin+'/api/v1/session')).json();
    const revoked=await returningOwner.context.request.post(origin+'/api/v1/jobs/'+delegatedGrant.job_id+'/support-grants/'+delegatedGrant.id+'/revoke',{headers:{Origin:origin,'X-CSRF-Token':ownerSession.csrf_token,'Idempotency-Key':randomUUID()},data:{expected_revision:delegatedGrant.revision,expected_version:delegatedGrant.version}});
    assert.equal(revoked.status(),200);
    assert.equal((await admin.context.request.get(origin+'/api/v1/admin/support-grants/'+delegatedGrant.id+'/results')).status(),404);
    await admin.page.reload();
    await admin.page.getByText('No active grants. Administrator status does not give access to customer jobs.',{exact:true}).waitFor();
    await admin.page.getByRole('button',{name:'Run synthetic selftest',exact:true}).click();
    const report=admin.page.getByRole('link',{name:'Download synthetic-selftest.json',exact:true});
    await report.waitFor({timeout:90000});
    const raw=await admin.context.request.get(origin+await report.getAttribute('href'));assert.equal(raw.status(),200);
    const value=await raw.json();assert.equal(value.passed,true);assert.equal(value.results.length,9);
    const health=await(await admin.context.request.get(origin+'/api/v1/admin/health')).json();
    assert.equal(health.worker,'healthy');assert.equal(health.models,'verified');assert(health.models_verified_at);
    await admin.page.setViewportSize({width:375,height:1000});
    const axe=await new AxeBuilder({page:admin.page}).analyze();if(axe.violations.length)console.log('Admin accessibility',JSON.stringify(axe.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))));assert.deepEqual(axe.violations.map(v=>v.id),[]);
    assert(await admin.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await admin.page.screenshot({path:new URL('../.local-saas/screenshots/owner-admin-mobile.png',import.meta.url).pathname,fullPage:true});
    console.log('PASS: actual OTP admin, immutable configuration draft, real isolated 9-case selftest, worker/model heartbeat evidence, anonymous metrics and mobile axe/layout.');
  }
  console.log('PASS: real OIDC login/logout, opaque cookie, saved UI job, A/B isolation, mobile accessibility/layout and actual OTP admin with no customer membership.');
} catch (error) {
  console.log('Check failure:',error.name, String(error.stack).split('\n').filter(line=>/at .*saas-browser\.mjs:\d/.test(line)).join('\n'));
  for (const context of contexts) { const p=context.pages().at(-1); if(p) console.log('Diagnostic page',new URL(p.url()).pathname,await p.locator('input').evaluateAll(nodes=>nodes.map(n=>({id:n.id,name:n.name,type:n.type}))),await p.locator('button').allTextContents(), (await p.locator('#kc-page-title').count()) ? await p.locator('#kc-page-title').textContent() : ''); }
  throw new Error("Browser verification failed; inspect the sanitized page diagnostic and local service state.");
} finally {for(const c of contexts)await c.close();await browser.close();}
