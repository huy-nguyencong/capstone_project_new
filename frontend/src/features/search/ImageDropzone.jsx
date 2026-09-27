import { ImageSquareIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { cx } from '@/components/ui/cx'

const MAX_BYTES = 10 * 1024 * 1024

const hasDraggedContent = (e) =>
  ['Files', 'text/uri-list', 'text/plain'].some((type) => e.dataTransfer?.types?.includes(type))

// Accepts a cropped person image from: a file picked or dropped from the computer, an image
// pasted with Ctrl+V, or a result card dragged from this page (search again from that person).
export function ImageDropzone({ imageUrl, imageName, onFile, onError }) {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const depth = useRef(0)

  const takeFile = (file) => {
    if (!file) return
    if (!file.type.startsWith('image/')) return onError('Tệp không phải ảnh hợp lệ (JPG, PNG).')
    if (file.size > MAX_BYTES) return onError('Ảnh vượt quá 10 MB.')
    onFile(file)
  }

  const takeUrl = async (raw) => {
    const url = new URL(raw.trim().split('\n')[0], window.location.href)
    // Only same-origin images can be read with the session cookie; other sites block this.
    if (url.origin !== window.location.origin) {
      return onError('Không lấy được ảnh từ trang khác. Hãy lưu ảnh về máy rồi kéo tệp vào.')
    }
    // Result cards show a widened display crop; search with the plain person crop instead.
    url.searchParams.delete('aspect')
    url.searchParams.delete('mark')
    setLoading(true)
    try {
      const response = await fetch(url, { credentials: 'include' })
      const blob = await response.blob()
      if (!response.ok || !blob.type.startsWith('image/')) throw new Error()
      const name = `${url.pathname.split('/').at(-2) || 'image'}.jpg`
      takeFile(new File([blob], name, { type: blob.type }))
    } catch {
      onError('Không tải được ảnh đã kéo vào. Hãy thử lại hoặc chọn tệp từ máy.')
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (dataTransfer) => {
    const file = [...(dataTransfer.files || [])].find((f) => f.type.startsWith('image/'))
    if (file) return takeFile(file)
    if (dataTransfer.files?.length) return takeFile(dataTransfer.files[0])
    const uri = dataTransfer.getData('text/uri-list') || dataTransfer.getData('text/plain')
    if (uri) return takeUrl(uri)
    onError('Không nhận được ảnh. Hãy kéo tệp ảnh hoặc một kết quả tìm kiếm.')
  }

  const onFileRef = useRef(onFile)
  useEffect(() => {
    onFileRef.current = onFile
  }, [onFile])

  useEffect(() => {
    // A drop that misses the zone must not make the browser open the image and leave the page.
    const block = (e) => hasDraggedContent(e) && e.preventDefault()
    const paste = (e) => {
      const file = [...(e.clipboardData?.files || [])].find((f) => f.type.startsWith('image/'))
      if (file) {
        e.preventDefault()
        onFileRef.current(file)
      }
    }
    window.addEventListener('dragover', block)
    window.addEventListener('drop', block)
    window.addEventListener('paste', paste)
    return () => {
      window.removeEventListener('dragover', block)
      window.removeEventListener('drop', block)
      window.removeEventListener('paste', paste)
    }
  }, [])

  return (
    <div className="flex flex-col gap-2">
      <label
        onDragEnter={(e) => {
          if (!hasDraggedContent(e)) return
          e.preventDefault()
          depth.current += 1
          setDragging(true)
        }}
        onDragOver={(e) => {
          if (!hasDraggedContent(e)) return
          e.preventDefault()
          e.dataTransfer.dropEffect = 'copy'
        }}
        onDragLeave={() => {
          depth.current = Math.max(0, depth.current - 1)
          if (!depth.current) setDragging(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          e.stopPropagation()
          depth.current = 0
          setDragging(false)
          handleDrop(e.dataTransfer)
        }}
        className={cx(
          'flex min-h-[150px] cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border border-dashed p-3.5 text-center transition-colors',
          dragging
            ? 'border-accent bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)]'
            : 'border-neutral-600 hover:border-accent',
        )}
      >
        <input
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            takeFile(e.target.files?.[0])
            // Allow picking the same file again.
            e.target.value = ''
          }}
        />
        {loading ? (
          <>
            <SpinnerGapIcon size={24} className="animate-spin text-accent" />
            <span className="text-[13px]">Đang tải ảnh…</span>
          </>
        ) : dragging ? (
          <>
            <ImageSquareIcon size={26} className="text-accent" />
            <span className="text-[13px]">Thả ảnh vào đây</span>
          </>
        ) : imageUrl ? (
          <>
            <img src={imageUrl} alt="" className="max-h-40 rounded-md" />
            <span className="text-xs text-neutral-300">
              {imageName} · bấm, kéo thả hoặc Ctrl+V để đổi ảnh
            </span>
          </>
        ) : (
          <>
            <ImageSquareIcon size={26} className="text-neutral-400" />
            <span className="text-[13px]">Kéo thả, dán (Ctrl+V) hoặc chọn ảnh đã crop</span>
            <span className="text-[11px] text-neutral-400">
              Ảnh chỉ chứa một người · JPG, PNG · có thể kéo một kết quả vào để tìm tiếp
            </span>
          </>
        )}
      </label>
    </div>
  )
}
