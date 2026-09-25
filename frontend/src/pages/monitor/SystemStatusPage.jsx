import { ArrowsClockwiseIcon, StethoscopeIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { MetricCard } from '@/components/ui/MetricCard'
import { PageHeader } from '@/components/ui/PageHeader'
import { KeyValueList, MasterDetail, SidePanel } from '@/components/ui/Panel'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { StatusDot } from '@/components/ui/StatusDot'
import { PATHS } from '@/constants/navigation'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { AREAS } from '@/mocks/areas'
import { useAppStore } from '@/store/hooks'
import { nowTime, wait } from '@/utils/format'

const FILTERS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'issue', label: 'Bất thường' },
  { value: 'conn', label: 'Lỗi kết nối' },
  { value: 'ai', label: 'Ngừng xử lý AI' },
]

const connBad = (c) => c.status === 'offline' || c.status === 'unverified'
const aiBad = (c) => c.aiState === 'error' || c.aiState === 'stopped'
const unknown = (c) => c.status === 'unknown'

const FILTER_FN = {
  all: () => true,
  issue: (c) => connBad(c) || aiBad(c) || unknown(c),
  conn: connBad,
  ai: aiBad,
}

const streamText = (c) => {
  if (c.status === 'online') return `${c.fps} fps · ${c.bitrate}`
  if (c.status === 'unknown') return 'Không xác định'
  return 'Không có tín hiệu'
}

const issueText = (c) => {
  if (c.aiState === 'error')
    return 'Tiến trình AI dừng bất thường lúc 09:15:03 — Tracker: CUDA out of memory.'
  if (c.status === 'offline') return 'Mất kết nối RTSP từ 08:57:40 — Connection timed out.'
  if (c.status === 'unknown') return 'Không lấy được trạng thái camera từ 07:12:05.'
  if (c.status === 'unverified') return 'Camera chưa từng kết nối thành công.'
  return null
}

export default function SystemStatusPage() {
  const { cameras, updateCamera } = useAppStore()
  const navigate = useNavigate()
  const [filter, setFilter] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [lastUpdated, setLastUpdated] = useState('09:48:12')
  const [refreshing, setRefreshing] = useState(false)

  const live = cameras.filter((c) => c.status !== 'retired')
  const rows = live.filter(FILTER_FN[filter])
  const selected = live.find((c) => c.id === selectedId)

  const refresh = async () => {
    setRefreshing(true)
    await wait(900)
    cameras
      .filter((c) => c.aiState === 'running')
      .forEach((c) => updateCamera(c.id, { latency: 70 + Math.round(Math.random() * 40) }))
    setLastUpdated(nowTime())
    setRefreshing(false)
  }

  const metrics = [
    {
      label: 'Hoạt động bình thường',
      tone: 'ok',
      value: live.filter((c) => c.status === 'online' && !aiBad(c)).length,
    },
    { label: 'Mất kết nối / chưa xác minh', tone: 'err', value: live.filter(connBad).length },
    { label: 'AI lỗi / ngừng xử lý', tone: 'warn', value: live.filter(aiBad).length },
    { label: 'Không xác định', tone: 'mute', value: live.filter(unknown).length },
  ]

  const columns = [
    {
      key: 'cam',
      header: 'Camera',
      render: (c) => <CellStack primary={c.name} secondary={AREAS[c.area]} />,
    },
    { key: 'conn', header: 'Kết nối', render: (c) => <StatusDot {...CAMERA_STATUS[c.status]} /> },
    {
      key: 'stream',
      header: 'Luồng RTSP',
      className: 'text-[13px] text-neutral-300',
      render: streamText,
    },
    { key: 'ai', header: 'Tiến trình AI', render: (c) => <StatusDot {...AI_STATE[c.aiState]} /> },
    {
      key: 'fps',
      header: 'FPS xử lý',
      className: 'text-[13px]',
      render: (c) => (c.aiState === 'running' ? `${c.procFps} fps` : '—'),
    },
    {
      key: 'lat',
      header: 'Độ trễ',
      className: 'text-[13px]',
      render: (c) => (c.latency ? `${c.latency} ms` : '—'),
    },
    {
      key: 'last',
      header: 'Tín hiệu cuối',
      className: 'text-[13px] text-neutral-300',
      render: (c) => c.last,
    },
  ]

  const detail = selected && (
    <SidePanel
      title={selected.name}
      subtitle={AREAS[selected.area]}
      onClose={() => setSelectedId(null)}
    >
      <KeyValueList
        items={[
          { k: 'Kết nối', v: CAMERA_STATUS[selected.status].label },
          { k: 'RTSP', v: `${selected.rtsp.replace(/:\d+.*/, '')}…` },
          { k: 'Độ phân giải', v: selected.res },
          {
            k: 'Luồng',
            v: selected.status === 'online' ? `${selected.fps} fps · ${selected.bitrate}` : '—',
          },
          { k: 'Xử lý AI', v: selected.ai ? 'Bật' : 'Tắt' },
          { k: 'Tiến trình', v: AI_STATE[selected.aiState].label },
          { k: 'Độ trễ', v: selected.latency ? `${selected.latency} ms` : '—' },
          { k: 'Tín hiệu cuối', v: selected.last },
        ]}
      />
      {issueText(selected) && (
        <div className="rounded-md bg-neutral-900 px-3 py-2.5 text-xs text-neutral-200">
          {issueText(selected)}
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

  return (
    <>
      <PageHeader
        kicker="UC-06 · Giám sát"
        title="Trạng thái hệ thống"
        description="Kết nối camera, luồng RTSP và tiến trình AI của từng camera."
      >
        <span className="text-xs text-neutral-400">Cập nhật lúc {lastUpdated}</span>
        <Button icon={ArrowsClockwiseIcon} onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Đang làm mới…' : 'Làm mới'}
        </Button>
      </PageHeader>

      <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-2.5">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>

      <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} className="mb-3" />

      <MasterDetail detail={detail}>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(c) => c.id}
          onRowClick={(c) => setSelectedId(c.id)}
          selectedKey={selectedId}
          emptyText="Không có camera nào khớp bộ lọc."
        />
      </MasterDetail>
    </>
  )
}
