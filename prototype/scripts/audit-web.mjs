import { spawn } from 'node:child_process'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const ORIGIN = process.env.ZHICE_WEB_ORIGIN || 'http://127.0.0.1:5173'
const API = process.env.ZHICE_API_ORIGIN || 'http://127.0.0.1:8002'
const CHROME = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const DEBUG_PORT = Number(process.env.CHROME_DEBUG_PORT || 9223)

const routes = [
  '/',
  '/replay',
  '/intraday',
  '/theme-workshop',
  '/theme-workshop?tab=events',
  '/theme-workshop?tab=cycle',
  '/theme-workshop?tab=chain',
  '/theme-workshop?tab=rotation',
  '/theme-workshop?tab=history',
  '/verification',
  '/verification?tab=capital',
  '/verification?tab=history',
  '/verification?tab=odds',
  '/verification?tab=cases',
  '/gv-overview',
  '/growth-workshop',
  '/growth-workshop?tab=macro',
  '/growth-workshop?tab=inflection',
  '/growth-workshop?tab=chain',
  '/growth-workshop?tab=etf',
  '/growth-workshop?tab=candidates',
  '/value-workshop',
  '/value-workshop?tab=valuation',
  '/value-workshop?tab=compare',
  '/value-workshop?tab=finance',
  '/value-workshop?tab=research',
  '/tools-home',
  '/stock-research',
  '/stock-research?tab=chain',
  '/stock-research?tab=pool',
  '/research-pool',
  '/strategy-workshop',
  '/strategy-workshop?tab=builder',
  '/strategy-workshop?tab=advanced',
  '/strategy-workshop?tab=recommend',
  '/strategy-workshop?tab=lab',
  '/my-workspace',
  '/my-workspace?tab=archive',
  '/membership',
  '/settings',
  '/admin',
  '/feature-map',
  '/replay-legacy',
  '/intraday-legacy',
  '/sentiment-legacy',
  '/sentiment-page',
  '/theme',
  '/stock',
  '/stock/000001',
  '/chain',
  '/strategy',
  '/strategy-builder',
  '/advanced-strategy',
  '/recommend',
  '/lab',
  '/dashboard',
  '/report-archive',
  '/vip',
  '/watchlist',
  '/broken-cases',
  '/growth',
  '/prosperity',
  '/etf-rotation',
  '/value',
  '/valuation',
  '/finance-compare',
  '/finance-report',
  '/research',
  '/longhu',
  '/rotation',
  '/hot-events',
]

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitFor(url, timeout = 10_000) {
  const start = Date.now()
  let last = ''
  while (Date.now() - start < timeout) {
    try {
      const res = await fetch(url)
      if (res.ok) return res
      last = `${res.status} ${res.statusText}`
    } catch (e) {
      last = e.message
    }
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}: ${last}`)
}

async function ensureUser() {
  const phone = 'audit_web'
  const password = 'audit123456'
  const payload = { phone, password, nickname: '审计用户' }
  const register = await fetch(`${API}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (register.ok) return register.json()
  const login = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, password }),
  })
  if (login.ok) return login.json()
  const text = await login.text()
  throw new Error(`auth failed: register ${register.status}, login ${login.status} ${text}`)
}

class Cdp {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    this.handlers = new Map()
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        if (msg.error) reject(new Error(msg.error.message))
        else resolve(msg.result)
      }
      if (msg.method && this.handlers.has(msg.method)) {
        for (const fn of this.handlers.get(msg.method)) fn(msg.params)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }))
  }
  on(method, fn) {
    if (!this.handlers.has(method)) this.handlers.set(method, [])
    this.handlers.get(method).push(fn)
  }
}

async function withChrome(fn) {
  const profile = join(tmpdir(), `zhice-audit-${Date.now()}`)
  await mkdir(profile, { recursive: true })
  const chrome = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank',
  ], { stdio: 'ignore' })
  try {
    await waitFor(`http://127.0.0.1:${DEBUG_PORT}/json/version`)
    await fn()
  } finally {
    chrome.kill()
    await sleep(500)
    await rm(profile, { recursive: true, force: true }).catch(() => {})
  }
}

