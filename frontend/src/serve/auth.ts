import request from '@/utils/request'

export interface AuthPayload {
  username: string
  password: string
}

export const login = (data: AuthPayload) =>
  request.post<unknown, { token: string; username: string }>('/auth/login', data)

export const sendCode = (username: string) =>
  request.post<unknown, { status: string; message: string }>('/auth/send-code', {
    username,
    password: '',
  })

export const register = (data: AuthPayload & { code: string }) =>
  request.post<unknown, { token: string; username: string }>('/auth/register', data)
