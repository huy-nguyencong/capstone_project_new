import {
  CpuIcon,
  FoldersIcon,
  FolderSimpleIcon,
  ListMagnifyingGlassIcon,
  MagnifyingGlassIcon,
  PulseIcon,
  SquaresFourIcon,
  StackIcon,
  StethoscopeIcon,
  UsersThreeIcon,
  VideoCameraIcon,
} from '@phosphor-icons/react'

export const PATHS = {
  login: '/login',
  users: '/admin/users',
  cameras: '/admin/cameras',
  ai: '/admin/ai',
  models: '/admin/models',
  videos: '/admin/videos',
  status: '/monitor/status',
  diagnostics: '/monitor/diagnostics',
  audit: '/monitor/audit',
  search: '/search',
  cases: '/cases',
  overview: '/overview',
  caseFiles: '/case-files',
}

export const NAVIGATION = {
  admin: [
    {
      section: 'Quản trị',
      items: [
        { to: PATHS.users, label: 'Tài khoản', icon: UsersThreeIcon },
        { to: PATHS.cameras, label: 'Camera', icon: VideoCameraIcon },
        { to: PATHS.ai, label: 'Xử lý AI', icon: CpuIcon },
        { to: PATHS.models, label: 'Mô hình AI', icon: StackIcon },
        { to: PATHS.videos, label: 'Xử lý video', icon: VideoCameraIcon },
      ],
    },
    {
      section: 'Giám sát',
      items: [
        { to: PATHS.status, label: 'Trạng thái hệ thống', icon: PulseIcon },
        { to: PATHS.diagnostics, label: 'Kiểm tra AI', icon: StethoscopeIcon },
        { to: PATHS.audit, label: 'Nhật ký hệ thống', icon: ListMagnifyingGlassIcon },
      ],
    },
  ],
  operator: [
    {
      section: 'Điều tra',
      items: [
        { to: PATHS.search, label: 'Tìm kiếm người', icon: MagnifyingGlassIcon },
        { to: PATHS.cases, label: 'Case của tôi', icon: FolderSimpleIcon },
      ],
    },
  ],
  viewer: [
    {
      section: 'Báo cáo',
      items: [
        { to: PATHS.overview, label: 'Tổng quan', icon: SquaresFourIcon },
        { to: PATHS.caseFiles, label: 'Hồ sơ vụ việc', icon: FoldersIcon },
      ],
    },
  ],
}

export const HOME_BY_ROLE = {
  admin: PATHS.users,
  operator: PATHS.search,
  viewer: PATHS.overview,
}
