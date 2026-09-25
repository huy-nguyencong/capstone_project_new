import { MagnifyingGlassIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { SelectField, TextField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { PATHS } from '@/constants/navigation'
import { CaseDetail } from '@/features/cases/CaseDetail'
import { CaseList } from '@/features/cases/CaseList'
import { useAppStore } from '@/store/hooks'
import { byUpdatedDesc, dmyToIso } from '@/utils/format'

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

export default function CaseBrowserPage({ mode }) {
  const { me, users, cases } = useAppStore()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState({ op: '', from: '', to: '' })
  const isOperator = mode === 'operator'
  const copy = COPY[mode]

  const userName = (id) => users.find((u) => u.id === id)?.name ?? '—'

  const list = cases
    .filter((c) => {
      if (isOperator) return c.owner === me.id
      const updated = dmyToIso(c.updated)
      return (
        (!filters.op || c.owner === filters.op) &&
        (!filters.from || updated >= filters.from) &&
        (!filters.to || updated <= filters.to)
      )
    })
    .sort(byUpdatedDesc)

  const current = list.find((c) => c.id === params.get('case')) ?? list[0]
  const owners = [...new Set(cases.map((c) => c.owner))]
  const setFilter = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }))

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
            options={owners.map((id) => ({ value: id, label: userName(id) }))}
          />
          <TextField
            label="Cập nhật từ"
            type="date"
            value={filters.from}
            onChange={setFilter('from')}
          />
          <TextField label="Đến" type="date" value={filters.to} onChange={setFilter('to')} />
        </div>
      )}

      <div className="grid items-start gap-[18px] lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
        <CaseList
          cases={list}
          selectedId={current?.id}
          onSelect={(id) => setParams({ case: id }, { replace: true })}
          metaFor={(c) => `${isOperator ? '' : `${userName(c.owner)} · `}Cập nhật ${c.updated}`}
          emptyText={copy.empty}
        />
        {current && <CaseDetail key={current.id} caseFile={current} editable={isOperator} />}
      </div>
    </>
  )
}
