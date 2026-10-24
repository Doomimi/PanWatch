import i18n from '@/i18n'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { DecisionProvenancePanel } from '@panwatch/biz-ui/components/decision-provenance'
import type { DecisionProvenance } from '@panwatch/api'

beforeEach(async () => { await i18n.changeLanguage('zh-CN') })

describe('decision provenance panel', () => {
  it('explains where the rating and confidence came from', () => {
    render(<DecisionProvenancePanel provenance={{
      rating_source: 'state.final_rating',
      confidence: 8,
      confidence_source: 'pm_text',
      review_required: false,
    }} />)
    expect(screen.getByText('决策溯源')).toBeTruthy()
    expect(screen.getByText('上游状态 final_rating')).toBeTruthy()
    expect(screen.getByText('PM 正文显式数字')).toBeTruthy()
    expect(screen.getByText('(8.00)')).toBeTruthy()
  })

  it('warns when a report needs manual review instead of pretending it is a hold', () => {
    render(<DecisionProvenancePanel provenance={{ rating_source: 'unresolved', review_required: true }} />)
    expect(screen.getByText('无法解析（需复核）')).toBeTruthy()
    expect(screen.getByText('需人工复核')).toBeTruthy()
  })

  it('renders model configuration without leaking credentials', () => {
    render(<DecisionProvenancePanel provenance={{
      model_config: { deep_think_llm: 'deepseek-chat', quick_think_llm: 'qwen-turbo', selected_analysts: ['market', 'news'], max_debate_rounds: 1 },
      data_injection: { kline_bars: 750, kline_range: ['2023-07-26', '2025-07-01'], quote: true, financial: true, technical: false },
      run: { timeout_minutes: 10, llm_max_retries: 2 },
    }} />)
    expect(screen.getByText('deepseek-chat')).toBeTruthy()
    expect(screen.getByText('qwen-turbo')).toBeTruthy()
    expect(screen.getByText('market, news')).toBeTruthy()
    expect(screen.getByText('K线 750 根')).toBeTruthy()
    expect(screen.getByText('范围 2023-07-26 → 2025-07-01')).toBeTruthy()
    expect(screen.getByText('超时 10 分钟')).toBeTruthy()
    expect(screen.getByText('重试 2 次')).toBeTruthy()
  })

  it('renders nothing when provenance is absent or not an object', () => {
    const { container } = render(<DecisionProvenancePanel provenance={undefined} />)
    expect(container.firstChild).toBeNull()
  })
})
