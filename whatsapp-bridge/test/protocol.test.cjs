'use strict';

const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const path = require('node:path');
const readline = require('node:readline');
const test = require('node:test');

test('responde status sem iniciar conexão externa', async () => {
  const child = spawn(process.execPath, [path.join(__dirname, '..', 'index.cjs')], { stdio: ['pipe', 'pipe', 'pipe'] });
  const lines = readline.createInterface({ input: child.stdout });
  const received = [];
  let stderr = '';
  child.stderr.on('data', chunk => { stderr += chunk.toString(); });

  const waitFor = predicate => new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`Tempo esgotado. stderr: ${stderr}`)), 5000);
    const onLine = line => {
      const message = JSON.parse(line);
      received.push(message);
      if (predicate(message)) {
        clearTimeout(timeout);
        lines.off('line', onLine);
        resolve(message);
      }
    };
    lines.on('line', onLine);
  });

  await waitFor(message => message.type === 'bridge_ready');
  const response = waitFor(message => message.id === '1');
  child.stdin.write(`${JSON.stringify({ id: '1', action: 'get_status' })}\n`);
  await response;
  child.kill();
  await once(child, 'exit');
  assert.equal(received[0].type, 'bridge_ready');
  assert.deepEqual(received.find(item => item.id === '1'), {
    type: 'response', id: '1', ok: true, result: { status: 'DISCONNECTED' },
  });
});
