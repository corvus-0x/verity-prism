import { expect } from 'storybook/test'
import DocumentList from '../components/documents/DocumentList'

export default {
  title: 'Documents/DocumentList',
  component: DocumentList,
  tags: ['ai-generated'],
}

const WS = 'test-workspace'
let _id = 0
const makeDoc = (overrides) => ({
  id: String(++_id),
  filename: '2024-03-14_DEED_SmithJohn_WarrantyDeed.pdf',
  detected_doc_type: 'DEED',
  extraction_status: 'complete',
  source_type: 'upload',
  ...overrides,
})

const ALL_STATUSES = ['complete', 'pending', 'needs_review', 'no_schema', 'failed']

export const Empty = {
  name: '✓ Empty list',
  render: () => <DocumentList documents={[]} workspaceId={WS} />,
}

export const SingleDocument = {
  name: '✓ Single document',
  render: () => <DocumentList documents={[makeDoc()]} workspaceId={WS} />,
  // Proves the link renders with the correct workspace id in the href
  play: async ({ canvas }) => {
    const link = canvas.getByRole('link')
    await expect(link.getAttribute('href')).toContain(WS)
  },
}

export const AllExtractionStatuses = {
  name: '✓ All extraction statuses',
  render: () => (
    <DocumentList
      documents={ALL_STATUSES.map(s => makeDoc({ extraction_status: s, id: s }))}
      workspaceId={WS}
    />
  ),
}

export const LongFilename = {
  name: '⚠ Very long filename',
  render: () => (
    <div style={{ width: '300px' }}>
      <DocumentList
        documents={[makeDoc({
          filename: '2024-03-14_PARCEL-RECORD_Cedar GroveCommunityDevelopmentCorporationTrustee_WarrantyDeedRecording.pdf',
          detected_doc_type: 'PARCEL-RECORD',
          extraction_status: 'needs_review',
        })]}
        workspaceId={WS}
      />
    </div>
  ),
}

export const NarrowContainer = {
  name: '⚠ Narrow container (200px)',
  render: () => (
    <div style={{ width: '200px' }}>
      <DocumentList
        documents={ALL_STATUSES.map(s => makeDoc({ extraction_status: s, id: s }))}
        workspaceId={WS}
      />
    </div>
  ),
}

export const ManyDocuments = {
  name: '⚠ Many documents (20)',
  render: () => (
    <div style={{ width: '300px', maxHeight: '400px', overflowY: 'auto' }}>
      <DocumentList
        documents={Array.from({ length: 20 }, (_, i) => makeDoc({
          id: `many-${i}`,
          filename: `2024-0${(i % 9) + 1}-14_DEED_Document${i + 1}.pdf`,
          extraction_status: ALL_STATUSES[i % ALL_STATUSES.length],
        }))}
        workspaceId={WS}
      />
    </div>
  ),
}

export const WithApiSourceBadge = {
  name: '✓ API-sourced document (source badge)',
  render: () => (
    <DocumentList
      documents={[makeDoc({ source_type: 'api_pull', detected_doc_type: '990' })]}
      workspaceId={WS}
    />
  ),
}
