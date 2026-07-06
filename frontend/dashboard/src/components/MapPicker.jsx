// MapPicker — location picker for the Locations modal.
//
// Merchants search their business/address, drop a draggable pin, or use the
// browser's geolocation; the map fills lat/lng so nobody hand-enters
// coordinates. Rough precision is enough for Wallet location relevance.
//
// Powered by MapTiler (vector tiles via MapLibre GL) so we get: a Street⇄
// Satellite toggle, on-the-fly Arabic⇄English label switching, and crisp
// retina rendering. Needs VITE_MAPTILER_KEY (free tier). Geocoding uses the
// same key + language, so Arabic searches return Arabic place names.
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MapPin, Loader2, LocateFixed, Search, Layers, Languages } from 'lucide-react'
import { Map as MtMap, MapStyle, Marker, config } from '@maptiler/sdk'
import '@maptiler/sdk/dist/maptiler-sdk.css'

const KEY = import.meta.env.VITE_MAPTILER_KEY
if (KEY) config.apiKey = KEY

// [lng, lat] — MapLibre uses lng-first. Default view = Cairo.
const DEFAULT_CENTER = [31.2357, 30.0444]
const DEFAULT_ZOOM = 10
const PICKED_ZOOM = 15
const PIN_COLOR = '#C4211C'

const styleFor = (base) => (base === 'satellite' ? MapStyle.HYBRID : MapStyle.STREETS)

