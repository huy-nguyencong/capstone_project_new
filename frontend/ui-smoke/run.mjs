// UI regression smoke: log in as each role, open every page at phone, tablet and desktop sizes,
// save full-page screenshots, and report horizontal overflow plus browser console errors.
//
// Needs the API and `npm run dev` running, and the seeded accounts. Uses the installed Microsoft
// Edge through playwright-core, so no browser is downloaded. Read-only: the search flow opens the
// "create case" dialog and cancels it.
//
//   npm run ui:smoke                 # all three sizes
//   npm run ui:smoke -- phone        # one size: phone | tablet | desktop
//
// Env: UI_SMOKE_BASE (default http://localhost:5173), UI_SMOKE_PASSWORD (default "password").
// Output: ui-smoke/output/<size>/*.png and report.json. Exit code 1 when anything is flagged.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const BASE = process.env.UI_SMOKE_BASE || 'http://localhost:5173'
const PASSWORD = process.env.UI_SMOKE_PASSWORD || 'password'
const SIZES = {
  phone: { width: 390, height: 844, isMobile: true, hasTouch: true },
  tablet: { width: 768, height: 1024, isMobile: true, hasTouch: true },
  desktop: { width: 1440, height: 900, isMobile: false, hasTouch: false },
}
const ROLES = {
  admin: [
    '/admin/users',
    '/admin/cameras',
    '/admin/ai',
    '/admin/models',
    '/admin/videos',
    '/monitor/status',
    '/monitor/diagnostics',
    '/monitor/audit',
  ],
  operator: ['/search', '/cases'],
  viewer: ['/overview', '/case-files'],
}
const TEXT_QUERY = 'a man wearing a black jacket and blue jeans'

const selected = process.argv.slice(2).filter((name) => name in SIZES)
const sizes = selected.length ? selected : Object.keys(SIZES)

// Elements whose right edge passes the viewport, ignoring fixed elements and content inside a
// container that scrolls horizontally on purpose (wide tables, filter chips).
const measureOverflow = (page) =>
  page.evaluate(() => {
    const viewport = document.documentElement.clientWidth
    const offenders = []
    for (const element of document.querySelectorAll('body *')) {
      const box = element.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) continue
      if (box.right <= viewport + 1 || getComputedStyle(element).position === 'fixed') continue
      let parent = element.parentElement
      let scrolls = false
      while (parent) {
        const overflowX = getComputedStyle(parent).overflowX
        if (
          (overflowX === 'auto' || overflowX === 'scroll') &&
          parent.scrollWidth > parent.clientWidth
        ) {
          scrolls = true
          break
        }
        parent = parent.parentElement
      }
      if (!scrolls)
        offenders.push({
          tag: element.tagName.toLowerCase(),
          cls: (element.className?.baseVal ?? element.className ?? '').toString().slice(0, 80),
          text: (element.innerText || '').trim().slice(0, 40),
          right: Math.round(box.right),
        })
    }
    return {
      viewport,
      scrollWidth: document.documentElement.scrollWidth,
      offenders: offenders.slice(0, 8),
    }
  })

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const report = {}
let flagged = 0

