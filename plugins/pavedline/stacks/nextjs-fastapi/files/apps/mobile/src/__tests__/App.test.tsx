import { act, fireEvent, render, screen } from '@testing-library/react-native'

import App from '../App'
import type { Health } from '../health'
import { UpdateRequired } from '../UpdateRequired'

const ok = (minAppVersion: string | null = '0.0.0'): (() => Promise<Health>) => async () => ({ state: 'ok', minAppVersion })

describe('App', () => {
  it('shows the loading state, then the API status', async () => {
    let finish: (h: Health) => void = () => {}
    const pending = new Promise<Health>((resolve) => {
      finish = resolve
    })
    await render(<App appVersion="1.0.0" fetchHealth={() => pending} />)
    expect(screen.getByLabelText('Checking the API')).toBeTruthy()
    await act(async () => finish({ state: 'ok', minAppVersion: '0.0.0' }))
    expect(await screen.findByLabelText('API status: up')).toBeTruthy()
  })

  it('shows an error with a retry button that checks again', async () => {
    const fetchHealth = jest
      .fn<Promise<Health>, [string]>()
      .mockResolvedValueOnce({ state: 'error', minAppVersion: null, reason: 'unreachable' })
      .mockResolvedValueOnce({ state: 'ok', minAppVersion: '0.0.0' })
    await render(<App appVersion="1.0.0" fetchHealth={fetchHealth} />)
    expect(await screen.findByLabelText('API status: not reachable, unreachable')).toBeTruthy()
    fireEvent.press(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByLabelText('API status: up')).toBeTruthy()
    expect(fetchHealth).toHaveBeenCalledTimes(2)
  })

  it('blocks with the update screen when the app is older than the minimum', async () => {
    await render(<App appVersion="1.0.0" fetchHealth={ok('1.1.0')} />)
    expect(await screen.findByText('Please update')).toBeTruthy()
    expect(screen.queryByLabelText('API status: up')).toBeNull()
  })

  it('blocks even when the API answered with an error but sent the header', async () => {
    const failing = async (): Promise<Health> => ({ state: 'error', minAppVersion: '9.0.0', reason: 'HTTP 503' })
    await render(<App appVersion="1.0.0" fetchHealth={failing} />)
    expect(await screen.findByText('Please update')).toBeTruthy()
  })

  it('does not block at or above the minimum', async () => {
    await render(<App appVersion="1.1.0" fetchHealth={ok('1.1.0')} />)
    expect(await screen.findByLabelText('API status: up')).toBeTruthy()
  })
})

describe('UpdateRequired', () => {
  it('names the version and offers no way past it', async () => {
    await render(<UpdateRequired minimum="2.0.0" />)
    expect(screen.getByText('Please update')).toBeTruthy()
    expect(screen.getByText(/2\.0\.0/)).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('link')).toBeNull()
  })
})
