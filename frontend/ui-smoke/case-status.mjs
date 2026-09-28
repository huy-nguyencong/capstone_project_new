// Case status filter check (desktop): the "Hoàn thành" tab must never show a stale case detail,
// and closing then reopening a case must move it between the tabs.
//
// Writes data: closes the first OPEN case of the operator, then reopens it, so the case ends as it
// started (two audit rows are added). Needs the API, `npm run dev` and at least one OPEN case.
//
//   npm run ui:case-status
import { chromium } from 'playwright-core'

const BASE = process.env.UI_SMOKE_BASE || 'http://localhost:5173'
const PASSWORD = process.env.UI_SMOKE_PASSWORD || 'password'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
const failures = []

const tab = async (name) => {
  await page.locator('.seg-opt', { hasText: name }).click()
  await page.waitForTimeout(800)
}
// Case cards start with the short case code, which is unique.
const listCodes = async () =>
  (await page.locator('button.option-card').allInnerTexts()).map((text) => text.split('\n')[0])
const detailShown = async () => (await page.getByText('Kết quả đã lưu').count()) > 0
const expect = (label, condition) => {
  console.log(condition ? 'ok  ' : 'FAIL', label)
  if (!condition) failures.push(label)
}

await page.goto(`${BASE}/login`)
await page.getByLabel('Tên đăng nhập').fill('operator')
await page.getByLabel('Mật khẩu').fill(PASSWORD)
await page.getByRole('button', { name: 'Đăng nhập' }).click()
await page.waitForURL(/search/)
await page.goto(`${BASE}/cases`)
await page.waitForTimeout(800)

await tab('Hoàn thành')
const closedBefore = await listCodes()
expect(
  'closed tab shows no detail when it has no case',
  closedBefore.length > 0 || !(await detailShown()),
)

await tab('Đang xử lý')
const openCodes = await listCodes()
if (!openCodes.length) {
  console.log('No OPEN case to close; skipping the close/reopen part.')
} else {
  const code = openCodes[0]
  await page.locator('button.option-card').first().click()
  await page.getByRole('button', { name: 'Đánh dấu hoàn thành' }).click()
  await page.getByRole('button', { name: 'Đánh dấu hoàn thành' }).last().click()
  await page.waitForTimeout(800)
  await tab('Hoàn thành')
  expect(`case ${code} appears under Hoàn thành after closing`, (await listCodes()).includes(code))

  await page.locator('button.option-card', { hasText: code }).click()
  await page.getByRole('button', { name: 'Mở lại vụ việc' }).click()
  await page.getByRole('button', { name: 'Mở lại', exact: true }).click()
  await page.waitForTimeout(800)
  expect(`case ${code} leaves Hoàn thành after reopening`, !(await listCodes()).includes(code))
  expect(
    'no stale detail left on Hoàn thành',
    (await listCodes()).length > 0 || !(await detailShown()),
  )
  await tab('Đang xử lý')
  expect(`case ${code} is back under Đang xử lý`, (await listCodes()).includes(code))
}

expect('no page errors', pageErrors.length === 0)
await browser.close()
process.exitCode = failures.length ? 1 : 0
