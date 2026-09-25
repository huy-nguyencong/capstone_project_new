import {
  CheckCircleIcon,
  CircleDashedIcon,
  MagnifyingGlassIcon,
  MinusCircleIcon,
  PlayIcon,
  VideoCameraIcon,
  WarningCircleIcon,
  XCircleIcon,
} from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { OptionCard } from '@/components/ui/Chip'
import { SelectField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { Spinner } from '@/components/ui/Spinner'
import { CAMERA_STATUS, TONE } from '@/constants/status'
import { useAppStore } from '@/store/hooks'
import { buildDiagnosticPlan, summarizeDiagnostic } from '@/utils/diagnostics'
import { pad } from '@/utils/format'

const GROUPS = [
  {
    id: 'pipeline',
    name: 'Camera Processing Pipeline',
    icon: VideoCameraIcon,
    flow: 'RTSP → Detector → Tracker → Image Encoder',
    note: 'Chọn một camera đang bật xử lý AI.',
  },
  {
    id: 'search',
    name: 'Search Components',
    icon: MagnifyingGlassIcon,
    flow: 'Image Encoder · Text Encoder',
    note: 'Không cần chọn camera.',
  },
]

const STEP = {
  pending: { icon: CircleDashedIcon, color: 'var(--color-neutral-500)', label: 'Chờ' },
  running: { icon: Spinner, color: 'var(--color-accent)', label: 'Đang kiểm tra' },
  ok: { icon: CheckCircleIcon, color: TONE.ok, label: 'Hoạt động' },
  fail: { icon: XCircleIcon, color: TONE.err, label: 'Lỗi' },
  warn: { icon: WarningCircleIcon, color: TONE.warn, label: 'Chưa xác minh' },
  skip: { icon: MinusCircleIcon, color: 'var(--color-neutral-500)', label: 'Bỏ qua' },
}

const SUMMARY_ICON = { ok: CheckCircleIcon, warn: WarningCircleIcon, err: XCircleIcon }

export default function DiagnosticsPage() {
  const { cameras, models } = useAppStore()
  const [params] = useSearchParams()
  const aiCams = cameras.filter((c) => c.ai && c.status !== 'retired')
  const initialCam = aiCams.some((c) => c.id === params.get('cam'))
    ? params.get('cam')
    : aiCams[0]?.id
  const [group, setGroup] = useState('pipeline')
  const [camId, setCamId] = useState(initialCam ?? '')
  const [steps, setSteps] = useState(null)
  const [summary, setSummary] = useState(null)
  const [running, setRunning] = useState(false)
  const timers = useRef([])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const reset = () => {
    setSteps(null)
    setSummary(null)
  }

  const run = () => {
    const plan = buildDiagnosticPlan(
      group,
      cameras.find((c) => c.id === camId),
      models,
    )
    const patch = (i, next) =>
      setSteps((prev) => prev.map((s, j) => (j === i ? { ...s, ...next } : s)))
    setRunning(true)
    setSummary(null)
    setSteps(plan.map((p) => ({ name: p.name, state: 'pending', msg: '' })))
    plan.forEach((p, i) => {
      timers.current.push(
        setTimeout(() => patch(i, { state: 'running', msg: 'Đang kiểm tra…' }), i * 650 + 60),
      )
      timers.current.push(
        setTimeout(
          () => {
            patch(i, { state: p.out, msg: p.msg })
            if (i === plan.length - 1) {
              setRunning(false)
              setSummary(summarizeDiagnostic(plan))
            }
          },
          i * 650 + 560,
        ),
      )
    })
  }

  const SummaryIcon = summary && SUMMARY_ICON[summary.tone]

  return (
    <>
      <PageHeader
        kicker="UC-07 · Giám sát"
        title="Kiểm tra hoạt động của AI"
        description="Kiểm tra độc lập hai nhóm thành phần. Kết quả phản ánh trạng thái hoạt động, không đánh giá độ chính xác mô hình."
      />

      <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-3">
        {GROUPS.map((g) => (
          <OptionCard
            key={g.id}
            active={group === g.id}
            className="gap-1.5 p-4"
            onClick={() => {
              if (running) return
              setGroup(g.id)
              reset()
            }}
          >
            <div className="flex items-center gap-2">
              <g.icon size={18} className="text-accent" />
              <span className="text-[15px] font-medium">{g.name}</span>
            </div>
            <div className="font-mono text-xs text-neutral-300">{g.flow}</div>
            <div className="text-xs text-neutral-400">{g.note}</div>
          </OptionCard>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        {group === 'pipeline' && (
          <SelectField
            label="Camera đang bật xử lý AI"
            className="min-w-[260px]"
            value={camId}
            onChange={(e) => {
              setCamId(e.target.value)
              reset()
            }}
            options={aiCams.map((c) => ({
              value: c.id,
              label: `${c.name} · ${CAMERA_STATUS[c.status].label}`,
            }))}
          />
        )}
        <Button variant="primary" icon={PlayIcon} className="h-9" onClick={run} disabled={running}>
          {running ? 'Đang kiểm tra…' : 'Chạy kiểm tra'}
        </Button>
      </div>

      {steps && (
        <div className="panel flex max-w-[880px] flex-col">
          {steps.map((s, i) => {
            const st = STEP[s.state]
            return (
              <div
                key={s.name}
                className="flex items-center gap-3.5 px-4 py-3.5 shadow-[inset_0_-1px_0_color-mix(in_srgb,var(--color-text)_7%,transparent)]"
              >
                <span className="font-mono text-xs text-neutral-500">{pad(i + 1)}</span>
                <span className="flex" style={{ color: st.color }}>
                  <st.icon size={20} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm">{s.name}</div>
                  <div className="text-xs text-neutral-400">{s.msg || '—'}</div>
                </div>
                <span className="text-xs" style={{ color: st.color }}>
                  {st.label}
                </span>
              </div>
            )
          })}
          {summary && (
            <div className="flex items-center gap-2.5 px-4 py-3.5 text-[13px]">
              <SummaryIcon size={16} style={{ color: TONE[summary.tone] }} />
              {summary.text}
            </div>
          )}
        </div>
      )}
    </>
  )
}
