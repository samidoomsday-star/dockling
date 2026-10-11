// Real HTTPS UI acceptance. Only the name-constrained fictional rehearsal CA is trusted.
import {createRequire} from 'node:module';
import {readFile, mkdir, mkdtemp, access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const {AxeBuilder}=require('@axe-core/playwright');
const root=fileURLToPath(new URL('../',import.meta.url));
const privateDir=root+'.staging-saas/rehearsal/';
const origin='https://localhost:8443';
assert.equal(process.env.NODE_EXTRA_CA_CERTS,privateDir+'tls/ca.pem','Start Node with the rehearsal CA for its separate request client.');
let legacy=false;
try {await access(process.env.HOME+'/.pki/nssdb');legacy=true;} catch {}
assert.equal(legacy,false,'A legacy global NSS store needs separate operator review.');
await mkdir(privateDir+'browser-trust',{recursive:true,mode:0o700});
const trust=await mkdtemp(privateDir+'browser-trust/run-');
const db=trust+'/pki/nssdb';await mkdir(db,{recursive:true,mode:0o700});
execFileSync('certutil',['-N','-d','sql:'+db,'--empty-password']);
execFileSync('certutil',['-A','-d','sql:'+db,'-t','C,,','-n','Dockling synthetic loopback CA','-i',privateDir+'tls/ca.pem']);
const emptyTrust=await mkdtemp(privateDir+'browser-trust/untrusted-');
async function browserEnvironment(directory) {
  // Unknown container UIDs have no usable home. Keep Chromium's crash/cache
  // scratch private and writable without changing HOME or certificate trust.
  await mkdir(directory+'/config',{recursive:true,mode:0o700});
  await mkdir(directory+'/cache',{recursive:true,mode:0o700});
  return {...process.env,XDG_DATA_HOME:directory,XDG_CONFIG_HOME:directory+'/config',XDG_CACHE_HOME:directory+'/cache'};
}
const untrusted=await chromium.launch({headless:true,channel:'chromium',env:await browserEnvironment(emptyTrust)});
try {await assert.rejects(async()=>{const page=await untrusted.newPage();await page.goto(origin);},/ERR_CERT_AUTHORITY_INVALID/);} finally {await untrusted.close();}
const browser=await chromium.launch({headless:true,channel:'chromium',env:await browserEnvironment(trust)});
assert(Number(browser.version().split('.')[0])>=146);
const fixture=JSON.parse(await readFile(privateDir+'bootstrap.json','utf8'));
const provisioned=process.argv.includes('--provisioned-workspaces');
const workspaces=JSON.parse(provisioned
  ? await readFile(privateDir+'browser-workspaces.json','utf8')
  : execFileSync(root+'.venv/bin/python',[root+'scripts/saas-rehearsal.py','verification-workspaces'],{encoding:'utf8'}));
assert(Array.isArray(workspaces)&&workspaces.length===2);
async function login(name,workspace) {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();assert.equal((await page.goto(origin)).status(),200);
  await page.getByRole('link',{name:'Sign in securely'}).click();
  const user=fixture.users.find(u=>u.username===name);
  await page.locator('#username').fill(name);await page.locator('#password').fill(user.password);
  await page.locator('#kc-login').click();await page.waitForURL(origin+'/app');
  const s=await(await context.request.get(origin+'/api/v1/session')).json();
  const changed=await context.request.post(origin+'/api/v1/session/workspace',{headers:{Origin:origin,'X-CSRF-Token':s.csrf_token,'Idempotency-Key':randomUUID()},data:{workspace_id:workspace}});
  assert.equal(changed.status(),200);await page.goto(origin+'/app');
  const cookie=(await context.cookies()).find(c=>c.name==='dockling_session');
  assert(cookie.secure&&cookie.httpOnly&&cookie.sameSite==='Lax');return {page,context};
}
try {
  const probe=await browser.newPage();
  await assert.rejects(()=>probe.goto('https://127.0.0.1:8443'),/ERR_CERT_COMMON_NAME_INVALID/);await probe.close();
  const a=await login('owner-a',workspaces[0]);const p=a.page;
  await p.getByRole('link',{name:'Create job'}).click();const name='Fictional HTTPS UI '+Date.now();
  await p.getByLabel('Job name').fill(name);await p.getByText('Conversion options',{exact:true}).click();
  await p.getByLabel('Date order',{exact:true}).selectOption('MDY');await p.getByLabel('Statement layout',{exact:true}).selectOption('generic');
  await p.getByRole('button',{name:'Save job'}).click();await p.getByRole('link',{name,exact:true}).click();
  await p.getByRole('heading',{name,exact:true}).waitFor();const id=p.url().split('/').at(-1);
  await p.getByLabel('Choose statement files').setInputFiles(root+'.local-saas/browser-fixtures/text.pdf');
  await p.getByLabel('These are fictional test documents').check();await p.getByRole('button',{name:'Upload files',exact:true}).click();
  await p.getByText('text.pdf',{exact:true}).first().waitFor();await p.getByRole('button',{name:'Inspect documents',exact:true}).click();
  await p.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Convert statements'&&!b.disabled),null,{timeout:90000});
  await p.getByRole('button',{name:'Convert statements',exact:true}).click();await p.getByText('Statement s0001 · 2 rows',{exact:true}).waitFor({timeout:90000});
  await p.getByText(/AI requests are paused/).waitFor();
  await p.getByRole('button',{name:'View source',exact:true}).click();await p.getByRole('img',{name:'Statement source page 1'}).waitFor();
  await p.waitForFunction(()=>document.querySelector('.pipeline-source')?.naturalWidth>0);
  await p.getByText('Account confirmation for OFX and merging',{exact:true}).click();await p.getByLabel('Your private account label').fill('Fictional HTTPS account');
  await p.getByLabel('I checked that these statements belong to the same account.').check();
  async function save(button,suffix) {
    const [response]=await Promise.all([p.waitForResponse(r=>r.url().endsWith(suffix)&&r.status()===200),p.getByRole('button',{name:button,exact:true}).click()]);
    const revision=(await response.json()).revision;
    await p.waitForFunction(r=>document.querySelector('[data-job-revision]')?.getAttribute('data-job-revision')===String(r),revision);
    await p.waitForFunction(()=>!document.querySelector('fieldset')?.matches(':disabled'));
  }
  await save('Confirm account','/account-group');
  for(const label of ['Excel','CSV','QuickBooks (3 columns)','QuickBooks (4 columns)','Xero','OFX'])await p.getByLabel(label,{exact:true}).check();
  await p.getByLabel('Import date format',{exact:true}).selectOption('MM/DD/YYYY');await save('Save download options','/output-options');
  const boxes=p.getByLabel('I compared this row with the source.',{exact:true});await expect(boxes).toHaveCount(2);
  for(const box of await boxes.all())await box.check();await p.getByRole('button',{name:'Confirm source check',exact:true}).click();
  await p.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Generate downloads'&&!b.disabled));
  await p.getByRole('button',{name:'Generate downloads',exact:true}).click();await p.getByRole('link',{name:'Download s0001.ofx',exact:true}).waitFor({timeout:90000});
  const exports=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/exports')).json();assert.equal(exports.items.length,6);
  await p.getByRole('button',{name:'Prepare delivery ZIP',exact:true}).click();const link=p.getByRole('link',{name:'Download reviewed-outputs.zip',exact:true});await link.waitFor({timeout:90000});
  assert.equal((await a.context.request.get(origin+await link.getAttribute('href'))).status(),200);
  const b=await login('owner-b',workspaces[1]);assert.equal((await b.context.request.get(origin+'/api/v1/jobs/'+id)).status(),404);
  await p.setViewportSize({width:375,height:1000});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  assert.deepEqual((await new AxeBuilder({page:p}).analyze()).violations.map(v=>v.id),[]);
  await p.screenshot({path:privateDir+'https-ui-mobile.png',fullPage:true});await p.setViewportSize({width:1440,height:1000});
  await p.screenshot({path:privateDir+'https-ui-desktop.png',fullPage:true});
  const current=await(await a.context.request.get(origin+'/api/v1/jobs/'+id)).json();
  const session=await(await a.context.request.get(origin+'/api/v1/session')).json();
  const closed=await a.context.request.post(origin+'/api/v1/jobs/'+id+'/close',{headers:{Origin:origin,'X-CSRF-Token':session.csrf_token,'Idempotency-Key':randomUUID()},data:{expected_revision:current.revision,confirm_removal:true}});
  assert.equal(closed.status(),202);
  await expect.poll(async()=>{const privacy=await(await a.context.request.get(origin+'/api/v1/jobs/'+id+'/privacy')).json();return privacy.deletion_state==='removed'&&Boolean(privacy.certificate);},{timeout:120000}).toBe(true);
  console.log('PASS: verified HTTPS (untrusted CA/wrong hostname rejected), real OIDC, Secure cookie, paused AI, source review, six exports, ZIP, tenant privacy, verified removal, mobile axe and layout. Fictional fixtures only.');
} finally {await browser.close();}
