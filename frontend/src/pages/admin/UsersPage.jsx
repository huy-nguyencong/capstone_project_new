import {
  LockIcon,
  LockOpenIcon,
  PencilSimpleIcon,
  UserMinusIcon,
  UserPlusIcon,
} from '@phosphor-icons/react'
import { useState } from 'react'
import { Button, IconButton } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { Input } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { StatusDot } from '@/components/ui/StatusDot'
import { Tag } from '@/components/ui/Tag'
import { ROLE_LABEL, ROLE_TAG, USER_STATUS } from '@/constants/status'
import { AREAS } from '@/mocks/areas'
import { useAppStore, useConfirm, useToast } from '@/store/hooks'
import { UserDialog } from './UserDialog'

const FILTERS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'operator', label: 'Operator' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'locked', label: 'Khóa / ngừng' },
]

const matchesFilter = (u, filter) => {
  if (filter === 'all') return true
  if (filter === 'locked') return u.status !== 'active'
  return u.role === filter
}

export default function UsersPage() {
  const { users, updateUser, log } = useAppStore()
  const confirm = useConfirm()
  const toast = useToast()
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(undefined)

  const q = query.trim().toLowerCase()
  const rows = users.filter(
    (u) => matchesFilter(u, filter) && (!q || `${u.name} ${u.username}`.toLowerCase().includes(q)),
  )

  const toggleLock = (u) => {
    const locked = u.status === 'locked'
    confirm({
      title: locked ? 'Mở khóa tài khoản?' : 'Khóa tài khoản?',
      body: locked
        ? `${u.name} sẽ có thể đăng nhập lại.`
        : `${u.name} sẽ không thể đăng nhập cho đến khi được mở khóa. Lịch sử hoạt động được giữ nguyên.`,
      label: locked ? 'Mở khóa' : 'Khóa tài khoản',
      onConfirm: () => {
        updateUser(u.id, { status: locked ? 'active' : 'locked' })
        log('Tài khoản', locked ? 'Mở khóa tài khoản' : 'Khóa tài khoản', u.username)
        toast(locked ? `Đã mở khóa ${u.username}.` : `Đã khóa ${u.username}.`)
      },
    })
  }

  const deactivate = (u) =>
    confirm({
      title: 'Ngừng hoạt động tài khoản?',
      body: `${u.name} sẽ không thể đăng nhập hoặc thực hiện nghiệp vụ mới. Case, kết quả tìm kiếm đã lưu và audit log do tài khoản này tạo vẫn được giữ nguyên.`,
      label: 'Ngừng hoạt động',
      onConfirm: () => {
        updateUser(u.id, { status: 'inactive' })
        log('Tài khoản', 'Ngừng hoạt động tài khoản', u.username)
        toast(`Đã ngừng hoạt động ${u.username}. Dữ liệu nghiệp vụ được giữ nguyên.`)
      },
    })

  const columns = [
    {
      key: 'user',
      header: 'Người dùng',
      render: (u) => <CellStack primary={u.name} secondary={u.username} />,
    },
    {
      key: 'role',
      header: 'Vai trò',
      render: (u) => <Tag variant={ROLE_TAG[u.role]}>{ROLE_LABEL[u.role]}</Tag>,
    },
    {
      key: 'area',
      header: 'Khu vực giám sát',
      className: 'text-[13px]',
      render: (u) => (u.role === 'operator' ? AREAS[u.area] : '—'),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (u) => <StatusDot {...USER_STATUS[u.status]} />,
    },
    {
      key: 'last',
      header: 'Đăng nhập gần nhất',
      className: 'text-[13px] text-neutral-300',
      render: (u) => u.last,
    },
    {
      key: 'actions',
      header: 'Thao tác',
      align: 'right',
      render: (u) => {
        if (u.role === 'admin')
          return <span className="text-xs text-neutral-500">Tài khoản quản trị</span>
        if (u.status === 'inactive')
          return <span className="text-xs text-neutral-500">Chỉ lưu lịch sử</span>
        const locked = u.status === 'locked'
        return (
          <div className="inline-flex gap-0.5">
            <IconButton icon={PencilSimpleIcon} label="Chỉnh sửa" onClick={() => setEditing(u)} />
            <IconButton
              icon={locked ? LockOpenIcon : LockIcon}
              label={locked ? 'Mở khóa' : 'Khóa'}
              onClick={() => toggleLock(u)}
            />
            <IconButton
              icon={UserMinusIcon}
              label="Ngừng hoạt động"
              onClick={() => deactivate(u)}
            />
          </div>
        )
      },
    },
  ]

  return (
    <>
      <PageHeader
        kicker="UC-02 · Quản trị"
        title="Tài khoản người dùng"
        description="Tạo, cập nhật, khóa hoặc ngừng hoạt động tài khoản. Mỗi Operator được gán đúng một khu vực giám sát."
      >
        <Button variant="primary" icon={UserPlusIcon} onClick={() => setEditing(null)}>
          Tạo tài khoản
        </Button>
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Tìm theo tên hoặc tên đăng nhập"
          className="max-w-[280px]"
        />
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(u) => u.id}
        rowClassName={(u) => u.status === 'inactive' && 'opacity-55'}
        emptyText="Không có tài khoản nào phù hợp."
      />

      {editing !== undefined && <UserDialog user={editing} onClose={() => setEditing(undefined)} />}
    </>
  )
}
