import { MagnifyingGlassIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { SelectField, TextField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { Spinner } from '@/components/ui/Spinner'
import { PATHS } from '@/constants/navigation'
import { CaseDetail } from '@/features/cases/CaseDetail'
import { CaseList } from '@/features/cases/CaseList'
import { casesApi } from '@/services/api/cases'
import { viewerApi } from '@/services/api/viewer'

const COPY = {
  operator: {
    kicker: 'UC-11 · Điều tra',
    title: 'Case của tôi',
    desc: 'Các Case do bạn phụ trách: tiêu đề, ghi chú và kết quả tìm kiếm đã lưu.',
    empty: 'Bạn chưa có Case nào. Tạo Case từ một kết quả trong trang Tìm kiếm.',
  },
  viewer: {
    kicker: 'UC-13 · UC-14 · Báo cáo',
    title: 'Hồ sơ vụ việc',
    desc: 'Toàn bộ Case trên hệ thống, chế độ chỉ xem.',
    empty: 'Không có Case nào phù hợp.',
  },
}

const PAGE_SIZE = 20

const OWNER_STATUS = {
  locked: 'đã khóa',
  inactive: 'ngừng hoạt động',
  deleted: 'đã xóa',
}

const localDayToUtc = (day, end) =>
  day ? new Date(`${day}T${end ? '23:59:59.999' : '00:00:00'}`).toISOString() : undefined

const listParams = (filters) => ({
  owner_user_id: filters.op || undefined,
  created_from: localDayToUtc(filters.from, false),
  created_to: localDayToUtc(filters.to, true),
  limit: PAGE_SIZE,
})

export default function CaseBrowserPage({ mode }) {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState({ op: '', from: '', to: '' })
  const [cases, setCases] = useState([])
  const [operators, setOperators] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const isOperator = mode === 'operator'
  const copy = COPY[mode]

  useEffect(() => {
    let active = true
    casesApi
      .list(listParams(filters))
      .then((page) => {
        if (!active) return
        setCases(page.items)
        setNextCursor(page.nextCursor)
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [filters])

  useEffect(() => {
    if (isOperator) return undefined
    let active = true
    viewerApi
      .operators()
      .then((items) => active && setOperators(items))
      .catch((requestError) => active && setError(requestError.message))
    return () => {
      active = false
    }
  }, [isOperator])

  const selectedId = params.get('case') || cases[0]?.id

  useEffect(() => {
    if (!selectedId) return undefined
    let active = true
    casesApi
      .get(selectedId)
      .then((next) => active && setDetail(next))
      .catch(
        (requestError) =>
          active && setDetailError({ id: selectedId, message: requestError.message }),
      )
    return () => {
      active = false
    }
  }, [selectedId])

  const loadMore = async () => {
    setLoading(true)
    try {
      const page = await casesApi.list({ ...listParams(filters), cursor: nextCursor })
      setCases((items) => [...items, ...page.items])
      setNextCursor(page.nextCursor)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const applyChange = (next) => {
    setDetail(next)
    setCases((items) => items.map((c) => (c.id === next.case.id ? next.case : c)))
  }

  const setFilter = (key) => (e) => {
    setLoading(true)
    setError(null)
    setFilters((f) => ({ ...f, [key]: e.target.value }))
  }

  return (
    <>
      <PageHeader kicker={copy.kicker} title={copy.title} description={copy.desc}>
        {isOperator && (
          <Button icon={MagnifyingGlassIcon} onClick={() => navigate(PATHS.search)}>
            Tìm thêm kết quả
          </Button>
        )}
      </PageHeader>

      {!isOperator && (
        <div className="mb-3.5 flex flex-wrap items-end gap-2.5">
          <SelectField
            label="Operator phụ trách"
            className="min-w-[200px]"
            value={filters.op}
            onChange={setFilter('op')}
            placeholder="Tất cả Operator"
            options={operators.map((op) => ({
              value: op.id,
              label: op.status === 'active' ? op.name : `${op.name} (${OWNER_STATUS[op.status]})`,
            }))}
          />
          <TextField label="Tạo từ" type="date" value={filters.from} onChange={setFilter('from')} />
          <TextField label="Đến" type="date" value={filters.to} onChange={setFilter('to')} />
          {loading && <Spinner className="mb-2.5 text-neutral-400" />}
        </div>
      )}

      {error && <Alert className="mb-3">{error}</Alert>}

      <div className="grid items-start gap-[18px] lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          <CaseList
            cases={cases}
            selectedId={selectedId}
            onSelect={(id) => setParams({ case: id }, { replace: true })}
            metaFor={(c) => `${isOperator ? '' : `${c.owner.name} · `}Cập nhật ${c.updated}`}
            emptyText={loading ? 'Đang tải Case…' : copy.empty}
          />
          {nextCursor && (
            <Button onClick={loadMore} disabled={loading}>
              Tải thêm
            </Button>
          )}
        </div>
        {detailError?.id === selectedId && detail?.case.id !== selectedId && (
          <Alert>{detailError.message}</Alert>
        )}
        {detail && detail.case.id === selectedId && (
          <CaseDetail
            key={detail.case.id}
            detail={detail}
            editable={isOperator}
            onChange={applyChange}
          />
        )}
      </div>
    </>
  )
}
