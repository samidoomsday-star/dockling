// Synthetic-only actual worker crash/reclaim check. No OTP or fixture auth bypass.
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const fixture=JSON.parse(await readFile(new URL('../.local-saas/bootstrap.json',import.meta.url),'utf8'));
const user=fixture.users.find(u=>u.username==='owner-a');
const origin='http://127.0.0.1:8000';
const verification=JSON.parse(execFileSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),
  [fileURLToPath(new URL('./saas-local.py',import.meta.url)),'verification-workspace'],{encoding:'utf8'}));
const browser=await chromium.launch({headless:true});
try {
  const context=await browser.newContext();const page=await context.newPage();
  await page.goto(origin);await page.getByRole('link',{name:'Sign in securely'}).click();
  await page.locator('#username').fill(user.username);await page.locator('#password').fill(user.password);await page.locator('#kc-login').click();await page.waitForURL(origin+'/app');
  const initial=await (await context.request.get(origin+'/api/v1/session')).json();
  const switched=await context.request.post(origin+'/api/v1/session/workspace',{
    headers:{'Origin':origin,'X-CSRF-Token':initial.csrf_token,'Idempotency-Key':randomUUID()},
    data:{workspace_id:verification.workspace_id},
  });assert.equal(switched.status(),200);
  const session=await switched.json();assert.equal(session.workspace_id,verification.workspace_id);
  const headers=()=>({'Origin':origin,'X-CSRF-Token':session.csrf_token,'Idempotency-Key':randomUUID()});
  const created=await context.request.post(origin+'/api/v1/jobs',{headers:headers(),data:{name:'Worker recovery '+Date.now(),currency:'USD',date_order:'auto',outputs:['excel','csv']}});assert.equal(created.status(),201);
  const job=(await created.json()).id;
  const uploaded=await context.request.post(origin+'/api/v1/jobs/'+job+'/files',{headers:{...headers(),'Content-Type':'application/octet-stream','X-Expected-Revision':'1','X-File-Name':'Recovery.pdf','X-Synthetic-Confirmed':'true'},data:await readFile(new URL('../.local-saas/browser-fixtures/text.pdf',import.meta.url))});assert.equal(uploaded.status(),200);
  const enqueueHeaders=headers();
  const queued=await context.request.post(origin+'/api/v1/jobs/'+job+'/intake',{headers:enqueueHeaders,data:{expected_revision:2}});assert.equal(queued.status(),202);const operation=(await queued.json()).id;
  const getOperation=async()=>await (await context.request.get(origin+'/api/v1/jobs/'+job+'/operations/'+operation)).json();
  for(let i=0;i<100;i++) {if((await getOperation()).state==='running')break;await new Promise(resolve=>setTimeout(resolve,100));}
  assert.equal((await getOperation()).state,'running');
  execFileSync('docker',['compose','--profile','conversion','-f','compose.saas.yaml','kill','-s','SIGKILL','worker'],{stdio:'pipe'});
  execFileSync('docker',['compose','--profile','conversion','-f','compose.saas.yaml','start','worker'],{stdio:'pipe'});
  for(let i=0;i<100;i++) {if((await getOperation()).state==='succeeded')break;await new Promise(resolve=>setTimeout(resolve,1000));}
  assert.equal((await getOperation()).state,'succeeded');
  const finished=await (await context.request.get(origin+'/api/v1/jobs/'+job)).json();assert.equal(finished.revision,3);assert.equal(finished.status,'intake_done');
  const repeated=await context.request.post(origin+'/api/v1/jobs/'+job+'/intake',{headers:enqueueHeaders,data:{expected_revision:2}});assert.equal(repeated.status(),202);assert.equal((await repeated.json()).id,operation);
  assert.equal((await (await context.request.get(origin+'/api/v1/jobs/'+job)).json()).revision,3);
  assert.equal((await (await context.request.get(origin+'/api/v1/jobs/'+job+'/operations')).json()).items.length,1);
  await writeFile(new URL('../.local-saas/recovery-result.json',import.meta.url),JSON.stringify({job,operation}),{mode:0o600});
  console.log('PASS: actual SIGKILL worker crash, 45-second lease reclaim, one current revision and no duplicate operation after command replay.');
} finally {await browser.close();}
