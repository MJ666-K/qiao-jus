import { ElMessage, ElNotification } from 'element-plus'

export function notifySuccess(title: string, message?: string) {
  ElNotification({
    title,
    message,
    type: 'success',
    duration: 4000,
    position: 'top-right',
  })
}

export function notifyError(title: string, message?: string) {
  ElNotification({
    title,
    message,
    type: 'error',
    duration: 6000,
    position: 'top-right',
  })
}

export function notifyInfo(title: string, message?: string) {
  ElNotification({
    title,
    message,
    type: 'info',
    duration: 5000,
    position: 'top-right',
  })
}

export function notifyWarning(title: string, message?: string) {
  ElNotification({
    title,
    message,
    type: 'warning',
    duration: 6000,
    position: 'top-right',
  })
}

export function toastError(message: string) {
  ElMessage.error({ message, duration: 5000, showClose: true })
}
