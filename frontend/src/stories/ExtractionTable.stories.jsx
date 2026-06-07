import { expect } from 'storybook/test'
import ExtractionTable from '../components/documents/ExtractionTable'

export default {
  title: 'Documents/ExtractionTable',
  component: ExtractionTable,
  tags: ['ai-generated'],
}

const makeField = (overrides) => ({
  id: Math.random().toString(36).slice(2),
  field_name: 'grantor_name',
  field_value: 'John A. Smith',
  confidence: 0.95,
  ocr_confidence: 0.91,
  attempt: 1,
  ...overrides,
})

const SAMPLE_EXTRACTIONS = [
  makeField({ field_name: 'grantor_name',   field_value: 'John A. Smith',     confidence: 0.97, ocr_confidence: 0.94 }),
  makeField({ field_name: 'grantee_name',   field_value: 'Cedar Grove Community Development Corporation', confidence: 0.91, ocr_confidence: 0.88 }),
  makeField({ field_name: 'sale_amount',    field_value: '10.00',             confidence: 0.85, ocr_confidence: 0.72 }),
  makeField({ field_name: 'recording_date', field_value: '2024-03-14',        confidence: 0.99, ocr_confidence: 0.98 }),
  makeField({ field_name: 'parcel_number',  field_value: '34-021-00-00-052-001', confidence: 0.62, ocr_confidence: 0.55 }),
]

export const Default = {
  name: '✓ Populated fields',
  render: () => (
    <div style={{ width: '500px' }}>
      <ExtractionTable extractions={SAMPLE_EXTRACTIONS} />
    </div>
  ),
  // Proves confidence values render in the DOM
  play: async ({ canvas }) => {
    await expect(canvas.getByText('grantor_name')).toBeVisible()
    await expect(canvas.getByText('John A. Smith')).toBeVisible()
  },
}

export const Empty = {
  name: '⚠ No extractions',
  render: () => <ExtractionTable extractions={[]} />,
}

export const LowConfidenceRows = {
  name: '⚠ Low confidence rows (yellow highlight)',
  render: () => (
    <div style={{ width: '500px' }}>
      <ExtractionTable
        extractions={[
          makeField({ field_name: 'sale_amount',   field_value: '$10.00', confidence: 0.45, ocr_confidence: 0.40 }),
          makeField({ field_name: 'grantor_name',  field_value: 'Smith',  confidence: 0.65, ocr_confidence: 0.90 }),
          makeField({ field_name: 'parcel_number', field_value: '',       confidence: 0.10, ocr_confidence: 0.15 }),
        ]}
      />
    </div>
  ),
}

export const HumanCorrected = {
  name: '✓ Human corrected field (attempt=3)',
  render: () => (
    <div style={{ width: '500px' }}>
      <ExtractionTable
        extractions={[makeField({ attempt: 3, field_value: 'Jane B. Smith (corrected)' })]}
      />
    </div>
  ),
}

export const NarrowContainer = {
  name: '⚠ Narrow container (280px) — text must wrap',
  render: () => (
    <div style={{ width: '280px' }}>
      <ExtractionTable
        extractions={[
          makeField({ field_name: 'legal_description_full_text', field_value: 'Lot 14 of the Cedar Grove Plat as recorded in Volume 3 Page 47 of the Madison County Auditor records.' }),
          makeField({ field_name: 'grantor_name', field_value: 'John A. Smith' }),
        ]}
      />
    </div>
  ),
}
