import { nextPriorityOrder } from '../utils/documentTiming'
import type { PriorityOrder } from '../utils/documentTiming'

export function StateSortHeader({ order, onChange }: { order: PriorityOrder; onChange: (order: PriorityOrder) => void }) {
  const symbol = order === 'normal' ? '↕' : order === 'high' ? '↑' : '↓'
  const description = order === 'normal' ? 'orden normal' : order === 'high' ? 'mayor prioridad primero' : 'menor prioridad primero'
  return <th scope="col" aria-sort={order === 'normal' ? 'none' : order === 'high' ? 'ascending' : 'descending'}>
    <button className="state-sort-button" type="button" aria-label={`Estado ${symbol}: ${description}`} onClick={() => onChange(nextPriorityOrder(order))}>Estado {symbol}</button>
  </th>
}
