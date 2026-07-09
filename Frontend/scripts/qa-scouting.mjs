import { chromium } from 'playwright'

const baseUrl = process.env.QA_BASE_URL ?? 'http://127.0.0.1:5173/#/scouting'
const channel = process.env.QA_BROWSER_CHANNEL ?? 'msedge'

const browser = await chromium.launch({ channel })
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
const consoleIssues = []
const networkIssues = []

page.on('console', (message) => {
  if (['error', 'warning'].includes(message.type())) {
    const text = message.text()

    if (text.includes('Failed to load resource: net::ERR_CONNECTION_REFUSED')) {
      networkIssues.push(text)
      return
    }

    consoleIssues.push(`${message.type()}: ${text}`)
  }
})

await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.pattern-board')

const initial = await readState(page)

await page.locator('.heatmap-zone-list button', { hasText: 'Net-front rebounds' }).click()
await page.waitForTimeout(150)
const afterZone = await readState(page)

await page.selectOption('#scouting-season', '2024')
await page.waitForTimeout(150)
const afterSeason = await readState(page)

const mobilePage = await browser.newPage({ viewport: { width: 390, height: 844 } })
await mobilePage.goto(baseUrl, { waitUntil: 'domcontentloaded' })
await mobilePage.waitForSelector('.pattern-board')
const mobile = await mobilePage.evaluate(() => ({
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  boardVisible: Boolean(document.querySelector('.pattern-board')),
  navText: document.querySelector('.scouting-workflow-nav')?.textContent?.replace(/\s+/g, ' ').trim(),
}))

await browser.close()

const result = {
  initial,
  afterZone,
  afterSeason,
  mobile,
  consoleIssues,
  networkIssues,
}

assert(initial.title === 'NHL PK Analytics', 'page title should load')
assert(initial.controls.join('|') === 'Season|PP team|PK team', 'season, PP, and PK controls should render together')
assert(initial.modeButtons.includes('Mismatch'), 'mode buttons should render')
assert(initial.overflow === 0, 'desktop should not horizontally overflow')
assert(afterZone.activeZone?.includes('Net-front rebounds'), 'zone click should activate Net-front rebounds')
assert(afterZone.briefMain?.includes('Net-front rebounds'), 'brief should update after zone click')
assert(afterSeason.season === '2024', 'season select should change to 2024')
assert(afterSeason.briefTitle?.includes('2024-25'), 'brief title should reflect selected season')
assert(mobile.overflow === 0, 'mobile should not horizontally overflow')
assert(mobile.boardVisible, 'mobile should render tactical board')
assert(consoleIssues.length === 0, `console should be clean: ${consoleIssues.join('; ')}`)

console.log(JSON.stringify(result, null, 2))

async function readState(activePage) {
  return activePage.evaluate(() => ({
    title: document.title,
    url: window.location.href,
    controls: Array.from(document.querySelectorAll('.heatmap-toolbar label')).map((label) => label.textContent),
    modeButtons: Array.from(document.querySelectorAll('.map-mode-toggle button')).map((button) => button.textContent),
    season: document.querySelector('#scouting-season')?.value,
    activeZone: document.querySelector('.heatmap-zone-list button.active')?.textContent?.replace(/\s+/g, ' ').trim(),
    briefTitle: document.querySelector('#scouting-brief h3')?.textContent,
    briefMain: document.querySelector('#scouting-brief .brief-report-grid strong')?.textContent,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }))
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}
