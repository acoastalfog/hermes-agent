import type { RuntimeReadinessResult } from '@/lib/runtime-readiness'
import { cn } from '@/lib/utils'

interface DraftTruthProps {
  gatewayOpen: boolean
  inferenceStatus: RuntimeReadinessResult | null
  model: string
  modelReadbackError: string | null
}

function modelLabel(model: string) {
  const value = model.trim()

  if (!value) {
    return null
  }

  return value.split('/').filter(Boolean).at(-1) ?? value
}

export function DraftTruth({ gatewayOpen, inferenceStatus, model, modelReadbackError }: DraftTruthProps) {
  const observedModel = modelLabel(model)

  return (
    <header className="flex min-h-9 items-center justify-center gap-2 border-b border-(--ui-stroke-tertiary) px-3 text-[0.6875rem] text-(--ui-text-tertiary)">
      <span className="font-medium text-(--ui-text-secondary)">Desktop draft</span>
      <span aria-hidden="true">·</span>
      <span className={cn(!gatewayOpen && 'text-destructive')}>
        {gatewayOpen ? 'Gateway connected' : 'Gateway disconnected'}
      </span>
      <span aria-hidden="true">·</span>
      <span title={modelReadbackError ?? inferenceStatus?.reason ?? undefined}>
        {observedModel ?? (modelReadbackError ? 'Model not observed' : 'Checking model')}
      </span>
      {gatewayOpen && inferenceStatus && !inferenceStatus.ready && (
        <>
          <span aria-hidden="true">·</span>
          <span className="text-destructive" title={inferenceStatus.reason ?? undefined}>
            Inference unavailable
          </span>
        </>
      )}
    </header>
  )
}
