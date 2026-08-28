<script setup lang="ts">
import { computed, defineComponent, h, onMounted, PropType, reactive, ref, watch } from 'vue'
import {
  BarChart3,
  Building2,
  CalendarCheck,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  DoorOpen,
  Eye,
  LogOut,
  MonitorUp,
  Pencil,
  Plus,
  Power,
  RefreshCcw,
  Save,
  Shield,
  UserCheck,
  UserRound,
  Users,
  X,
  XCircle,
} from '@lucide/vue'
import { api, Booking, Campus, DaySchedule, formatLocalDate, formatLocalMonthDay, formatLocalTime, getToken, RecurringBookingResult, RecurringSeries, RecurringSeriesCancelResult, Room, setToken, User } from './api'

type Tab = 'home' | 'schedule' | 'mine' | 'admin'
type MobileAdminView = 'home' | 'bookings' | 'rooms' | 'stats'
type DesktopView = 'schedule' | 'mine' | 'admin-bookings' | 'admin-rooms' | 'admin-recurring' | 'admin-stats'
type DesktopMineView = 'upcoming' | 'recurring' | 'finished' | 'cancelled'
type RecurringStatusFilter = 'active' | 'cancelled'

const DESKTOP_VIEW_KEY = 'meeting_room_desktop_view'
const desktopViews: DesktopView[] = ['schedule', 'mine', 'admin-bookings', 'admin-rooms', 'admin-recurring', 'admin-stats']
function savedDesktopView(): DesktopView {
  const saved = localStorage.getItem(DESKTOP_VIEW_KEY) as DesktopView | null
  return saved && desktopViews.includes(saved) ? saved : 'schedule'
}
type AdminBookingStatus = 'active' | 'finished' | 'cancelled'
type RoomStatusFilter = 'all' | 'active' | 'disabled'
type CampusFilter = 'all' | Campus

const CAMPUS_OPTIONS: Campus[] = ['庆春', '钱塘', '大运河', '绍兴']

function dateInputInShanghai(value = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(value)
}

function mobileDateLabel(value: string) {
  const date = new Date(`${value}T00:00:00+08:00`)
  const parts = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    timeZone: 'Asia/Shanghai',
  }).formatToParts(date)
  const part = (type: string) => parts.find((item) => item.type === type)?.value || ''
  return `${part('month')}月${part('day')}日 ${part('weekday')}`
}

const user = ref<User | null>(null)
const tokenChecked = ref(false)
const error = ref('')
const notice = ref('')
const activeTab = ref<Tab>('home')
const mobileAdminView = ref<MobileAdminView>('home')
const desktopView = ref<DesktopView>(savedDesktopView())
const desktopMineView = ref<DesktopMineView>('upcoming')
const desktopBookingDrawerOpen = ref(false)
const desktopRecurringDrawerOpen = ref(false)
const desktopBookingPreview = ref<{
  booking: Booking
  left: number
  top: number
  placement: 'above' | 'below'
} | null>(null)
let desktopPreviewTimer: number | undefined
const desktopRecurringStatus = ref<RecurringStatusFilter>('active')
const desktopRecurringSeriesList = ref<RecurringSeries[]>([])
const desktopSelectedSeries = ref<RecurringSeries | null>(null)
const adminBookingDate = ref(dateInputInShanghai())
const adminBookingStatus = ref<AdminBookingStatus>('active')
const adminBookingCampus = ref<CampusFilter>('all')
const adminRoomStatus = ref<RoomStatusFilter>('all')
const adminRoomCampus = ref<CampusFilter>('all')
const mobileRoomSheetOpen = ref(false)
const recurringSheetOpen = ref(false)
const recurringMode = ref<'manage' | 'create' | 'cancel'>('manage')
const recurringResult = ref<RecurringBookingResult | null>(null)
const recurringSeriesList = ref<RecurringSeries[]>([])
const recurringSeriesCancelResult = ref<RecurringSeriesCancelResult | null>(null)
const selectedDate = ref(dateInputInShanghai())
const selectedCampus = ref<Campus>('庆春')
const schedule = ref<DaySchedule | null>(null)
const myBookings = ref<Booking[]>([])
const myRecurringSeries = ref<RecurringSeries[]>([])
const allBookings = ref<Booking[]>([])
const rooms = ref<Room[]>([])
const stats = ref<Record<string, number>>({})
const loading = ref(false)
const scheduleRefreshing = ref(false)
let toastTimer: number | undefined
const mobileBookingOpen = ref(false)
const bookingStep = ref<'slots' | 'details'>('slots')
const selectedRoom = ref<Room | null>(null)
const selectedSlotStart = ref<number | null>(null)
const selectedSlotEnd = ref<number | null>(null)
const detailBooking = ref<Booking | null>(null)
const sheetDragY = ref(0)
const sheetDragging = ref(false)
let sheetStartY = 0
let activeSheetClose: (() => void) | null = null
let lockedScrollY = 0

const hasOpenSheet = computed(() => mobileBookingOpen.value || desktopBookingDrawerOpen.value || desktopRecurringDrawerOpen.value || !!detailBooking.value || mobileRoomSheetOpen.value || recurringSheetOpen.value)

watch(desktopView, (view) => localStorage.setItem(DESKTOP_VIEW_KEY, view))

watch(hasOpenSheet, (open) => {
  if (open) {
    lockedScrollY = window.scrollY
    document.body.style.position = 'fixed'
    document.body.style.top = `-${lockedScrollY}px`
    document.body.style.left = '0'
    document.body.style.right = '0'
    document.body.style.width = '100%'
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.position = ''
    document.body.style.top = ''
    document.body.style.left = ''
    document.body.style.right = ''
    document.body.style.width = ''
    document.body.style.overflow = ''
    window.scrollTo(0, lockedScrollY)
  }
})

const authMode = ref<'login' | 'register'>('login')
const loginForm = reactive({ staff_id: '', password: '' })
const registerForm = reactive({ staff_id: '', confirm_staff_id: '', name: '', department: '' })
const roomOriginalActive = ref(true)
const roomForm = reactive({ id: 0, campus: '庆春' as Campus, campus_locked: false, name: '', location: '', capacity: 10, description: '', is_active: true })
const bookingForm = reactive({
  id: 0,
  room_id: 0,
  booking_date: selectedDate.value,
  start_hour: '09',
  start_minute: '00',
  end_hour: '10',
  end_minute: '00',
  title: '',
  attendee_count: 1,
  note: '',
})

const weekdayOptions = [
  { value: 0, label: '周一' },
  { value: 1, label: '周二' },
  { value: 2, label: '周三' },
  { value: 3, label: '周四' },
  { value: 4, label: '周五' },
  { value: 5, label: '周六' },
  { value: 6, label: '周日' },
]
const recurringForm = reactive({
  room_id: 0,
  start_date: adminBookingDate.value,
  end_date: adminBookingDate.value,
  weekdays: [] as number[],
  start_hour: '09',
  start_minute: '00',
  end_hour: '10',
  end_minute: '00',
  title: '',
  attendee_count: 1,
  note: '',
})
const isAdmin = computed(() => user.value?.role === '管理员')
const desktopTitle = computed(() => ({
  schedule: '会议室预约',
  mine: '我的预约',
  'admin-bookings': '预约管理',
  'admin-rooms': '会议室管理',
  'admin-recurring': '周期预约管理',
  'admin-stats': '统计信息',
}[desktopView.value]))
const mobileTitle = computed(() => {
  if (activeTab.value === 'home') return '医务科会议室'
  if (activeTab.value === 'schedule') return '预定会议室'
  if (activeTab.value === 'mine') return '我的预定'
  if (mobileAdminView.value === 'bookings') return '预约管理'
  if (mobileAdminView.value === 'rooms') return '会议室管理'
  if (mobileAdminView.value === 'stats') return '统计信息'
  return '管理后台'
})
const OPEN_HOUR = 7
const CLOSE_HOUR = 18
const SLOT_MINUTES = 30
const SLOT_COUNT = (CLOSE_HOUR - OPEN_HOUR) * (60 / SLOT_MINUTES)
const SCHEDULE_MINUTES = (CLOSE_HOUR - OPEN_HOUR) * 60
const hourOptions = Array.from({ length: CLOSE_HOUR - OPEN_HOUR }, (_, i) => String(i + OPEN_HOUR).padStart(2, '0'))
const endHourOptions = Array.from({ length: CLOSE_HOUR - OPEN_HOUR }, (_, i) => String(i + OPEN_HOUR + 1).padStart(2, '0'))
const minuteOptions = ['00', '30']
const desktopHours = Array.from({ length: CLOSE_HOUR - OPEN_HOUR + 1 }, (_, index) => index + OPEN_HOUR)
watch(() => bookingForm.end_hour, (hour) => {
  if (Number(hour) === CLOSE_HOUR) bookingForm.end_minute = '00'
})
watch(() => recurringForm.end_hour, (hour) => {
  if (Number(hour) === CLOSE_HOUR) recurringForm.end_minute = '00'
})
const normalMyBookings = computed(() => myBookings.value.filter((booking) => !booking.recurring_series_id))
const upcoming = computed(() => normalMyBookings.value.filter((booking) => booking.status === 'active' && new Date(booking.end_at) > new Date()))
const finished = computed(() => normalMyBookings.value.filter((booking) => booking.status === 'active' && new Date(booking.end_at) <= new Date()))
const cancelled = computed(() => normalMyBookings.value.filter((booking) => booking.status === 'cancelled'))
const desktopMyBookingRows = computed(() => {
  if (desktopMineView.value === 'upcoming') return upcoming.value
  if (desktopMineView.value === 'finished') return finished.value
  if (desktopMineView.value === 'cancelled') return cancelled.value
  return []
})
const activeMyRecurringSeries = computed(() => myRecurringSeries.value.filter((series) => series.status === 'active' && series.future_active_booking_count > 0))
const hasMineContent = computed(() => activeMyRecurringSeries.value.length > 0 || normalMyBookings.value.length > 0)
const visibleScheduleRooms = computed(() => schedule.value?.rooms || [])
const recurringActiveRooms = computed(() => rooms.value.filter((room) => room.is_active))
const recurringRoomsByCampus = computed(() => CAMPUS_OPTIONS.map((campus) => ({
  campus,
  rooms: recurringActiveRooms.value.filter((room) => room.campus === campus),
})).filter((group) => group.rooms.length > 0))
const recurringSummary = computed(() => {
  const result = recurringResult.value
  if (!result) return ''
  return `已创建 ${result.success.length} 条，冲突跳过 ${result.conflicts.length} 条，过期跳过 ${result.expired.length} 条`
})
const recurringSeriesCancelSummary = computed(() => {
  const result = recurringSeriesCancelResult.value
  if (!result) return ''
  return `已取消 ${result.cancelled.length} 条，已结束跳过 ${result.skipped_expired_count} 条`
})


const adminCampusRooms = computed(() => rooms.value.filter((room) => adminRoomCampus.value === 'all' || room.campus === adminRoomCampus.value))

const adminFilteredRooms = computed(() => {
  return adminCampusRooms.value.filter((room) => {
    if (adminRoomStatus.value === 'active') return room.is_active
    if (adminRoomStatus.value === 'disabled') return !room.is_active
    return true
  })
})

const adminFilteredBookings = computed(() => {
  const target = adminBookingDate.value
  return allBookings.value.filter((booking) => {
    if (adminBookingCampus.value !== 'all' && bookingCampus(booking) !== adminBookingCampus.value) return false
    const sameDate = dateInputInShanghai(new Date(booking.start_at)) === target
    if (!sameDate) return false
    if (adminBookingStatus.value === 'cancelled') return booking.status === 'cancelled'
    if (booking.status !== 'active') return false
    const ended = new Date(booking.end_at) <= new Date()
    return adminBookingStatus.value === 'finished' ? ended : !ended
  })
})


const selectedRoomSchedule = computed(() => schedule.value?.rooms.find((item) => item.room.id === bookingForm.room_id))
const nowTick = ref(Date.now())

function campusStorageKey(staffId: string) {
  return `meeting_room_selected_campus_${staffId}`
}

function restoreSelectedCampus(currentUser: User) {
  const saved = localStorage.getItem(campusStorageKey(currentUser.staff_id)) as Campus | null
  selectedCampus.value = saved && CAMPUS_OPTIONS.includes(saved) ? saved : '庆春'
}

