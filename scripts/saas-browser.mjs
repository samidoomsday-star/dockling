// Real Keycloak auth-code/PKCE browser checks. Reads only ignored synthetic accounts.
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHmac } from 'node:crypto';
import assert from 'node:assert/strict';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const { AxeBuilder } = require('@axe-core/playwright');
const fixturePath = new URL('../.local-saas/bootstrap.json', import.meta.url);
const realmPath = new URL('../.local-saas/realm.json', import.meta.url);
const fixture = JSON.parse(await readFile(fixturePath, 'utf8'));
const origin = 'http://127.0.0.1:8000';
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
  return {page,context};
}
try {
  const a=await signIn('owner-a');
  const session=await a.context.request.get(origin+'/api/v1/session');assert.equal(session.status(),200);
  const s=await session.json();assert.equal(s.role,'owner');assert.equal(s.platform_admin,false);
  const cookies=await a.context.cookies();const cookie=cookies.find(c=>c.name==='dockling_session');assert(cookie.httpOnly);assert.equal(cookie.sameSite,'Lax');
  await a.page.getByRole('link',{name:'Create job'}).click();
  const name='Browser synthetic '+Date.now();
  await a.page.getByLabel('Job name').fill(name);await a.page.getByRole('button',{name:'Save job'}).click();
  await a.page.getByRole('link',{name,exact:true}).waitFor();
  await a.page.getByRole('link',{name,exact:true}).click();
  await a.page.getByRole('heading',{name,exact:true}).waitFor();
  const id=a.page.url().split('/').at(-1);
  const b=await signIn('owner-b',{width:375,height:900});
  const forbidden=await b.context.request.get(origin+'/api/v1/jobs/'+id);assert.equal(forbidden.status(),404);
  await b.page.goto(origin+'/app/jobs');await b.page.getByRole('heading',{name:'Your jobs'}).waitFor();
  assert.equal(await b.page.getByRole('link',{name,exact:true}).count(),0);
  const accessibility=await new AxeBuilder({page:b.page}).analyze();assert.deepEqual(accessibility.violations.map(v=>v.id),[]);
  assert(await b.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await mkdir(new URL('../.local-saas/screenshots/',import.meta.url),{recursive:true});
  await b.page.screenshot({path:new URL('../.local-saas/screenshots/jobs-mobile.png',import.meta.url).pathname,fullPage:true});
  await a.page.goto(origin+'/app/jobs');await a.page.getByRole('heading',{name:'Your jobs'}).waitFor();
  await a.page.screenshot({path:new URL('../.local-saas/screenshots/jobs-desktop.png',import.meta.url).pathname,fullPage:true});
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
} catch {
  for (const context of contexts) { const p=context.pages().at(-1); if(p) console.log('Diagnostic page',new URL(p.url()).pathname,await p.locator('input').evaluateAll(nodes=>nodes.map(n=>({id:n.id,name:n.name,type:n.type}))),await p.locator('button').allTextContents(), (await p.locator('#kc-page-title').count()) ? await p.locator('#kc-page-title').textContent() : ''); }
  throw new Error("Browser verification failed; inspect the sanitized page diagnostic and local service state.");
} finally {for(const c of contexts)await c.close();await browser.close();}
