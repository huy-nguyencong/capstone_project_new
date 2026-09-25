import {
  ArrowRightIcon,
  CheckCircleIcon,
  InfoIcon,
  LockSimpleIcon,
  XCircleIcon,
} from '@phosphor-icons/react'
import { Fragment, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { OptionCard } from '@/components/ui/Chip'
import { PageHeader } from '@/components/ui/PageHeader'
import { Tag } from '@/components/ui/Tag'
import { cx } from '@/components/ui/cx'
import { TONE } from '@/constants/status'
import {
  DETECTORS,
  FIXED_ENCODERS,
  INCOMPATIBLE,
  TRACKERS,
  detectorName,
  trackerName,
} from '@/mocks/models'
import { useAppStore, useToast } from '@/store/hooks'
import { wait } from '@/utils/format'

function ModelOption({ model, active, current, onPick }) {
  const unavailable = model.ready === false
  return (
    <OptionCard active={active} disabled={unavailable} onClick={onPick}>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">{model.name}</span>
        {current && <Tag variant="accent">Đang dùng</Tag>}
        {unavailable && <Tag>Không khả dụng</Tag>}
      </div>
      <div className="text-xs text-neutral-300">{model.desc}</div>
      <div className="text-[11px] text-neutral-500">{model.meta}</div>
    </OptionCard>
  )
}

export default function ModelsPage() {
  const { models, setModels, log } = useAppStore()
  const toast = useToast()
  const [sel, setSel] = useState(models)
  const [applying, setApplying] = useState(false)

  const selDet = DETECTORS.find((d) => d.id === sel.det)
  const incompat = INCOMPATIBLE[`${sel.det}|${sel.trk}`]
  const noChange = sel.det === models.det && sel.trk === models.trk
  const invalid = !selDet.ready || Boolean(incompat)

  const pipeline = [
    { k: 'Nguồn', v: 'RTSP', changed: false },
    { k: 'Detector', v: detectorName(sel.det), changed: sel.det !== models.det },
    { k: 'Tracker', v: trackerName(sel.trk), changed: sel.trk !== models.trk },
    { k: 'Image Encoder', v: 'Cố định', changed: false },
  ]

  let check
  if (!selDet.ready)
    check = {
      icon: XCircleIcon,
      color: TONE.err,
      msg: `${selDet.name} không ở trạng thái sẵn sàng.`,
    }
  else if (incompat)
    check = {
      icon: XCircleIcon,
      color: TONE.err,
      msg: `Không tương thích: ${incompat} Hãy chọn tổ hợp khác.`,
    }
  else if (noChange)
    check = {
      icon: InfoIcon,
      color: 'var(--color-neutral-400)',
      msg: 'Đang dùng cấu hình này. Chọn Detector hoặc Tracker khác để thay đổi.',
    }
  else
    check = {
      icon: CheckCircleIcon,
      color: TONE.ok,
      msg: `Tổ hợp ${detectorName(sel.det)} + ${trackerName(sel.trk)} tương thích với pipeline.`,
    }

  const apply = async () => {
    setApplying(true)
    await wait(1200)
    if (sel.det !== models.det) {
      log(
        'Mô hình AI',
        'Thay đổi Detector',
        'Camera Processing Pipeline',
        true,
        `${detectorName(models.det)} → ${detectorName(sel.det)}`,
      )
    }
    if (sel.trk !== models.trk) {
      log(
        'Mô hình AI',
        'Thay đổi Tracker',
        'Camera Processing Pipeline',
        true,
        `${trackerName(models.trk)} → ${trackerName(sel.trk)}`,
      )
    }
    setModels(sel)
    setApplying(false)
    toast('Đã áp dụng cấu hình mới. Nên chạy lại Kiểm tra Camera Processing Pipeline.')
  }

  return (
    <>
      <PageHeader
        kicker="UC-05 · Quản trị"
        title="Cấu hình mô hình AI"
        description="Chọn Detector và Tracker cho Camera Processing Pipeline. Image Encoder và Text Encoder là thành phần cố định."
      />

      <div className="mb-[22px] flex flex-wrap items-stretch gap-2">
        {pipeline.map((p, i) => (
          <Fragment key={p.k}>
            <div
              className={cx(
                'min-w-[150px] rounded-md bg-surface px-3.5 py-2.5',
                p.changed ? 'shadow-accent' : 'shadow-sm',
              )}
            >
              <div className="text-[10px] tracking-[0.1em] text-neutral-400 uppercase">{p.k}</div>
              <div className="mt-0.5 text-sm">{p.v}</div>
            </div>
            {i < pipeline.length - 1 && (
              <ArrowRightIcon size={16} className="self-center text-neutral-500" />
            )}
          </Fragment>
        ))}
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-5">
        <div className="flex flex-col gap-2">
          <h5 className="mb-1">Detector</h5>
          {DETECTORS.map((d) => (
            <ModelOption
              key={d.id}
              model={d}
              active={d.id === sel.det}
              current={d.id === models.det}
              onPick={() => setSel((s) => ({ ...s, det: d.id }))}
            />
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <h5 className="mb-1">Tracker</h5>
          {TRACKERS.map((t) => (
            <ModelOption
              key={t.id}
              model={t}
              active={t.id === sel.trk}
              current={t.id === models.trk}
              onPick={() => setSel((s) => ({ ...s, trk: t.id }))}
            />
          ))}
          <h5 className="mt-4 mb-1">Thành phần cố định</h5>
          {FIXED_ENCODERS.map((e) => (
            <div
              key={e.name}
              className="flex items-center gap-3 rounded-md border border-dashed border-divider px-3.5 py-2.5"
            >
              <LockSimpleIcon size={16} className="text-neutral-400" />
              <div className="flex-1">
                <div className="text-[13px]">{e.name}</div>
                <div className="text-[11px] text-neutral-400">{e.role}</div>
              </div>
              <span className="text-xs text-neutral-300">{e.model}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel mt-[22px] flex flex-wrap items-center gap-3 px-4 py-3.5">
        <span className="flex" style={{ color: check.color }}>
          <check.icon size={18} />
        </span>
        <span className="min-w-[220px] flex-1 text-[13px]">{check.msg}</span>
        <Button onClick={() => setSel(models)} disabled={noChange}>
          Hoàn tác
        </Button>
        <Button variant="primary" onClick={apply} disabled={noChange || invalid || applying}>
          {applying ? 'Đang áp dụng…' : 'Áp dụng cấu hình'}
        </Button>
      </div>
    </>
  )
}
