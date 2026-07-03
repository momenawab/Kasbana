// Last-resort fallback for the top-level Sentry ErrorBoundary (Phase 3): shown
// when a render/route error escapes the app (Sentry has already captured it).
// Kept dependency-free and bilingual — i18n itself may be what failed — with a
// reload as the only recovery.
export default function AppCrash() {
  return (
    <div
      role="alert"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        padding: '2rem',
        textAlign: 'center',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <h1 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
        Something went wrong · حدث خطأ ما
      </h1>
      <p style={{ color: '#6b7280' }}>Please reload the page. · يُرجى إعادة تحميل الصفحة.</p>
      <button
        onClick={() => window.location.reload()}
        style={{
          padding: '0.5rem 1rem',
          borderRadius: '0.5rem',
          border: 'none',
          background: '#111827',
          color: '#fff',
          cursor: 'pointer',
        }}
      >
        Reload · إعادة التحميل
      </button>
    </div>
  )
}
