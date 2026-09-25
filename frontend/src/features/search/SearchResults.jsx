import { DatabaseIcon, InfoIcon, UsersThreeIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Form'
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
        Không có dữ liệu đã phân tích trong camera hoặc khoảng thời gian đã chọn. Thử mở rộng phạm
        vi.
      </EmptyState>
    )
  }

  if (status !== 'done') {
    return (
      <EmptyState icon={UsersThreeIcon} title="Chưa có tìm kiếm">
        Chọn phương thức, cung cấp thông tin người cần tìm và bấm Tìm kiếm. Kết quả được xếp theo
        Điểm phù hợp — mỗi kết quả là một lần xuất hiện (track) trên một camera.
      </EmptyState>
    )
  }

  const described = results.map(describeSearchResult)
  const rank = new Map(described.map((r, i) => [r.id, i + 1]))
  let list = described
  if (camFilter !== 'all') list = list.filter((r) => r.camId === camFilter)
  if (sort === 'time') {
    list = [...list].sort((a, b) => b.appearedAt.localeCompare(a.appearedAt))
  }
  const viewerItems = list.map((result) => ({ rid: result.id, score: result.score, result }))

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
            {list.length} kết quả{camFilter !== 'all' && ' (đã lọc)'} · top_k = {topk}
          </div>
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
            onOpen={() => setViewerIndex(i)}
          />
        ))}
      </div>

      {viewerIndex != null && (
        <ResultViewer
          items={viewerItems}
          index={viewerIndex}
          context="search"
          onIndexChange={setViewerIndex}
          onClose={() => setViewerIndex(null)}
        />
      )}
    </>
  )
}