for (const size of sizes) {
  const { width, height, ...device } = SIZES[size]
  const outDir = new URL(`./output/${size}/`, import.meta.url)
  mkdirSync(outDir, { recursive: true })
  const results = {}
  let errors = []

  const newPage = async () => {
    const context = await browser.newContext({
      viewport: { width, height },
      deviceScaleFactor: 1,
      locale: 'vi-VN',
      ...device,
    })
    const page = await context.newPage()
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => {
      // Failed requests are reported with their URL by the response handler below.
      if (message.type() === 'error' && !message.text().startsWith('Failed to load resource'))
        errors.push(`console: ${message.text().slice(0, 300)}`)
    })
    page.on('response', (response) => {
      const { pathname } = new URL(response.url())
      // Checking the session before login is expected to answer 401.
      if (response.status() === 401 && pathname === '/api/v1/auth/me') return
      if (response.status() >= 400) errors.push(`http ${response.status()}: ${pathname}`)
    })
    return { context, page }
  }

  const shot = async (page, name) => {
    await page.waitForTimeout(700)
    await page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, outDir)), fullPage: true })
    results[name] = { ...(await measureOverflow(page)), errors }
    errors = []
  }

  {
    const { context, page } = await newPage()
    await page.goto(`${BASE}/login`)
    await shot(page, 'login')
    await context.close()
  }

  for (const [role, paths] of Object.entries(ROLES)) {
    const { context, page } = await newPage()
    await page.goto(`${BASE}/login`)
    await page.getByLabel('Tên đăng nhập').fill(role)
    await page.getByLabel('Mật khẩu').fill(PASSWORD)
    await page.getByRole('button', { name: 'Đăng nhập' }).click()
    await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15000 })
    errors = []

    for (const path of paths) {
      await page.goto(`${BASE}${path}`)
      await page.waitForLoadState('networkidle').catch(() => {})
      await shot(page, `${role}${path.replaceAll('/', '_')}`)
    }

    if (role === 'admin') {
      // Picking a model card must select it (regression: the click handler was not wired).
      await page.goto(`${BASE}/admin/models`)
      await page.waitForLoadState('networkidle').catch(() => {})
      const unpicked = page.locator('button.option-card:not([disabled]):not([aria-pressed="true"])')
      if (await unpicked.count()) {
        const card = await unpicked.first().elementHandle()
        await card.click()
        if ((await card.getAttribute('aria-pressed')) !== 'true')
          errors.push('model card click did not select it')
      }
      await shot(page, 'admin_models_picked')
      await page.goto(`${BASE}/admin/users`)
      await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
      await shot(page, 'admin_create_user_dialog')
    }

    if (role === 'operator') {
      await page.goto(`${BASE}/search`)
      await page.getByText('Văn bản', { exact: true }).click()
      await page.locator('textarea').fill(TEXT_QUERY)
      await page.getByRole('button', { name: 'Tìm kiếm' }).click()
      await page.waitForSelector('text=kết quả phù hợp nhất', { timeout: 60000 }).catch(() => {})
      await shot(page, 'operator_search_results')
      const card = page.locator('button[draggable="true"]').first()
      if (await card.count()) {
        await card.click()
        await shot(page, 'operator_result_viewer')
        await page.getByRole('button', { name: 'Tạo vụ việc mới' }).click()
        await shot(page, 'operator_create_case_dialog')
        await page.getByRole('button', { name: 'Hủy' }).click()
        await page.getByRole('button', { name: 'Đóng' }).click()
      } else {
        results.operator_search_results.errors.push('no search result card found')
      }
      await page.goto(`${BASE}/search`)
      await page.getByText('Thuộc tính', { exact: true }).click()
      await shot(page, 'operator_search_attributes')
      await page.getByRole('combobox').nth(2).click()
      await shot(page, 'operator_attribute_dropdown')
    }
    await context.close()
  }

  writeFileSync(new URL('report.json', outDir), JSON.stringify(results, null, 2))
  report[size] = results
  console.log(`\n== ${size} (${width}x${height})`)
  for (const [name, result] of Object.entries(results)) {
    const problems = []
    if (result.scrollWidth > result.viewport) problems.push(`OVERFLOW ${result.scrollWidth}px`)
    if (result.offenders.length) problems.push(`${result.offenders.length} clipped`)
    if (result.errors.length) problems.push(`${result.errors.length} error(s)`)
    flagged += problems.length ? 1 : 0
    console.log(name.padEnd(34), problems.length ? problems.join(', ') : 'ok')
    for (const item of result.offenders.slice(0, 3)) console.log('   ', JSON.stringify(item))
    for (const item of result.errors.slice(0, 3)) console.log('   ', item)
  }
}

await browser.close()
console.log(`\n${flagged ? `${flagged} screen(s) flagged` : 'all screens ok'}`)
process.exitCode = flagged ? 1 : 0
