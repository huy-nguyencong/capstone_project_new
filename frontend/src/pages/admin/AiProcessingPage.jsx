import { ArrowRightIcon, StackIcon } from '@phosphor-icons/react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusDot } from '@/components/ui/StatusDot'
import { Switch } from '@/components/ui/Switch'
import { PATHS } from '@/constants/navigation'
import { AI_STATE, CAMERA_STATUS } from '@/constants/status'
import { AREAS } from '@/mocks/areas'
import { detectorName, trackerName } from '@/mocks/models'
import { useAppStore, useConfirm, useToast } from '@/store/hooks'

export default function AiProcessingPage() {
  const { cameras, models, updateCamera, log } = useAppStore()
  const confirm = useConfirm()
  const toast = useToast()
  const navigate = useNavigate()
  const det = detectorName(models.det)
  const trk = trackerName(models.trk)

  const toggle = (c) => {
    if (c.status === 'retired') {
      toast('Camera đã bị loại khỏi vận hành, không thể bật/tắt xử lý AI.', 'err')
      return
    }
    const on = !c.ai
    confirm({
      title: on ? 'Bật xử lý AI?' : 'Tắt xử lý AI?',
      body: on
        ? `Hệ thống sẽ khởi động tiến trình phân tích cho ${c.name} với Detector ${det} và Tracker ${trk}.`
        : `Tiến trình phân tích của ${c.name} sẽ dừng. Dữ liệu đã phân tích trước đó được giữ nguyên.`,
      label: on ? 'Bật xử lý AI' : 'Tắt xử lý AI',
      onConfirm: () => {
        if (!on) {
          updateCamera(c.id, { ai: false, aiState: 'off', procFps: 0, latency: null })
          log('Xử lý AI', 'Tắt xử lý AI', c.name)
          toast(`Đã dừng xử lý AI cho ${c.name}. Dữ liệu cũ được giữ nguyên.`)
          return
        }
        if (c.status !== 'online') {
          log('Xử lý AI', 'Bật xử lý AI', c.name, false, 'Camera không khả dụng')
          toast(
            `Không thể bật: ${c.name} đang ở trạng thái "${CAMERA_STATUS[c.status].label}". Tiến trình chưa được khởi động.`,
            'err',
          )
          return
        }
        updateCamera(c.id, { ai: true, aiState: 'starting' })
        log('Xử lý AI', 'Bật xử lý AI', c.name)
        setTimeout(() => {
          updateCamera(c.id, { aiState: 'running', procFps: 12, latency: 88 })
          toast(`Đã khởi động xử lý AI cho ${c.name}.`)
        }, 1300)
      },
    })
  }

  const columns = [
    { key: 'name', header: 'Camera', className: 'text-sm', render: (c) => c.name },
    { key: 'area', header: 'Khu vực', className: 'text-[13px]', render: (c) => AREAS[c.area] },
    {
      key: 'conn',
      header: 'Kết nối RTSP',
      render: (c) => <StatusDot {...CAMERA_STATUS[c.status]} />,
    },
    { key: 'ai', header: 'Tiến trình AI', render: (c) => <StatusDot {...AI_STATE[c.aiState]} /> },
    {
      key: 'toggle',
      header: 'Xử lý AI',
      align: 'right',
      render: (c) => (
        <Switch
          checked={c.ai}
          disabled={c.status === 'retired'}
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
        kicker="UC-04 · Quản trị"
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

      <DataTable
        columns={columns}
        rows={cameras}
        rowKey={(c) => c.id}
        rowClassName={(c) => c.status === 'retired' && 'opacity-45'}
      />
    </>
  )
}