watch(selectedCampus, (campus) => {
  if (user.value) localStorage.setItem(campusStorageKey(user.value.staff_id), campus)
})

function bookingCampus(booking: Booking) {
  return booking.campus || booking.room.campus
}

function recurringCampus(series: RecurringSeries) {
  return series.campus || series.room.campus
}

const mobileSlots = computed(() => {
  const bookings = selectedRoomSchedule.value?.bookings || []
  return Array.from({ length: SLOT_COUNT }, (_, index) => {
    const start = OPEN_HOUR * 60 + index * SLOT_MINUTES
    const end = start + SLOT_MINUTES
    const occupiedBy = bookings.find((booking) => {
      if (bookingForm.id && booking.id === bookingForm.id) return false
      const bookingStart = localMinutes(booking.start_at)
      const bookingEnd = localMinutes(booking.end_at)
      return bookingStart < end && bookingEnd > start
    })
    const expired = isSlotExpired(end)
    return {
      index,
      start,
      end,
      label: `${minutesToText(start)}-${minutesToText(end)}`,
      occupiedBy,
      expired,
    }
  })
})

const BookingItem = defineComponent({
  props: { booking: { type: Object as PropType<Booking>, required: true } },
  emits: ['edit', 'cancel'],
  setup(props, { emit }) {
    return () =>
      h('article', { class: 'booking-row' }, [
        h('span', `${formatLocalMonthDay(props.booking.start_at)} ${formatLocalTime(props.booking.start_at)} - ${formatLocalTime(props.booking.end_at)}`),
        h('strong', props.booking.title),
        h('small', `${bookingCampus(props.booking)} · ${props.booking.room.name} · ${props.booking.user_name || props.booking.applicant.name} · ${props.booking.status === 'active' ? '有效' : '已取消'}`),
        props.booking.status === 'active' && new Date(props.booking.end_at) > new Date()
          ? h('div', { class: 'row-actions' }, [
              h('button', { onClick: () => emit('edit', undefined, props.booking) }, '编辑'),
              h('button', { onClick: () => emit('cancel', props.booking) }, '取消'),
            ])
          : null,
      ])
  },
})

function clearToastLater() {
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    notice.value = ''
    error.value = ''
  }, 2600)
}

function showMessage(message: string) {
  notice.value = message
  error.value = ''
  clearToastLater()
}

function showError(message: unknown) {
  error.value = message instanceof Error ? message.message : String(message)
  notice.value = ''
  clearToastLater()
}

async function withLoading(task: () => Promise<void>) {
  loading.value = true
  try {
    await task()
  } catch (err) {
    showError(err)
  } finally {
    loading.value = false
  }
}

async function loadMe() {
  if (!getToken()) {
    tokenChecked.value = true
    return
  }
  try {
    user.value = await api.me()
    restoreSelectedCampus(user.value)
    if (user.value.role !== '管理员' && desktopView.value.startsWith('admin-')) desktopView.value = 'schedule'
  } catch {
    setToken(null)
  } finally {
    tokenChecked.value = true
  }
}

async function login() {
  await withLoading(async () => {
    const result = await api.login(loginForm.staff_id.trim(), loginForm.password)
    setToken(result.access_token)
    user.value = result.user
    restoreSelectedCampus(result.user)
    activeTab.value = 'home'
    desktopView.value = 'schedule'
    await refreshAll()
  })
}

async function registerUser() {
  await withLoading(async () => {
    const result = await api.register({
      staff_id: registerForm.staff_id.trim(),
      confirm_staff_id: registerForm.confirm_staff_id.trim(),
      name: registerForm.name.trim(),
      department: registerForm.department.trim(),
    })
    setToken(result.access_token)
    user.value = result.user
    restoreSelectedCampus(result.user)
    activeTab.value = 'home'
    desktopView.value = 'schedule'
    showMessage('注册成功')
    await refreshAll()
  })
}

function logout() {
  setToken(null)
  user.value = null
  detailBooking.value = null
  mobileRoomSheetOpen.value = false
  mobileAdminView.value = 'home'
  desktopView.value = 'schedule'
  activeTab.value = 'home'
}

async function refreshAll() {
  if (!user.value) return
  await Promise.all([loadSchedule(), loadRooms(), loadMine()])
  if (isAdmin.value) await loadAdminData()
}

async function loadSchedule() {
  nowTick.value = Date.now()
  schedule.value = await api.schedule(selectedDate.value, selectedCampus.value)
}

async function refreshScheduleWithSkeleton() {
  scheduleRefreshing.value = true
  try {
    await loadSchedule()
  } catch (err) {
    showError(err)
  } finally {
    scheduleRefreshing.value = false
  }
}

async function loadRooms() {
  rooms.value = await api.rooms(isAdmin.value)
}

async function loadMine() {
  const [bookings, series] = await Promise.all([api.myBookings(), api.myRecurringSeries('active')])
  myBookings.value = bookings
  myRecurringSeries.value = series
}

async function loadAdminData() {
  await Promise.all([loadAdminBookings(), refreshAdminStatsData()])
}

async function loadAdminBookings() {
  allBookings.value = await api.bookings(
    adminBookingDate.value,
    adminBookingCampus.value === 'all' ? undefined : adminBookingCampus.value,
  )
}

async function refreshAdminStatsData() {
  stats.value = await api.stats()
}


function shiftDate(offset: number) {
  clearDesktopTimelineSelection()
  const date = new Date(`${selectedDate.value}T00:00:00+08:00`)
  date.setDate(date.getDate() + offset)
  selectedDate.value = dateInputInShanghai(date)
  bookingForm.booking_date = selectedDate.value
  withLoading(loadSchedule)
}

function shiftAdminBookingDate(offset: number) {
  const date = new Date(`${adminBookingDate.value}T00:00:00+08:00`)
  date.setDate(date.getDate() + offset)
  adminBookingDate.value = dateInputInShanghai(date)
  withLoading(loadAdminBookings)
}

function handleCampusChange() {
  clearDesktopTimelineSelection()
  bookingForm.booking_date = selectedDate.value
  withLoading(loadSchedule)
}

function handleAdminBookingFilterChange() {
  withLoading(loadAdminBookings)
}

function mobileBack() {
  if (activeTab.value === 'admin' && mobileAdminView.value !== 'home') {
    mobileAdminView.value = 'home'
    mobileRoomSheetOpen.value = false
    detailBooking.value = null
    return
  }
  if (activeTab.value === 'home') return
  activeTab.value = 'home'
  mobileAdminView.value = 'home'
  mobileBookingOpen.value = false
  mobileRoomSheetOpen.value = false
  detailBooking.value = null
}

function localMinutes(value: string) {
  const text = formatLocalTime(value)
  const [hour, minute] = text.split(':').map(Number)
  if (hour === 0 && dateInputInShanghai(new Date(value)) !== selectedDate.value) return 24 * 60
  return hour * 60 + minute
}

function minutesToText(value: number) {
  if (value === 24 * 60) return '24:00'
  const hour = Math.floor(value / 60)
  const minute = value % 60
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function slotIndexForTime(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  const minutes = hour * 60 + minute
  return Math.max(0, Math.min(SLOT_COUNT - 1, Math.floor((minutes - OPEN_HOUR * 60) / SLOT_MINUTES)))
}

function slotEndIndexForEndTime(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  const minutes = hour * 60 + minute - SLOT_MINUTES
  return Math.max(0, Math.min(SLOT_COUNT - 1, Math.floor((minutes - OPEN_HOUR * 60) / SLOT_MINUTES)))
}

function bookingOccupantText(booking: Booking) {
  return `已被 ${booking.department || booking.applicant.department} ${booking.user_name || booking.applicant.name} 预定 · ${booking.title}`
}

function hideDesktopBookingPreview() {
  window.clearTimeout(desktopPreviewTimer)
  desktopPreviewTimer = undefined
  desktopBookingPreview.value = null
}

function showDesktopBookingPreview(event: Event, booking: Booking) {
  window.clearTimeout(desktopPreviewTimer)
  const target = event.currentTarget as HTMLElement
  desktopPreviewTimer = window.setTimeout(() => {
    if (!target.isConnected) return
    const rect = target.getBoundingClientRect()
    const previewWidth = 288
    const viewportGap = 12
    const left = Math.min(
      Math.max(rect.left + rect.width / 2 - previewWidth / 2, viewportGap),
      window.innerWidth - previewWidth - viewportGap,
    )
    const placement = rect.top >= 150 ? 'above' : 'below'
    desktopBookingPreview.value = {
      booking,
      left,
      top: placement === 'above' ? rect.top - 10 : rect.bottom + 10,
      placement,
    }
  }, 180)
}

function bookingDateTimeText(booking: Booking) {
  const start = new Date(booking.start_at)
  const date = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(start).replaceAll('-', '/')
  return `${date} ${formatLocalTime(booking.start_at)} - ${formatLocalTime(booking.end_at)}`
}

function openBookingDetail(booking: Booking) {
  detailBooking.value = booking
}

async function releaseBooking(booking: Booking) {
  if (!window.confirm('确认释放该会议室？')) return
  await cancelBooking(booking)
}


function isSlotExpired(slotEndMinutes: number) {
  const selected = bookingForm.booking_date || selectedDate.value
  const today = dateInputInShanghai(new Date(nowTick.value))
  if (selected < today) return true
  if (selected > today) return false
  const now = new Date(nowTick.value)
  const timeText = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' }).format(now)
  const [hour, minute] = timeText.split(':').map(Number)
  return slotEndMinutes <= hour * 60 + minute
}

function expiredTimelineStyle() {
  const today = dateInputInShanghai(new Date(nowTick.value))
  if (selectedDate.value > today) return { width: '0%' }
  if (selectedDate.value < today) return { width: '100%' }
  const timeText = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' }).format(new Date(nowTick.value))
  const [hour, minute] = timeText.split(':').map(Number)
  const nowMinutes = hour * 60 + minute
  const expiredUntil = Math.max(OPEN_HOUR * 60, Math.min(CLOSE_HOUR * 60, Math.floor(nowMinutes / SLOT_MINUTES) * SLOT_MINUTES))
  const width = Math.max(0, expiredUntil - OPEN_HOUR * 60) / SCHEDULE_MINUTES * 100
  return { width: `${width}%` }
}

function isSlotSelected(index: number) {
  if (selectedSlotStart.value === null || selectedSlotEnd.value === null) return false
  return index >= selectedSlotStart.value && index <= selectedSlotEnd.value
}

function chooseSlot(index: number) {
  const slot = mobileSlots.value[index]
  if (!slot || slot.occupiedBy || slot.expired) return
  if (selectedSlotStart.value === null || selectedSlotEnd.value === null || bookingStep.value === 'details') {
    selectedSlotStart.value = index
    selectedSlotEnd.value = index
    bookingStep.value = 'slots'
    return
  }

  if (index >= selectedSlotStart.value && index <= selectedSlotEnd.value) {
    if (index === selectedSlotStart.value) {
      selectedSlotStart.value = null
      selectedSlotEnd.value = null
      return
    }
    selectedSlotEnd.value = index - 1
    return
  }

  const start = Math.min(selectedSlotStart.value, index)
  const end = Math.max(selectedSlotStart.value, index)
  const hasOccupied = mobileSlots.value.slice(start, end + 1).some((item) => item.occupiedBy || item.expired)
  if (hasOccupied) {
    showError('所选时间包含已占用或已过期时段')
    selectedSlotStart.value = index
    selectedSlotEnd.value = index
    return
  }
  selectedSlotStart.value = start
  selectedSlotEnd.value = end
}

function selectedSlotText() {
  if (selectedSlotStart.value === null || selectedSlotEnd.value === null) return '请选择时间'
  return `${minutesToText(OPEN_HOUR * 60 + selectedSlotStart.value * SLOT_MINUTES)}-${minutesToText(OPEN_HOUR * 60 + (selectedSlotEnd.value + 1) * SLOT_MINUTES)}`
}

function applySelectedSlotsToForm() {
  if (selectedSlotStart.value === null || selectedSlotEnd.value === null) return false
  const startText = minutesToText(OPEN_HOUR * 60 + selectedSlotStart.value * SLOT_MINUTES)
  const endText = minutesToText(OPEN_HOUR * 60 + (selectedSlotEnd.value + 1) * SLOT_MINUTES)
  const [startHour, startMinute] = startText.split(':')
  const [endHour, endMinute] = endText.split(':')
  bookingForm.start_hour = startHour
  bookingForm.start_minute = startMinute
  bookingForm.end_hour = endHour
  bookingForm.end_minute = endMinute
  return true
}

function nextBookingStep() {
  if (!applySelectedSlotsToForm()) {
    showError('请选择预约时间')
    return
  }
  bookingStep.value = 'details'
}

function closeMobileBooking() {
  mobileBookingOpen.value = false
}

function closeDetailSheet() {
  detailBooking.value = null
}

function sheetDragStyle() {
  return { transform: `translateY(${sheetDragY.value}px)` }
}

function startSheetPointerDrag(event: PointerEvent, close: () => void) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  sheetStartY = event.clientY
  beginSheetDrag(close)
  window.addEventListener('pointermove', onSheetPointerDrag)
  window.addEventListener('pointerup', endSheetPointerDrag, { once: true })
  window.addEventListener('pointercancel', endSheetPointerDrag, { once: true })
}

