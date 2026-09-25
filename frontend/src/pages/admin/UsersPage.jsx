import {
  LockIcon,
  LockOpenIcon,
  PencilSimpleIcon,
  UserMinusIcon,
  UserPlusIcon,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button, IconButton } from '@/components/ui/Button'
import { CellStack, DataTable } from '@/components/ui/DataTable'
import { Input } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/PageHeader'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Spinner } from '@/components/ui/Spinner'
import { StatusDot } from '@/components/ui/StatusDot'
import { Tag } from '@/components/ui/Tag'
import { ROLE_LABEL, ROLE_TAG, USER_STATUS } from '@/constants/status'
import { usersApi } from '@/services/api/users'
import { useConfirm, useToast } from '@/store/hooks'
import { UserDialog } from './UserDialog'

const FILTERS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'operator', label: 'Operator' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'locked', label: 'Đã khóa' },
]

const filterParams = (filter) => {
  if (filter === 'operator' || filter === 'viewer') return { role: filter.toUpperCase() }
  if (filter === 'locked') return { status: 'LOCKED' }
  return {}
}

export default function UsersPage() {
  const confirm = useConfirm()
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [areas, setAreas] = useState([])
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(undefined)
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    usersApi
      .areas()
      .then((items) => active && setAreas(items))
      .catch((requestError) => active && setError(requestError.message))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const timer = setTimeout(() => {
      setLoading(true)
      setError(null)
      usersApi
        .list({ ...filterParams(filter), q: query.trim() || undefined, limit: 20 })
        .then((page) => {
          if (!active) return
          setUsers(page.items)
          setNextCursor(page.nextCursor)
        })
        .catch((requestError) => active && setError(requestError.message))
        .finally(() => active && setLoading(false))
    }, 250)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [filter, query])

  const replaceUser = (updated) => {
    setUsers((items) => {
      const normalizedQuery = query.trim().toLowerCase()
      const matchesFilter =
        filter === 'all' ||
        (filter === 'locked' && updated.status === 'locked') ||
        updated.role === filter
      const matchesQuery =
        !normalizedQuery ||
        `${updated.name} ${updated.username}`.toLowerCase().includes(normalizedQuery)
      if (!matchesFilter || !matchesQuery) {
        return items.filter((item) => item.id !== updated.id)
      }
      const exists = items.some((item) => item.id === updated.id)
      return exists
        ? items.map((item) => (item.id === updated.id ? updated : item))
        : [updated, ...items]
    })
  }

  const runStatusAction = async (user, action) => {
    try {
      const updated = await usersApi[action](user.id)
      replaceUser(updated)
      const messages = {
        lock: `Đã khóa ${user.username}.`,
        unlock: `Đã mở khóa ${user.username}.`,
        deactivate: `Đã ngừng hoạt động ${user.username}. Dữ liệu nghiệp vụ được giữ nguyên.`,
      }
      toast(messages[action])
    } catch (requestError) {
      toast(requestError.message, 'err')
    }
  }

  const toggleLock = (user) => {
    const locked = user.status === 'locked'
    confirm({
      title: locked ? 'Mở khóa tài khoản?' : 'Khóa tài khoản?',
      body: locked
        ? `${user.name} sẽ có thể đăng nhập lại.`
        : `${user.name} sẽ không thể đăng nhập cho đến khi được mở khóa.`,
      label: locked ? 'Mở khóa' : 'Khóa tài khoản',
      onConfirm: () => runStatusAction(user, locked ? 'unlock' : 'lock'),
    })
  }

  const deactivate = (user) =>
    confirm({
      title: 'Ngừng hoạt động tài khoản?',
      body: `${user.name} sẽ không thể đăng nhập. Case và nhật ký đã tạo vẫn được giữ nguyên.`,
      label: 'Ngừng hoạt động',
      onConfirm: () => runStatusAction(user, 'deactivate'),
    })

  const loadMore = async () => {
    setLoading(true)
    try {
      const page = await usersApi.list({
        ...filterParams(filter),
        q: query.trim() || undefined,
        limit: 20,
        cursor: nextCursor,
      })
      setUsers((items) => [...items, ...page.items])
      setNextCursor(page.nextCursor)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      key: 'user',
      header: 'Người dùng',
      render: (user) => <CellStack primary={user.name} secondary={user.username} />,
    },
    {
      key: 'role',
      header: 'Vai trò',
      render: (user) => <Tag variant={ROLE_TAG[user.role]}>{ROLE_LABEL[user.role]}</Tag>,
    },
    {
      key: 'area',
      header: 'Khu vực giám sát',
      className: 'text-[13px]',
      render: (user) => (user.role === 'operator' ? user.area?.name || '—' : '—'),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (user) => <StatusDot {...USER_STATUS[user.status]} />,
    },
    {
      key: 'last',
      header: 'Đăng nhập gần nhất',
      className: 'text-[13px] text-neutral-300',
      render: (user) => user.last,
    },
    {
      key: 'actions',
      header: 'Thao tác',
      align: 'right',
      render: (user) => {
        if (user.role === 'admin') {
          return <span className="text-xs text-neutral-500">Tài khoản quản trị</span>
        }
        if (user.status === 'inactive') {
          return <span className="text-xs text-neutral-500">Chỉ lưu lịch sử</span>
        }
        const locked = user.status === 'locked'
        return (
          <div className="inline-flex gap-0.5">
            <IconButton
              icon={PencilSimpleIcon}
              label="Chỉnh sửa"
              onClick={() => setEditing(user)}
            />
            <IconButton
              icon={locked ? LockOpenIcon : LockIcon}
              label={locked ? 'Mở khóa' : 'Khóa'}
              onClick={() => toggleLock(user)}
            />
            <IconButton
              icon={UserMinusIcon}
              label="Ngừng hoạt động"
              onClick={() => deactivate(user)}
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
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm theo tên hoặc tên đăng nhập"
          className="max-w-[280px]"
        />
        {loading && <Spinner className="text-neutral-400" />}
      </div>

      {error && <Alert className="mb-3">{error}</Alert>}
      <DataTable
        columns={columns}
        rows={users}
        rowKey={(user) => user.id}
        rowClassName={(user) => user.status === 'inactive' && 'opacity-55'}
        emptyText={loading ? 'Đang tải tài khoản…' : 'Không có tài khoản nào phù hợp.'}
      />
      {nextCursor && (
        <div className="mt-3 flex justify-center">
          <Button onClick={loadMore} disabled={loading}>
            Xem thêm
          </Button>
        </div>
      )}

      {editing !== undefined && (
        <UserDialog
          user={editing}
          areas={areas}
          onSaved={replaceUser}
          onClose={() => setEditing(undefined)}
        />
      )}
    </>
  )
}
