import { ArrowsClockwiseIcon, CaretRightIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { MetricCard } from '@/components/ui/MetricCard'
import { PageHeader } from '@/components/ui/PageHeader'
import { PATHS } from '@/constants/navigation'
import { useAppStore } from '@/store/hooks'
import { byUpdatedDesc, nowTime, wait } from '@/utils/format'

export default function OverviewPage() {
  const { cases, users } = useAppStore()
  const navigate = useNavigate()
  const [lastUpdated, setLastUpdated] = useState('09:50:02')
  const [refreshing, setRefreshing] = useState(false)

  const recent = [...cases].sort(byUpdatedDesc).slice(0, 6)
  const totalItems = cases.reduce((n, c) => n + c.items.length, 0)
  const userName = (id) => users.find((u) => u.id === id)?.name ?? '—'

  const refresh = async () => {
    setRefreshing(true)
    await wait(800)
    setLastUpdated(nowTime())
    setRefreshing(false)
  }

  const columns = [
    {
      key: 'case',
      header: 'Case',
      render: (c) => <CellStack primary={c.title} secondary={c.id} mono />,
    },
    {
      key: 'owner',
      header: 'Operator phụ trách',
      className: 'text-[13px]',
      render: (c) => userName(c.owner),
    },
    { key: 'count', header: 'Kết quả', className: 'text-[13px]', render: (c) => c.items.length },
    {
      key: 'updated',
      header: 'Cập nhật gần nhất',
      className: 'text-[13px] text-neutral-300',
      render: (c) => c.updated,
    },
    {
      key: 'go',
      header: '',
      align: 'right',
      className: 'text-neutral-400',
      render: () => <CaretRightIcon size={14} className="inline" />,
    },
  ]

  return (
    <>
      <PageHeader
        kicker="UC-12 · Báo cáo"
        title="Tổng quan"
        description="Case và kết quả đã lưu trên toàn hệ thống."
      >
        <span className="text-xs text-neutral-400">Cập nhật lúc {lastUpdated}</span>
        <Button icon={ArrowsClockwiseIcon} onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Đang làm mới…' : 'Làm mới'}
        </Button>
      </PageHeader>

      <div className="mb-[26px] grid max-w-[720px] grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3">
        <MetricCard label="Tổng số Case" value={cases.length} size="lg" highlight />
        <MetricCard label="Kết quả đã lưu vào Case" value={totalItems} size="lg" />
      </div>

      <h5 className="mb-2">Case gần đây</h5>
      <DataTable
        columns={columns}
        rows={recent}
        rowKey={(c) => c.id}
        onRowClick={(c) => navigate(`${PATHS.caseFiles}?case=${c.id}`)}
      />
    </>
  )
}
