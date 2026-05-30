import { renderHook, waitFor } from '@testing-library/react'
import { vi, it, expect, afterEach } from 'vitest'
import useExtractionStream from '../hooks/useExtractionStream'

it('cancels the stream reader when the hook unmounts during streaming', async () => {
  const cancelMock = vi.fn()
  const readerMock = {
    read: vi.fn().mockImplementation(() => new Promise(() => {})), // never resolves
    cancel: cancelMock,
  }
  const bodyMock = { getReader: () => readerMock }
  global.fetch = vi.fn().mockResolvedValue({ ok: true, body: bodyMock })

  const onUpdate = vi.fn()
  const { unmount } = renderHook(() =>
    useExtractionStream('ws-1', 'doc-1', 'pending', onUpdate)
  )

  // Wait until reader.read() has been called — proves reader was assigned
  await waitFor(() => expect(readerMock.read).toHaveBeenCalled())

  unmount()

  expect(cancelMock).toHaveBeenCalled()
})

afterEach(() => {
  vi.restoreAllMocks()
  delete global.fetch
})
