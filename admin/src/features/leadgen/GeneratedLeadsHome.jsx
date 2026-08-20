import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import LeadsPanel from './LeadsPanel'

// Every generated lead, across every search. The job page answers "how did that
// search go"; this answers "who should I call", which is a different question
// and deserves its own screen rather than a filter on the first one.
export default function GeneratedLeadsHome() {
  return (
    <div className="space-y-5">
      <Link
        to="/leadgen"
        className="inline-flex items-center gap-1.5 text-sm text-tx-2 hover:text-tx"
      >
        <ArrowLeft size={14} /> Searches
      </Link>
      <header>
        <h1 className="text-xl font-semibold text-tx">Generated leads</h1>
        <p className="mt-1 text-sm text-tx-2">
          Everything discovered so far, best fit first. Duplicates and merged branches are
          hidden.
        </p>
      </header>
      <LeadsPanel />
    </div>
  )
}
