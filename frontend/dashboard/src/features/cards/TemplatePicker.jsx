// TemplatePicker — first step of the new-card flow. Shows the eight wallet-pass
// templates (rendered live from the shared library's registry) and lets the
// merchant pick a starting design before filling in their own data.
//
// Backend reality: only the loyalty template maps to a publishable card today
// (the /cards API is STAMP/POINTS only). The other seven render as previews and
// are clearly marked "coming soon" so nothing dead-ends at save time.
import { useTranslation } from 'react-i18next'
import Button from '../../components/Button'
import { TEMPLATES } from '../../wallet-pass'
import { PUBLISHABLE } from './templateSeeds'

export default function TemplatePicker({ onChoose, onSkip }) {
  const { t } = useTranslation()
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head text-2xl font-bold text-tx">{t('templatePicker.title')}</h1>
          <p className="mt-1 text-sm text-tx-3">{t('templatePicker.subtitle')}</p>
        </div>
        <Button variant="ghost" onClick={onSkip}>
          {t('templatePicker.skip')}
        </Button>
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-6">
        {TEMPLATES.map(({ id, name, component: Pass, theme, sample }) => {
          const publishable = PUBLISHABLE.has(id)
          const choose = publishable ? () => onChoose(id) : undefined
          return (
            <div key={id} className="flex flex-col items-center gap-3">
              <div className={`w-full max-w-[240px] ${publishable ? '' : 'opacity-70'}`}>
                <Pass {...sample} theme={theme} interactive={publishable} onClick={choose} />
              </div>
              <div className="flex w-full max-w-[240px] flex-col items-center gap-1">
                <span className="text-sm font-semibold text-tx-2">
                  {t(`templatePicker.names.${id}`, name)}
                </span>
                {publishable ? (
                  <Button size="sm" className="w-full" onClick={choose}>
                    {t('templatePicker.use')}
                  </Button>
                ) : (
                  <>
                    <Button size="sm" variant="ghost" disabled className="w-full">
                      {t('templatePicker.comingSoon')}
                    </Button>
                    <span className="text-center text-[11px] text-tx-3">
                      {t('templatePicker.previewOnly')}
                    </span>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
