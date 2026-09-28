import { useCallback, useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { useCameraAdmin } from '@/hooks/useCameraAdmin'
import { aiApi, camerasApi } from '@/services/api/cameras'
import { monitorApi } from '@/services/api/monitor'
import { ArrowRightIcon, StackIcon } from '@phosphor-icons/react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusDot } from '@/components/ui/StatusDot'
import { Switch } from '@/components/ui/Switch'
import { PATHS } from '@/constants/navigation'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { useConfirm, useToast } from '@/store/hooks'

export default function AiProcessingPage() {
  const { cameras, error, loading, nextCursor, load } = useCameraAdmin()
  const [models, setModels] = useState(null)
  const [busy, setBusy] = useState({})
  // Worker state per camera, from the same source as the system status page.
  const [workerStates, setWorkerStates] = useState({})
  const loadWorkerStates = useCallback(
    () =>
      monitorApi
        .systemStatus()
        .then((status) =>
          setWorkerStates(Object.fromEntries(status.cameras.map((c) => [c.id, c.aiState]))),
        )
        .catch(() => setWorkerStates({})),
    [],
  )
  useEffect(() => {
    loadWorkerStates()
  }, [loadWorkerStates])
  const confirm = useConfirm()
  const toast = useToast()
  const navigate = useNavigate()
  useEffect(() => {
    let live = true
    aiApi
      .config()
      .then((value) => {
        if (live) setModels(value)
      })
      .catch((e) => {
        if (live) toast(e.message, 'err')
      })
    return () => {
      live = false
    }
  }, [toast])
  const det = models?.detector_id || 'Chưa cấu hình'
  const trk = models?.tracker_id || 'Chưa cấu hình'

  const toggle = (c) => {
    if (c.status === 'retired') {
      toast('Camera đã bị loại khỏi vận hành, không thể bật/tắt xử lý AI.', 'err')
      return
    }
    const on = !c.ai
    confirm({
      title: on ? 'Bật xử lý AI?' : 'Tắt xử lý AI?',
      body: on
        ? `Cho phép xử lý dữ liệu từ ${c.name} với Detector ${det} và Tracker ${trk}.`
        : `Camera ${c.name} sẽ không nhận tác vụ mới. Dữ liệu đã phân tích trước đó được giữ nguyên.`,
      label: on ? 'Bật xử lý AI' : 'Tắt xử lý AI',
      onConfirm: async () => {
        setBusy((old) => ({ ...old, [c.id]: true }))
        try {
          await camerasApi.state(c.id, on)
          await Promise.all([load(), loadWorkerStates()])
          toast(on ? 'Đã bật quyền xử lý AI cho camera.' : 'Đã tắt quyền xử lý AI cho camera.')
        } catch (e) {
          toast(e.message, 'err')
        } finally {
          setBusy((old) => ({ ...old, [c.id]: false }))
        }
      },
    })
  }

  const columns = [
    { key: 'name', header: 'Camera', className: 'text-sm', render: (c) => c.name },
    { key: 'area', header: 'Khu vực', className: 'text-[13px]', render: (c) => c.area.name },
    {
      key: 'conn',
      header: 'Kết nối RTSP',
      render: (c) => <StatusDot {...CAMERA_STATUS[c.status]} />,
    },
    {
      key: 'ai',
      header: 'Tiến trình AI',
      render: (c) => <StatusDot {...AI_STATE[c.ai ? workerStates[c.id] || c.aiState : 'off']} />,
    },
    {
      key: 'toggle',
      header: 'Xử lý AI',
      align: 'right',
      render: (c) => (
        <Switch
          checked={c.ai}
          disabled={c.lifecycle !== 'ACTIVE' || busy[c.id]}
          onChange={() => toggle(c)}
          label={
            c.status === 'retired'
              ? 'Camera đã ngừng vận hành'
              : c.ai
                ? 'Tắt xử lý AI'
                : 'Bật xử lý AI'
          }
        />
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="Xử lý AI trên camera"
        description="Bật hoặc tắt phân tích AI cho từng camera. Tắt xử lý không xóa dữ liệu đã phân tích."
      />

      <div className="panel mb-3.5 flex flex-wrap items-center gap-3.5 px-4 py-3 text-[13px]">
        <StackIcon size={16} className="text-accent" />
        <span className="text-muted">Cấu hình hiện hành</span>
        <span>
          Detector <strong className="font-medium">{det}</strong>
        </span>
        <span>
          Tracker <strong className="font-medium">{trk}</strong>
        </span>
        <Button
          variant="ghost"
          iconRight={ArrowRightIcon}
          className="ml-auto"
          onClick={() => navigate(PATHS.models)}
        >
          Đổi mô hình
        </Button>
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
        rows={cameras}
        rowKey={(c) => c.id}
        rowClassName={(c) => c.status === 'retired' && 'opacity-45'}
      />
      {nextCursor && (
        <Button disabled={loading} onClick={() => load(nextCursor)}>
          Tải thêm
        </Button>
      )}
    </>
  )
}
