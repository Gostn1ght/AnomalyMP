  // Deploy as a Google Apps Script web app: execute as owner, access Anyone.
  // Configure this script's GCP project as lostzoneapi (925113269298).
  // No client-supplied email, UID, sender or admin token is accepted.
  const PROJECT = 'lostzoneapi';
  const API_KEY = 'AIzaSyCvZlBceoWHVcGk-cYRYIlHA_dRqXJplkA';
  const TTL = 10 * 60 * 1000;
  const RESEND_DELAY = 60 * 1000;
  const MAX_ATTEMPTS = 5;
  const MAX_PER_HOUR = 5;

  function setup() {
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const store = PropertiesService.getScriptProperties();
      if (!store.getProperty('OTP_SECRET')) {
        // Google's owner OAuth bearer token supplies secret entropy. It is
        // reduced to a digest and never saved, logged or returned to callers.
        const seed = ScriptApp.getOAuthToken() + ':' + Utilities.getUuid();
        store.setProperty('OTP_SECRET', hex_(Utilities.computeDigest(
          Utilities.DigestAlgorithm.SHA_256, seed, Utilities.Charset.UTF_8)));
      }
      // Check the owner's permissions without changing an account or sending mail.
      const reply = UrlFetchApp.fetch('https://identitytoolkit.googleapis.com/v1/projects/' + PROJECT + '/accounts:lookup', {
        method: 'post', contentType: 'application/json',
        headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()},
        payload: JSON.stringify({localId: ['lostzone-permission-check-does-not-exist']}),
        muteHttpExceptions: true
      });
      if (reply.getResponseCode() !== 200) throw new Error('FIREBASE_ADMIN_PERMISSION_REQUIRED');
      console.log('Setup complete. Remaining email recipients today: ' + MailApp.getRemainingDailyQuota());
    } finally { lock.releaseLock(); }
  }

  function doGet() { return json_({ok: true, service: 'lostzone-email-code', version: 1}); }

  function doPost(event) {
    try {
      const body = event && event.postData && event.postData.contents;
      if (typeof body !== 'string' || body.length > 8192) return json_({ok: false, error: 'INVALID_REQUEST'});
      const request = JSON.parse(body);
      if (!request || typeof request !== 'object' || Array.isArray(request) ||
          !['send', 'verify'].includes(request.action) || typeof request.idToken !== 'string' ||
          request.idToken.length < 100 || request.idToken.length > 4096) {
        return json_({ok: false, error: 'INVALID_REQUEST'});
      }
      if (request.action === 'verify' && (typeof request.code !== 'string' || !/^\d{6}$/.test(request.code))) {
        return json_({ok: false, error: 'INVALID_CODE'});
      }
      const user = lookup_(request.idToken);
      if (user.emailVerified === true) return json_({ok: true, verified: true});
      const lock = LockService.getScriptLock();
      if (!lock.tryLock(10000)) return json_({ok: false, error: 'SERVICE_BUSY'});
      try { return json_(process_(request, user, PropertiesService.getScriptProperties(), Date.now())); }
      finally { lock.releaseLock(); }
    } catch (error) {
      // Never return upstream responses or exception objects with credentials.
      const allowed = ['INVALID_ID_TOKEN', 'TOKEN_EXPIRED', 'USER_DISABLED', 'INVALID_RESPONSE',
        'CODE_SERVICE_NOT_CONFIGURED', 'MAIL_QUOTA_EXCEEDED', 'MAIL_SEND_FAILED', 'FIREBASE_ADMIN_PERMISSION_REQUIRED'];
      return json_({ok: false, error: allowed.includes(error.message) ? error.message : 'SERVICE_ERROR'});
    }
  }

  function lookup_(token) {
    const result = google_('https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=' + API_KEY, {idToken: token});
    const user = result.users && result.users.length === 1 && result.users[0];
    if (!user || typeof user.localId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(user.localId) ||
        typeof user.email !== 'string' || user.email.length > 254 || /[\r\n,;]/.test(user.email)) throw new Error('INVALID_RESPONSE');
    return user;
  }

  function process_(request, user, store, now) {
    const secret = store.getProperty('OTP_SECRET');
    if (!secret || !/^[0-9a-f]{64}$/.test(secret)) throw new Error('CODE_SERVICE_NOT_CONFIGURED');
    const key = 'otp:' + user.localId;
    let record = JSON.parse(store.getProperty(key) || 'null');
    if (request.action === 'send') {
      // Bounded registry: remove expired hourly budgets/challenges before adding.
      const records = store.getProperties();
      let active = 0;
      for (const item of Object.keys(records)) {
        if (!item.startsWith('otp:')) continue;
        const state = JSON.parse(records[item]);
        if (state.window + 60 * 60 * 1000 <= now) store.deleteProperty(item);
        else ++active;
      }
      if (!record || record.window + 60 * 60 * 1000 <= now) {
        if (active >= 500) return {ok: false, error: 'SERVICE_BUSY'};
        record = {window: now, sends: 0, failures: 0, sent: 0};
      }
      if (record.failures >= MAX_ATTEMPTS) return {ok: false, error: 'CODE_ATTEMPTS_EXCEEDED'};
      if (record.sends >= MAX_PER_HOUR) return {ok: false, error: 'CODE_SEND_LIMIT'};
      if (record.sent && now - record.sent < RESEND_DELAY) return {ok: false, error: 'CODE_RESEND_WAIT'};
      if (MailApp.getRemainingDailyQuota() < 1) throw new Error('MAIL_QUOTA_EXCEEDED');
      const nonce = Utilities.getUuid();
      const code = code_(secret, user.localId + ':' + user.email + ':' + now + ':' + nonce);
      record.email = user.email; record.nonce = nonce; record.expires = now + TTL;
      record.hash = hmac_(secret, user.localId + ':' + user.email + ':' + nonce + ':' + code);
      record.sent = now; ++record.sends;
      // Reserve before send; concurrent retries cannot generate multiple valid codes.
      store.setProperty(key, JSON.stringify(record));
      try {
        MailApp.sendEmail({to: user.email, name: 'Lost Zone',
          subject: 'Код подтверждения Lost Zone',
          body: 'Код подтверждения электронной почты в Lost Zone:\n\n' + code +
            '\n\nВведите его в игре и нажмите «Продолжить». Код действует 10 минут.\n' +
            'Если вы не создавали аккаунт, проигнорируйте это письмо. Никому не сообщайте код.'});
      } catch (error) {
        // Invalidate a code that was not delivered. Keep rate/guessing budgets.
        record.hash = ''; record.expires = now; store.setProperty(key, JSON.stringify(record));
        throw new Error('MAIL_SEND_FAILED');
      }
      return {ok: true, expiresIn: TTL / 1000, retryAfter: RESEND_DELAY / 1000};
    }
    if (!record || !record.hash || now >= record.expires) return {ok: false, error: 'CODE_EXPIRED'};
    if (record.email !== user.email) return {ok: false, error: 'CODE_EXPIRED'};
    if (record.failures >= MAX_ATTEMPTS) return {ok: false, error: 'CODE_ATTEMPTS_EXCEEDED'};
    const candidate = hmac_(secret, user.localId + ':' + user.email + ':' + record.nonce + ':' + request.code);
    if (!equal_(record.hash, candidate)) {
      ++record.failures; store.setProperty(key, JSON.stringify(record));
      return {ok: false, error: record.failures >= MAX_ATTEMPTS ? 'CODE_ATTEMPTS_EXCEEDED' : 'INVALID_CODE'};
    }
    // Fix the verified email to the address that received the code. A concurrent
    // email change cannot make another address verified by racing this update.
    google_('https://identitytoolkit.googleapis.com/v1/projects/' + PROJECT + '/accounts:update',
      {localId: user.localId, email: record.email, emailVerified: true}, true);
    store.deleteProperty(key);
    return {ok: true, verified: true};
  }

  function google_(url, data, admin) {
    const options = {method: 'post', contentType: 'application/json', payload: JSON.stringify(data), muteHttpExceptions: true};
    if (admin) options.headers = {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()};
    const response = UrlFetchApp.fetch(url, options);
    let value;
    try { value = JSON.parse(response.getContentText()); } catch (_) { throw new Error('INVALID_RESPONSE'); }
    if (response.getResponseCode() !== 200) {
      const message = value.error && value.error.message;
      if (admin) throw new Error('FIREBASE_ADMIN_PERMISSION_REQUIRED');
    throw new Error(['INVALID_ID_TOKEN', 'TOKEN_EXPIRED', 'USER_DISABLED'].includes(message) ? message : 'SERVICE_ERROR');
    }
    return value;
  }
  function json_(value) { return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON); }
  function hex_(bytes) { return bytes.map(value => ('0' + ((value + 256) & 255).toString(16)).slice(-2)).join(''); }
  function hmac_(secret, message) { return hex_(Utilities.computeHmacSha256Signature(message, secret, Utilities.Charset.UTF_8)); }
  function code_(secret, message) {
    // A keyed PRF supplies unpredictability; UUID/time are non-secret nonces.
    const bytes = Utilities.computeHmacSha256Signature(message, secret, Utilities.Charset.UTF_8);
    for (let i = 0; i + 3 < bytes.length; i += 4) {
      const n = (((bytes[i] & 255) * 256 + (bytes[i+1] & 255)) * 256 + (bytes[i+2] & 255)) * 256 + (bytes[i+3] & 255);
      if (n < 4294000000) return ('000000' + (n % 1000000)).slice(-6);
    }
    return code_(secret, message + ':retry');
  }
  function equal_(left, right) {
    if (typeof left !== 'string' || typeof right !== 'string' || left.length !== 64 || right.length !== 64) return false;
    let difference = 0;
    for (let i = 0; i < 64; ++i) difference |= left.charCodeAt(i) ^ right.charCodeAt(i);
    return difference === 0;
  }
