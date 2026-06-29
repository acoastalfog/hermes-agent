import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ComposerControls } from './controls'

vi.mock('@/i18n', () => ({
  useI18n: () => ({
    t: {
      composer: {
        endConversation: 'End conversation',
        endShort: 'End',
        listening: 'Listening',
        muted: 'Muted',
        muteMic: 'Mute',
        queueMessage: 'Queue message',
        send: 'Send',
        speaking: 'Speaking',
        startVoice: 'Start voice',
        steer: 'Steer',
        stop: 'Stop',
        stopDictation: 'Stop dictation',
        stopListening: 'Stop listening',
        stopShort: 'Stop',
        thinking: 'Thinking',
        transcribing: 'Transcribing',
        transcribingDictation: 'Transcribing dictation',
        unmuteMic: 'Unmute',
        voiceDictation: 'Voice dictation'
      }
    }
  })
}))

vi.mock('@/lib/keybinds/combo', () => ({ formatCombo: () => 'Cmd+Enter' }))

vi.mock('./model-pill', () => ({
  ModelPill: ({ disabled }: { disabled: boolean }) => <button disabled={disabled}>Model picker</button>
}))

describe('ComposerControls readiness', () => {
  it('disables Send for runtime-not-ready while leaving model repair available', () => {
    render(
      <ComposerControls
        busy={false}
        busyAction="stop"
        canSteer={false}
        canSubmit
        conversation={{
          active: false,
          level: 0,
          muted: false,
          onEnd: vi.fn(),
          onStart: vi.fn(),
          onStopTurn: vi.fn(),
          onToggleMute: vi.fn(),
          status: 'idle'
        }}
        disabled={false}
        hasComposerPayload
        onDictate={vi.fn()}
        onSteer={vi.fn()}
        state={{
          model: { canSwitch: true, model: 'gpt-5.5', provider: 'custom' },
          tools: { enabled: true, label: 'Add context' },
          voice: { active: false, enabled: true }
        }}
        submitDisabled
        voiceStatus="idle"
      />
    )

    expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Model picker' }) as HTMLButtonElement).disabled).toBe(false)
  })
})
