import {
  ImageIcon,
  MagnifyingGlassIcon,
  SlidersHorizontalIcon,
  TextAaIcon,
} from '@phosphor-icons/react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { CAMERA_STATUS, TONE } from '@/constants/status'
import { AttributePicker } from './AttributePicker'
import { ImageDropzone } from './ImageDropzone'

const METHODS = [
  { value: 'image', label: 'Hình ảnh', icon: ImageIcon },
  { value: 'text', label: 'Văn bản', icon: TextAaIcon },
  { value: 'attr', label: 'Thuộc tính', icon: SlidersHorizontalIcon },
]

export function SearchForm({ state, onChange, areaCameras, running, onRun }) {
  const set = (patch) => onChange({ ...patch, error: null })

  const onFile = (file) => {
    if (!/^image\//.test(file.type)) return onChange({ error: 'Tệp không phải ảnh hợp lệ.' })
    set({ imageUrl: URL.createObjectURL(file), imageFile: file, imageName: file.name })
  }

  const toggleCam = (id) =>
    set({
      cams: state.cams.includes(id) ? state.cams.filter((x) => x !== id) : [...state.cams, id],
    })

  return (
    <div className="panel sticky top-4 flex max-w-[360px] flex-[1_1_300px] flex-col gap-4 p-4">
      <SegmentedControl
        options={METHODS}
        value={state.method}
        onChange={(method) => set({ method })}
        stretch
      />

      {state.method === 'image' && (
        <ImageDropzone imageUrl={state.imageUrl} imageName={state.imageName} onFile={onFile} />
      )}

      {state.method === 'text' && (
        <TextAreaField
          label="Mô tả người cần tìm"
          value={state.text}
          onChange={(e) => set({ text: e.target.value })}
          placeholder="vd. người mặc áo đỏ, quần đen, mang ba lô"
        />
      )}

      {state.method === 'attr' && (
        <AttributePicker value={state.attrs} onChange={(attrs) => set({ attrs })} />
      )}

      <div>
        <div className="mb-1.5 text-xs text-neutral-300">Camera trong khu vực</div>
        <div className="flex flex-wrap gap-1.5">
          <Chip active={!state.cams.length} dot={TONE.acc} onClick={() => set({ cams: [] })}>
            Tất cả camera
          </Chip>
          {areaCameras.map((c) => (
            <Chip
              key={c.id}
              active={state.cams.includes(c.id)}
              dot={TONE[CAMERA_STATUS[c.status].tone]}
              onClick={() => toggleCam(c.id)}
            >
              {c.name.split(' ')[0]}
              {!c.ai && ' · AI tắt'}
            </Chip>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <TextField
          label="Từ ngày"
          type="date"
          value={state.from}
          onChange={(e) => set({ from: e.target.value })}
        />
        <TextField
          label="Đến ngày"
          type="date"
          value={state.to}
          onChange={(e) => set({ to: e.target.value })}
        />
      </div>

      <TextField
        label="Số kết quả tối đa (top_k)"
        type="number"
        min={4}
        max={16}
        step={4}
        value={state.topk}
        onChange={(e) => set({ topk: e.target.value })}
      />

      {state.error && <Alert className="text-xs">{state.error}</Alert>}

      <Button
        variant="primary"
        icon={MagnifyingGlassIcon}
        className="h-[38px] text-sm"
        onClick={onRun}
        disabled={running}
      >
        {running ? 'Đang tìm…' : 'Tìm kiếm'}
      </Button>
    </div>
  )
}
