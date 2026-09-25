import { LockSimpleIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { SearchForm } from '@/features/search/SearchForm'
import { SearchResults } from '@/features/search/SearchResults'
import { searchesApi } from '@/services/api/searches'
import { useAppStore } from '@/store/hooks'
import { attributesToPrompt, validateSearch } from '@/utils/search'

const INITIAL = {
  method: 'text',
  imageUrl: null,
  imageFile: null,
  imageName: '',
  text: 'người mặc áo đỏ, quần đen, mang ba lô',
  attrs: { shirt: null, pants: null, type: null, bag: null },
  cams: [],
  from: '2026-09-23',
  to: '2026-09-25',
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
          ? `Hình ảnh · ${form.imageName} · ${response.encoder_version}`
          : response.mode === 'ATTRIBUTES'
            ? `Thuộc tính · ${response.prompt || attributesToPrompt(form.attrs)} · ${response.encoder_version}`
            : `Văn bản · “${response.prompt}” · ${response.encoder_version}`
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

  const runningMessage = `Đang mã hóa truy vấn bằng ${outcome.method === 'image' ? 'Image Encoder' : 'Text Encoder'} và so khớp trong ${outcome.camCount} camera thuộc khu vực của bạn…`

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
