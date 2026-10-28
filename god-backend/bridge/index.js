const path = require('node:path');
const fs = require('node:fs');
function dependency(name) {
  try { return require(name); }
  catch (_) { return require(path.resolve(__dirname, '../../bot/node_modules', name)); }
}
const { Client, LocalAuth } = dependency('whatsapp-web.js');
const qrcode = dependency('qrcode-terminal');

const BACKEND_URL = (process.env.BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ADMIN_KEY = process.env.VERNIER_ADMIN_KEY || '';
const BROWSER_PATH = [
  process.env.VERNIER_BROWSER_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].find(candidate => candidate && fs.existsSync(candidate));
// Reuse the existing Vernier login without copying or printing its private files.
const AUTH_PATH = process.env.VERNIER_AUTH_PATH || path.resolve(__dirname, '../../bot/.wwebjs_auth');
const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'vernier', dataPath: AUTH_PATH }),
  puppeteer: { headless: true, ...(BROWSER_PATH ? { executablePath: BROWSER_PATH } : {}) },
});

const headers = { 'Content-Type': 'application/json' };
if (ADMIN_KEY) headers['X-Vernier-Key'] = ADMIN_KEY;

async function callBackend(route, options = {}) {
  const response = await fetch(`${BACKEND_URL}${route}`, {
    ...options,
    headers,
    signal: AbortSignal.timeout(120000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Backend returned ${response.status}`);
  return data;
}

// The backend's VERNIER_ENABLE_GROUPS is the only group switch; the bridge follows it
// so the two can never disagree. Re-checked often because the backend may restart.
let groupsOn = null;
async function refreshGroups() {
  try {
    const on = (await callBackend('/health')).groups_enabled === true;
    if (on !== groupsOn) {
      console.log(on ? 'Groups: on'
        : 'Groups: off. To turn them on, set $env:VERNIER_ENABLE_GROUPS="1" in the backend window and restart the backend.');
    }
    groupsOn = on;
  } catch (error) {
    if (groupsOn === null) console.error('Could not ask the backend whether groups are on:', error.message);
  }
}
refreshGroups();
setInterval(refreshGroups, 15000);

async function isMentioned(message) {
  const me = client.info?.wid?.user;
  try {
    const mentions = await message.getMentions();
    if (mentions.some(contact => contact.isMe)) return true;
  } catch (_) {}
  const ids = (message.mentionedIds || []).map(id => String(id._serialized || id));
  return !!me && ids.some(id => id.includes(me));
}

client.on('qr', qr => {
  console.log('On the Vernier phone: Linked devices > Link a device. Scan this QR:');
  qrcode.generate(qr, { small: true });
});
client.on('auth_failure', reason => console.error('WhatsApp login failed:', reason));
client.on('disconnected', reason => console.error('WhatsApp disconnected:', reason));

client.on('message', async message => {
  const from = message.from || '';
  const isGroup = from.endsWith('@g.us');
  if (message.fromMe || !message.body || from.endsWith('@broadcast') ||
      from.endsWith('@newsletter') || (isGroup && !groupsOn)) return;
  try {
    let chatName = '';
    if (isGroup) {
      try { chatName = (await message.getChat()).name || ''; } catch (_) {}
    }
    const data = await callBackend('/message', {
      method: 'POST',
      body: JSON.stringify({
        message_id: message.id?._serialized || '',
        chat_id: from,
        chat_name: chatName,
        is_group: isGroup,
        mentioned: isGroup ? await isMentioned(message) : false,
        author: message.author || from,
        text: message.body,
      }),
    });
    if (data.action === 'ignored_group') {
      // The backend turned groups off since the last check; follow it straight away.
      await refreshGroups();
      return;
    }
    if (data.reply && !data.duplicate) await message.reply(data.reply);
    console.log(`${isGroup ? 'Group' : 'DM'} handled: ${data.action}${data.duplicate ? ' (duplicate)' : ''}`);
  } catch (error) {
    console.error('Could not handle message:', error.message);
    if (!isGroup) {
      try { await message.reply('I am having trouble connecting right now. Please try again shortly.'); }
      catch (sendError) { console.error('Could not send fallback:', sendError.message); }
    }
  }
});

let polling = false;
async function sendOutbox() {
  if (polling) return;
  polling = true;
  try {
    const { messages } = await callBackend('/outbox');
    for (const entry of messages) {
      try {
        await client.sendMessage(entry.to_chat, entry.text);
        await callBackend(`/outbox/${entry.id}/ack`, { method: 'POST', body: '{}' });
        console.log(`Alert delivered: #${entry.id}`);
      } catch (error) {
        console.error(`Alert #${entry.id} failed:`, error.message);
        try { await callBackend(`/outbox/${entry.id}/retry`, { method: 'POST', body: '{}' }); }
        catch (retryError) { console.error('Could not release alert:', retryError.message); }
      }
    }
  } catch (error) {
    console.error('Outbox polling failed:', error.message);
  } finally {
    polling = false;
  }
}

client.on('ready', () => {
  console.log(`Vernier is connected. Backend: ${BACKEND_URL}. Groups: ${groupsOn === null ? 'unknown (backend not reachable yet)' : groupsOn ? 'on' : 'off'}`);
  sendOutbox();
  setInterval(sendOutbox, 5000);
});

client.initialize().catch(error => console.error('Could not start WhatsApp:', error));