async function createPage() {
  const targetRes = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/new?about:blank`, { method: 'PUT' })
  const target = await targetRes.json()
  const ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  return new Cdp(ws)
}

async function auditRoute(cdp, route, auth, browserEvents) {
  const messages = []
  const requests = []
  const script = `
    localStorage.setItem('zhice.token', ${JSON.stringify(auth.token)});
    localStorage.setItem('zhice.user', ${JSON.stringify(JSON.stringify(auth.user))});
  `

  browserEvents.current = { messages, requests }

  await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: script })
  await cdp.send('Runtime.evaluate', { expression: script })
  await cdp.send('Page.navigate', { url: `${ORIGIN}${route}` })
  await sleep(1600)
  const result = await cdp.send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => {
      const text = document.body.innerText || '';
      const headings = [...document.querySelectorAll('h1,h2,.ant-card-head-title')].slice(0, 8).map(e => e.textContent.trim()).filter(Boolean);
      const activeMenu = [...document.querySelectorAll('.ant-menu-item-selected')].map(e => e.textContent.trim()).join('|');
      return {
        url: location.pathname + location.search,
        title: document.title,
        len: text.length,
        empty: text.trim().length < 20,
        notFound: /404|页面不存在/.test(text),
        login: /登录|注册/.test(text) && location.pathname === '/login',
        devPlaceholder: (text.match(/开发中/g) || []).length,
        markdownLeak: /#{2,}|\\*\\*|\\n- /.test(text),
        headings,
        activeMenu,
        bodyStart: text.trim().slice(0, 200),
      }
    })()`,
  })
  return { route, ...result.result.value, messages, requests }
}

await waitFor(`${ORIGIN}/`)
await waitFor(`${API}/api/health`)
const auth = await ensureUser()

const output = []
await withChrome(async () => {
  const cdp = await createPage()
  const browserEvents = { current: null }
  await Promise.all([
    cdp.send('Page.enable'),
    cdp.send('Runtime.enable'),
    cdp.send('Network.enable'),
    cdp.send('Log.enable'),
  ])
  cdp.on('Runtime.exceptionThrown', (p) => {
    browserEvents.current?.messages.push({ type: 'exception', text: p.exceptionDetails?.text || p.exceptionDetails?.exception?.description || '' })
  })
  cdp.on('Runtime.consoleAPICalled', (p) => {
    if (['error', 'warning'].includes(p.type)) {
      browserEvents.current?.messages.push({ type: p.type, text: p.args?.map((a) => a.value || a.description || '').join(' ') || '' })
    }
  })
  cdp.on('Network.responseReceived', (p) => {
    const url = p.response.url
    const status = p.response.status
    if (url.includes('/api/') && status >= 400) browserEvents.current?.requests.push({ status, url })
  })
  for (const route of routes) {
    output.push(await auditRoute(cdp, route, auth, browserEvents))
  }
})

const reportPath = join(process.cwd(), 'web-audit-report.json')
await writeFile(reportPath, JSON.stringify(output, null, 2), 'utf8')

const bad = output.filter((r) =>
  r.empty || r.notFound || r.login || r.devPlaceholder > 0 ||
  r.messages.some((m) => m.type === 'exception' || /Error|Failed|Cannot|Uncaught/i.test(m.text)) ||
  r.requests.length
)
console.log(JSON.stringify({ checked: output.length, bad: bad.length, reportPath, bad: bad.map((r) => ({
  route: r.route,
  url: r.url,
  headings: r.headings,
  activeMenu: r.activeMenu,
  empty: r.empty,
  notFound: r.notFound,
  login: r.login,
  devPlaceholder: r.devPlaceholder,
  messages: r.messages.slice(0, 3),
  requests: r.requests.slice(0, 3),
})) }, null, 2))
