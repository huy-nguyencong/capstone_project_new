import { DatabaseIcon, InfoIcon, UsersThreeIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Select } from '@/components/ui/Form'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Spinner } from '@/components/ui/Spinner'
import { ResultCard } from '@/components/person/ResultCard'
import { ResultViewer } from '@/features/results/ResultViewer'
import { describeSearchResult } from '@/utils/results'

const SORTS = [
  { value: 'score', label: 'Điểm phù hợp' },
  { value: 'time', label: 'Thời gian' },
]

export function SearchResults({ status, results, queryLabel, topk, runningMessage, areaCameras }) {
  const [camFilter, setCamFilter] = useState('all')
  const [timeFrom, setTimeFrom] = useState('')
  const [timeTo, setTimeTo] = useState('')
  const [sort, setSort] = useState('score')
  const [viewerIndex, setViewerIndex] = useState(null)

  if (status === 'running') {
    return (
      <div className="flex items-center gap-2.5 px-2 py-12 text-sm text-neutral-300">
        <Spinner />
        {runningMessage}
      </div>
    )
  }

  if (status === 'nodata') {
    return (
      <EmptyState icon={DatabaseIcon} title="Không có dữ liệu phù hợp để tìm kiếm">
        Chưa có dữ liệu đã được phân tích trong camera hoặc khoảng thời gian đã chọn. Hãy chọn thêm
        camera hoặc mở rộng khoảng thời gian.
      </EmptyState>
    )
  }

  if (status !== 'done') {
    return (
      <EmptyState icon={UsersThreeIcon} title="Chưa có tìm kiếm">
        Chọn cách tìm, cung cấp ảnh hoặc mô tả người cần tìm rồi bấm Tìm kiếm. Kết quả được xếp theo
        điểm phù hợp; mỗi kết quả là một lần người đó xuất hiện trên một camera.
      </EmptyState>
    )
  }

  const described = results.map(describeSearchResult)
  const rank = new Map(described.map((r, i) => [r.id, i + 1]))
  let list = described
  if (camFilter !== 'all') list = list.filter((r) => r.camId === camFilter)
  // UC-10 A2: narrow the current result set by local appearance time, without a new search.
  if (timeFrom) list = list.filter((r) => new Date(r.appearedAt) >= new Date(timeFrom))
  if (timeTo) list = list.filter((r) => new Date(r.appearedAt) <= new Date(timeTo))
  const filtered = camFilter !== 'all' || Boolean(timeFrom || timeTo)
  // Area and day are the same on every card for an Operator's single area; show them once.
  const days = new Set(described.map((r) => r.day))
  const sameDay = days.size === 1
  const scope = [
    described[0] && `Khu vực ${described[0].area}`,
    sameDay && described[0]?.day,
  ].filter(Boolean)
  if (sort === 'time') {
    list = [...list].sort((a, b) => b.appearedAt.localeCompare(a.appearedAt))
  }

  const camOptions = [
    { value: 'all', label: 'Tất cả camera' },
    ...areaCameras
      .filter((c) => described.some((r) => r.camId === c.id))
      .map((c) => ({ value: c.id, label: c.name })),
  ]

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <div className="min-w-[220px] flex-1">
          <div className="text-[15px]">
            {filtered
              ? `Đang hiển thị ${list.length} / ${described.length} kết quả`
              : `${list.length} kết quả phù hợp nhất`}
            {described.length < topk && (
              <span className="text-neutral-400">
                {' '}
                · chỉ có {described.length} kết quả trong phạm vi tìm kiếm
              </span>
            )}
          </div>
          {scope.length > 0 && <div className="text-xs text-neutral-300">{scope.join(' · ')}</div>}
          <div className="text-xs text-neutral-400">{queryLabel}</div>
        </div>
        <Select
          value={camFilter}
          onChange={(e) => setCamFilter(e.target.value)}
          options={camOptions}
          className="w-auto min-w-[170px]"
        />
        <SegmentedControl options={SORTS} value={sort} onChange={setSort} />
      </div>

      <div className="mb-3 flex flex-wrap items-end gap-2 text-xs text-neutral-400">
        <span className="basis-full">Lọc theo thời gian xuất hiện</span>
        <label className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-none">
          Từ
          <Input
            type="datetime-local"
            step="1"
            value={timeFrom}
            onChange={(e) => setTimeFrom(e.target.value)}
            className="w-full sm:w-auto"
          />
        </label>
        <label className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-none">
          Đến
          <Input
            type="datetime-local"
            step="1"
            value={timeTo}
            onChange={(e) => setTimeTo(e.target.value)}
            className="w-full sm:w-auto"
          />
        </label>
        {(timeFrom || timeTo) && (
          <button
            type="button"
            className="text-accent-300"
            onClick={() => {
              setTimeFrom('')
              setTimeTo('')
            }}
          >
            Bỏ lọc thời gian
          </button>
        )}
      </div>

      <div className="mb-3.5 flex items-center gap-2 text-xs text-neutral-400">
        <InfoIcon size={14} />
        Điểm phù hợp chỉ hỗ trợ xếp hạng, không phải kết luận danh tính. Hãy quan sát ảnh để đánh
        giá.
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(148px,1fr))] gap-3">
        {list.map((result, i) => (
          <ResultCard
            key={result.id}
            result={result}
            rank={rank.get(result.id)}
            showDate={!sameDay}
            onOpen={() => setViewerIndex(i)}
          />
        ))}
      </div>

      {viewerIndex != null && (
        <ResultViewer
          items={list}
          index={viewerIndex}
          context="search"
          onIndexChange={setViewerIndex}
          onClose={() => setViewerIndex(null)}
        />
      )}
    </>
  )
}
