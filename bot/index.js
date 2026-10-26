console.log('Starting Vernier...');

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const BACKEND = 'http://localhost:8000';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const humanDelay = () => sleep(1000 + Math.random() * 2000);

process.on('unhandledRejection', err => console.log('Unhandled error (bot keeps running):', err && err.message));
process.on('uncaughtException', err => console.log('Uncaught error (bot keeps running):', err && err.message));

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'vernier' }),
  puppeteer: { headless: false, args: ['--no-sandbox'] }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));
client.on('loading_screen', (p, m) => console.log('Loading', p, m));
client.on('auth_failure', m => console.log('Auth failure:', m));
client.on('disconnected', r => console.log('Disconnected:', r));

client.on('ready', () => {
  console.log('Vernier is online as', client.info.wid._serialized);
  setInterval(sendOutbox, 5000);
});

async function isMentioned(msg) {
  const me = client.info.wid.user;
  try {
    const mentions = await msg.getMentions();
    if (mentions.some(c => c.isMe)) return true;
  } catch (e) {}
  const ids = (msg.mentionedIds || []).map(id => String(id._serialized || id));
  if (ids.some(id => id.includes(me))) return true;
  if (msg.body.includes('@' + me)) return true;
  if (/^\s*@?vernier\b/i.test(msg.body)) return true;
  return false;
}

client.on('message', async msg => {
  try {
    if (msg.fromMe || msg.from === 'status@broadcast' || !msg.body) return;
    if (msg.from.endsWith('@newsletter') || msg.from.endsWith('@broadcast')) return;

    const isGroup = msg.from.endsWith('@g.us');
    let chatName = '';
    let chat = null;
    try {
      chat = await msg.getChat();
      chatName = chat.name || '';
    } catch (e) {
      console.log('  (could not load chat details, continuing)');
    }

    const mentioned = isGroup ? await isMentioned(msg) : false;

    const payload = {
      chat_id: msg.from,
      chat_name: chatName,
      is_group: isGroup,
      author: msg.author || msg.from,
      text: msg.body,
      mentioned
    };
    console.log(isGroup ? `[GROUP ${chatName}]` : '[DM]', payload.author, ':', msg.body);
    if (isGroup) console.log('  mentioned:', mentioned, '| mentionedIds:', JSON.stringify(msg.mentionedIds));

    const res = await fetch(`${BACKEND}/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    console.log('  -> intent:', data.intent, '| reply:', data.reply);

    if (data.reply) {
      try { if (chat) await chat.sendStateTyping(); } catch (e) {}
      await humanDelay();
      try {
        await msg.reply(data.reply);
      } catch (e) {
        await client.sendMessage(msg.from, data.reply);
      }
    }
  } catch (err) {
    console.log('Error handling message:', err.message);
  }
});

async function sendOutbox() {
  try {
    const res = await fetch(`${BACKEND}/outbox`);
    const items = await res.json();
    for (const item of items) {
      await humanDelay();
      try {
        await client.sendMessage(item.to_chat, item.text);
        console.log('  -> sent alert to', item.to_chat);
      } catch (e) {
        console.log('  -> could not send alert to', item.to_chat, ':', e.message);
      }
    }
  } catch (err) {
    console.log('Outbox error:', err.message);
  }
}

client.initialize();