// RewardStampRow — the loyalty stamp strip. Renders `target` chips (supports
// 3 / 5 / 8 / 10 / 12) and fills the first `progress` of them. The final chip is
// the reward: it shows a gift/star icon and lights up once the card is complete
// (progress ≥ target), matching "★★★★○ → highlighted reward" from the brief.
//
// Chip states: empty (faded outline) · filled (solid accent) · reward (final,
// dashed until earned) · completed (reward lit + soft glow). Newly-filled chips
// animate in when `animate` is set.
import { Star, Gift } from 'lucide-react'

const CHIP = { 3: 34, 5: 30, 8: 26, 10: 22, 12: 20 }

function chipSize(target) {
  const keys = Object.keys(CHIP).map(Number)
  const nearest = keys.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a))
  return CHIP[nearest]
}

export default function RewardStampRow({
  progress = 0,
  target = 5,
  icon: Icon = Star,
  rewardIcon: RewardIcon = Gift,
  theme,
  animate = true,
}) {
  if (!target || target < 1) return null
  const total = Math.max(1, Math.min(target, 12))
  const filledCount = Math.max(0, Math.min(progress, total))
  const complete = filledCount >= total
  const size = chipSize(total)
  const iconPx = Math.round(size * 0.52)

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {Array.from({ length: total }).map((_, i) => {
        const isReward = i === total - 1
        const filled = i < filledCount
        const rewardLit = isReward && complete
        const on = filled || rewardLit
        const Glyph = isReward ? RewardIcon : Icon

        const style = { width: size, height: size }
        if (on) {
          style.background = theme?.accent
          style.color = theme?.accentFg
          if (rewardLit) style['--pass-reward-glow'] = 'rgba(255,255,255,0.55)'
        } else {
          style.border = `1.5px ${isReward ? 'dashed' : 'solid'} ${theme?.hairline}`
          style.color = theme?.sub
        }

        const anim = animate && filled ? 'pass-stamp-anim' : ''
        const glow = rewardLit ? 'pass-reward-glow' : ''
        return (
          <span
            key={i}
            style={{ ...style, animationDelay: anim ? `${i * 60}ms` : undefined }}
            className={`flex items-center justify-center rounded-full ${anim} ${glow}`}
          >
            <Glyph size={iconPx} strokeWidth={2.4} fill={on ? 'currentColor' : 'none'} />
          </span>
        )
      })}
    </div>
  )
}
