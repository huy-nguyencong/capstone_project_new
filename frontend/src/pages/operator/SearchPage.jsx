import { LockSimpleIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { SearchForm } from '@/features/search/SearchForm'
import { SearchResults } from '@/features/search/SearchResults'
import { searchesApi } from '@/services/api/searches'
import { useAppStore } from '@/store/hooks'
import { EMPTY_ATTRIBUTES, attributesToPrompt } from '@/constants/attributes'
import { validateSearch } from '@/utils/search'

const INITIAL = {
  method: 'text',
  imageUrl: null,
  imageFile: null,
  imageName: '',
  text: '',
  attrs: EMPTY_ATTRIBUTES,
  cams: [],
  from: '',
  to: '',
  topk: '8',
  error: null,
}

export default function SearchPage() {
  const { me } = useAppStore()
  const [form, setForm] = useState(INITIAL)
  const [outcome, setOutcome] = useState({ status: 'idle', runId: 0 })
  const [areaCameras, setAreaCameras] = useState([])

  useEffect(() => {
    let active = true
    searchesApi
      .cameras()
      .then(
        (items) =>
          active &&
          setAreaCameras(items.map((c) => ({ ...c, ai: c.ai_enabled, status: 'online' }))),
      )
      .catch((error) => active && setForm((f) => ({ ...f, error: error.message })))
    return () => {
      active = false
    }
  }, [])

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
    try {
      const response = await searchesApi.run(form)
      const label =
        response.mode === 'IMAGE'
          ? `Tìm bằng hình ảnh · ${form.imageName}`
          : response.mode === 'ATTRIBUTES'
            ? `Tìm theo đặc điểm · “${response.prompt || attributesToPrompt(form.attrs)}”`
            : `Tìm bằng mô tả · “${response.prompt}”`
      setOutcome({
        status: response.results.length ? 'done' : 'nodata',
        runId,
        results: response.results,
        label,
        topk: response.top_k,
      })
    } catch (apiError) {
      setOutcome({ status: 'idle', runId })
      setForm((f) => ({ ...f, error: apiError.message }))
    }
  }

  const runningMessage = `Đang tìm trong ${outcome.camCount} camera thuộc khu vực của bạn…`

  return (
    <>
      <PageHeader
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
