import { ArrowsClockwiseIcon, StethoscopeIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { MetricCard } from '@/components/ui/MetricCard'
import { PageHeader } from '@/components/ui/PageHeader'
import { KeyValueList, MasterDetail, SidePanel } from '@/components/ui/Panel'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { StatusDot } from '@/components/ui/StatusDot'
import { PATHS } from '@/constants/navigation'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { monitorApi } from '@/services/api/monitor'

const FILTERS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'issue', label: 'Bất thường' },
  { value: 'connection_issues', label: 'Lỗi kết nối' },
  { value: 'ai_issues', label: 'Lỗi xử lý AI' },
]

const FILTER_FN = {
  all: () => true,
  issue: (c) => c.category !== 'healthy',
  connection_issues: (c) => c.category === 'connection_issues',
  ai_issues: (c) => c.category === 'ai_issues',
}

const WORKER_LABEL = {
  IDLE: { label: 'Chờ việc', tone: 'mute' },
  RUNNING: { label: 'Đang xử lý', tone: 'ok' },
  ERROR: { label: 'Mất tín hiệu', tone: 'err' },
}

const upDown = (state) =>
  state === 'UP' ? { label: 'Hoạt động', tone: 'ok' } : { label: 'Không khả dụng', tone: 'err' }

const ERROR_TEXT = {
  worker_heartbeat_lost: 'Worker không gửi tín hiệu, job đang chạy có thể đã dừng.',
  video_decode_failed: 'Không giải mã được video.',
  detector_failed: 'Detector lỗi khi xử lý video.',
  tracker_failed: 'Tracker lỗi khi xử lý video.',
  encoder_failed: 'Image Encoder lỗi khi xử lý video.',
  storage_ingestion_failed: 'Không lưu được track vào kho dữ liệu.',
  pipeline_unavailable: 'Không nạp được pipeline AI.',
  worker_retries_exhausted: 'Job thất bại sau nhiều lần thử lại.',
}

const timeFormatter = new Intl.DateTimeFormat('vi-VN', { timeStyle: 'medium' })

const metricText = (value, unit) => (value == null ? '—' : `${value} ${unit}`)

export default function SystemStatusPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState(null)
  const [filter, setFilter] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [refreshing, setRefreshing] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    monitorApi
      .systemStatus()
      .then((next) => {
        if (!active) return
        setStatus(next)
        setError(null)
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setRefreshing(false))
    return () => {
      active = false
    }
  }, [reloadKey])

  const refresh = () => {
    setRefreshing(true)
    setReloadKey((key) => key + 1)
  }

  const cameras = status?.cameras ?? []
  const rows = cameras.filter(FILTER_FN[filter])
  const selected = cameras.find((c) => c.id === selectedId)
  const summary = status?.summary ?? {}

  const metrics = [
    { label: 'Hoạt động bình thường', tone: 'ok', value: summary.healthy },
    { label: 'Mất kết nối', tone: 'err', value: summary.connection_issues },
    { label: 'Lỗi xử lý AI', tone: 'warn', value: summary.ai_issues },
    { label: 'Không xác định', tone: 'mute', value: summary.unknown },
  ]

  const columns = [
    {
      key: 'cam',
      header: 'Camera',
      render: (c) => <CellStack primary={c.name} secondary={c.areaName} />,
    },
    { key: 'conn', header: 'Kết nối', render: (c) => <StatusDot {...CAMERA_STATUS[c.status]} /> },
    { key: 'ai', header: 'Tiến trình AI', render: (c) => <StatusDot {...AI_STATE[c.aiState]} /> },
    {
      key: 'fps',
      header: 'FPS xử lý',
      className: 'text-[13px]',
      render: (c) => metricText(c.metrics.processed_fps, 'fps'),
    },
    {
      key: 'lat',
      header: 'Độ trễ',
      className: 'text-[13px]',
      render: (c) => metricText(c.metrics.latency_ms, 'ms'),
    },
    {
      key: 'last',
      header: 'Tín hiệu cuối',
      className: 'text-[13px] text-neutral-300',
      render: (c) => c.lastHeartbeat,
    },
  ]

  const detail = selected && (
    <SidePanel
      title={selected.name}
      subtitle={selected.areaName}
      onClose={() => setSelectedId(null)}
    >
      <KeyValueList
        items={[
          { k: 'Kết nối', v: CAMERA_STATUS[selected.status].label },
          { k: 'Kiểm tra RTSP gần nhất', v: selected.lastChecked },
          { k: 'Luồng', v: metricText(selected.metrics.source_fps, 'fps') },
          { k: 'Xử lý AI', v: selected.ai ? 'Bật' : 'Tắt' },
          { k: 'Tiến trình', v: AI_STATE[selected.aiState].label },
          { k: 'Job đang chạy', v: selected.activeJobId?.slice(0, 8) ?? '—', mono: true },
          { k: 'Tín hiệu cuối', v: selected.lastHeartbeat },
        ]}
      />
      {selected.lastError && (
        <div className="rounded-md bg-neutral-900 px-3 py-2.5 text-xs text-neutral-200">
          {ERROR_TEXT[selected.lastError] ?? selected.lastError}
        </div>
      )}
      <Button
        variant="primary"
        icon={StethoscopeIcon}
        disabled={!selected.ai}
        onClick={() => navigate(`${PATHS.diagnostics}?cam=${selected.id}`)}
      >
        Kiểm tra pipeline AI
      </Button>
    </SidePanel>
  )

  const infra = status && [
    ...Object.entries(status.storage).map(([name, state]) => ({
      k: { postgres: 'PostgreSQL', milvus: 'Milvus', minio: 'MinIO' }[name] ?? name,
      v: <StatusDot {...upDown(state)} />,
    })),
    { k: 'Encoder tìm kiếm', v: <StatusDot {...upDown(status.encoder)} /> },
    {
      k: 'Worker xử lý video',
      v: (
        <span className="flex items-center gap-2">
          <StatusDot {...WORKER_LABEL[status.worker.state]} />
          <span className="text-xs text-neutral-400">{status.worker.queue_depth} job chờ</span>
        </span>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        kicker="UC-06 · Giám sát"
        title="Trạng thái hệ thống"
        description="Kết nối camera, tiến trình AI và các dịch vụ lưu trữ, tìm kiếm."
      >
        {status && (
          <span className="text-xs text-neutral-400">
            Cập nhật lúc {timeFormatter.format(new Date(status.generatedAt))}
          </span>
        )}
        <Button icon={ArrowsClockwiseIcon} onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Đang làm mới…' : 'Làm mới'}
        </Button>
      </PageHeader>

      {error && <Alert className="mb-3">{error}</Alert>}

      <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-2.5">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} value={m.value ?? '—'} />
        ))}
      </div>

      {infra && (
        <div className="panel mb-4 max-w-[560px] p-4">
          <h5 className="mb-2">Dịch vụ nền</h5>
          <KeyValueList items={infra} />
        </div>
      )}

      <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} className="mb-3" />

      <MasterDetail detail={detail}>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(c) => c.id}
          onRowClick={(c) => setSelectedId(c.id)}
          selectedKey={selectedId}
          emptyText={status ? 'Không có camera nào khớp bộ lọc.' : 'Đang tải…'}
        />
      </MasterDetail>
    </>
  )
}