export default function MapPicker({ lat, lng, onPick }) {
  const { t, i18n } = useTranslation()
  const mapEl = useRef(null)
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const onPickRef = useRef(onPick)
  onPickRef.current = onPick

  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [status, setStatus] = useState('') // 'searching' | 'noresults' | 'geoerror' | ''
  const [locating, setLocating] = useState(false)
  const [base, setBase] = useState('streets') // 'streets' | 'satellite'
  const [lang, setLang] = useState(i18n.language === 'en' ? 'en' : 'ar')

  const hasCoords = lat !== '' && lat != null && lng !== '' && lng != null

  // Create/move the draggable pin and report new coordinates upward.
  function placePin(la, ln, recenter = true) {
    const map = mapRef.current
    if (!map) return
    if (markerRef.current) {
      markerRef.current.setLngLat([ln, la])
    } else {
      const marker = new Marker({ color: PIN_COLOR, draggable: true })
        .setLngLat([ln, la])
        .addTo(map)
      marker.on('dragend', () => {
        const p = marker.getLngLat()
        onPickRef.current?.({ lat: round(p.lat), lng: round(p.lng) })
      })
      markerRef.current = marker
    }
    if (recenter) map.flyTo({ center: [ln, la], zoom: Math.max(map.getZoom(), PICKED_ZOOM) })
  }

  // Init the map once.
  useEffect(() => {
    if (!KEY) return // no key → render the fallback notice instead
    const center = hasCoords ? [Number(lng), Number(lat)] : DEFAULT_CENTER
    const map = new MtMap({
      container: mapEl.current,
      style: styleFor('streets'),
      center,
      zoom: hasCoords ? PICKED_ZOOM : DEFAULT_ZOOM,
      navigationControl: true,
      geolocateControl: false,
    })
    mapRef.current = map
    map.on('load', () => {
      map.setLanguage(lang)
      map.resize() // modal may have sized the container after creation
      if (hasCoords) placePin(Number(lat), Number(lng), false)
    })
    // Click anywhere to drop / move the pin.
    map.on('click', (e) => {
      placePin(e.lngLat.lat, e.lngLat.lng, false)
      onPickRef.current?.({ lat: round(e.lngLat.lat), lng: round(e.lngLat.lng) })
    })
    return () => {
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
    // Init only — later changes are driven by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Street ⇄ Satellite. Re-apply the label language once the new style loads.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    map.setStyle(styleFor(base))
    map.once('styledata', () => map.setLanguage(lang))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base])

  // Arabic ⇄ English map labels.
  useEffect(() => {
    mapRef.current?.setLanguage(lang)
  }, [lang])

  async function runSearch(e) {
    e?.preventDefault()
    const q = query.trim()
    if (!q || !KEY) return
    setStatus('searching')
    setResults([])
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(
        q,
      )}.json?key=${KEY}&language=${lang}&limit=5`
      const data = await fetch(url).then((r) => r.json())
      const feats = Array.isArray(data?.features) ? data.features : []
      if (feats.length === 0) {
        setStatus('noresults')
        return
      }
      setResults(feats)
      setStatus('')
    } catch {
      setStatus('noresults')
    }
  }

  function chooseResult(f) {
    const [ln, la] = f.center // [lng, lat]
    setResults([])
    setQuery(f.place_name)
    placePin(la, ln, true)
    onPickRef.current?.({ lat: round(la), lng: round(ln), address: f.place_name })
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setStatus('geoerror')
      return
    }
    setLocating(true)
    setStatus('')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { latitude, longitude } = pos.coords
        placePin(latitude, longitude, true)
        onPickRef.current?.({ lat: round(latitude), lng: round(longitude) })
      },
      () => {
        setLocating(false)
        setStatus('geoerror')
      },
      { enableHighAccuracy: false, timeout: 8000 },
    )
  }

  if (!KEY) {
    return (
      <div className="rounded-ctl border border-dashed border-line bg-paper p-4 text-center text-sm text-tx-3">
        {t('locations.mapKeyMissing')}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Search + geolocation */}
      <div className="flex gap-2">
        <form onSubmit={runSearch} className="relative z-[5] flex-1">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('locations.searchPlaceholder')}
            className="w-full rounded-ctl border border-line py-2 pe-9 ps-3 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            aria-label={t('locations.search')}
            className="absolute inset-y-0 end-2 flex items-center text-tx-3 hover:text-primary"
          >
            {status === 'searching' ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Search size={16} />
            )}
          </button>

          {results.length > 0 && (
            <ul className="absolute z-[5] mt-1 max-h-52 w-full overflow-auto rounded-ctl border border-line bg-white shadow-bold">
              {results.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => chooseResult(f)}
                    className="flex w-full items-start gap-2 px-3 py-2 text-start text-sm hover:bg-paper"
                  >
                    <MapPin size={14} className="mt-0.5 shrink-0 text-tx-3" />
                    <span className="line-clamp-2">{f.place_name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>

        <button
          type="button"
          onClick={useMyLocation}
          className="flex items-center gap-1 rounded-ctl border border-line px-3 text-sm text-tx-2 hover:border-primary hover:text-primary"
        >
          {locating ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <LocateFixed size={16} />
          )}
          <span className="hidden sm:inline">{t('locations.useMyLocation')}</span>
        </button>
      </div>

      {status === 'noresults' && <p className="text-xs text-tx-3">{t('locations.noResults')}</p>}
      {status === 'geoerror' && <p className="text-xs text-danger">{t('locations.geoError')}</p>}

      {/* Map + overlaid layer / language toggles */}
      <div className="relative">
        <div ref={mapEl} className="h-56 w-full overflow-hidden rounded-ctl border border-line" />

        <div className="pointer-events-none absolute inset-x-2 top-2 z-[2] flex items-start justify-between">
          <Segmented
            icon={Layers}
            value={base}
            onChange={setBase}
            options={[
              ['streets', t('locations.mapStreet')],
              ['satellite', t('locations.mapSatellite')],
            ]}
          />
          <Segmented
            icon={Languages}
            value={lang}
            onChange={setLang}
            options={[
              ['ar', 'عربي'],
              ['en', 'EN'],
            ]}
          />
        </div>
      </div>

      <p className="text-xs text-tx-3">
        {t('locations.mapHint')}{' '}
        {hasCoords && (
          <span className="font-num text-tx-2">
            {Number(lat).toFixed(4)}, {Number(lng).toFixed(4)}
          </span>
        )}
      </p>
    </div>
  )
}

// Small pill-style segmented toggle overlaid on the map.
function Segmented({ icon: Icon, value, onChange, options }) {
  return (
    <div className="pointer-events-auto flex items-center gap-0.5 rounded-full bg-white/90 p-0.5 shadow-bold backdrop-blur">
      <Icon size={14} className="mx-1 text-tx-3" aria-hidden="true" />
      {options.map(([val, label]) => (
        <button
          key={val}
          type="button"
          onClick={() => onChange(val)}
          className={`rounded-full px-2.5 py-1 text-xs font-semibold transition ${
            value === val ? 'bg-primary text-white' : 'text-tx-2 hover:text-primary'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

// Rough precision is fine for Wallet relevance — 5 decimals ≈ 1 m.
function round(n) {
  return Math.round(n * 1e5) / 1e5
}