function startSheetTouchDrag(event: TouchEvent, close: () => void) {
  const touch = event.touches[0]
  if (!touch) return
  sheetStartY = touch.clientY
  beginSheetDrag(close)
  window.addEventListener('touchmove', onSheetTouchDrag, { passive: false })
  window.addEventListener('touchend', endSheetTouchDrag, { once: true })
  window.addEventListener('touchcancel', endSheetTouchDrag, { once: true })
}

function beginSheetDrag(close: () => void) {
  activeSheetClose = close
  sheetDragging.value = true
  sheetDragY.value = 0
}

function onSheetPointerDrag(event: PointerEvent) {
  sheetDragY.value = Math.max(0, event.clientY - sheetStartY)
}

function onSheetTouchDrag(event: TouchEvent) {
  const touch = event.touches[0]
  if (!touch) return
  event.preventDefault()
  sheetDragY.value = Math.max(0, touch.clientY - sheetStartY)
}

function endSheetPointerDrag() {
  window.removeEventListener('pointermove', onSheetPointerDrag)
  endSheetDrag()
}

function endSheetTouchDrag() {
  window.removeEventListener('touchmove', onSheetTouchDrag)
  endSheetDrag()
}

function endSheetDrag() {
  const shouldClose = sheetDragY.value > 80
  sheetDragging.value = false
  if (shouldClose && activeSheetClose) activeSheetClose()
  sheetDragY.value = 0
  activeSheetClose = null
}


