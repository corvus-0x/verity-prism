import { MemoryRouter } from 'react-router-dom'
import { initialize, mswLoader } from 'msw-storybook-addon'
import { ToastProvider } from '../src/hooks/useToast'
import { mswHandlers } from './msw-handlers'
import '../src/index.css'

initialize({ onUnhandledRequest: 'bypass' })

/** @type { import('@storybook/react-vite').Preview } */
export default {
  loaders: [mswLoader],
  parameters: {
    msw: {
      handlers: [
        ...mswHandlers.auth,
        ...mswHandlers.workspaces,
      ],
    },
    backgrounds: {
      default: 'app',
      values: [
        { name: 'app',     value: '#040810' },
        { name: 'surface', value: '#0C1424' },
        { name: 'light',   value: '#ffffff' },
      ],
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: { test: 'todo' },
  },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <ToastProvider>
          <div style={{ background: '#040810', padding: '1.5rem', minHeight: '100vh', fontFamily: 'Outfit, sans-serif' }}>
            <Story />
          </div>
        </ToastProvider>
      </MemoryRouter>
    ),
  ],
}
