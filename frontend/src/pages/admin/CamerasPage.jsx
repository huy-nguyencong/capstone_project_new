import { ArchiveIcon, PencilSimpleIcon, PlugsConnectedIcon, PlusIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button, IconButton } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { PageHeader } from '@/components/ui/PageHeader'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Dot, StatusDot } from '@/components/ui/StatusDot'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { AREAS, areaShort } from '@/mocks/areas'
import { isRtspReachable } from '@/mocks/cameras'
import { useAppStore, useConfirm, useToast } from '@/store/hooks'
import { wait } from '@/utils/format'
import { CameraDialog } from './CameraDialog'

const AREA_FILTERS = [
  { value: 'all', label: 'Tất cả' },
  ...AREAS.map((_, i) => ({ value: String(i), label: areaShort(i) })),
]

function CameraThumb({ status }) {
  return (
    <div className="relative h-9 w-16 flex-none rounded-sm bg-[linear-gradient(180deg,var(--color-neutral-800),var(--color-bg))] shadow-sm">
      <Dot tone={CAMERA_STATUS[status].tone} size={5} className="absolute right-1 bottom-1" />
    </div>
  )
}

export default function CamerasPage() {
  const { cameras, updateCamera, log } = useAppStore()
  const confirm = useConfirm()
  const toast = useToast()
  const [area, setArea] = useState('all')
  const [testing, setTesting] = useState({})
  const [editing, setEditing] = useState(undefined)

  const rows = cameras.filter((c) => area === 'all' || String(c.area) === area)
  const activeCount = rows.filter((c) => c.status !== 'retired').length

  const testRow = async (c) => {
    setTesting((t) => ({ ...t, [c.id]: true }))
    await wait(1100)
    const ok = isRtspReachable(c.rtsp)
    setTesting((t) => ({ ...t, [c.id]: false }))
    updateCamera(
      c.id,
      ok
        ? { status: 'online', fps: c.fps || 25, bitrate: c.bitrate || '3.6 Mbps', last: 'vừa xong' }
        : { status: c.status === 'unverified' ? 'unverified' : 'offline' },
    )
    log('Camera', 'Kiểm tra kết nối', c.name, ok, ok ? undefined : 'RTSP timeout sau 10s')
    toast(
      ok
        ? `${c.name}: kết nối RTSP thành công.`
        : `${c.name}: không thể kết nối RTSP. Kiểm tra địa chỉ, thông tin xác thực hoặc mạng.`,
      ok ? 'ok' : 'err',
    )
  }

  const retire = (c) =>
    confirm({
      title: 'Loại camera khỏi vận hành?',
      body: `${c.name} sẽ ngừng tạo dữ liệu AI mới và không được chọn cho truy vấn mới. Embedding, frame, bounding box và kết quả đã lưu trong Case được giữ nguyên.`,
      label: 'Loại khỏi vận hành',
      onConfirm: () => {
        updateCamera(c.id, { status: 'retired', ai: false, aiState: 'off' })
        log('Camera', 'Loại camera khỏi vận hành', c.name)
        toast(`Đã loại ${c.name} khỏi vận hành. Dữ liệu lịch sử được giữ lại.`)
      },
    })

  const columns = [
    {
      key: 'camera',
      header: 'Camera',
      render: (c) => (
        <div className="flex items-center gap-3">
          <CameraThumb status={c.status} />
          <CellStack primary={c.name} secondary={c.res} />
        </div>
      ),
    },
    { key: 'area', header: 'Khu vực', className: 'text-[13px]', render: (c) => AREAS[c.area] },
    {
      key: 'rtsp',
      header: 'Địa chỉ RTSP',
      className: 'font-mono text-xs text-neutral-300',
      render: (c) => c.rtsp,
    },
    { key: 'status', header: 'Kết nối', render: (c) => <StatusDot {...CAMERA_STATUS[c.status]} /> },
    {
      key: 'ai',
      header: 'Xử lý AI',
      className: 'text-[13px] text-neutral-300',
      render: (c) => (c.ai ? AI_STATE[c.aiState].label : 'Đã tắt'),
    },
    {
      key: 'actions',
      header: 'Thao tác',
      align: 'right',
      render: (c) =>
        c.status === 'retired' ? (
          <span className="text-xs text-neutral-500">Giữ dữ liệu lịch sử</span>
        ) : (
          <div className="inline-flex gap-0.5">
            <Button
              variant="quiet"
              icon={PlugsConnectedIcon}
              className="text-xs"
              disabled={testing[c.id]}
              onClick={() => testRow(c)}
            >
              {testing[c.id] ? 'Đang kiểm tra…' : 'Kiểm tra'}
            </Button>
            <IconButton icon={PencilSimpleIcon} label="Chỉnh sửa" onClick={() => setEditing(c)} />
            <IconButton icon={ArchiveIcon} label="Loại khỏi vận hành" onClick={() => retire(c)} />
          </div>
        ),
    },
  ]

  return (
    <>
      <PageHeader
        kicker="UC-03 · Quản trị"
        title="Camera"
        description="Camera kết nối qua RTSP. Camera không kết nối được vẫn có thể lưu ở trạng thái Chưa xác minh."
      >
        <Button variant="primary" icon={PlusIcon} onClick={() => setEditing(null)}>
          Thêm camera
        </Button>
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <SegmentedControl options={AREA_FILTERS} value={area} onChange={setArea} />
        <span className="text-xs text-neutral-400">{activeCount} camera đang vận hành</span>
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(c) => c.id}
        rowClassName={(c) => c.status === 'retired' && 'opacity-50'}
      />

      {editing !== undefined && (
        <CameraDialog camera={editing} onClose={() => setEditing(undefined)} />
      )}
    </>
  )
}
