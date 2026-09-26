import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { SelectField, TextField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { jobsApi } from '@/services/api/jobs'
import { camerasApi } from '@/services/api/cameras'
import { useToast } from '@/store/hooks'

const STATES = {
  PENDING: 'Đang chờ',
  RUNNING: 'Đang xử lý',
  SUCCEEDED: 'Hoàn tất',
  FAILED: 'Thất bại',
  CANCELLED: 'Đã hủy',
}
const active = (job) => ['PENDING', 'RUNNING'].includes(job.status)
const date = (value) => (value ? new Date(value).toLocaleString('vi-VN') : '—')

export default function VideoProcessingPage() {
  const toast = useToast()
  const [cameras, setCameras] = useState([])
  const [camera, setCamera] = useState('')
  const [recorded, setRecorded] = useState('')
  const [samplingProfile, setSamplingProfile] = useState('throughput')
  const [file, setFile] = useState(null)
  const [jobs, setJobs] = useState([])
  const [cursor, setCursor] = useState(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [cameraError, setCameraError] = useState(null)
  const [pollError, setPollError] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const [cancelling, setCancelling] = useState({})
  const [selected, setSelected] = useState(null)
  const key = useRef(null)
  const input = useRef(null)
  const mounted = useRef(false)
  const generation = useRef(0)
  const currentJobs = useRef(jobs)
  useEffect(() => {
    currentJobs.current = jobs
  }, [jobs])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      generation.current += 1
    }
  }, [])
  useEffect(() => {
    let live = true
    async function loadCameras() {
      try {
        const all = []
        let next
        do {
          const page = await camerasApi.list({ status: 'ACTIVE', limit: 100, cursor: next })
          all.push(...page.items)
          next = page.nextCursor
        } while (next && live)
        if (live) {
          setCameras(all.filter((item) => item.ai))
          setCameraError(null)
        }
      } catch (e) {
        if (live) setCameraError(e.message)
      }
    }
    loadCameras()
    return () => {
      live = false
    }
  }, [refresh])
  const load = useCallback(async (next = null) => {
    const requestId = ++generation.current
    setLoading(true)
    try {
      const page = await jobsApi.list({ cursor: next, limit: 20 })
      if (!mounted.current || requestId !== generation.current) return
      setJobs((old) =>
        next
          ? [...old, ...page.items.filter((item) => !old.some((job) => job.id === item.id))]
          : page.items,
      )
      setCursor(page.next_cursor)
      setError(null)
    } catch (e) {
      if (mounted.current && requestId === generation.current) setError(e.message)
    } finally {
      if (mounted.current && requestId === generation.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    const timer = setTimeout(() => load(), 0)
    return () => clearTimeout(timer)
  }, [load, refresh])
  useEffect(() => {
    let disposed = false
    let timer
    async function poll() {
      try {
        const pending = currentJobs.current.filter(active)
        const results = await Promise.all(pending.map((job) => jobsApi.get(job.id)))
        if (disposed) return
        const byId = new Map(results.map((job) => [job.id, job]))
        setJobs((old) => old.map((job) => byId.get(job.id) || job))
        setSelected((old) => (old ? byId.get(old.id) || old : null))
        setPollError(null)
      } catch (e) {
        if (!disposed) setPollError(e.message)
      } finally {
        if (!disposed) timer = setTimeout(poll, 3000)
      }
    }
    timer = setTimeout(poll, 3000)
    return () => {
      disposed = true
      clearTimeout(timer)
    }
  }, [])
  const changed = (setter) => (e) => {
    key.current = null
    setter(e.target.value)
  }
  const upload = async (e) => {
    e.preventDefault()
    if (!file || !camera || !recorded) {
      setError('Chọn camera, video và thời điểm bắt đầu ghi.')
      return
    }
    if (!key.current) key.current = crypto.randomUUID()
    const data = new FormData()
    data.append('file', file)
    data.append('recorded_started_at', new Date(recorded).toISOString())
    data.append('sampling_profile', samplingProfile)
    setUploading(true)
    setProgress(0)
    setError(null)
    try {
      const job = await jobsApi.upload(camera, data, key.current, (value) => {
        if (mounted.current) setProgress(value)
      })
      if (!mounted.current) return
      setJobs((old) => [job, ...old.filter((item) => item.id !== job.id)])
      setSelected(job)
      setFile(null)
      key.current = null
      if (input.current) input.current.value = ''
      toast('Đã nhận video và đưa vào hàng đợi.')
    } catch (e) {
      if (mounted.current) setError(e.message)
    } finally {
      if (mounted.current) setUploading(false)
    }
  }
  const cancel = async (job) => {
    setCancelling((old) => ({ ...old, [job.id]: true }))
    try {
      const updated = await jobsApi.cancel(job.id)
      if (!mounted.current) return
      setJobs((old) => old.map((item) => (item.id === job.id ? updated : item)))
      setSelected((old) => (old?.id === job.id ? updated : old))
      toast(updated.status === 'CANCELLED' ? 'Đã hủy tác vụ.' : 'Đã gửi yêu cầu hủy.')
    } catch (e) {
      if (mounted.current) setError(e.message)
    } finally {
      if (mounted.current) setCancelling((old) => ({ ...old, [job.id]: false }))
    }
  }
  const columns = [
    {
      key: 'camera',
      header: 'Camera / tác vụ',
      render: (job) => (
        <button className="text-left text-sm" onClick={() => setSelected(job)}>
          {job.camera.name}
          <span className="text-muted block text-xs">
            {job.id.slice(0, 8)}
            {job.pipeline_mode === 'DEMO' ? ' · Demo giả lập' : ''}
          </span>
        </button>
      ),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (job) => (job.cancel_requested && active(job) ? 'Đang hủy…' : STATES[job.status]),
    },
    {
      key: 'progress',
      header: 'Khung hình',
      render: (job) => (
        <span>
          {job.processed_frames} / {job.total_frames ?? '—'}
          <span className="text-muted block text-xs">{job.sampled_frames} đã lấy mẫu</span>
        </span>
      ),
    },
    {
      key: 'tracks',
      header: 'Track',
      render: (job) =>
        `${job.tracks_ready} sẵn sàng · ${job.tracks_failed} lỗi · ${job.tracks_pending} chờ lưu`,
    },
    { key: 'created', header: 'Đã nhận', render: (job) => date(job.created_at) },
    {
      key: 'actions',
      header: '',
      render: (job) =>
        active(job) && (
          <Button disabled={job.cancel_requested || cancelling[job.id]} onClick={() => cancel(job)}>
            Hủy tác vụ
          </Button>
        ),
    },
  ]
  return (
    <>
      <PageHeader
        title="Xử lý video"
        description="Tải video lên camera đang bật AI và theo dõi tiến độ xử lý."
      >
        <Button disabled={loading} onClick={() => setRefresh((old) => old + 1)}>
          Làm mới
        </Button>
      </PageHeader>
      {cameraError && <Alert>{cameraError}</Alert>}
      <form onSubmit={upload} className="panel mb-5 flex flex-col gap-4 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <SelectField
            label="Camera"
            value={camera}
            onChange={changed(setCamera)}
            disabled={uploading}
            placeholder="— Chọn camera —"
            options={cameras.map((item) => ({
              value: item.id,
              label: `${item.code} · ${item.name}`,
            }))}
          />
          <TextField
            label="Bắt đầu ghi (giờ địa phương)"
            type="datetime-local"
            step="1"
            required
            value={recorded}
            onChange={changed(setRecorded)}
            disabled={uploading}
          />
          <SelectField
            label="Chế độ lấy mẫu"
            value={samplingProfile}
            onChange={changed(setSamplingProfile)}
            disabled={uploading}
            options={[
              { value: 'baseline', label: 'Cân bằng · mỗi 10 khung hình' },
              { value: 'throughput', label: 'Nhanh · mỗi 20 khung hình' },
            ]}
          />
        </div>
        <label className="text-sm">
          Video MP4, MKV hoặc AVI
          <input
            ref={input}
            type="file"
            accept=".mp4,.mkv,.avi"
            disabled={uploading}
            className="mt-2 block w-full"
            onChange={(e) => {
              setFile(e.target.files[0] || null)
              key.current = null
            }}
          />
        </label>
        {!cameras.length && !cameraError && (
          <p className="text-muted text-sm">
            Chưa có camera đủ điều kiện. Thêm camera, áp dụng mô hình và bật AI trước.
          </p>
        )}
        {uploading && (
          <div role="status">
            <progress className="w-full" max="100" value={progress ?? undefined} />
            <p className="text-sm">
              {progress === 100
                ? 'Đã gửi file, máy chủ đang kiểm tra video…'
                : `Đang tải lên${progress == null ? '…' : ` ${progress}%`}`}
            </p>
          </div>
        )}
        <Button type="submit" variant="primary" disabled={uploading || !file || !camera}>
          {uploading ? 'Đang tải…' : 'Tải lên và xử lý'}
        </Button>
      </form>
      {error && <Alert>{error}</Alert>}
      {pollError && <Alert>Chưa cập nhật được tiến độ: {pollError}. Hệ thống sẽ thử lại.</Alert>}
      {loading && <p className="text-muted text-sm">Đang tải tác vụ…</p>}
      <div className="overflow-x-auto [&_table]:min-w-[850px]">
        <DataTable
          columns={columns}
          rows={jobs}
          rowKey={(job) => job.id}
          emptyText={loading ? undefined : 'Chưa có tác vụ. Tải video lên để bắt đầu.'}
        />
      </div>
      {cursor && (
        <Button disabled={loading} onClick={() => load(cursor)}>
          Tải thêm
        </Button>
      )}
      {selected && (
        <section className="panel mt-4 p-4" aria-label="Chi tiết tác vụ">
          <div className="flex justify-between gap-3">
            <h3>
              {selected.camera.name} · {selected.id.slice(0, 8)}
            </h3>
            <Button onClick={() => setSelected(null)}>Đóng</Button>
          </div>
          {selected.pipeline_mode === 'DEMO' && (
            <p className="my-2 text-sm">
              Demo giả lập: track và embedding tổng hợp dùng để kiểm tra luồng, không phải kết quả
              nhận diện người.
            </p>
          )}
          <p className="text-sm">
            {STATES[selected.status]} · Ghi từ {date(selected.recorded_started_at)} · Lấy mẫu mỗi{' '}
            {selected.sampling_interval} frame
          </p>
          <p className="text-muted text-sm">
            Bắt đầu xử lý: {date(selected.started_at)} · Kết thúc: {date(selected.ended_at)}
          </p>
          {selected.error_message && (
            <Alert>
              {selected.error_message} ({selected.error_code})
            </Alert>
          )}
        </section>
      )}
    </>
  )
}
