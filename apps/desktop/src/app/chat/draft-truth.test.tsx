import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DraftTruth } from './draft-truth'

describe('DraftTruth', () => {
  it('renders a healthy empty-store state as a Desktop draft with gateway and model truth', () => {
    render(
      <DraftTruth
        gatewayOpen
        inferenceStatus={{
          checksDisagree: false,
          ready: true,
          reason: null,
          source: 'runtime_check'
        }}
        model="openai/gpt-5.5"
        modelReadbackError={null}
      />
    )

    expect(screen.getByText('Desktop draft')).not.toBeNull()
    expect(screen.getByText('Gateway connected')).not.toBeNull()
    expect(screen.getByText('gpt-5.5')).not.toBeNull()
    expect(screen.queryByText(/telegram/i)).toBeNull()
  })

  it('names an unobserved model instead of rendering a blank', () => {
    render(
      <DraftTruth
        gatewayOpen
        inferenceStatus={{
          checksDisagree: false,
          ready: true,
          reason: null,
          source: 'runtime_check'
        }}
        model=""
        modelReadbackError="Configured model readback failed."
      />
    )

    expect(screen.getByText('Model not observed')).not.toBeNull()
  })
})
