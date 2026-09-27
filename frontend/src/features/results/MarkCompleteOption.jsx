import { Switch } from '@/components/ui/Switch'

// Optional "mark as completed" step offered when saving a result into a case.
export function MarkCompleteOption({ checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md bg-bg px-3 py-2.5">
      <Switch
        checked={checked}
        onChange={() => onChange(!checked)}
        label="Đánh dấu vụ việc đã hoàn thành"
      />
      <span className="text-xs">
        <span className="block text-[13px]">Đánh dấu vụ việc đã hoàn thành</span>
        <span className="block text-neutral-400">
          Vụ việc sẽ bị khóa sau khi lưu. Có thể mở lại trong trang Vụ việc của tôi.
        </span>
      </span>
    </label>
  )
}
