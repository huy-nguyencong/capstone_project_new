import { MagnifyingGlassIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { SelectField, TextField } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { KeyValueList, MasterDetail, SidePanel } from '@/components/ui/Panel'
import { StatusDot } from '@/components/ui/StatusDot'
import { Tag } from '@/components/ui/Tag'
import { AUDIT_EVENTS, AUDIT_GROUPS, auditGroupOf } from '@/constants/status'
import { monitorApi } from '@/services/api/monitor'

const EMPTY = { from: '', to: '', group: '', actor: '', result: '' }
const PAGE_SIZE = 50

const localDayToUtc = (day, end) =>
  day ? new Date(`${day}T${end ? '23:59:59.999' : '00:00:00'}`).toISOString() : undefined

const queryParams = (filters) => ({
  occurred_from: localDayToUtc(filters.from, false),
  occurred_to: localDayToUtc(filters.to, true),
  event_type: AUDIT_GROUPS.find((g) => g.label === filters.group)?.events,
  actor_user_id: filters.actor || undefined,
  result: filters.result || undefined,
  limit: PAGE_SIZE,
})

const detailText = (metadata) => {
  const entries = Object.entries(metadata).filter(([key]) => key !== 'actor')
  if (!entries.length) return '—'
  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)
    .join(' · ')
}

export default function AuditLogPage() {
  const [form, setForm] = useState(EMPTY)
  const [applied, setApplied] = useState(EMPTY)
  const [rows, setRows] = useState([])
  const [actors, setActors] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    let active = true
    monitorApi
      .auditActors()
      .then((items) => active && setActors(items))
      .catch((requestError) => active && setError(requestError.message))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    monitorApi
      .auditLogs(queryParams(applied))
      .then((page) => {
        if (!active) return
        setRows(page.items)
        setNextCursor(page.nextCursor)
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [applied])

  const selected = rows.find((l) => l.id === selectedId)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const load = (filters) => {
    setError(null)
    setSelectedId(null)
    setLoading(true)
    setApplied(filters)
  }

  const apply = () => {
    if (form.from && form.to && form.from > form.to) {
      setError('Khoảng thời gian không hợp lệ: ngày bắt đầu sau ngày kết thúc.')
      return
    }
    load({ ...form })
  }

  const clear = () => {
    setForm(EMPTY)
    load(EMPTY)
  }

  const loadMore = async () => {
    setLoading(true)
    try {
      const page = await monitorApi.auditLogs({ ...queryParams(applied), cursor: nextCursor })
      setRows((items) => [...items, ...page.items])
      setNextCursor(page.nextCursor)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      key: 't',
      header: 'Thời gian',
      className: 'font-mono text-xs text-neutral-300 whitespace-nowrap',
      render: (l) => l.at,
    },
    { key: 'user', header: 'Người thực hiện', className: 'text-[13px]', render: (l) => l.actor },
    { key: 'type', header: 'Loại', render: (l) => <Tag>{auditGroupOf(l.eventType)}</Tag> },
    {
      key: 'action',
      header: 'Hành động',
      className: 'text-[13px]',
      render: (l) => AUDIT_EVENTS[l.eventType] ?? l.eventType,
    },
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
    <SidePanel
      title={AUDIT_EVENTS[selected.eventType] ?? selected.eventType}
      onClose={() => setSelectedId(null)}
    >
      <KeyValueList
        items={[
          { k: 'Thời gian', v: selected.at },
          { k: 'Người thực hiện', v: selected.actor },
          { k: 'Loại sự kiện', v: selected.eventType, mono: true },
          { k: 'Đối tượng', v: `${selected.targetType} · ${selected.target}` },
          { k: 'Kết quả', v: selected.ok ? 'Thành công' : 'Thất bại' },
          { k: 'Chi tiết', v: detailText(selected.metadata) },
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
          value={form.group}
          onChange={set('group')}
          placeholder="Tất cả"
          options={AUDIT_GROUPS.map((g) => ({ value: g.label, label: g.label }))}
        />
        <SelectField
          label="Người thực hiện"
          className="min-w-[160px]"
          value={form.actor}
          onChange={set('actor')}
          placeholder="Tất cả"
          options={actors.map((a) => ({ value: a.id, label: a.username }))}
        />
        <SelectField
          label="Kết quả"
          className="min-w-[140px]"
          value={form.result}
          onChange={set('result')}
          placeholder="Tất cả"
          options={[
            { value: 'SUCCESS', label: 'Thành công' },
            { value: 'FAILURE', label: 'Thất bại' },
          ]}
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
        <div className="flex flex-col gap-2">
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(l) => l.id}
            onRowClick={(l) => setSelectedId(l.id)}
            selectedKey={selectedId}
            emptyText={
              loading ? 'Đang tải…' : 'Không tìm thấy bản ghi nào phù hợp với điều kiện tra cứu.'
            }
          />
          {nextCursor && (
            <Button onClick={loadMore} disabled={loading} className="self-start">
              Tải thêm
            </Button>
          )}
        </div>
      </MasterDetail>
    </>
  )
}
