import { ArrowsClockwiseIcon, CaretRightIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { MetricCard } from '@/components/ui/MetricCard'
import { PageHeader } from '@/components/ui/PageHeader'
import { Tag } from '@/components/ui/Tag'
import { PATHS } from '@/constants/navigation'
import { viewerApi } from '@/services/api/viewer'
import { nowTime } from '@/utils/format'

const OWNER_NOTE = {
  locked: 'Đã khóa',
  inactive: 'Ngừng hoạt động',
  deleted: 'Đã xóa',
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [refreshing, setRefreshing] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    viewerApi
      .dashboard()
      .then((next) => {
        if (!active) return
        setDashboard(next)
        setLastUpdated(nowTime())
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

  const columns = [
    {
      key: 'case',
      header: 'Case',
      render: (c) => <CellStack primary={c.title} secondary={c.code} mono />,
    },
    {
      key: 'owner',
      header: 'Operator phụ trách',
      className: 'text-[13px]',
      render: (c) => (
        <span className="flex items-center gap-2">
          {c.owner.name}
          {OWNER_NOTE[c.owner.status] && <Tag>{OWNER_NOTE[c.owner.status]}</Tag>}
        </span>
      ),
    },
    { key: 'count', header: 'Kết quả', className: 'text-[13px]', render: (c) => c.resultCount },
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
        title="Tổng quan"
        description="Case và kết quả đã lưu trên toàn hệ thống."
      >
        {lastUpdated && (
          <span className="text-xs text-neutral-400">Cập nhật lúc {lastUpdated}</span>
        )}
        <Button icon={ArrowsClockwiseIcon} onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Đang làm mới…' : 'Làm mới'}
        </Button>
      </PageHeader>

      {error && <Alert className="mb-3">{error}</Alert>}

      <div className="mb-[26px] grid max-w-[720px] grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3">
        <MetricCard label="Tổng số Case" value={dashboard?.totalCases ?? '—'} size="lg" highlight />
        <MetricCard
          label="Kết quả đã lưu vào Case"
          value={dashboard?.totalCaseResults ?? '—'}
          size="lg"
        />
      </div>

      <h5 className="mb-2">Case gần đây</h5>
      <DataTable
        columns={columns}
        rows={dashboard?.recentCases ?? []}
        rowKey={(c) => c.id}
        onRowClick={(c) => navigate(`${PATHS.caseFiles}?case=${c.id}`)}
        emptyText={dashboard ? 'Chưa có Case nào.' : 'Đang tải…'}
      />
    </>
  )
}
