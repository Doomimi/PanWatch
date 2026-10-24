import { useTranslation } from 'react-i18next'
import type { DecisionProvenance } from '@panwatch/api'

const INJECTION_LABELS: Record<string, string> = {
  quote: 'quote',
  capital_flow: 'capital_flow',
  events: 'events',
  financial: 'financial',
  technical: 'technical',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asNumber(value: unknown): number | null {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

/** 决策溯源：回答"这个结论怎么来的"，供复盘时回建信任。 */
export function DecisionProvenancePanel({ provenance }: { provenance?: DecisionProvenance | null }) {
  const { t } = useTranslation('bizUi')
  const tr = (key: string, options?: Record<string, unknown>) =>
    (t as unknown as (key: string, options?: Record<string, unknown>) => string)(`decisionProvenance.${key}`, options)

  if (!provenance || typeof provenance !== 'object') return null
  const model = asRecord(provenance.model_config)
  const injection = asRecord(provenance.data_injection)
  const run = asRecord(provenance.run)
  const ratingSource = provenance.rating_source ? String(provenance.rating_source) : ''
  const confidenceSource = provenance.confidence_source ? String(provenance.confidence_source) : ''
  const confidence = asNumber(provenance.confidence)
  const bars = asNumber(injection.kline_bars)
  const range = Array.isArray(injection.kline_range) ? (injection.kline_range as unknown[]).map(v => String(v)) : []
  const analysts = Array.isArray(model.selected_analysts) ? (model.selected_analysts as unknown[]).map(v => String(v)) : []

  return (
    <section aria-label={tr('title')} className="rounded-xl border border-border/50 bg-muted/20 p-3 text-[12px]">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="font-medium">{tr('title')}</h4>
        <span className="text-[11px] text-muted-foreground">{tr('subtitle')}</span>
      </div>

      <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
        {ratingSource && <div className="flex items-baseline gap-2">
          <dt className="shrink-0 text-muted-foreground">{tr('rating')}</dt>
          <dd className="font-mono text-[11px] [overflow-wrap:anywhere]">{tr(`sources.${ratingSource}`)}</dd>
        </div>}
        {confidenceSource && <div className="flex items-baseline gap-2">
          <dt className="shrink-0 text-muted-foreground">{tr('confidence')}</dt>
          <dd className="font-mono text-[11px] [overflow-wrap:anywhere]">
            {tr(`confidenceSources.${confidenceSource}`)}
            {confidence != null && <span className="text-muted-foreground"> ({confidence.toFixed(2)})</span>}
          </dd>
        </div>}
        {provenance.review_required && <div className="flex items-baseline gap-2">
          <dt className="shrink-0 text-muted-foreground">{tr('reviewRequired')}</dt>
          <dd className="text-[11px] font-medium text-amber-600 dark:text-amber-400">⚠️ {tr('sources.unresolved')}</dd>
        </div>}
      </dl>

      {(model.deep_think_llm || model.quick_think_llm || analysts.length > 0) && (
        <div className="mt-3 border-t border-border/40 pt-2">
          <h5 className="text-[11px] font-medium text-muted-foreground">{tr('model')}</h5>
          <dl className="mt-1 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
            {!!model.deep_think_llm && <div className="flex items-baseline gap-2">
              <dt className="shrink-0 text-muted-foreground">{tr('deepModel')}</dt>
              <dd className="font-mono text-[11px] [overflow-wrap:anywhere]">{String(model.deep_think_llm)}</dd>
            </div>}
            {!!model.quick_think_llm && <div className="flex items-baseline gap-2">
              <dt className="shrink-0 text-muted-foreground">{tr('quickModel')}</dt>
              <dd className="font-mono text-[11px] [overflow-wrap:anywhere]">{String(model.quick_think_llm)}</dd>
            </div>}
            {analysts.length > 0 && <div className="flex items-baseline gap-2">
              <dt className="shrink-0 text-muted-foreground">{tr('analysts')}</dt>
              <dd className="font-mono text-[11px] [overflow-wrap:anywhere]">{analysts.join(', ')}</dd>
            </div>}
            {model.max_debate_rounds != null && <div className="flex items-baseline gap-2">
              <dt className="shrink-0 text-muted-foreground">{tr('debateRounds')}</dt>
              <dd className="font-mono text-[11px]">{String(model.max_debate_rounds)}</dd>
            </div>}
          </dl>
        </div>
      )}

      {(bars != null || Object.keys(injection).length > 0) && (
        <div className="mt-3 border-t border-border/40 pt-2">
          <h5 className="text-[11px] font-medium text-muted-foreground">{tr('injection')}</h5>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-[11px]">
            {bars != null && <span>{tr('klineBars', { count: bars })}</span>}
            {range.length === 2 && <span className="text-muted-foreground">{tr('klineRange', { start: range[0], end: range[1] })}</span>}
            {Object.entries(injection)
              .filter(([key]) => key !== 'kline_bars' && key !== 'kline_range')
              .map(([key, value]) => (
                <span key={key} className={value ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground line-through'}>
                  {tr(`fields.${INJECTION_LABELS[key] || key}`)}
                  {typeof value === 'number' && value > 0 && <span className="text-muted-foreground"> ({value})</span>}
                </span>
              ))}
          </div>
        </div>
      )}

      {(run.timeout_minutes != null || run.llm_max_retries != null) && (
        <div className="mt-3 border-t border-border/40 pt-2">
          <h5 className="text-[11px] font-medium text-muted-foreground">{tr('run')}</h5>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-[11px] text-muted-foreground">
            {run.timeout_minutes != null && <span>{tr('timeout', { value: String(run.timeout_minutes) })}</span>}
            {run.llm_max_retries != null && <span>{tr('retries', { value: String(run.llm_max_retries) })}</span>}
          </div>
        </div>
      )}
    </section>
  )
}
