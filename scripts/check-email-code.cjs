// Exercise the deployed service source with fake Google APIs; sends no mail.
const fs = require('node:fs'), vm = require('node:vm'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../services/email-code/Code.gs'), 'utf8');
let now=1_000_000, quota=100, available=true, mailFailure=false, adminFailure=false, lookupFailure=false, mail=[], updates=[], serial=0;
const properties = new Map(), users = new Map();
const token = (uid) => 'test-only-'.repeat(12)+uid;
const user = uid => { const value={localId:uid,email:uid+'@example.invalid',emailVerified:false}; users.set(token(uid),value); return value; };
const store = {getProperty:k=>properties.get(k)||null,setProperty:(k,v)=>properties.set(k,v),deleteProperty:k=>properties.delete(k),getProperties:()=>Object.fromEntries(properties)};
const context = vm.createContext({console:{log(){}}, Date:{now:()=>now},
 PropertiesService:{getScriptProperties:()=>store},
 LockService:{getScriptLock:()=>({tryLock:()=>available,waitLock(){assert(available)},releaseLock(){}})},
 ScriptApp:{getOAuthToken:()=> 'fake-owner-oauth-only'},
 Utilities:{getUuid:()=> 'fake-nonce-'+(++serial),Charset:{UTF_8:'utf8'},DigestAlgorithm:{SHA_256:'sha256'},
  computeDigest:(kind,s)=>Array.from(crypto.createHash(kind).update(s).digest()),
  computeHmacSha256Signature:(s,key)=>Array.from(crypto.createHmac('sha256',key).update(s).digest())},
 MailApp:{getRemainingDailyQuota:()=>quota,sendEmail:message=>{if(mailFailure)throw Error('upstream secret'); mail.push(message);quota--;}},
 ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({setMimeType:()=>JSON.parse(text)})},
 UrlFetchApp:{fetch:(url,opts)=>{
  const data=JSON.parse(opts.payload); let body={},status=200;
  if(url.includes('/projects/') && url.endsWith('accounts:lookup')) assert(opts.headers.Authorization==='Bearer fake-owner-oauth-only');
  else if(url.endsWith('/accounts:update')){
   assert(opts.headers.Authorization==='Bearer fake-owner-oauth-only');
   if(adminFailure){status=403;body={error:{message:'owner-token-must-not-leak'}};}
   else{const u=[...users.values()].find(u=>u.localId===data.localId); assert(u); assert.equal(data.email,u.email); assert.equal(data.emailVerified,true);u.emailVerified=true;updates.push(data);}
  } else if(lookupFailure){status=503;body={error:{message:'upstream-service-unavailable'}};}
  else {const u=users.get(data.idToken);if(!u){status=400;body={error:{message:'INVALID_ID_TOKEN'}};}else body={users:[u]};}
  return {getResponseCode:()=>status,getContentText:()=>JSON.stringify(body)};
 }}});
vm.runInContext(source,context);context.setup();
const post = (uid,action,code,extra={})=>context.doPost({postData:{contents:JSON.stringify({action,idToken:token(uid),code,...extra})}});
const getCode=()=>mail.at(-1).body.match(/\n\n(\d{6})\n/)[1];
user('one');assert.equal(post('one','send',undefined,{email:'victim@example.invalid',localId:'victim'}).ok,true);
assert.equal(mail[0].to,'one@example.invalid');const first=getCode();assert(!mail[0].body.includes('https://'));assert(!properties.get('otp:one').includes(first));
assert.equal(post('one','send').error,'CODE_RESEND_WAIT');
const wrong = first==='000000'?'111111':'000000';assert.equal(post('one','verify',wrong).error,'INVALID_CODE');assert.equal(updates.length,0);
now+=61_000;assert.equal(post('one','send').ok,true);assert.equal(JSON.parse(properties.get('otp:one')).failures,1);
assert.equal(post('one','verify',first).error,'INVALID_CODE');assert.equal(post('one','verify',getCode()).verified,true);assert.equal(updates.length,1);assert(!properties.has('otp:one'));
assert.equal(post('one','verify',first).verified,true);assert.equal(updates.length,1); // Verified user, no replayed mutation.
user('two');post('two','send');const code2=getCode();user('three');assert.equal(post('three','verify',code2).error,'CODE_EXPIRED');
for(let i=0;i<5;i++)post('two','verify',code2==='000000'?'111111':'000000');assert.equal(post('two','verify',code2).error,'CODE_ATTEMPTS_EXCEEDED');now+=61_000;assert.equal(post('two','send').error,'CODE_ATTEMPTS_EXCEEDED');
user('expired');post('expired','send');const expired=getCode();now+=600_001;assert.equal(post('expired','verify',expired).error,'CODE_EXPIRED');
user('changed');post('changed','send');const changed=getCode();users.get(token('changed')).email='changed-new@example.invalid';assert.equal(post('changed','verify',changed).error,'CODE_EXPIRED');
user('admin');post('admin','send');const admin=getCode();adminFailure=true;assert.equal(post('admin','verify',admin).error,'FIREBASE_ADMIN_PERMISSION_REQUIRED');assert(!users.get(token('admin')).emailVerified);adminFailure=false;assert.equal(post('admin','verify',admin).verified,true);
user('quota');quota=0;assert.equal(post('quota','send').error,'MAIL_QUOTA_EXCEEDED');assert(!properties.has('otp:quota'));quota=100;
user('fail');mailFailure=true;assert.equal(post('fail','send').error,'MAIL_SEND_FAILED');assert.equal(post('fail','verify','000000').error,'CODE_EXPIRED');mailFailure=false;
user('busy');available=false;assert.equal(post('busy','send').error,'SERVICE_BUSY');assert(!properties.has('otp:busy'));available=true;
assert.equal(post('unknown','send').error,'INVALID_ID_TOKEN');assert.equal(post('busy','verify','12345').error,'INVALID_CODE');
lookupFailure=true;const sentBeforeFailure=mail.length;
assert.equal(post('busy','send').error,'SERVICE_ERROR');assert.equal(mail.length,sentBeforeFailure);lookupFailure=false;
assert.equal(context.doPost({postData:{contents:'not json'}}).ok,false);
assert.equal(context.doPost({postData:{contents:'x'.repeat(8193)}}).error,'INVALID_REQUEST');
user('limit');for(let i=0;i<5;i++){assert.equal(post('limit','send').ok,true);now+=61_000;}assert.equal(post('limit','send').error,'CODE_SEND_LIMIT');
assert(updates.every(u=>u.localId==='one'||u.localId==='admin'));
console.log('Email code service PASS: token-bound recipients, six digits, HMAC storage, expiration, resend and guessing limits, cross-account denial, email changes, admin errors, quotas and locks. No real mail sent.');
