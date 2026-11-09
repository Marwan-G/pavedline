import Constants from 'expo-constants'

const extra = Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined

export const API_BASE_URL: string = extra?.apiBaseUrl ?? 'http://localhost:8000'
export const APP_VERSION: string = Constants.expoConfig?.version ?? '0.0.0'
