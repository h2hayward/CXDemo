import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(root, '../docs/SDR-research-workflow.png');
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], { cwd: root, stdio: 'pipe' });
let browser;
try {
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Preview server did not start')), 15000);
    server.stdout.on('data', (chunk) => {
      if (String(chunk).includes('4173')) { clearTimeout(timeout); resolve(); }
    });
    server.once('exit', code => { clearTimeout(timeout); reject(new Error(`Preview server exited: ${code}`)); });
  });
  const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const executablePath = process.env.CHROME_EXECUTABLE || (existsSync(macChrome) ? macChrome : undefined);
  browser = await chromium.launch({ headless: true, executablePath });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1300 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:4173', { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-ready="true"]');
  await page.waitForFunction(() => Array.from(document.querySelectorAll('.react-flow__node')).every(node => node.getBoundingClientRect().height > 0));
  if (await page.locator('.react-flow__node').count() !== 7) throw new Error('Expected seven React Flow nodes');
  if (await page.locator('.react-flow__edge').count() !== 6) throw new Error('Expected six React Flow edges');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download PNG' }).click();
  const download = await downloadPromise;
  mkdirSync(path.dirname(output), { recursive: true });
  await download.saveAs(output);
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('Exported seven H2-styled React Flow nodes and six edges through the PNG download button.');
  console.log(output);
} finally {
  await browser?.close();
  server.kill();
}
