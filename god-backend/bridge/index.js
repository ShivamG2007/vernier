const path = require('node:path');
const fs = require('node:fs');
function dependency(name) {
  try { return require(name); }
  catch (_) { return require(path.resolve(__dirname, '../../bot/node_modules', name)); }
}
const { Client, LocalAuth } = dependency('whatsapp-web.js');
const qrcode = dependency('qrcode-terminal');

const STARTED_AT = Math.floor(Date.now() / 1000);
const BACKEND_URL =(process.env.BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ENABLE_GROUPS = process.env.VERNIER_ENABLE_GROUPS === '1';
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
      from.endsWith('@newsletter') || (isGroup && !ENABLE_GROUPS)) return;
  // WhatsApp replays messages that arrived while Vernier was off; only answer new ones.
  if (message.timestamp && message.timestamp < STARTED_AT) return;
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
  console.log(`Vernier is connected. Backend: ${BACKEND_URL}. Groups: ${ENABLE_GROUPS ? 'on' : 'off'}`);
  sendOutbox();
  setInterval(sendOutbox, 5000);
});

client.initialize().catch(error => console.error('Could not start WhatsApp:', error));
