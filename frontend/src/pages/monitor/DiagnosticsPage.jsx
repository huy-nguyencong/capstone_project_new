import {
  CheckCircleIcon,
  MagnifyingGlassIcon,
  MinusCircleIcon,
  PlayIcon,
  VideoCameraIcon,
  WarningCircleIcon,
  XCircleIcon,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { OptionCard } from '@/components/ui/Chip'
import { SelectField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { Spinner } from '@/components/ui/Spinner'
import { CAMERA_STATUS, TONE } from '@/constants/status'
import { camerasApi } from '@/services/api/cameras'
import { monitorApi } from '@/services/api/monitor'
import { summarizeDiagnostic, toDiagnosticSteps } from '@/utils/diagnostics'
import { pad } from '@/utils/format'

const GROUPS = [
  {
    id: 'pipeline',
    name: 'Camera Processing Pipeline',
    icon: VideoCameraIcon,
    flow: 'Nguồn khung hình → Detector → Tracker → Image Encoder',
    note: 'Chọn một camera đang bật xử lý AI.',
  },
  {
    id: 'search',
    name: 'Search Components',
    icon: MagnifyingGlassIcon,
    flow: 'Text Encoder · Image Encoder · Kho dữ liệu',
    note: 'Không cần chọn camera.',
  },
]

const STEP = {
  ok: { icon: CheckCircleIcon, color: TONE.ok, label: 'Hoạt động' },
  fail: { icon: XCircleIcon, color: TONE.err, label: 'Lỗi' },
  warn: { icon: WarningCircleIcon, color: TONE.warn, label: 'Chưa xác minh' },
  skip: { icon: MinusCircleIcon, color: 'var(--color-neutral-500)', label: 'Bỏ qua' },
}

const SUMMARY_ICON = { ok: CheckCircleIcon, warn: WarningCircleIcon, err: XCircleIcon }

export default function DiagnosticsPage() {
  const [params] = useSearchParams()
  const [aiCams, setAiCams] = useState([])
  const [group, setGroup] = useState('pipeline')
  const [camId, setCamId] = useState(params.get('cam') ?? '')
  const [steps, setSteps] = useState(null)
  const [summary, setSummary] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    camerasApi
      .list({ status: 'ACTIVE', limit: 100 })
      .then((page) => {
        if (!active) return
        const enabled = page.items.filter((c) => c.ai)
        setAiCams(enabled)
        setCamId((current) =>
          enabled.some((c) => c.id === current) ? current : (enabled[0]?.id ?? ''),
        )
      })
      .catch((requestError) => active && setError(requestError.message))
    return () => {
      active = false
    }
  }, [])

  const reset = () => {
    setSteps(null)
    setSummary(null)
    setError(null)
  }

  const run = async () => {
    if (group === 'pipeline' && !camId) return setError('Chọn một camera đang bật xử lý AI.')
    reset()
    setRunning(true)
    try {
      const report =
        group === 'pipeline'
          ? await monitorApi.cameraPipeline(camId)
          : await monitorApi.searchComponents()
      const next = toDiagnosticSteps(report)
      setSteps(next)
      setSummary(summarizeDiagnostic(report, next))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRunning(false)
    }
  }

  const SummaryIcon = summary && SUMMARY_ICON[summary.tone]

  return (
    <>
      <PageHeader
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
            placeholder={aiCams.length ? undefined : 'Không có camera bật AI'}
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

      {error && <Alert className="mb-3 max-w-[880px]">{error}</Alert>}

      {running && (
        <div className="panel flex max-w-[880px] items-center gap-3 px-4 py-3.5 text-sm">
          <Spinner className="text-accent" />
          Đang kiểm tra các thành phần…
        </div>
      )}

      {steps && (
        <div className="panel flex max-w-[880px] flex-col">
          {steps.map((s, i) => {
            const st = STEP[s.state]
            return (
              <div
                key={`${i}-${s.name}`}
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
