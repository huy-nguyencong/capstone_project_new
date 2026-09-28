// Full demo rehearsal (files/demo-script.md) at 1440x900, recorded as a video.
//
// Admin adds an RTSP camera and tests it, turns AI on, the worker starts a session on its own;
// Operator searches by image, saves the first result into a new case marked completed; Viewer
// checks the dashboard and the case; Admin turns AI off again.
//
// WRITES DATA (a camera, a case, audit rows, tracks from the RTSP session). Rehearse on the demo
// baseline and restore it afterwards (see demo-script.md, "Sau khi diễn tập").
//
//   DEMO_RTSP_URL=rtsp://<IP-LAN>:8554/cam2 npm run ui:demo
//
// Env: DEMO_RTSP_URL (required), DEMO_QUERY (default ../backend/var/demo-queries/WT-Q006.jpg),
// DEMO_CAMERA_CODE (default DEMO-RTSP), UI_SMOKE_BASE, UI_SMOKE_PASSWORD.
// Output: ui-smoke/output/demo/<timestamp>/ (video .webm and screenshots).
import { chromium } from 'playwright-core'
import { mkdirSync, readdirSync, renameSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const BASE = process.env.UI_SMOKE_BASE || 'http://localhost:5173'
const PASSWORD = process.env.UI_SMOKE_PASSWORD || 'password'
const RTSP_URL = process.env.DEMO_RTSP_URL
const QUERY = fileURLToPath(
  new URL(process.env.DEMO_QUERY || '../../backend/var/demo-queries/WT-Q006.jpg', import.meta.url),
)
const CODE = process.env.DEMO_CAMERA_CODE || 'DEMO-RTSP'
const NAME = 'Camera sảnh chính (RTSP)'
const PAUSE = 1500 // lets a viewer of the video follow each step
if (!RTSP_URL) {
  console.error('Set DEMO_RTSP_URL, e.g. rtsp://192.168.1.10:8554/cam2 (printed by rtsp.ps1 up).')
  process.exit(2)
}

const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
const outDir = fileURLToPath(new URL(`./output/demo/${stamp}/`, import.meta.url))
mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ channel: 'msedge', headless: true })

// Warm-up (not recorded): the first search after the API starts loads the RaSa encoder, which
// takes minutes while the worker is busy with an RTSP session. demo-script.md does this by hand.
{
  const warm = await (await browser.newContext()).newPage()
  const started = Date.now()
  await warm.goto(`${BASE}/login`)
  await warm.getByLabel('Tên đăng nhập').fill('operator')
  await warm.getByLabel('Mật khẩu').fill(PASSWORD)
  await warm.getByRole('button', { name: 'Đăng nhập' }).click()
  await warm.waitForURL(/search/, { timeout: 15000 })
  await warm.getByText('Hình ảnh', { exact: true }).click()
  await warm.locator('input[type="file"]').setInputFiles(QUERY)
  await warm.getByRole('button', { name: 'Tìm kiếm' }).click()
  await warm.getByText('kết quả phù hợp nhất').waitFor({ timeout: 180000 })
  console.log(`warm-up search ${((Date.now() - started) / 1000).toFixed(1)}s (not recorded)`)
  await warm.context().close()
}

const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  locale: 'vi-VN',
  recordVideo: { dir: outDir, size: { width: 1440, height: 900 } },
})
const page = await context.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
page.on('response', (response) => {
  const { pathname } = new URL(response.url())
  if (response.status() === 401 && pathname === '/api/v1/auth/me') return
  if (response.status() >= 400) errors.push(`http ${response.status()}: ${pathname}`)
})

const started = Date.now()
let stepStarted = started
const step = async (label, action) => {
  stepStarted = Date.now()
  try {
    await action()
  } catch (error) {
    await page.screenshot({ path: `${outDir}FAILED.png` })
    console.log(`FAIL ${label}: ${error.message.split('\n')[0]}`)
    await context.close()
    await browser.close()
    process.exit(1)
  }
  await page.waitForTimeout(PAUSE)
  const seconds = ((Date.now() - stepStarted) / 1000).toFixed(1)
  console.log(`ok   ${label.padEnd(52)} ${seconds}s`)
}
const shot = (name) => page.screenshot({ path: `${outDir}${name}.png` })
const login = async (username) => {
  await page.goto(`${BASE}/login`)
  await page.getByLabel('Tên đăng nhập').fill(username)
  await page.getByLabel('Mật khẩu').fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15000 })
}
const logout = async () => {
  await page.getByRole('button', { name: 'Đăng xuất' }).first().click()
  await confirmDialog('Đăng xuất').click()
  await page.waitForURL(/\/login/, { timeout: 15000 })
}
// Wait until every image on the page has loaded, so screenshots and the video show real crops.
const imagesLoaded = () =>
  page.waitForFunction(
    () => [...document.images].every((image) => image.complete && image.naturalWidth > 0),
    null,
    { timeout: 60000 },
  )
const CASE_TITLE = 'Tìm người mang túi hoa, giày trắng'
const cameraRow = () => page.locator('tr', { hasText: NAME })
const confirmDialog = (label) => page.getByRole('dialog').getByRole('button', { name: label })

