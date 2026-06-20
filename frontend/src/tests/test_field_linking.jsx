import { render, screen, fireEvent } from '@testing-library/react'

import ExtractionTable from '../components/documents/ExtractionTable'
import {
  buildPageSearchOrder,
  findFirstMatchingPage,
  pdfRegionToScreenMatch,
} from '../components/documents/pdfFieldLinking'

test('buildPageSearchOrder prefers the active page first', () => {
  expect(buildPageSearchOrder(3, 5)).toEqual([3, 1, 2, 4, 5])
})

test('pdfRegionToScreenMatch converts PDF coordinates into screen coordinates', () => {
  expect(
    pdfRegionToScreenMatch({ x: 10, y: 120, width: 40, height: 15 }, { height: 200 })
  ).toEqual({
    x: 10,
    y: 65,
    width: 40,
    height: 15,
  })
})

test('findFirstMatchingPage scans other pages when the current page has no match', async () => {
  const cache = new Map()
  const pdfProxy = {
    numPages: 2,
    getPage: async (pageNumber) => ({
      getViewport: () => ({ width: 600, height: 800 }),
      getTextContent: async () => ({
        items: pageNumber === 1
          ? [{ str: 'Not the owner', transform: [0, 0, 0, 0, 10, 200], width: 50, height: 12 }]
          : [
              { str: 'John', transform: [0, 0, 0, 0, 10, 200], width: 30, height: 12 },
              { str: ' ', transform: [0, 0, 0, 0, 40, 200], width: 8, height: 12 },
              { str: 'Smith', transform: [0, 0, 0, 0, 48, 200], width: 35, height: 12 },
            ],
      }),
    }),
  }

  const result = await findFirstMatchingPage({
    pdfProxy,
    fieldValue: 'John Smith',
    currentPage: 1,
    cache,
  })

  expect(result.pageNumber).toBe(2)
  expect(result.matches).toHaveLength(1)
  expect(cache.size).toBe(2)
})

test('ExtractionTable row click forwards field value and evidence', () => {
  const onFieldFocus = vi.fn()

  render(
    <ExtractionTable
      extractions={[
        {
          id: 'e1',
          field_name: 'grantor_name',
          field_value: 'John Smith',
          confidence: 0.91,
          ocr_confidence: 0.94,
          attempt: 3,
          evidence: { page: 2, region: { x: 1, y: 2, width: 3, height: 4 } },
        },
      ]}
      onFieldFocus={onFieldFocus}
    />
  )

  fireEvent.click(screen.getByText('grantor_name'))

  expect(onFieldFocus).toHaveBeenCalledWith(
    'grantor_name',
    'John Smith',
    { page: 2, region: { x: 1, y: 2, width: 3, height: 4 } },
  )
})
