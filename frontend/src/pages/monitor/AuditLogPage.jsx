import { MagnifyingGlassIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { SelectField, TextField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { KeyValueList, MasterDetail, SidePanel } from '@/components/ui/Panel'
import { StatusDot } from '@/components/ui/StatusDot'
import { Tag } from '@/components/ui/Tag'
import { AUDIT_TYPES } from '@/constants/status'
import { useAppStore } from '@/store/hooks'
import { dmyToIso } from '@/utils/format'

const EMPTY = { from: '', to: '', type: '', user: '', q: '' }

const matches = (log, f) => {
  const iso = dmyToIso(log.t)
  return (
    (!f.from || iso >= f.from) &&
    (!f.to || iso <= f.to) &&
    (!f.type || log.type === f.type) &&
    (!f.user || log.user === f.user) &&
    (!f.q || `${log.action} ${log.target}`.toLowerCase().includes(f.q.toLowerCase()))
  )
}

const logKey = (l) => `${l.t}|${l.user}|${l.action}|${l.target}`

export default function AuditLogPage() {
  const { logs, users } = useAppStore()
  const [form, setForm] = useState(EMPTY)
  const [applied, setApplied] = useState(EMPTY)
  const [error, setError] = useState(null)
  const [selectedKey, setSelectedKey] = useState(null)

  const rows = logs.filter((l) => matches(l, applied))
  const selected = logs.find((l) => logKey(l) === selectedKey)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const apply = () => {
    if (form.from && form.to && form.from > form.to) {
      setError('Khoảng thời gian không hợp lệ: ngày bắt đầu sau ngày kết thúc.')
      return
    }
    setError(null)
    setApplied(form)
    setSelectedKey(null)
  }

  const clear = () => {
    setForm(EMPTY)
    setApplied(EMPTY)
    setError(null)
    setSelectedKey(null)
  }

  const columns = [
    {
      key: 't',
      header: 'Thời gian',
      className: 'font-mono text-xs text-neutral-300 whitespace-nowrap',
      render: (l) => l.t,
    },
    { key: 'user', header: 'Người thực hiện', className: 'text-[13px]', render: (l) => l.user },
    { key: 'type', header: 'Loại', render: (l) => <Tag>{l.type}</Tag> },
    { key: 'action', header: 'Hành động', className: 'text-[13px]', render: (l) => l.action },
    {
      key: 'target',
      header: 'Đối tượng',
      className: 'text-[13px] text-neutral-300',
      render: (l) => l.target,
    },
    {
      key: 'res',
      header: 'Kết quả',
      render: (l) => (
        <StatusDot tone={l.ok ? 'ok' : 'err'} label={l.ok ? 'Thành công' : 'Thất bại'} />
      ),
    },
  ]

  const detail = selected && (
    <SidePanel title={selected.action} onClose={() => setSelectedKey(null)}>
      <KeyValueList
        items={[
          { k: 'Thời gian', v: selected.t },
          { k: 'Người thực hiện', v: selected.user },
          { k: 'Loại sự kiện', v: selected.type },
          { k: 'Đối tượng', v: selected.target },
          { k: 'Kết quả', v: selected.ok ? 'Thành công' : 'Thất bại' },
          { k: 'Chi tiết', v: selected.detail || '—' },
        ]}
      />
    </SidePanel>
  )

  return (
    <>
      <PageHeader
        kicker="UC-08 · Giám sát"
        title="Nhật ký hệ thống"
        description="Audit log thao tác quản trị và sự kiện kỹ thuật. Chỉ tra cứu, không chỉnh sửa."
      />

      <div className="mb-3 flex flex-wrap items-end gap-2.5">
        <TextField label="Từ ngày" type="date" value={form.from} onChange={set('from')} />
        <TextField label="Đến ngày" type="date" value={form.to} onChange={set('to')} />
        <SelectField
          label="Loại sự kiện"
          className="min-w-[180px]"
          value={form.type}
          onChange={set('type')}
          placeholder="Tất cả"
          options={AUDIT_TYPES.map((t) => ({ value: t, label: t }))}
        />
        <SelectField
          label="Người thực hiện"
          className="min-w-[160px]"
          value={form.user}
          onChange={set('user')}
          placeholder="Tất cả"
          options={[...users.map((u) => u.username), 'system'].map((u) => ({ value: u, label: u }))}
        />
        <TextField
          label="Đối tượng / hành động"
          className="max-w-[280px] min-w-[200px] flex-1"
          value={form.q}
          onChange={set('q')}
          placeholder="vd. A-03, CS-0142"
        />
        <Button variant="primary" icon={MagnifyingGlassIcon} className="h-9" onClick={apply}>
          Tra cứu
        </Button>
        <Button className="h-9" onClick={clear}>
          Xóa lọc
        </Button>
      </div>

      {error && <Alert className="mb-3">{error}</Alert>}

      <MasterDetail detail={detail}>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={logKey}
          onRowClick={(l) => setSelectedKey(logKey(l))}
          selectedKey={selectedKey}
          emptyText="Không tìm thấy bản ghi nào phù hợp với điều kiện tra cứu."
        />
      </MasterDetail>
    </>
  )
}