await step('Quản trị viên đăng nhập', () => login('admin'))
await step('Thêm camera RTSP và kiểm tra kết nối', async () => {
  await page.goto(`${BASE}/admin/cameras`)
  await page.getByRole('button', { name: 'Thêm camera' }).click()
  await page.getByLabel('Mã camera').fill(CODE)
  await page.getByLabel('Tên camera').fill(NAME)
  await page.getByLabel('Khu vực').selectOption({ label: 'Gate A' })
  await page.getByLabel(/^RTSP/).fill(RTSP_URL)
  await page.getByRole('button', { name: 'Lưu và kiểm tra RTSP' }).click()
  await cameraRow().getByText('Trực tuyến').waitFor({ timeout: 30000 })
  await shot('1-camera-online')
})
await step('Bật xử lý AI cho camera', async () => {
  await page.goto(`${BASE}/admin/ai`)
  await cameraRow().getByRole('switch').click()
  await confirmDialog('Bật xử lý AI').click()
  await cameraRow().getByRole('switch', { checked: true }).waitFor({ timeout: 15000 })
  await shot('2-ai-on')
})
await step('Worker tự tạo phiên RTSP (Trạng thái hệ thống)', async () => {
  await page.goto(`${BASE}/monitor/status`)
  const deadline = Date.now() + 120000
  while (!(await cameraRow().getByText('Đang xử lý').count())) {
    if (Date.now() > deadline) throw new Error('camera did not reach "Đang xử lý" in 120 s')
    await page.waitForTimeout(5000)
    await page.getByRole('button', { name: 'Làm mới' }).click()
  }
  await shot('3-status-running')
})
await step('Đăng xuất', logout)

await step('Giám sát viên đăng nhập', () => login('operator'))
await step('Tìm bằng ảnh', async () => {
  await page.goto(`${BASE}/search`)
  await page.getByText('Hình ảnh', { exact: true }).click()
  await page.locator('input[type="file"]').setInputFiles(QUERY)
  await page.getByRole('button', { name: 'Tìm kiếm' }).click()
  await page.getByText('kết quả phù hợp nhất').waitFor({ timeout: 90000 })
  await imagesLoaded()
  await shot('4-search-results')
})
await step('Mở kết quả đầu tiên', async () => {
  await page.locator('button[draggable="true"]').first().click()
  await page.getByRole('button', { name: 'Tạo vụ việc mới' }).waitFor()
  await imagesLoaded()
  await shot('5-result-viewer')
})
await step('Tạo vụ việc, đánh dấu hoàn thành khi lưu', async () => {
  await page.getByRole('button', { name: 'Tạo vụ việc mới' }).click()
  const dialog = page.getByRole('dialog', { name: 'Tạo vụ việc mới' })
  await dialog.getByLabel('Tiêu đề').fill(CASE_TITLE)
  await dialog.getByLabel('Ghi chú').fill('Đã xác định người trên nhiều camera khu Gate A.')
  await dialog.getByRole('switch', { name: 'Đánh dấu vụ việc đã hoàn thành' }).click()
  await shot('6-create-case')
  await dialog.getByRole('button', { name: 'Tạo vụ việc' }).click()
  await dialog.waitFor({ state: 'detached', timeout: 15000 })
  await page.getByRole('button', { name: 'Đóng' }).click()
})
await step('Xem vụ việc trong tab Hoàn thành', async () => {
  await page.goto(`${BASE}/cases`)
  await page.locator('.seg-opt', { hasText: 'Hoàn thành' }).click()
  await page.getByText(CASE_TITLE).first().click()
  await page.getByText('Kết quả đã lưu').waitFor()
  await imagesLoaded()
  await shot('7-case-closed')
})
await step('Đăng xuất', logout)

await step('Quản lý đăng nhập, xem dashboard', async () => {
  await login('viewer')
  await page.goto(`${BASE}/overview`)
  await page.getByText(CASE_TITLE).waitFor({ timeout: 30000 })
  await shot('8-dashboard')
})
await step('Mở hồ sơ vụ việc', async () => {
  await page.goto(`${BASE}/case-files`)
  await page.getByText(CASE_TITLE).first().click()
  await page.getByText('Kết quả đã lưu').waitFor()
  await imagesLoaded()
  await shot('9-case-file')
})
await step('Đăng xuất', logout)

await step('Quản trị viên tắt xử lý AI (kết thúc demo)', async () => {
  await login('admin')
  await page.goto(`${BASE}/admin/ai`)
  await cameraRow().getByRole('switch').click()
  await confirmDialog('Tắt xử lý AI').click()
  await cameraRow().getByRole('switch', { checked: false }).waitFor({ timeout: 15000 })
})

await context.close()
await browser.close()
const video = readdirSync(outDir).find((name) => name.endsWith('.webm'))
if (video) renameSync(`${outDir}${video}`, `${outDir}demo.webm`)
console.log(`\ntotal ${((Date.now() - started) / 1000).toFixed(0)}s, output ${outDir}`)
if (errors.length) console.log('errors:\n  ' + errors.slice(0, 10).join('\n  '))
process.exitCode = errors.length ? 1 : 0
