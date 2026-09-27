import {
  ArchiveIcon,
  ArrowCounterClockwiseIcon,
  PencilSimpleIcon,
  PlugsConnectedIcon,
  PlusIcon,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Button, IconButton } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { PageHeader } from '@/components/ui/PageHeader'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Dot, StatusDot } from '@/components/ui/StatusDot'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { camerasApi } from '@/services/api/cameras'
import { usersApi } from '@/services/api/users'
import { useCameraAdmin } from '@/hooks/useCameraAdmin'
import { Alert } from '@/components/ui/Alert'
import { useConfirm, useToast } from '@/store/hooks'
import { CameraDialog } from './CameraDialog'

function CameraThumb({ status }) {
  return (
    <div className="relative hidden h-9 w-16 flex-none rounded-sm bg-[linear-gradient(180deg,var(--color-neutral-800),var(--color-bg))] shadow-sm sm:block">
      <Dot tone={CAMERA_STATUS[status].tone} size={5} className="absolute right-1 bottom-1" />
    </div>
  )
}

export default function CamerasPage() {
  const confirm = useConfirm()
  const toast = useToast()
  const [area, setArea] = useState('all')
  const { cameras, error, loading, nextCursor, load } = useCameraAdmin(area)
  const [areas, setAreas] = useState([])
  useEffect(() => {
    let live = true
    usersApi
      .areas()
      .then((items) => {
        if (live) setAreas(items)
      })
      .catch((e) => {
        if (live) toast(e.message, 'err')
      })
    return () => {
      live = false
    }
  }, [toast])
  const areaFilters = [
    { value: 'all', label: 'Tất cả' },
    ...areas.map((a) => ({ value: a.id, label: a.name })),
  ]
  const [testing, setTesting] = useState({})
  const [editing, setEditing] = useState(undefined)

  const rows = cameras
  const activeCount = rows.filter((c) => c.status !== 'retired').length

  const testRow = async (c) => {
    setTesting((t) => ({ ...t, [c.id]: true }))
    try {
      const result = await camerasApi.test(c.id)
      toast(result.message, result.rtsp_status === 'ONLINE' ? 'ok' : 'warn')
      await load()
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setTesting((t) => ({ ...t, [c.id]: false }))
    }
  }

  const retire = (c) =>
    confirm({
      title: 'Loại camera khỏi vận hành?',
      body: `${c.name} sẽ ngừng nhận luồng để xử lý và lưu trữ. Dữ liệu đã phân tích (đặc trưng, khung hình, vị trí người và thông tin đi kèm) được giữ nguyên nhưng tạm thời không được tìm kiếm cho đến khi camera vận hành trở lại. Kết quả đã lưu trong vụ việc vẫn xem được.`,
      label: 'Loại khỏi vận hành',
      onConfirm: async () => {
        try {
          await camerasApi.retire(c.id)
          await load()
          toast(`Đã loại ${c.name} khỏi vận hành.`)
        } catch (e) {
          toast(e.message, 'err')
        }
      },
    })

  const reactivate = (c) =>
    confirm({
      title: 'Đưa camera vận hành trở lại?',
      body: `${c.name} trở lại vận hành với xử lý AI ở trạng thái tắt. Dữ liệu đã tạo trước đó được tìm kiếm lại bình thường.`,
      label: 'Đưa vào vận hành',
      onConfirm: async () => {
        try {
          await camerasApi.reactivate(c.id)
          await load()
          toast(`Đã đưa ${c.name} vận hành trở lại. Bật xử lý AI tại trang Xử lý AI.`)
        } catch (e) {
          toast(e.message, 'err')
        }
      },
    })

  const columns = [
    {
      key: 'camera',
      header: 'Camera',
      render: (c) => (
        <div className="flex items-center gap-3">
          <CameraThumb status={c.status} />
          <CellStack primary={c.name} secondary={c.code} />
        </div>
      ),
    },
    { key: 'area', header: 'Khu vực', className: 'text-[13px]', render: (c) => c.area.name },
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
          <Button
            variant="quiet"
            icon={ArrowCounterClockwiseIcon}
            className="text-xs"
            onClick={() => reactivate(c)}
          >
            Đưa vào vận hành
          </Button>
        ) : (
          <div className="inline-flex gap-0.5">
            <Button
              variant="quiet"
              icon={PlugsConnectedIcon}
              className="text-xs"
              disabled={testing[c.id] || !c.hasRtsp}
              onClick={() => testRow(c)}
            >
              {testing[c.id] ? 'Đang kiểm tra…' : 'Kiểm tra'}
            </Button>
            <IconButton
              icon={PencilSimpleIcon}
              label="Chỉnh sửa"
              onClick={async () => {
                try {
                  setEditing(await camerasApi.get(c.id))
                } catch (e) {
                  toast(e.message, 'err')
                }
              }}
            />
            <IconButton icon={ArchiveIcon} label="Loại khỏi vận hành" onClick={() => retire(c)} />
          </div>
        ),
    },
  ]

  return (
    <>
      <PageHeader
        title="Camera"
        description="Camera kết nối qua RTSP. Camera không kết nối được vẫn có thể lưu ở trạng thái Chưa xác minh."
      >
        <Button variant="primary" icon={PlusIcon} onClick={() => setEditing(null)}>
          Thêm camera
        </Button>
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <SegmentedControl options={areaFilters} value={area} onChange={setArea} />
        <span className="text-xs text-neutral-400">
          {activeCount} camera đang vận hành trong trang đã tải
        </span>
      </div>

      {error && (
        <Alert>
          {error}
          <Button onClick={() => load()}>Thử lại</Button>
        </Alert>
      )}
      {loading && <p className="text-muted text-sm">Đang tải…</p>}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(c) => c.id}
        rowClassName={(c) => c.status === 'retired' && 'opacity-50'}
      />

      {nextCursor && (
        <Button disabled={loading} onClick={() => load(nextCursor)}>
          Tải thêm
        </Button>
      )}
      {editing !== undefined && (
        <CameraDialog
          onSaved={() => load()}
          camera={editing}
          onClose={() => setEditing(undefined)}
        />
      )}
    </>
  )
}
