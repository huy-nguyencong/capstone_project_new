import { ImageSquareIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { PersonFigure } from '@/components/person/PersonFigure'
import { COLORS } from '@/constants/status'

function SampleCrop() {
  return (
    <div className="w-[72px]">
      <div className="relative aspect-[3/5] overflow-hidden rounded-md bg-[linear-gradient(180deg,var(--color-neutral-800),var(--color-neutral-900))]">
        <PersonFigure shirt={COLORS.red.swatch} pants={COLORS.black.swatch} bag />
      </div>
    </div>
  )
}

export function ImageDropzone({ imageUrl, imageName, sample, onFile, onUseSample }) {
  const hasImage = Boolean(imageUrl) || sample

  const handleFiles = (files) => {
    const file = files?.[0]
    if (file) onFile(file)
  }

  return (
    <div className="flex flex-col gap-2">
      <label
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          handleFiles(e.dataTransfer.files)
        }}
        className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border border-dashed border-neutral-600 p-3.5 text-center hover:border-accent"
      >
        <input
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {imageUrl && <img src={imageUrl} alt="" className="max-h-40 rounded-md" />}
        {!imageUrl && sample && <SampleCrop />}
        {hasImage ? (
          <span className="text-xs text-neutral-300">{imageName} · bấm để đổi ảnh</span>
        ) : (
          <>
            <ImageSquareIcon size={26} className="text-neutral-400" />
            <span className="text-[13px]">Kéo thả hoặc chọn ảnh đã crop</span>
            <span className="text-[11px] text-neutral-400">Ảnh chỉ chứa một người · JPG, PNG</span>
          </>
        )}
      </label>
      <Button variant="ghost" className="self-start text-xs" onClick={onUseSample}>
        Dùng ảnh mẫu
      </Button>
    </div>
  )
}
