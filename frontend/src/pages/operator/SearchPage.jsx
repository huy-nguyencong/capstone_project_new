import { LockSimpleIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { SearchForm } from '@/features/search/SearchForm'
import { SearchResults } from '@/features/search/SearchResults'
import { mockAreaIndex } from '@/mocks/areas'
import { useAppStore } from '@/store/hooks'
import { wait } from '@/utils/format'
import { runMockSearch, validateSearch } from '@/utils/search'

const INITIAL = {
  method: 'text',
  imageUrl: null,
  imageName: '',
  sample: false,
  text: 'người mặc áo đỏ, quần đen, mang ba lô',
  attrs: { shirt: null, pants: null, type: null, bag: null },
  cams: [],
  from: '2026-09-23',
  to: '2026-09-25',
  topk: '24',
  error: null,
}

export default function SearchPage() {
  const { me, cameras } = useAppStore()
  const [form, setForm] = useState(INITIAL)
  const [outcome, setOutcome] = useState({ status: 'idle', runId: 0 })

  const areaCameras = cameras.filter(
    (c) => c.area === mockAreaIndex(me.area) && c.status !== 'retired',
  )

  const run = async () => {
    const error = validateSearch(form)
    if (error) return setForm((f) => ({ ...f, error }))
    const runId = outcome.runId + 1
    setOutcome({
      status: 'running',
      runId,
      method: form.method,
      camCount: form.cams.length || areaCameras.length,
    })
    await wait(900)
    const ids = areaCameras
      .filter((c) => !form.cams.length || form.cams.includes(c.id))
      .map((c) => c.id)
    const { results, label } = runMockSearch(form, ids)
    setOutcome({
      status: results ? 'done' : 'nodata',
      runId,
      results,
      label,
      topk: form.topk,
    })
  }

  const runningMessage = `Đang mã hóa truy vấn bằng ${outcome.method === 'image' ? 'Image Encoder' : 'Text Encoder'} và so khớp trong ${outcome.camCount} camera thuộc khu vực của bạn…`

  return (
    <>
      <PageHeader
        kicker="UC-09 · UC-10 · Điều tra"
        title="Tìm kiếm người"
        description="Tìm bằng ảnh crop, mô tả văn bản hoặc thuộc tính ngoại hình trong dữ liệu đã được AI phân tích."
      >
        <div className="flex items-center gap-2 rounded-md px-3 py-[7px] text-xs shadow-sm">
          <LockSimpleIcon size={14} className="text-accent" />
          <span className="text-muted">Khu vực giám sát</span>
          <span>{me.area?.name}</span>
        </div>
      </PageHeader>

      <div className="flex flex-wrap items-start gap-[18px]">
        <SearchForm
          state={form}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
          areaCameras={areaCameras}
          running={outcome.status === 'running'}
          onRun={run}
        />
        <div className="min-w-0 flex-[999_1_480px]">
          <SearchResults
            key={outcome.runId}
            status={outcome.status}
            results={outcome.results}
            queryLabel={outcome.label}
            topk={outcome.topk}
            runningMessage={runningMessage}
            areaCameras={areaCameras}
          />
        </div>
      </div>
    </>
  )
}
