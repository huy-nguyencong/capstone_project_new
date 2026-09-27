import { useCallback, useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { OptionCard } from '@/components/ui/Chip'
import { PageHeader } from '@/components/ui/PageHeader'
import { Tag } from '@/components/ui/Tag'
import { aiApi } from '@/services/api/cameras'
import { useToast } from '@/store/hooks'

export default function ModelsPage() {
  const toast = useToast()
  const [registry, setRegistry] = useState(null)
  const [config, setConfig] = useState(null)
  const [selected, setSelected] = useState({ detector_id: null, tracker_id: null })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let live = true
    Promise.all([aiApi.models(), aiApi.config()])
      .then(([models, active]) => {
        if (!live) return
        setRegistry(models)
        setConfig(active)
        setSelected(active)
        setError(null)
      })
      .catch((e) => {
        if (live) setError(e.message)
      })
    return () => {
      live = false
    }
  }, [reload])
  const retry = useCallback(() => setReload((old) => old + 1), [])
  const detector = registry?.detectors.find((m) => m.id === selected.detector_id)
  const tracker = registry?.trackers.find((m) => m.id === selected.tracker_id)
  const compatible = tracker?.compatible_detectors?.includes(selected.detector_id)
  const unchanged =
    selected.detector_id === config?.detector_id && selected.tracker_id === config?.tracker_id
  const apply = async () => {
    setBusy(true)
    setError(null)
    try {
      const active = await aiApi.apply({
        detector_id: selected.detector_id,
        tracker_id: selected.tracker_id,
        version: config.version,
      })
      setConfig(active)
      setSelected(active)
      toast('Đã áp dụng cấu hình AI cho tác vụ mới.')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeader
        title="Cấu hình mô hình AI"
        description="Chọn Detector và Tracker dùng chung toàn hệ thống. Image Encoder và Text Encoder là thành phần cố định."
      />
      {error && (
        <Alert>
          {error}
          <Button disabled={busy} onClick={retry}>
            Tải lại
          </Button>
        </Alert>
      )}
      {!registry && !error && <p>Đang tải cấu hình…</p>}
      {registry && (
        <>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-5">
            {['detectors', 'trackers'].map((kind) => {
              const key = kind === 'detectors' ? 'detector_id' : 'tracker_id'
              return (
                <div key={kind} className="flex flex-col gap-2">
                  <h5>{kind === 'detectors' ? 'Detector' : 'Tracker'}</h5>
                  {!registry[kind].length && (
                    <p className="text-muted text-sm">Chưa có mô hình được đăng ký.</p>
                  )}
                  {registry[kind].map((model) => (
                    <OptionCard
                      key={model.id}
                      active={selected[key] === model.id}
                      disabled={!model.available || busy}
                      onPick={() => setSelected((old) => ({ ...old, [key]: model.id }))}
                    >
                      <div className="text-sm font-medium">
                        {model.name}{' '}
                        {config?.[key] === model.id && <Tag variant="accent">Đang dùng</Tag>}{' '}
                        {!model.available && <Tag>Không khả dụng</Tag>}
                      </div>
                      <div className="text-muted text-xs">{model.description}</div>
                      <div className="text-muted text-xs">{model.meta}</div>
                    </OptionCard>
                  ))}
                </div>
              )
            })}
          </div>
          <div className="panel my-4 flex flex-col gap-1 p-4 text-sm">
            <div className="text-muted text-xs">
              Thành phần cố định, không thay đổi từ giao diện quản trị
            </div>
            {['Image Encoder', 'Text Encoder'].map((role) => (
              <div key={role}>
                {role}:{' '}
                {registry.encoder
                  ? `${registry.encoder.name} · ${registry.encoder.version} · ${registry.encoder.dimension} chiều`
                  : 'Chưa cấu hình'}
              </div>
            ))}
          </div>
          <div className="panel mt-5 flex items-center gap-3 p-4">
            <span className="flex-1 text-sm">
              {!detector || !tracker
                ? 'Chọn một Detector và Tracker.'
                : !compatible
                  ? 'Cặp mô hình không tương thích.'
                  : unchanged
                    ? 'Đang dùng cấu hình này.'
                    : 'Cặp mô hình tương thích.'}
            </span>
            <Button disabled={busy || !config} onClick={() => setSelected(config)}>
              Hoàn tác
            </Button>
            <Button
              variant="primary"
              onClick={apply}
              disabled={
                busy ||
                unchanged ||
                !compatible ||
                !detector?.available ||
                !tracker?.available ||
                !config ||
                !registry.encoder
              }
            >
              {busy ? 'Đang áp dụng…' : 'Áp dụng cấu hình'}
            </Button>
          </div>
        </>
      )}
    </>
  )
}
