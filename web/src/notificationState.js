export function unreadNotificationCount(items) {
  return (Array.isArray(items) ? items : []).filter(item => !item.is_read).length;
}

export function formatNotificationTimestamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const parts = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  const part = type => parts.find(item => item.type === type)?.value || '';
  return `${part('day')}/${part('month')}/${part('year')} ${part('hour')}:${part('minute')}`;
}

export function notificationTypeLabel(type) {
  return ({
    extraction_finished: 'Đã trích xuất OCR',
    invoice_submitted: 'Đã gửi hóa đơn',
    invoice_decision: 'Kết quả phê duyệt',
    invoice_message: 'Tin nhắn hóa đơn',
    direct_message: 'Tin nhắn nhân viên',
    schedule_assigned: 'Được giao lịch công tác',
    legacy: 'Thông báo chung',
  })[type] || type || 'Thông báo chung';
}

export function setNotificationRead(items, id) {
  return (Array.isArray(items) ? items : []).map(item =>
    item.id === id && !item.is_read ? { ...item, is_read: true } : item,
  );
}

export function setAllNotificationsRead(items) {
  return (Array.isArray(items) ? items : []).map(item =>
    item.is_read ? item : { ...item, is_read: true },
  );
}

export function notificationTarget(notification) {
  if (notification?.type === 'direct_message') return {kind: 'message', path: '/messages'};
  if (notification?.invoice_id != null && notification.type === 'invoice_message') {
    return { kind: 'invoice', path: `/invoices/${notification.invoice_id}/messages` };
  }
  if (notification?.invoice_id != null) {
    return { kind: 'invoice', path: `/invoices/${notification.invoice_id}` };
  }
  if (notification?.schedule_id != null) {
    return { kind: 'schedule', path: `/schedule#schedule-${notification.schedule_id}` };
  }
  return null;
}

export async function openNotificationAfterAccessCheck(notification, get, markRead, navigate) {
  const target = notificationTarget(notification);
  if (target?.kind === 'invoice') await get(target.path);
  if (target?.kind === 'schedule') {
    const schedules = await get('/schedules');
    if (!Array.isArray(schedules) || !schedules.some(item => Number(item.id) === Number(notification.schedule_id))) {
      throw new Error('Bạn không có quyền xem lịch công tác này.');
    }
  }
  await markRead(notification.id);
  if (target) navigate(target.path);
  return target;
}

export async function markNotificationReadAfterSuccess(items, id, request, setItems) {
  const notification = (Array.isArray(items) ? items : []).find(item => item.id === id);
  if (!notification || notification.is_read) return false;

  await request(id);
  setItems(current => setNotificationRead(current, id));
  return true;
}

export async function markAllNotificationsReadAfterSuccess(request, setItems) {
  await request();
  setItems(current => setAllNotificationsRead(current));
}
