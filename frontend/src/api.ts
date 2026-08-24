export type Role = '管理员' | '普通用户'

export interface User {
  id: number
  staff_id: string
  name: string
  department: string
  role: Role
}

export interface Room {
  id: number
  name: string
  location: string
  capacity: number
  description?: string | null
  is_active: boolean
}

export interface Booking {
  id: number
  room: Room
  applicant: User
  recurring_series_id?: number | null
  title: string
  department?: string | null
  user_name?: string | null
  attendee_count: number
  note?: string | null
  start_at: string
  end_at: string
  status: 'active' | 'cancelled'
  cancelled_at?: string | null
  created_at: string
}

export interface RoomSchedule {
  room: Room
  bookings: Booking[]
}

export interface RecurringBookingPayload {
  room_id: number
  start_date: string
  end_date: string
  weekdays: number[]
  start_time: string
  end_time: string
  title: string
  attendee_count: number
  note?: string | null
}

export interface RecurringBookingItem {
  booking_date: string
  start_at: string
  end_at: string
  status: 'success' | 'conflict' | 'expired'
  reason?: string | null
  conflict_booking?: Booking | null
  booking?: Booking | null
}

export interface RecurringSeries {
  id: number
  room: Room
  created_by: User
  title: string
  department?: string | null
  user_name?: string | null
  attendee_count: number
  note?: string | null
  start_date: string
  end_date: string
  weekdays: number[]
  start_time: string
  end_time: string
  status: 'active' | 'cancelled'
  cancelled_at?: string | null
  created_at: string
  active_booking_count: number
  future_active_booking_count: number
}

export interface RecurringBookingResult {
  success: RecurringBookingItem[]
  conflicts: RecurringBookingItem[]
  expired: RecurringBookingItem[]
  series?: RecurringSeries | null
}

export interface RecurringSeriesCancelResult {
  series: RecurringSeries
  cancelled: Booking[]
  skipped_expired_count: number
}

export interface DaySchedule {
  date: string
  rooms: RoomSchedule[]
}

const configuredApiBase = import.meta.env.VITE_API_BASE_URL || ''
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
const isDevPort = window.location.port === '5173'
const isPlainHttp = window.location.protocol === 'http:'
const inferredDevApiBase = isLocalhost
  ? 'http://localhost:8000'
  : isPlainHttp && isDevPort
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : ''
const API_BASE = configuredApiBase || inferredDevApiBase
const TOKEN_KEY = 'meeting_room_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (response.status === 401) setToken(null)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(data.detail || '请求失败')
  }
  return response.json()
}

export const api = {
  async login(staff_id: string, password: string) {
    return request<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ staff_id, password }),
    })
  },
  register: (payload: Record<string, string>) =>
    request<{ access_token: string; user: User }>('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => request<User>('/api/auth/me'),
  rooms: (includeDisabled = false) => request<Room[]>(`/api/rooms?include_disabled=${includeDisabled}`),
  createRoom: (payload: Partial<Room>) => request<Room>('/api/rooms', { method: 'POST', body: JSON.stringify(payload) }),
  updateRoom: (id: number, payload: Partial<Room>) =>
    request<Room>(`/api/rooms/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  schedule: (date: string) => request<DaySchedule>(`/api/bookings/schedule?target_date=${date}`),
  bookings: () => request<Booking[]>('/api/bookings'),
  myBookings: () => request<Booking[]>('/api/bookings/mine'),
  createBooking: (payload: Record<string, unknown>) =>
    request<Booking>('/api/bookings', { method: 'POST', body: JSON.stringify(payload) }),
  updateBooking: (id: number, payload: Record<string, unknown>) =>
    request<Booking>(`/api/bookings/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  cancelBooking: (id: number) => request<Booking>(`/api/bookings/${id}/cancel`, { method: 'POST', body: JSON.stringify({}) }),
  previewRecurringBookings: (payload: RecurringBookingPayload) =>
    request<RecurringBookingResult>('/api/bookings/recurring/preview', { method: 'POST', body: JSON.stringify(payload) }),
  createRecurringBookings: (payload: RecurringBookingPayload) =>
    request<RecurringBookingResult>('/api/bookings/recurring', { method: 'POST', body: JSON.stringify(payload) }),
  recurringSeries: (status = 'active') => request<RecurringSeries[]>(`/api/bookings/recurring?status=${status}`),
  myRecurringSeries: (status = 'active') => request<RecurringSeries[]>(`/api/bookings/recurring?status=${status}&mine=true`),
  cancelRecurringSeries: (id: number) =>
    request<RecurringSeriesCancelResult>(`/api/bookings/recurring/${id}/cancel`, { method: 'POST', body: JSON.stringify({}) }),
  stats: () => request<Record<string, number>>('/api/bookings/stats'),
}

export function formatLocalTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Shanghai',
  }).format(new Date(value))
}


export function formatLocalMonthDay(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(value))
}

export function formatLocalDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(`${value}T00:00:00+08:00`))
}