function prepareBooking(room?: Room, booking?: Booking) {
  activeTab.value = 'schedule'
  nowTick.value = Date.now()
  selectedRoom.value = booking?.room || room || null
  bookingForm.id = booking?.id || 0
  bookingForm.room_id = booking?.room.id || room?.id || rooms.value[0]?.id || 0
  bookingForm.booking_date = booking ? dateInputInShanghai(new Date(booking.start_at)) : selectedDate.value
  bookingForm.title = booking?.title || ''
  bookingForm.attendee_count = booking?.attendee_count || 1
  bookingForm.note = booking?.note || ''
  if (booking) {
    bookingForm.start_hour = formatLocalTime(booking.start_at).slice(0, 2)
    bookingForm.start_minute = formatLocalTime(booking.start_at).slice(3, 5)
    const endText = formatLocalTime(booking.end_at)
    bookingForm.end_hour = endText.slice(0, 2)
    bookingForm.end_minute = endText.slice(3, 5)
    selectedSlotStart.value = slotIndexForTime(`${bookingForm.start_hour}:${bookingForm.start_minute}`)
    selectedSlotEnd.value = slotEndIndexForEndTime(`${bookingForm.end_hour}:${bookingForm.end_minute}`)
    bookingStep.value = 'details'
  } else {
    bookingForm.start_hour = '09'
    bookingForm.start_minute = '00'
    bookingForm.end_hour = '10'
    bookingForm.end_minute = '00'
    selectedSlotStart.value = null
    selectedSlotEnd.value = null
    bookingStep.value = 'slots'
  }
  mobileBookingOpen.value = true
  document.querySelector('.booking-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function saveBooking() {
  await withLoading(async () => {
    if (mobileBookingOpen.value) applySelectedSlotsToForm()
    const payload = {
      room_id: Number(bookingForm.room_id),
      booking_date: bookingForm.booking_date,
      start_time: `${bookingForm.start_hour}:${bookingForm.start_minute}`,
      end_time: `${bookingForm.end_hour}:${Number(bookingForm.end_hour) === CLOSE_HOUR ? '00' : bookingForm.end_minute}`,
      title: bookingForm.title.trim(),
      attendee_count: Number(bookingForm.attendee_count),
      note: bookingForm.note.trim() || null,
    }
    if (bookingForm.id) await api.updateBooking(bookingForm.id, payload)
    else await api.createBooking(payload)
    bookingForm.id = 0
    bookingForm.title = ''
    bookingForm.note = ''
    mobileBookingOpen.value = false
    desktopBookingDrawerOpen.value = false
    selectedSlotStart.value = null
    selectedSlotEnd.value = null
    showMessage('预约已保存')
    await refreshAll()
  })
}

async function cancelBooking(booking: Booking) {
  await withLoading(async () => {
    await api.cancelBooking(booking.id)
    showMessage('预约已取消')
    await refreshAll()
  })
}

function editRoom(room?: Room) {
  roomForm.id = room?.id || 0
  roomForm.campus = room?.campus || (adminRoomCampus.value === 'all' ? '庆春' : adminRoomCampus.value)
  roomForm.campus_locked = room?.campus_locked ?? false
  roomForm.name = room?.name || ''
  roomForm.location = room?.location || ''
  roomForm.capacity = room?.capacity || 10
  roomForm.description = room?.description || ''
  roomForm.is_active = room?.is_active ?? true
  roomOriginalActive.value = room?.is_active ?? true
}

function openMobileRoomSheet(room?: Room) {
  editRoom(room)
  mobileRoomSheetOpen.value = true
}

function closeMobileRoomSheet() {
  mobileRoomSheetOpen.value = false
}

async function adminCancelBooking(booking: Booking) {
  if (!window.confirm('确认取消这条预约？')) return
  await cancelBooking(booking)
}

async function refreshAdminStats() {
  await withLoading(async () => {
    await refreshAdminStatsData()
    showMessage('统计已刷新')
  })
}

function weekdayFromDate(value: string) {
  const day = new Date(`${value}T00:00:00+08:00`).getDay()
  return day === 0 ? 6 : day - 1
}

function openRecurringManager() {
  recurringMode.value = 'manage'
  recurringSheetOpen.value = true
}

function initRecurringCreateForm() {
  recurringForm.room_id = recurringForm.room_id || recurringActiveRooms.value[0]?.id || 0
  recurringForm.start_date = adminBookingDate.value
  recurringForm.end_date = adminBookingDate.value
  if (recurringForm.weekdays.length === 0) recurringForm.weekdays = [weekdayFromDate(adminBookingDate.value)]
  recurringResult.value = null
}

async function loadRecurringSeries() {
  recurringSeriesList.value = await api.recurringSeries('active')
}

function openRecurringSheet() {
  recurringMode.value = 'create'
  initRecurringCreateForm()
  recurringSheetOpen.value = true
}

async function openRecurringCancelSheet() {
  recurringMode.value = 'cancel'
  recurringSeriesCancelResult.value = null
  recurringSheetOpen.value = true
  await withLoading(loadRecurringSeries)
}

function closeRecurringSheet() {
  recurringSheetOpen.value = false
}

function toggleRecurringWeekday(value: number) {
  if (recurringForm.weekdays.includes(value)) recurringForm.weekdays = recurringForm.weekdays.filter((item) => item !== value)
  else recurringForm.weekdays = [...recurringForm.weekdays, value].sort((a, b) => a - b)
}

function recurringPayload() {
  return {
    room_id: Number(recurringForm.room_id),
    start_date: recurringForm.start_date,
    end_date: recurringForm.end_date,
    weekdays: recurringForm.weekdays,
    start_time: `${recurringForm.start_hour}:${recurringForm.start_minute}`,
    end_time: `${recurringForm.end_hour}:${Number(recurringForm.end_hour) === CLOSE_HOUR ? '00' : recurringForm.end_minute}`,
    title: recurringForm.title.trim(),
    attendee_count: Number(recurringForm.attendee_count),
    note: recurringForm.note.trim() || null,
  }
}

async function previewRecurringBookings() {
  await withLoading(async () => {
    recurringResult.value = await api.previewRecurringBookings(recurringPayload())
  })
}

async function createRecurringBookings() {
  await withLoading(async () => {
    recurringResult.value = await api.createRecurringBookings(recurringPayload())
    showMessage('周期预约已处理')
    await refreshAll()
  })
}

async function cancelRecurringSeries(series: RecurringSeries) {
  if (!window.confirm(`确认取消「${series.title}」这个周期会议？将取消该周期组下 ${series.future_active_booking_count} 条未来有效预约。`)) return
  await withLoading(async () => {
    recurringSeriesCancelResult.value = await api.cancelRecurringSeries(series.id)
    showMessage('周期会议已取消')
    await loadRecurringSeries()
    await refreshAll()
  })
}

function recurringSeriesText(series: RecurringSeries) {
  const days = series.weekdays.map((day) => weekdayOptions.find((item) => item.value === day)?.label || '').filter(Boolean).join('、')
  return `${series.start_date} 至 ${series.end_date} · ${days} · ${series.start_time}-${series.end_time}`
}

function recurringSeriesShortText(series: RecurringSeries) {
  const days = series.weekdays.map((day) => weekdayOptions.find((item) => item.value === day)?.label || '').filter(Boolean).join('、')
  return `${days} ${series.start_time}-${series.end_time}`
}


function recurringItemText(item: { start_at: string; end_at: string }) {
  return `${bookingDateTimeText({ start_at: item.start_at, end_at: item.end_at } as Booking)}`
}

function recurringConflictText(item: { conflict_booking?: Booking | null }) {
  const booking = item.conflict_booking
  if (!booking) return '该时段已被预约'
  return `已被 ${booking.department || booking.applicant.department} ${booking.user_name || booking.applicant.name} 预定 · ${booking.title}`
}

async function saveRoom() {
  if (roomForm.id && roomOriginalActive.value && !roomForm.is_active && !window.confirm('该会议室可能已有未来预约，停用后不会自动取消已有预约，确认停用？')) return
  await withLoading(async () => {
    const payload = {
      campus: roomForm.campus,
      name: roomForm.name.trim(),
      location: roomForm.location.trim(),
      capacity: Number(roomForm.capacity),
      description: roomForm.description.trim() || null,
      is_active: roomForm.is_active,
    }
    if (roomForm.id) await api.updateRoom(roomForm.id, payload)
    else await api.createRoom(payload)
    editRoom()
    mobileRoomSheetOpen.value = false
    showMessage('会议室已保存')
    await refreshAll()
  })
}

async function toggleRoomStatus(room: Room) {
  if (room.is_active && !window.confirm('停用后不能产生新预约，但不会取消已有预约。确认停用该会议室？')) return
  await withLoading(async () => {
    await api.updateRoom(room.id, {
      campus: room.campus,
      name: room.name,
      location: room.location,
      capacity: room.capacity,
      description: room.description,
      is_active: !room.is_active,
    })
    showMessage(room.is_active ? '会议室已停用' : '会议室已启用')
    await refreshAll()
  })
}

function setDesktopView(view: DesktopView) {
  if (view.startsWith('admin-') && !isAdmin.value) return
  if (view !== 'schedule') clearDesktopTimelineSelection()
  desktopView.value = view
  if (view === 'admin-recurring') withLoading(loadDesktopRecurringSeries)
}

function clearDesktopTimelineSelection() {
  selectedSlotStart.value = null
  selectedSlotEnd.value = null
  selectedRoom.value = null
}

function handleDesktopScheduleDateChange() {
  clearDesktopTimelineSelection()
  bookingForm.booking_date = selectedDate.value
  withLoading(loadSchedule)
}

function desktopGoToday() {

  selectedDate.value = dateInputInShanghai()
  bookingForm.booking_date = selectedDate.value
  withLoading(loadSchedule)
}

function desktopBookingDateText(booking: Booking) {
  return mobileDateLabel(dateInputInShanghai(new Date(booking.start_at)))
}

function desktopSlotExpired(slotEndMinutes: number) {
  const today = dateInputInShanghai(new Date(nowTick.value))
  if (selectedDate.value < today) return true
  if (selectedDate.value > today) return false
  const timeText = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' }).format(new Date(nowTick.value))
  const [hour, minute] = timeText.split(':').map(Number)
  return slotEndMinutes <= hour * 60 + minute
}

function desktopSlotsForRoom(item: DaySchedule['rooms'][number]) {
  const slots = Array.from({ length: SLOT_COUNT }, (_, index) => {
    const start = OPEN_HOUR * 60 + index * SLOT_MINUTES
    const end = start + SLOT_MINUTES
    const occupiedBy = item.bookings.find((booking) => {
      if (bookingForm.id && booking.id === bookingForm.id) return false
      const bookingStart = localMinutes(booking.start_at)
      const bookingEnd = localMinutes(booking.end_at)
      return bookingStart < end && bookingEnd > start
    })
    return {
      index,
      occupiedBy,
      expired: desktopSlotExpired(end),
      selected: selectedRoom.value?.id === item.room.id && isSlotSelected(index),
    }
  })
  return slots.map((slot, index) => {
    const bookingId = slot.occupiedBy?.id
    return {
      ...slot,
      bookingStart: !!bookingId && slots[index - 1]?.occupiedBy?.id !== bookingId,
      bookingEnd: !!bookingId && slots[index + 1]?.occupiedBy?.id !== bookingId,
    }
  })
}

function initializeDesktopBooking(room: Room, booking?: Booking) {
  nowTick.value = Date.now()
  selectedRoom.value = booking?.room || room
  bookingForm.id = booking?.id || 0
  bookingForm.room_id = booking?.room.id || room.id
  bookingForm.booking_date = booking ? dateInputInShanghai(new Date(booking.start_at)) : selectedDate.value
  bookingForm.title = booking?.title || ''
  bookingForm.attendee_count = booking?.attendee_count || 1
  bookingForm.note = booking?.note || ''
  if (booking) {
    bookingForm.start_hour = formatLocalTime(booking.start_at).slice(0, 2)
    bookingForm.start_minute = formatLocalTime(booking.start_at).slice(3, 5)
    const endText = formatLocalTime(booking.end_at)
    bookingForm.end_hour = endText.slice(0, 2)
    bookingForm.end_minute = endText.slice(3, 5)
    selectedSlotStart.value = slotIndexForTime(`${bookingForm.start_hour}:${bookingForm.start_minute}`)
    selectedSlotEnd.value = slotEndIndexForEndTime(`${bookingForm.end_hour}:${bookingForm.end_minute}`)
  } else {
    bookingForm.title = ''
    bookingForm.attendee_count = 1
    bookingForm.note = ''
  }
}

function chooseDesktopSlot(item: DaySchedule['rooms'][number], index: number) {
  hideDesktopBookingPreview()
  const slots = desktopSlotsForRoom(item)
  const slot = slots[index]
  if (!slot) return
  if (slot.occupiedBy) {
    openBookingDetail(slot.occupiedBy)
    return
  }
  if (slot.expired) return

  if (selectedRoom.value?.id !== item.room.id || selectedSlotStart.value === null || selectedSlotEnd.value === null) {
    initializeDesktopBooking(item.room)
    selectedSlotStart.value = index
    selectedSlotEnd.value = index
    return
  }

  const start = Math.min(selectedSlotStart.value, index)
  const end = Math.max(selectedSlotStart.value, index)
  const blocked = slots.slice(start, end + 1).some((candidate) => candidate.occupiedBy || candidate.expired)
  if (blocked) {
    showError('所选时间包含已占用或已过期时段')
    selectedSlotStart.value = index
    selectedSlotEnd.value = index
    return
  }
  selectedSlotStart.value = start
  selectedSlotEnd.value = end
  applySelectedSlotsToForm()
  desktopBookingDrawerOpen.value = true
}

function prepareDesktopBooking(booking: Booking) {
  initializeDesktopBooking(booking.room, booking)
  desktopBookingDrawerOpen.value = true
}

function closeDesktopBookingDrawer() {
  desktopBookingDrawerOpen.value = false
  clearDesktopTimelineSelection()
  bookingForm.id = 0
}

async function cancelDesktopBooking(booking: Booking) {
  if (!window.confirm('确认取消这条预约？')) return
  await cancelBooking(booking)
}

async function loadDesktopRecurringSeries() {
  desktopRecurringSeriesList.value = await api.recurringSeries(desktopRecurringStatus.value)
}

function openDesktopRecurringCreate() {
  initRecurringCreateForm()
  desktopSelectedSeries.value = null
  desktopRecurringDrawerOpen.value = true
}

function openDesktopRecurringDetail(series: RecurringSeries) {
  desktopSelectedSeries.value = series
  recurringResult.value = null
  desktopRecurringDrawerOpen.value = true
}

function closeDesktopRecurringDrawer() {
  desktopRecurringDrawerOpen.value = false
  desktopSelectedSeries.value = null
  recurringResult.value = null
}

async function createDesktopRecurringBookings() {
  await withLoading(async () => {
    recurringResult.value = await api.createRecurringBookings(recurringPayload())
    showMessage(recurringSummary.value)
    desktopRecurringDrawerOpen.value = false
    await Promise.all([refreshAll(), loadDesktopRecurringSeries()])
  })
}

async function cancelDesktopRecurringSeries(series: RecurringSeries) {
  if (!window.confirm(`确认取消「${series.title}」？将取消该周期组下 ${series.future_active_booking_count} 条未来有效预约。`)) return
  await withLoading(async () => {
    recurringSeriesCancelResult.value = await api.cancelRecurringSeries(series.id)
    showMessage(recurringSeriesCancelSummary.value)
    desktopSelectedSeries.value = null
    desktopRecurringDrawerOpen.value = false
    await Promise.all([refreshAll(), loadDesktopRecurringSeries()])
  })
}

function bookingBarStyle(booking: Booking) {
  const start = new Date(booking.start_at)
  const end = new Date(booking.end_at)
  const startParts = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' }).format(start).split(':')
  const endParts = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' }).format(end).split(':')
  const startValue = Number(startParts[0]) + Number(startParts[1]) / 60
  let endValue = Number(endParts[0]) + Number(endParts[1]) / 60
  if (endValue === 0 && dateInputInShanghai(end) !== dateInputInShanghai(start)) endValue = CLOSE_HOUR
  const scheduleHours = CLOSE_HOUR - OPEN_HOUR
  const left = Math.max(0, Math.min(scheduleHours, startValue - OPEN_HOUR)) / scheduleHours * 100
  const width = Math.max(0.8, Math.min(scheduleHours, endValue - OPEN_HOUR) / scheduleHours * 100 - left)
  return { left: `${left}%`, width: `${width}%` }
}

onMounted(async () => {
  await loadMe()
  await refreshAll()
  if (isAdmin.value && desktopView.value === 'admin-recurring') await loadDesktopRecurringSeries()
})
</script>

<template>
  <main v-if="tokenChecked" class="app-shell">
    <section v-if="!user" class="login-view">
      <div class="login-box">
        <h1>{{ authMode === 'login' ? '会议室登记' : '员工注册' }}</h1>
        <form v-if="authMode === 'login'" @submit.prevent="login" class="form-stack">
          <label>工号<input v-model="loginForm.staff_id" autocomplete="username" inputmode="numeric" /></label>
          <label>密码<input v-model="loginForm.password" type="password" autocomplete="current-password" placeholder="同工号" /></label>
          <button class="primary" :disabled="loading">登录</button>
          <button type="button" class="link-button" @click="authMode = 'register'; error = ''; notice = ''">员工注册</button>
          <p v-if="error" class="message error">{{ error }}</p>
        </form>
        <form v-else @submit.prevent="registerUser" class="form-stack">
          <label><span>工号/ID <b class="required-star">*</b></span><input v-model="registerForm.staff_id" inputmode="numeric" autocomplete="off" required /></label>
          <label><span>确认工号/ID <b class="required-star">*</b></span><input v-model="registerForm.confirm_staff_id" inputmode="numeric" autocomplete="off" required /></label>
          <label><span>姓名 <b class="required-star">*</b></span><input v-model="registerForm.name" autocomplete="name" required /></label>
          <label><span>科室 <b class="required-star">*</b></span><input v-model="registerForm.department" required /></label>
          <button class="primary" :disabled="loading">注册并登录</button>
          <button type="button" class="link-button" @click="authMode = 'login'; error = ''; notice = ''">返回登录</button>
          <p v-if="error" class="message error">{{ error }}</p>
        </form>
      </div>
    </section>

    <template v-else>
      <section class="mobile-app">
        <header class="mobile-nav">
          <button class="mobile-back" @click="mobileBack" :class="{ invisible: activeTab === 'home' }"><ChevronLeft :size="32" /></button>
          <h1>{{ mobileTitle }}</h1>
          <button class="mobile-more" @click="logout" title="退出登录"><LogOut :size="24" /></button>
        </header>



        <section v-show="activeTab === 'home'" class="mobile-home">
          <div class="mobile-hero">
            <div>
              <strong>医务科会议室</strong>
              <span>如有技术问题联系许家晟662441</span>
            </div>
            <MonitorUp :size="78" />
          </div>
          <div class="mobile-menu-card">
            <button @click="activeTab = 'schedule'">
              <CalendarCheck :size="32" />
              <span>预定会议室</span>
              <ChevronRight :size="26" />
            </button>
            <button @click="activeTab = 'mine'">
              <UserCheck :size="32" />
              <span>我的预定</span>
              <ChevronRight :size="26" />
            </button>
          </div>
          <div v-if="isAdmin" class="mobile-menu-card">
            <button @click="activeTab = 'admin'">
              <Shield :size="32" />
              <span>管理后台</span>
              <ChevronRight :size="26" />
            </button>
          </div>
        </section>

        <section v-show="activeTab === 'schedule'" class="mobile-schedule">
          <div class="mobile-schedule-controls">
            <label class="mobile-campus-select">
              <span><Building2 :size="17" />院区</span>
              <select v-model="selectedCampus" @change="handleCampusChange">
                <option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option>
              </select>
            </label>
            <div class="mobile-filters">
              <button title="前一天" @click="shiftDate(-1)"><ChevronLeft :size="18" /></button>
              <label class="mobile-date-picker"><span>{{ mobileDateLabel(selectedDate) }}</span><input v-model="selectedDate" type="date" @change="withLoading(loadSchedule)" /></label>
              <button title="后一天" @click="shiftDate(1)"><ChevronRight :size="18" /></button>
              <button class="reset" :disabled="scheduleRefreshing" @click="refreshScheduleWithSkeleton"><RefreshCcw :size="16" />{{ scheduleRefreshing ? '刷新中' : '刷新' }}</button>
            </div>
          </div>

          <div v-if="scheduleRefreshing" class="mobile-skeleton-list">
            <div v-for="item in 5" :key="item" class="mobile-room-card skeleton-card">
              <div class="skeleton-icon"></div>
              <div class="skeleton-main">
                <span></span>
                <small></small>
              </div>
              <div class="skeleton-action"></div>
              <div class="skeleton-timeline"><span></span><em></em></div>
            </div>
          </div>
          <div v-else-if="visibleScheduleRooms.length === 0" class="mobile-schedule-empty">
            <span><Building2 :size="30" /></span>
            <strong>{{ selectedCampus }}院区暂无可预定会议室</strong>
          </div>
          <article v-else v-for="item in visibleScheduleRooms" :key="item.room.id" class="mobile-room-card" @click="prepareBooking(item.room)">
            <div class="room-icon"><MonitorUp :size="30" /></div>
            <div class="mobile-room-main">
              <div class="mobile-room-title">
                <h2>{{ item.room.name }}</h2>
              </div>
              <p>{{ item.room.capacity }}人　{{ item.room.description || item.room.location }}</p>
            </div>
            <div class="mobile-card-actions">
              <CalendarCheck :size="24" />
            </div>
            <div class="mobile-timeline">
              <div class="timeline-track">
                <span class="expired-segment" :style="expiredTimelineStyle()"></span>
                <span v-for="booking in item.bookings" :key="booking.id" class="busy-segment" :style="bookingBarStyle(booking)"></span>
              </div>
              <div class="timeline-hours"><span v-for="hour in desktopHours" :key="hour">{{ hour }}</span></div>
            </div>
          </article>
        </section>

        <section v-show="activeTab === 'mine'" class="mobile-mine">
          <div v-if="!hasMineContent" class="mobile-empty-state">
            <div class="empty-figure"><DoorOpen :size="72" /></div>
            <p>还没有预定过会议室，快去预定吧</p>
            <button @click="activeTab = 'schedule'">立即预定</button>
          </div>
          <template v-else>
            <h2>周期会议</h2>
            <div class="upcoming-card-list">
              <article v-for="series in activeMyRecurringSeries" :key="series.id" class="upcoming-card recurring-card">
                <h3>{{ series.title }}</h3>
                <p><strong>院区：</strong>{{ recurringCampus(series) }}</p>
                <p><strong>会议室：</strong>{{ series.room.name }}</p>
                <p><strong>周期：</strong>{{ recurringSeriesShortText(series) }}</p>
                <p><strong>日期：</strong>{{ series.start_date }} 至 {{ series.end_date }}</p>
                <p><strong>未来：</strong>{{ series.future_active_booking_count }} 次</p>
              </article>
            </div>
            <h2>即将开始</h2>
            <div class="upcoming-card-list">
              <article v-for="booking in upcoming" :key="booking.id" class="upcoming-card">
                <h3>{{ booking.room.name }}</h3>
                <p><strong>时间：</strong>{{ bookingDateTimeText(booking) }}</p>
                <p><strong>院区：</strong>{{ bookingCampus(booking) }}</p>
                <p><strong>地址：</strong>{{ booking.room.location || '暂无' }}</p>
                <div class="upcoming-actions">
                  <button @click="releaseBooking(booking)">释放会议室</button>
                  <button @click="openBookingDetail(booking)">会议详情</button>
                </div>
              </article>
            </div>
            <h2>已结束</h2>
            <div class="booking-list"><BookingItem v-for="booking in finished" :key="booking.id" :booking="booking" /></div>
            <h2>已取消</h2>
            <div class="booking-list"><BookingItem v-for="booking in cancelled" :key="booking.id" :booking="booking" /></div>
          </template>
        </section>

        <section v-if="isAdmin" v-show="activeTab === 'admin'" class="mobile-admin">
          <div v-if="mobileAdminView === 'home'" class="mobile-menu-card admin-menu-card">
            <button @click="mobileAdminView = 'bookings'">
              <CalendarDays :size="32" />
              <span>预约管理</span>
              <ChevronRight :size="26" />
            </button>
            <button @click="mobileAdminView = 'rooms'">
              <MonitorUp :size="32" />
              <span>会议室管理</span>
              <ChevronRight :size="26" />
            </button>
            <button @click="openRecurringManager">
              <CalendarCheck :size="32" />
              <span>周期预约管理</span>
              <ChevronRight :size="26" />
            </button>
            <button @click="mobileAdminView = 'stats'">
              <RefreshCcw :size="32" />
              <span>统计信息</span>
              <ChevronRight :size="26" />
            </button>
          </div>

          <section v-else-if="mobileAdminView === 'bookings'" class="admin-subpage">
            <div class="mobile-schedule-controls admin-filter-panel">
              <label class="mobile-campus-select admin-campus-select">
                <span><Building2 :size="17" />院区</span>
                <select v-model="adminBookingCampus" @change="handleAdminBookingFilterChange">
                  <option value="all">全部院区</option>
                  <option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option>
                </select>
              </label>
              <div class="mobile-filters">
                <button title="前一天" @click="shiftAdminBookingDate(-1)"><ChevronLeft :size="18" /></button>
                <label class="mobile-date-picker"><span>{{ mobileDateLabel(adminBookingDate) }}</span><input v-model="adminBookingDate" type="date" @change="handleAdminBookingFilterChange" /></label>
                <button title="后一天" @click="shiftAdminBookingDate(1)"><ChevronRight :size="18" /></button>
                <button class="reset" @click="withLoading(loadAdminData)"><RefreshCcw :size="16" />刷新</button>
              </div>
            </div>
            <div class="segmented-control">
              <button :class="{ active: adminBookingStatus === 'active' }" @click="adminBookingStatus = 'active'">有效</button>
              <button :class="{ active: adminBookingStatus === 'cancelled' }" @click="adminBookingStatus = 'cancelled'">已取消</button>
              <button :class="{ active: adminBookingStatus === 'finished' }" @click="adminBookingStatus = 'finished'">已结束</button>
            </div>
            <div v-if="adminFilteredBookings.length === 0" class="empty mobile-empty">暂无预约</div>
            <article v-for="booking in adminFilteredBookings" :key="booking.id" class="admin-list-card">
              <h3>{{ booking.room.name }}</h3>
              <p><strong>院区：</strong>{{ bookingCampus(booking) }}</p>
              <p><strong>时间：</strong>{{ bookingDateTimeText(booking) }}</p>
              <p><strong>使用人：</strong>{{ booking.department || booking.applicant.department }} {{ booking.user_name || booking.applicant.name }}</p>
              <p><strong>会议：</strong>{{ booking.title }}</p>
              <div class="admin-card-actions">
                <button @click="openBookingDetail(booking)">会议详情</button>
                <button v-if="booking.status === 'active' && new Date(booking.end_at) > new Date()" @click="adminCancelBooking(booking)">取消预约</button>
              </div>
            </article>
          </section>

          <section v-else-if="mobileAdminView === 'rooms'" class="admin-subpage">
            <label class="mobile-campus-select admin-campus-select">
              <span><Building2 :size="17" />院区</span>
              <select v-model="adminRoomCampus">
                <option value="all">全部院区</option>
                <option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option>
              </select>
            </label>
            <div class="admin-toolbar">
              <div class="segmented-control compact">
                <button :class="{ active: adminRoomStatus === 'all' }" @click="adminRoomStatus = 'all'">全部</button>
                <button :class="{ active: adminRoomStatus === 'active' }" @click="adminRoomStatus = 'active'">启用</button>
                <button :class="{ active: adminRoomStatus === 'disabled' }" @click="adminRoomStatus = 'disabled'">停用</button>
              </div>
              <button class="primary" @click="openMobileRoomSheet()">新增</button>
            </div>
            <div v-if="adminFilteredRooms.length === 0" class="empty mobile-empty">暂无会议室</div>
            <article v-for="room in adminFilteredRooms" :key="room.id" class="admin-list-card room-admin-card">
              <div>
                <h3>{{ room.name }}</h3>
                <p>{{ room.campus }}院区</p>
                <p>{{ room.location || '暂无地址' }} · {{ room.capacity }}人</p>
                <p>{{ room.description || '暂无备注' }}</p>
              </div>
              <span :class="['status-pill', room.is_active ? 'ok' : 'muted']">{{ room.is_active ? '启用' : '停用' }}</span>
              <button @click="openMobileRoomSheet(room)">编辑</button>
            </article>
          </section>


          <section v-else class="admin-subpage">
            <div class="stats admin-stats-grid">
              <span>今日 {{ stats.today_bookings || 0 }}</span>
              <span>本周 {{ stats.week_bookings || 0 }}</span>
              <span>启用 {{ stats.active_rooms || 0 }}</span>
            </div>
            <button class="primary wide-button" :disabled="loading" @click="refreshAdminStats">{{ loading ? '刷新中' : '刷新' }}</button>
          </section>
        </section>

        <div v-if="mobileRoomSheetOpen" class="sheet-mask" @click.self="closeMobileRoomSheet">
          <section class="mobile-sheet room-edit-sheet" :class="{ dragging: sheetDragging }" :style="sheetDragStyle()">
            <div class="sheet-handle" @pointerdown.prevent="startSheetPointerDrag($event, closeMobileRoomSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeMobileRoomSheet)"></div>
            <button class="sheet-close" @click="closeMobileRoomSheet"><X :size="22" /></button>
            <div class="sheet-room-head" @pointerdown.prevent="startSheetPointerDrag($event, closeMobileRoomSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeMobileRoomSheet)">
              <h2>{{ roomForm.id ? '编辑会议室' : '新增会议室' }}</h2>
              <p>{{ roomForm.is_active ? '当前启用' : '当前停用' }}</p>
            </div>
            <form class="form-stack sheet-form" @submit.prevent="saveRoom">
              <label><span>院区 <b class="required-star">*</b></span><select v-model="roomForm.campus" :disabled="roomForm.campus_locked" required><option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option></select><small v-if="roomForm.campus_locked" class="form-hint">已有预约或周期记录，院区不可修改</small></label>
              <label><span>名称 <b class="required-star">*</b></span><input v-model="roomForm.name" required /></label>
              <label>位置<input v-model="roomForm.location" /></label>
              <label>容量<input v-model.number="roomForm.capacity" type="number" min="1" required /></label>
              <label>备注/设备<textarea v-model="roomForm.description" rows="3" /></label>
              <label class="check"><input v-model="roomForm.is_active" type="checkbox" />启用会议室</label>
              <button class="primary sheet-submit" :disabled="loading">保存会议室</button>
            </form>
          </section>
        </div>

        <div v-if="mobileBookingOpen" class="sheet-mask" @click.self="closeMobileBooking">
          <section class="mobile-sheet" :class="{ dragging: sheetDragging }" :style="sheetDragStyle()">
            <div class="sheet-handle" @pointerdown.prevent="startSheetPointerDrag($event, closeMobileBooking)" @touchstart.prevent="startSheetTouchDrag($event, closeMobileBooking)"></div>
            <button class="sheet-close" @click="closeMobileBooking"><X :size="22" /></button>
            <div class="sheet-room-head" @pointerdown.prevent="startSheetPointerDrag($event, closeMobileBooking)" @touchstart.prevent="startSheetTouchDrag($event, closeMobileBooking)">
              <h2>{{ selectedRoom?.name || rooms.find((room) => room.id === bookingForm.room_id)?.name || '会议室' }}</h2>
              <p><Users :size="18" />{{ selectedRoom?.capacity || rooms.find((room) => room.id === bookingForm.room_id)?.capacity || '-' }}　<Building2 :size="18" />{{ selectedRoom?.description || selectedRoom?.location || '会议室' }}</p>
            </div>

            <section v-if="bookingStep === 'slots'" class="slot-step">
              <div class="slot-summary">
                <strong>{{ selectedSlotText() }}</strong>
                <span>请选择连续的 30 分钟时间段</span>
              </div>
              <div class="slot-list">
                <button
                  v-for="slot in mobileSlots"
                  :key="slot.index"
                  class="slot-row"
                  :class="{ selected: isSlotSelected(slot.index), occupied: !!slot.occupiedBy, expired: slot.expired }"
                  :disabled="!!slot.occupiedBy || slot.expired"
                  @click="chooseSlot(slot.index)"
                >
                  <span class="slot-check"></span>
                  <span class="slot-time">{{ slot.label }}</span>
                  <span v-if="slot.occupiedBy" class="slot-occupant">{{ bookingOccupantText(slot.occupiedBy) }}</span>
                  <span v-else-if="slot.expired" class="slot-occupant">已过期</span>
                </button>
              </div>
              <div class="sheet-footer">
                <button class="primary sheet-submit" :disabled="selectedSlotStart === null" @click="nextBookingStep">下一步</button>
              </div>
            </section>

            <form v-else class="form-stack sheet-form" @submit.prevent="saveBooking">
              <button type="button" class="sheet-back" @click="bookingStep = 'slots'"><ChevronLeft :size="18" />重新选择时间</button>
              <div class="selected-time-card">{{ selectedSlotText() }}</div>
              <label>部门<input :value="user?.department || ''" readonly /></label>
              <label>使用人<input :value="user?.name || ''" readonly /></label>
              <label>日期<input :value="bookingForm.booking_date" readonly /></label>
              <label>会议名称<input v-model="bookingForm.title" required /></label>
              <label>参会人数<input v-model.number="bookingForm.attendee_count" type="number" min="1" /></label>
              <label>备注<textarea v-model="bookingForm.note" rows="3" /></label>
              <button class="primary sheet-submit" :disabled="loading || !bookingForm.room_id">{{ bookingForm.id ? '保存修改' : '提交预约' }}</button>
            </form>
          </section>
        </div>

        <div v-if="detailBooking" class="sheet-mask" @click.self="closeDetailSheet">
          <section class="mobile-sheet detail-sheet" :class="{ dragging: sheetDragging }" :style="sheetDragStyle()">
            <div class="sheet-handle" @pointerdown.prevent="startSheetPointerDrag($event, closeDetailSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeDetailSheet)"></div>
            <button class="sheet-close" @click="closeDetailSheet"><X :size="22" /></button>
            <div class="sheet-room-head" @pointerdown.prevent="startSheetPointerDrag($event, closeDetailSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeDetailSheet)">
              <h2>会议详情</h2>
              <p>{{ detailBooking.room.name }}</p>
            </div>
            <div class="detail-list">
              <div><span>会议室</span><strong>{{ detailBooking.room.name }}</strong></div>
              <div><span>院区</span><strong>{{ bookingCampus(detailBooking) }}</strong></div>
              <div><span>时间</span><strong>{{ bookingDateTimeText(detailBooking) }}</strong></div>
              <div><span>地址</span><strong>{{ detailBooking.room.location || '暂无' }}</strong></div>
              <div><span>部门</span><strong>{{ detailBooking.department || detailBooking.applicant.department }}</strong></div>
              <div><span>使用人</span><strong>{{ detailBooking.user_name || detailBooking.applicant.name }}</strong></div>
              <div><span>会议名称</span><strong>{{ detailBooking.title }}</strong></div>
              <div><span>参会人数</span><strong>{{ detailBooking.attendee_count }}人</strong></div>
              <div><span>备注</span><strong>{{ detailBooking.note || '无' }}</strong></div>
              <div><span>状态</span><strong>{{ detailBooking.status === 'active' ? '有效' : '已取消' }}</strong></div>
            </div>
          </section>
        </div>
      </section>

        <div v-if="recurringSheetOpen" class="sheet-mask" @click.self="closeRecurringSheet">
          <section class="mobile-sheet recurring-sheet" :class="{ dragging: sheetDragging }" :style="sheetDragStyle()">
            <div class="sheet-handle" @pointerdown.prevent="startSheetPointerDrag($event, closeRecurringSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeRecurringSheet)"></div>
            <button class="sheet-close" @click="closeRecurringSheet"><X :size="22" /></button>
            <div class="sheet-room-head" @pointerdown.prevent="startSheetPointerDrag($event, closeRecurringSheet)" @touchstart.prevent="startSheetTouchDrag($event, closeRecurringSheet)">
              <h2>{{ recurringMode === 'manage' ? '周期预约管理' : recurringMode === 'create' ? '预约周期会议' : '取消周期会议' }}</h2>
              <p>{{ recurringMode === 'manage' ? '选择要执行的周期会议操作' : recurringMode === 'create' ? '每周重复，先预览再确认创建' : '选择周期组，取消该组下未来有效预约' }}</p>
            </div>

            <div v-if="recurringMode === 'manage'" class="mobile-menu-card recurring-manage-card">
              <button @click="openRecurringSheet">
                <CalendarCheck :size="30" />
                <span>预约周期会议</span>
                <ChevronRight :size="24" />
              </button>
              <button @click="openRecurringCancelSheet">
                <XCircle :size="30" />
                <span>取消周期会议</span>
                <ChevronRight :size="24" />
              </button>
            </div>

            <template v-else-if="recurringMode === 'create'">
              <form class="form-stack sheet-form" @submit.prevent="previewRecurringBookings">
                <label><span>会议室 <b class="required-star">*</b></span><select v-model.number="recurringForm.room_id" required><optgroup v-for="group in recurringRoomsByCampus" :key="group.campus" :label="group.campus"><option v-for="room in group.rooms" :key="room.id" :value="room.id">{{ room.name }}</option></optgroup></select></label>
                <div class="time-grid"><label><span>开始日期 <b class="required-star">*</b></span><input v-model="recurringForm.start_date" type="date" required /></label><label><span>结束日期 <b class="required-star">*</b></span><input v-model="recurringForm.end_date" type="date" required /></label></div>
                <div class="weekday-grid">
                  <button v-for="item in weekdayOptions" :key="item.value" type="button" :class="{ active: recurringForm.weekdays.includes(item.value) }" @click="toggleRecurringWeekday(item.value)">{{ item.label }}</button>
                </div>
                <div class="time-grid"><label>开始小时<select v-model="recurringForm.start_hour"><option v-for="h in hourOptions" :key="h">{{ h }}</option></select></label><label>开始分钟<select v-model="recurringForm.start_minute"><option v-for="m in minuteOptions" :key="m">{{ m }}</option></select></label><label>结束小时<select v-model="recurringForm.end_hour"><option v-for="h in endHourOptions" :key="h">{{ h }}</option></select></label><label>结束分钟<select v-model="recurringForm.end_minute" :disabled="Number(recurringForm.end_hour) === CLOSE_HOUR"><option v-for="m in minuteOptions" :key="m">{{ m }}</option></select></label></div>
                <label>部门<input :value="user?.department || ''" readonly /></label>
                <label>使用人<input :value="user?.name || ''" readonly /></label>
                <label><span>会议名称 <b class="required-star">*</b></span><input v-model="recurringForm.title" required /></label>
                <label><span>参会人数 <b class="required-star">*</b></span><input v-model.number="recurringForm.attendee_count" type="number" min="1" required /></label>
                <label>备注<textarea v-model="recurringForm.note" rows="3" /></label>
                <div class="recurring-actions">
                  <button class="primary" :disabled="loading || recurringForm.weekdays.length === 0 || !recurringForm.room_id">预览</button>
                  <button type="button" :disabled="loading || !recurringResult" @click="createRecurringBookings">确认创建</button>
                </div>
              </form>
              <section v-if="recurringResult" class="recurring-result">
                <h3>{{ recurringSummary }}</h3>
                <div v-if="recurringResult.success.length"><strong>成功</strong><p v-for="item in recurringResult.success" :key="`s-${item.start_at}`">{{ recurringItemText(item) }}</p></div>
                <div v-if="recurringResult.conflicts.length"><strong>冲突</strong><p v-for="item in recurringResult.conflicts" :key="`c-${item.start_at}`">{{ recurringItemText(item) }} {{ recurringConflictText(item) }}</p></div>
                <div v-if="recurringResult.expired.length"><strong>过期</strong><p v-for="item in recurringResult.expired" :key="`e-${item.start_at}`">{{ recurringItemText(item) }} 已结束</p></div>
              </section>
            </template>

            <template v-else>
              <div class="recurring-result recurring-series-list">
                <button class="primary wide-button" :disabled="loading" @click="withLoading(loadRecurringSeries)">刷新周期组</button>
                <div v-if="recurringSeriesList.length === 0" class="empty mobile-empty">暂无可取消的周期会议</div>
                <article v-for="series in recurringSeriesList" :key="series.id" class="admin-list-card">
                  <h3>{{ series.title }}</h3>
                  <p><strong>院区：</strong>{{ recurringCampus(series) }}</p>
                  <p><strong>会议室：</strong>{{ series.room.name }}</p>
                  <p><strong>周期：</strong>{{ recurringSeriesText(series) }}</p>
                  <p><strong>使用人：</strong>{{ series.department || series.created_by.department }} {{ series.user_name || series.created_by.name }}</p>
                  <p><strong>未来有效：</strong>{{ series.future_active_booking_count }} 条</p>
                  <button :disabled="loading || series.future_active_booking_count === 0" @click="cancelRecurringSeries(series)">取消这个周期会议</button>
                </article>
              </div>
              <section v-if="recurringSeriesCancelResult" class="recurring-result">
                <h3>{{ recurringSeriesCancelSummary }}</h3>
                <div v-if="recurringSeriesCancelResult.cancelled.length"><strong>已取消</strong><p v-for="booking in recurringSeriesCancelResult.cancelled" :key="`series-cancel-${booking.id}`">{{ bookingDateTimeText(booking) }} · {{ booking.room.name }}</p></div>
              </section>
            </template>
          </section>
        </div>

      <div v-if="notice || error" class="toast" :class="{ error: !!error }">{{ error || notice }}</div>

      <section class="desktop-app">
        <div class="pc-shell">
          <aside class="pc-sidebar">
            <div class="pc-brand">
              <span class="pc-brand-icon"><MonitorUp :size="24" /></span>
              <div class="pc-brand-copy"><strong>医务科会议室</strong><small>预约管理系统</small></div>
            </div>

            <nav class="pc-navigation" aria-label="主要导航">
              <button title="会议室预约" :class="{ active: desktopView === 'schedule' }" @click="setDesktopView('schedule')"><CalendarDays :size="20" /><span>会议室预约</span></button>
              <button title="我的预约" :class="{ active: desktopView === 'mine' }" @click="setDesktopView('mine')"><UserRound :size="20" /><span>我的预约</span></button>
              <template v-if="isAdmin">
                <p>管理后台</p>
                <button title="预约管理" :class="{ active: desktopView === 'admin-bookings' }" @click="setDesktopView('admin-bookings')"><CalendarCheck :size="20" /><span>预约管理</span></button>
                <button title="会议室管理" :class="{ active: desktopView === 'admin-rooms' }" @click="setDesktopView('admin-rooms')"><MonitorUp :size="20" /><span>会议室管理</span></button>
                <button title="周期预约管理" :class="{ active: desktopView === 'admin-recurring' }" @click="setDesktopView('admin-recurring')"><RefreshCcw :size="20" /><span>周期预约管理</span></button>
                <button title="统计信息" :class="{ active: desktopView === 'admin-stats' }" @click="setDesktopView('admin-stats')"><BarChart3 :size="20" /><span>统计信息</span></button>
              </template>
            </nav>

            <footer class="pc-sidebar-footer">
              <span class="pc-user-avatar">{{ user?.name?.slice(0, 1) }}</span>
              <div class="pc-user-copy"><strong>{{ user?.name }}</strong><small>{{ user?.department }} · {{ user?.role }}</small></div>
              <button title="退出登录" @click="logout"><LogOut :size="19" /></button>
            </footer>
          </aside>

          <div class="pc-workspace">
            <header class="pc-header">
              <div><span>医务科会议室</span><h1>{{ desktopTitle }}</h1></div>
            </header>

            <main class="pc-content">
              <section v-show="desktopView === 'schedule'" class="pc-page">
                <div class="pc-toolbar">
                  <div class="pc-date-controls">
                    <label class="pc-campus-select"><Building2 :size="16" /><span>院区</span><select v-model="selectedCampus" @change="handleCampusChange"><option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option></select></label>
                    <span class="pc-control-divider"></span>
                    <button class="icon-button" title="前一天" @click="shiftDate(-1)"><ChevronLeft :size="19" /></button>
                    <label class="pc-date-picker"><span>{{ mobileDateLabel(selectedDate) }}</span><input v-model="selectedDate" type="date" @change="handleDesktopScheduleDateChange" /></label>
                    <button class="icon-button" title="后一天" @click="shiftDate(1)"><ChevronRight :size="19" /></button>
                    <button @click="desktopGoToday">今天</button>
                    <button :disabled="scheduleRefreshing" @click="refreshScheduleWithSkeleton"><RefreshCcw :size="17" />{{ scheduleRefreshing ? '刷新中' : '刷新' }}</button>
                  </div>
                  <span v-if="selectedSlotStart !== null && selectedRoom && !desktopBookingDrawerOpen" class="pc-selection-hint">{{ selectedRoom.name }} · 起点 {{ minutesToText(OPEN_HOUR * 60 + selectedSlotStart * SLOT_MINUTES) }}，请再选择结束时段</span>
                </div>

                <div v-if="scheduleRefreshing" class="pc-loading-band">正在刷新会议室状态</div>
                <div v-else-if="visibleScheduleRooms.length === 0" class="pc-table-empty pc-schedule-empty"><span><Building2 :size="26" /></span><strong>{{ selectedCampus }}院区暂无可预定会议室</strong></div>
                <div v-else class="pc-schedule-table">
                  <div class="pc-schedule-head">
                    <span>会议室</span>
                    <div class="pc-timeline-hours"><span v-for="hour in desktopHours" :key="hour" :style="{ left: `${((hour - OPEN_HOUR) / (CLOSE_HOUR - OPEN_HOUR)) * 100}%` }">{{ hour }}</span></div>
                  </div>
                  <article v-for="item in visibleScheduleRooms" :key="item.room.id" class="pc-schedule-row">
                    <div class="pc-room-summary">
                      <strong>{{ item.room.name }}</strong>
                      <span>{{ item.room.location || '暂无位置' }} · {{ item.room.capacity }}人</span>
                      <small>{{ item.room.description || '暂无备注或设备说明' }}</small>
                    </div>
                    <div class="pc-slot-grid">
                      <button
                        v-for="slot in desktopSlotsForRoom(item)"
                        :key="slot.index"
                        :class="{ occupied: !!slot.occupiedBy, expired: slot.expired, selected: slot.selected, 'booking-start': slot.bookingStart, 'booking-end': slot.bookingEnd }"
                        :disabled="slot.expired"
                        :title="slot.occupiedBy ? undefined : slot.expired ? '已过期' : `${minutesToText(OPEN_HOUR * 60 + slot.index * SLOT_MINUTES)}-${minutesToText(OPEN_HOUR * 60 + (slot.index + 1) * SLOT_MINUTES)}`"
                        :aria-label="slot.occupiedBy ? bookingOccupantText(slot.occupiedBy) : slot.expired ? '已过期' : `${minutesToText(OPEN_HOUR * 60 + slot.index * SLOT_MINUTES)}-${minutesToText(OPEN_HOUR * 60 + (slot.index + 1) * SLOT_MINUTES)}`"
                        @pointerenter="slot.occupiedBy && showDesktopBookingPreview($event, slot.occupiedBy)"
                        @pointerleave="hideDesktopBookingPreview"
                        @focus="slot.occupiedBy && showDesktopBookingPreview($event, slot.occupiedBy)"
                        @blur="hideDesktopBookingPreview"
                        @click="chooseDesktopSlot(item, slot.index)"
                      />
                    </div>
                  </article>
                </div>
                <div class="pc-timeline-legend"><span class="expired">已过期</span><span class="occupied">已预约</span><span class="available">可预约</span></div>
              </section>

              <section v-show="desktopView === 'mine'" class="pc-page">
                <div class="pc-tab-row">
                  <button :class="{ active: desktopMineView === 'upcoming' }" @click="desktopMineView = 'upcoming'">即将开始 {{ upcoming.length }}</button>
                  <button :class="{ active: desktopMineView === 'recurring' }" @click="desktopMineView = 'recurring'">周期会议 {{ activeMyRecurringSeries.length }}</button>
                  <button :class="{ active: desktopMineView === 'finished' }" @click="desktopMineView = 'finished'">已结束 {{ finished.length }}</button>
                  <button :class="{ active: desktopMineView === 'cancelled' }" @click="desktopMineView = 'cancelled'">已取消 {{ cancelled.length }}</button>
                </div>

                <div v-if="desktopMineView === 'recurring'" class="pc-data-table pc-recurring-table">
                  <div class="pc-table-head"><span>会议名称</span><span>院区</span><span>会议室</span><span>重复规则</span><span>日期范围</span><span>未来预约</span><span>操作</span></div>
                  <div v-if="activeMyRecurringSeries.length === 0" class="pc-table-empty">暂无周期会议</div>
                  <article v-for="series in activeMyRecurringSeries" :key="series.id" class="pc-table-row">
                    <strong>{{ series.title }}</strong><span>{{ recurringCampus(series) }}</span><span>{{ series.room.name }}</span><span>{{ recurringSeriesShortText(series) }}</span><span>{{ series.start_date }} 至 {{ series.end_date }}</span><span>{{ series.future_active_booking_count }} 次</span><button title="查看周期会议详情" @click="openDesktopRecurringDetail(series)"><Eye :size="16" />详情</button>
                  </article>
                </div>

                <div v-else class="pc-data-table pc-my-table">
                  <div class="pc-table-head"><span>日期</span><span>时间</span><span>院区</span><span>会议室</span><span>会议名称</span><span>位置</span><span>操作</span></div>
                  <div v-if="desktopMyBookingRows.length === 0" class="pc-table-empty">当前分类暂无预约</div>
                  <article v-for="booking in desktopMyBookingRows" :key="booking.id" class="pc-table-row">
                    <span>{{ desktopBookingDateText(booking) }}</span>
                    <strong>{{ formatLocalTime(booking.start_at) }}-{{ formatLocalTime(booking.end_at) }}</strong>
                    <span>{{ bookingCampus(booking) }}</span>
                    <span>{{ booking.room.name }}</span>
                    <span>{{ booking.title }}</span>
                    <span>{{ booking.room.location || '暂无位置' }}</span>
                    <div class="pc-row-actions">
                      <button title="查看会议详情" @click="openBookingDetail(booking)"><Eye :size="16" />详情</button>
                      <button v-if="desktopMineView === 'upcoming'" title="修改预约" @click="prepareDesktopBooking(booking)"><Pencil :size="16" />修改</button>
                      <button v-if="desktopMineView === 'upcoming'" class="danger" title="取消预约" @click="cancelDesktopBooking(booking)"><XCircle :size="16" />取消</button>
                    </div>
                  </article>
                </div>
              </section>

              <section v-if="isAdmin" v-show="desktopView === 'admin-bookings'" class="pc-page">
                <div class="pc-toolbar">
                  <div class="pc-date-controls">
                    <label class="pc-campus-select"><Building2 :size="16" /><span>院区</span><select v-model="adminBookingCampus" @change="handleAdminBookingFilterChange"><option value="all">全部院区</option><option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option></select></label>
                    <span class="pc-control-divider"></span>
                    <button class="icon-button" title="前一天" @click="shiftAdminBookingDate(-1)"><ChevronLeft :size="19" /></button>
                    <label class="pc-date-picker"><span>{{ mobileDateLabel(adminBookingDate) }}</span><input v-model="adminBookingDate" type="date" @change="handleAdminBookingFilterChange" /></label>
                    <button class="icon-button" title="后一天" @click="shiftAdminBookingDate(1)"><ChevronRight :size="19" /></button>
                    <button @click="withLoading(loadAdminBookings)"><RefreshCcw :size="17" />刷新</button>
                  </div>
                </div>
                <div class="pc-tab-row compact">
                  <button :class="{ active: adminBookingStatus === 'active' }" @click="adminBookingStatus = 'active'">有效</button>
                  <button :class="{ active: adminBookingStatus === 'finished' }" @click="adminBookingStatus = 'finished'">已结束</button>
                  <button :class="{ active: adminBookingStatus === 'cancelled' }" @click="adminBookingStatus = 'cancelled'">已取消</button>
                </div>
                <div class="pc-data-table pc-admin-booking-table">
                  <div class="pc-table-head"><span>时间</span><span>院区</span><span>会议室</span><span>会议名称</span><span>科室 / 使用人</span><span>状态</span><span>操作</span></div>
                  <div v-if="adminFilteredBookings.length === 0" class="pc-table-empty">当前条件下暂无预约</div>
                  <article v-for="booking in adminFilteredBookings" :key="booking.id" class="pc-table-row">
                    <strong>{{ formatLocalTime(booking.start_at) }}-{{ formatLocalTime(booking.end_at) }}</strong>
                    <span>{{ bookingCampus(booking) }}</span>
                    <span>{{ booking.room.name }}</span>
                    <span>{{ booking.title }}</span>
                    <span>{{ booking.department || booking.applicant.department }} · {{ booking.user_name || booking.applicant.name }}</span>
                    <span><b :class="['pc-status', booking.status === 'cancelled' ? 'disabled' : 'active']">{{ booking.status === 'cancelled' ? '已取消' : adminBookingStatus === 'finished' ? '已结束' : '有效' }}</b></span>
                    <div class="pc-row-actions">
                      <button title="查看会议详情" @click="openBookingDetail(booking)"><Eye :size="16" />详情</button>
                      <button v-if="booking.status === 'active' && new Date(booking.end_at) > new Date()" class="danger" title="取消预约" @click="adminCancelBooking(booking)"><XCircle :size="16" />取消</button>
                    </div>
                  </article>
                </div>
              </section>

              <section v-if="isAdmin" v-show="desktopView === 'admin-rooms'" class="pc-page">
                <div class="pc-toolbar">
                  <div class="pc-room-filters"><label class="pc-campus-select"><Building2 :size="16" /><span>院区</span><select v-model="adminRoomCampus"><option value="all">全部院区</option><option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option></select></label><span class="pc-control-divider"></span><div class="pc-tab-row compact">
                    <button :class="{ active: adminRoomStatus === 'all' }" @click="adminRoomStatus = 'all'">全部 {{ adminCampusRooms.length }}</button>
                    <button :class="{ active: adminRoomStatus === 'active' }" @click="adminRoomStatus = 'active'">启用 {{ adminCampusRooms.filter((room) => room.is_active).length }}</button>
                    <button :class="{ active: adminRoomStatus === 'disabled' }" @click="adminRoomStatus = 'disabled'">停用 {{ adminCampusRooms.filter((room) => !room.is_active).length }}</button>
                  </div></div>
                  <button class="primary" @click="openMobileRoomSheet()"><Plus :size="18" />新增会议室</button>
                </div>
                <div class="pc-data-table pc-room-table">
                  <div class="pc-table-head"><span>院区</span><span>会议室</span><span>位置</span><span>容量</span><span>备注 / 设备</span><span>状态</span><span>操作</span></div>
                  <div v-if="adminFilteredRooms.length === 0" class="pc-table-empty">当前条件下暂无会议室</div>
                  <article v-for="room in adminFilteredRooms" :key="room.id" class="pc-table-row">
                    <span>{{ room.campus }}</span><strong>{{ room.name }}</strong><span>{{ room.location || '暂无位置' }}</span><span>{{ room.capacity }} 人</span><span>{{ room.description || '暂无' }}</span><span><b :class="['pc-status', room.is_active ? 'active' : 'disabled']">{{ room.is_active ? '启用' : '停用' }}</b></span>
                    <div class="pc-row-actions"><button title="编辑会议室" @click="openMobileRoomSheet(room)"><Pencil :size="16" />编辑</button><button :class="{ danger: room.is_active }" :title="room.is_active ? '停用会议室' : '启用会议室'" @click="toggleRoomStatus(room)"><Power :size="16" />{{ room.is_active ? '停用' : '启用' }}</button></div>
                  </article>
                </div>
              </section>

              <section v-if="isAdmin" v-show="desktopView === 'admin-recurring'" class="pc-page">
                <div class="pc-toolbar">
                  <div class="pc-tab-row compact">
                    <button :class="{ active: desktopRecurringStatus === 'active' }" @click="desktopRecurringStatus = 'active'; withLoading(loadDesktopRecurringSeries)">有效周期</button>
                    <button :class="{ active: desktopRecurringStatus === 'cancelled' }" @click="desktopRecurringStatus = 'cancelled'; withLoading(loadDesktopRecurringSeries)">已取消</button>
                  </div>
                  <button class="primary" @click="openDesktopRecurringCreate"><Plus :size="18" />新建周期会议</button>
                </div>
                <div class="pc-data-table pc-series-table">
                  <div class="pc-table-head"><span>会议名称</span><span>院区</span><span>会议室</span><span>重复星期</span><span>时间</span><span>日期范围</span><span>未来预约</span><span>操作</span></div>
                  <div v-if="desktopRecurringSeriesList.length === 0" class="pc-table-empty">当前分类暂无周期会议</div>
                  <article v-for="series in desktopRecurringSeriesList" :key="series.id" class="pc-table-row">
                    <strong>{{ series.title }}</strong><span>{{ recurringCampus(series) }}</span><span>{{ series.room.name }}</span><span>{{ series.weekdays.map((day) => weekdayOptions.find((item) => item.value === day)?.label).join('、') }}</span><span>{{ series.start_time }}-{{ series.end_time }}</span><span>{{ series.start_date }} 至 {{ series.end_date }}</span><span>{{ series.future_active_booking_count }} 次</span>
                    <div class="pc-row-actions"><button title="查看周期会议详情" @click="openDesktopRecurringDetail(series)"><Eye :size="16" />详情</button><button v-if="series.status === 'active'" class="danger" title="取消周期会议" @click="cancelDesktopRecurringSeries(series)"><XCircle :size="16" />取消</button></div>
                  </article>
                </div>
              </section>

              <section v-if="isAdmin" v-show="desktopView === 'admin-stats'" class="pc-page">
                <div class="pc-toolbar"><span></span><button @click="refreshAdminStats"><RefreshCcw :size="17" />刷新</button></div>
                <div class="pc-stats">
                  <article><span>今日预约</span><strong>{{ stats.today_bookings || 0 }}</strong></article>
                  <article><span>本周预约</span><strong>{{ stats.week_bookings || 0 }}</strong></article>
                  <article><span>启用会议室</span><strong>{{ stats.active_rooms || 0 }}</strong></article>
                </div>
              </section>
            </main>
          </div>
        </div>

        <div
          v-if="desktopBookingPreview"
          class="pc-booking-preview"
          :class="desktopBookingPreview.placement"
          :style="{ left: `${desktopBookingPreview.left}px`, top: `${desktopBookingPreview.top}px` }"
          role="tooltip"
        >
          <strong>{{ desktopBookingPreview.booking.title }}</strong>
          <span>{{ bookingCampus(desktopBookingPreview.booking) }} · {{ desktopBookingPreview.booking.room.name }} · {{ formatLocalTime(desktopBookingPreview.booking.start_at) }}-{{ formatLocalTime(desktopBookingPreview.booking.end_at) }}</span>
          <small>{{ desktopBookingPreview.booking.department || desktopBookingPreview.booking.applicant.department }} · {{ desktopBookingPreview.booking.user_name || desktopBookingPreview.booking.applicant.name }}</small>
        </div>

        <div v-if="desktopBookingDrawerOpen" class="pc-drawer-mask" @click.self="closeDesktopBookingDrawer">
          <aside class="pc-drawer pc-booking-drawer">
            <header><div><span>预约信息</span><h2>{{ bookingForm.id ? '修改预约' : '新建预约' }}</h2></div><button class="icon-button" title="关闭" @click="closeDesktopBookingDrawer"><X :size="20" /></button></header>
            <form class="form-stack" @submit.prevent="saveBooking">
              <label><span>会议室 <b class="required-star">*</b></span><select v-model.number="bookingForm.room_id" required><optgroup v-for="group in recurringRoomsByCampus" :key="group.campus" :label="group.campus"><option v-for="room in group.rooms" :key="room.id" :value="room.id">{{ room.name }}</option></optgroup></select></label>
              <div class="pc-readonly-grid"><label>部门<input :value="user?.department || ''" readonly /></label><label>使用人<input :value="user?.name || ''" readonly /></label></div>
              <label><span>日期 <b class="required-star">*</b></span><input v-model="bookingForm.booking_date" type="date" required /></label>
              <div class="time-grid"><label>开始小时<select v-model="bookingForm.start_hour"><option v-for="hour in hourOptions" :key="hour">{{ hour }}</option></select></label><label>开始分钟<select v-model="bookingForm.start_minute"><option v-for="minute in minuteOptions" :key="minute">{{ minute }}</option></select></label><label>结束小时<select v-model="bookingForm.end_hour"><option v-for="hour in endHourOptions" :key="hour">{{ hour }}</option></select></label><label>结束分钟<select v-model="bookingForm.end_minute" :disabled="Number(bookingForm.end_hour) === CLOSE_HOUR"><option v-for="minute in minuteOptions" :key="minute">{{ minute }}</option></select></label></div>
              <label><span>会议名称 <b class="required-star">*</b></span><input v-model="bookingForm.title" required /></label>
              <label><span>参会人数 <b class="required-star">*</b></span><input v-model.number="bookingForm.attendee_count" type="number" min="1" required /></label>
              <label>备注<textarea v-model="bookingForm.note" rows="4" /></label>
              <div class="pc-drawer-actions"><button type="button" @click="closeDesktopBookingDrawer">取消</button><button class="primary" :disabled="loading || !bookingForm.room_id"><Save :size="17" />{{ bookingForm.id ? '保存修改' : '提交预约' }}</button></div>
            </form>
          </aside>
        </div>

        <div v-if="mobileRoomSheetOpen" class="pc-drawer-mask" @click.self="closeMobileRoomSheet">
          <aside class="pc-drawer">
            <header><div><span>会议室信息</span><h2>{{ roomForm.id ? '编辑会议室' : '新增会议室' }}</h2></div><button class="icon-button" title="关闭" @click="closeMobileRoomSheet"><X :size="20" /></button></header>
            <form class="form-stack" @submit.prevent="saveRoom">
              <label><span>院区 <b class="required-star">*</b></span><select v-model="roomForm.campus" :disabled="roomForm.campus_locked" required><option v-for="campus in CAMPUS_OPTIONS" :key="campus" :value="campus">{{ campus }}</option></select><small v-if="roomForm.campus_locked" class="form-hint">已有预约或周期记录，院区不可修改</small></label><label><span>名称 <b class="required-star">*</b></span><input v-model="roomForm.name" required /></label><label>位置<input v-model="roomForm.location" /></label><label><span>容量 <b class="required-star">*</b></span><input v-model.number="roomForm.capacity" type="number" min="1" required /></label><label>备注/设备<textarea v-model="roomForm.description" rows="4" /></label><label class="check pc-check"><input v-model="roomForm.is_active" type="checkbox" />启用会议室</label>
              <div class="pc-drawer-actions"><button type="button" @click="closeMobileRoomSheet">取消</button><button class="primary" :disabled="loading"><Save :size="17" />保存会议室</button></div>
            </form>
          </aside>
        </div>

        <div v-if="detailBooking" class="pc-drawer-mask" @click.self="closeDetailSheet">
          <aside class="pc-drawer">
            <header><div><span>预约记录</span><h2>会议详情</h2></div><button class="icon-button" title="关闭" @click="closeDetailSheet"><X :size="20" /></button></header>
            <div class="pc-detail-list">
              <div><span>会议室</span><strong>{{ detailBooking.room.name }}</strong></div><div><span>院区</span><strong>{{ bookingCampus(detailBooking) }}</strong></div><div><span>时间</span><strong>{{ bookingDateTimeText(detailBooking) }}</strong></div><div><span>地址</span><strong>{{ detailBooking.room.location || '暂无' }}</strong></div><div><span>部门</span><strong>{{ detailBooking.department || detailBooking.applicant.department }}</strong></div><div><span>使用人</span><strong>{{ detailBooking.user_name || detailBooking.applicant.name }}</strong></div><div><span>会议名称</span><strong>{{ detailBooking.title }}</strong></div><div><span>参会人数</span><strong>{{ detailBooking.attendee_count }}人</strong></div><div><span>备注</span><strong>{{ detailBooking.note || '无' }}</strong></div><div><span>状态</span><strong>{{ detailBooking.status === 'active' ? '有效' : '已取消' }}</strong></div>
            </div>
          </aside>
        </div>

        <div v-if="desktopRecurringDrawerOpen" class="pc-drawer-mask" @click.self="closeDesktopRecurringDrawer">
          <aside class="pc-drawer pc-recurring-drawer">
            <header><div><span>周期组</span><h2>{{ desktopSelectedSeries ? '周期会议详情' : '新建周期会议' }}</h2></div><button class="icon-button" title="关闭" @click="closeDesktopRecurringDrawer"><X :size="20" /></button></header>
            <template v-if="desktopSelectedSeries">
              <div class="pc-detail-list"><div><span>会议名称</span><strong>{{ desktopSelectedSeries.title }}</strong></div><div><span>院区</span><strong>{{ recurringCampus(desktopSelectedSeries) }}</strong></div><div><span>会议室</span><strong>{{ desktopSelectedSeries.room.name }}</strong></div><div><span>周期规则</span><strong>{{ recurringSeriesText(desktopSelectedSeries) }}</strong></div><div><span>科室</span><strong>{{ desktopSelectedSeries.department || desktopSelectedSeries.created_by.department }}</strong></div><div><span>使用人</span><strong>{{ desktopSelectedSeries.user_name || desktopSelectedSeries.created_by.name }}</strong></div><div><span>参会人数</span><strong>{{ desktopSelectedSeries.attendee_count }}人</strong></div><div><span>未来预约</span><strong>{{ desktopSelectedSeries.future_active_booking_count }}次</strong></div><div><span>备注</span><strong>{{ desktopSelectedSeries.note || '无' }}</strong></div><div><span>状态</span><strong>{{ desktopSelectedSeries.status === 'active' ? '有效' : '已取消' }}</strong></div></div>
              <button v-if="isAdmin && desktopView === 'admin-recurring' && desktopSelectedSeries.status === 'active'" class="danger pc-full-button" @click="cancelDesktopRecurringSeries(desktopSelectedSeries)"><XCircle :size="17" />取消这个周期会议</button>
            </template>
            <template v-else>
              <form class="form-stack" @submit.prevent="previewRecurringBookings">
                <label><span>会议室 <b class="required-star">*</b></span><select v-model.number="recurringForm.room_id" required><optgroup v-for="group in recurringRoomsByCampus" :key="group.campus" :label="group.campus"><option v-for="room in group.rooms" :key="room.id" :value="room.id">{{ room.name }}</option></optgroup></select></label>
                <div class="pc-readonly-grid"><label><span>开始日期 <b class="required-star">*</b></span><input v-model="recurringForm.start_date" type="date" required /></label><label><span>结束日期 <b class="required-star">*</b></span><input v-model="recurringForm.end_date" type="date" required /></label></div>
                <div class="weekday-grid"><button v-for="item in weekdayOptions" :key="item.value" type="button" :class="{ active: recurringForm.weekdays.includes(item.value) }" @click="toggleRecurringWeekday(item.value)">{{ item.label }}</button></div>
                <div class="time-grid"><label>开始小时<select v-model="recurringForm.start_hour"><option v-for="hour in hourOptions" :key="hour">{{ hour }}</option></select></label><label>开始分钟<select v-model="recurringForm.start_minute"><option v-for="minute in minuteOptions" :key="minute">{{ minute }}</option></select></label><label>结束小时<select v-model="recurringForm.end_hour"><option v-for="hour in endHourOptions" :key="hour">{{ hour }}</option></select></label><label>结束分钟<select v-model="recurringForm.end_minute" :disabled="Number(recurringForm.end_hour) === CLOSE_HOUR"><option v-for="minute in minuteOptions" :key="minute">{{ minute }}</option></select></label></div>
                <div class="pc-readonly-grid"><label>部门<input :value="user?.department || ''" readonly /></label><label>使用人<input :value="user?.name || ''" readonly /></label></div>
                <label><span>会议名称 <b class="required-star">*</b></span><input v-model="recurringForm.title" required /></label><label><span>参会人数 <b class="required-star">*</b></span><input v-model.number="recurringForm.attendee_count" type="number" min="1" required /></label><label>备注<textarea v-model="recurringForm.note" rows="3" /></label>
                <div class="pc-drawer-actions"><button class="primary" :disabled="loading || recurringForm.weekdays.length === 0 || !recurringForm.room_id">预览</button><button type="button" :disabled="loading || !recurringResult" @click="createDesktopRecurringBookings">确认创建</button></div>
              </form>
              <section v-if="recurringResult" class="pc-recurring-result"><h3>{{ recurringSummary }}</h3><div v-if="recurringResult.success.length"><strong>可创建</strong><p v-for="item in recurringResult.success" :key="`pc-s-${item.start_at}`">{{ recurringItemText(item) }}</p></div><div v-if="recurringResult.conflicts.length"><strong>冲突跳过</strong><p v-for="item in recurringResult.conflicts" :key="`pc-c-${item.start_at}`">{{ recurringItemText(item) }} · {{ recurringConflictText(item) }}</p></div><div v-if="recurringResult.expired.length"><strong>过期跳过</strong><p v-for="item in recurringResult.expired" :key="`pc-e-${item.start_at}`">{{ recurringItemText(item) }}</p></div></section>
            </template>
          </aside>
        </div>
      </section>
    </template>
  </main>
</template>
