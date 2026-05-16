import { useEffect, useState } from 'react'
import {
  ArrowRight,
  Database,
  ListFilter,
  Medal,
  Route,
  Sparkles,
  Target,
} from 'lucide-react'

import { apiGet } from './api/client'
import {
  fallbackDashboard,
  type AnalyticsDashboard,
  type EntryRow,
  type ForayRow,
  type PlayerLeader,
} from './data/dashboard'

type ApiState = 'loading' | 'live' | 'snapshot' | 'fallback'
type RouteName = 'home' | 'models' | 'model' | 'scouting' | 'about' | 'honesty'

type AppRoute = {
  name: RouteName
  modelNumber?: number
}

type ModelStory = {
  number: number
  slug: string
  title: string
  shortTitle: string
  question: string
  finding: string
  whyItMatters: string
  graphic: 'forays' | 'clearance' | 'entries' | 'faceoffs' | 'forwards' | 'defense' | 'discipline' | 'centers' | 'blocks'
  caveat: string
  summary: string
}

const modelStories: ModelStory[] = [
  {
    number: 2,
    slug: 'pk-foray-risk-reward',
    title: 'PK Offensive-Zone Foray Risk-Reward',
    shortTitle: 'OZ Forays',
    question: 'When a penalty kill gets up ice, does the reward survive the counterattack risk?',
    finding: 'Short-handed offensive-zone forays were positive in the short window, with small measured immediate counterattack risk.',
    whyItMatters: 'This reframes PK offense as a possession decision instead of a vague aggression label.',
    graphic: 'forays',
    caveat: 'The model does not know how many skaters committed up ice because tracking and shift data are not present.',
    summary: 'The result is not "attack more." It is "PK offense has measurable short-window value, but we still need tracking data before judging commitment."',
  },
  {
    number: 3,
    slug: 'intentional-clearance-faceoff',
    title: 'Intentional Clearance For OZ Faceoff',
    shortTitle: 'OZ Whistles',
    question: 'Is forcing a whistle in the offensive zone actually a safe reset while short-handed?',
    finding: 'Inferred out-of-play/OZ-faceoff situations were negative on average compared with keeping play alive.',
    whyItMatters: 'It challenges the instinct that any whistle away from your net is automatically good.',
    graphic: 'clearance',
    caveat: 'Intentionality is inferred from event context. The play-by-play feed does not explicitly tag intent.',
    summary: 'Treat the whistle as a trade: less chaos now, but a faceoff you still have to survive.',
  },
  {
    number: 4,
    slug: 'entry-defense-outcomes',
    title: 'PK Entry Defense Outcomes',
    shortTitle: 'Entry Defense',
    question: 'What happens after controlled entries and dump-ins against the penalty kill?',
    finding: 'Dump-in entries were more dangerous than controlled entries in the latest run.',
    whyItMatters: 'The result turns entry defense into an outcome question instead of a formation guess.',
    graphic: 'entries',
    caveat: 'This is not a forecheck-structure detector. It cannot identify wedge, diamond, or pressure shape.',
    summary: 'This page compares what happened after entry types, not what the PK formation looked like.',
  },
  {
    number: 5,
    slug: 'pk-faceoff-play-selection',
    title: 'PK Defensive-Zone Faceoff Value',
    shortTitle: 'DZ Faceoffs',
    question: 'How much does a defensive-zone PK faceoff win change the next twenty seconds?',
    finding: 'PK faceoff wins cut immediate xGA by roughly 0.027 compared with matched losses.',
    whyItMatters: 'This is one of the cleanest tactical signals in the project.',
    graphic: 'faceoffs',
    caveat: 'The treatment is faceoff win versus loss, not a full randomized causal experiment.',
    summary: 'A DZ faceoff win changes the next shift immediately: fewer shots, less xGA, less survival mode.',
  },
  {
    number: 6,
    slug: 'forward-defensive-events',
    title: 'PK Forward Defensive Event Profile',
    shortTitle: 'Forward Events',
    question: 'Which forwards show up in positive tagged defensive events on the penalty kill?',
    finding: 'The leaders combine takeaways, blocks, and hits with low giveaway/penalty rates.',
    whyItMatters: 'It gives scouts a supported event-participant view without pretending to know every shift.',
    graphic: 'forwards',
    caveat: 'These are tagged events only. This is not true on-ice shot suppression.',
    summary: 'Use this for event style: who gets tagged on takeaways, blocks, hits, penalties, and giveaways.',
  },
  {
    number: 7,
    slug: 'defenseman-disruption',
    title: 'PK Defenseman Disruption Events',
    shortTitle: 'D Disruption',
    question: 'Which defensemen are directly tagged on disruption events while short-handed?',
    finding: 'Top profiles are heavily driven by blocked shots, takeaways, and hits with low negative-event rates.',
    whyItMatters: 'It separates repeat event involvement from unsupported gap-control claims.',
    graphic: 'defense',
    caveat: 'Gap control requires player positioning. This model only sees direct event participation.',
    summary: 'Use this as a disruption ledger, not as a full defensive grade.',
  },
  {
    number: 8,
    slug: 'forward-discipline-blocks',
    title: 'PK Forward Discipline And Blocks',
    shortTitle: 'Forward Blocks',
    question: 'Which forwards bring shot-blocking value without giving it back in penalties and giveaways?',
    finding: 'The model separates block-heavy profiles from low-risk, takeaway-heavy profiles.',
    whyItMatters: 'It makes forward PK contributions easier to scout by role.',
    graphic: 'discipline',
    caveat: 'No per-60 or all-shift claims are made because time-on-ice is unavailable.',
    summary: 'This separates block-first forwards from low-risk, takeaway-heavy penalty killers.',
  },
  {
    number: 9,
    slug: 'center-faceoff-value',
    title: 'PK Center Faceoff Value',
    shortTitle: 'Center Value',
    question: 'Which center seasons created the most PK value through faceoffs?',
    finding: 'Center faceoff value is one of the strongest player-level views because faceoff participants are explicit.',
    whyItMatters: 'This is the cleanest player model in the suite.',
    graphic: 'centers',
    caveat: 'Faceoff participants are inferred from tagged event players and may include non-center support in edge cases.',
    summary: 'This is the player model I trust most because faceoff participants are directly observable.',
  },
  {
    number: 10,
    slug: 'defense-shot-blocks',
    title: 'PK Defenseman Shot Blocks',
    shortTitle: 'Shot Blocks',
    question: 'Which defensemen are tagged on the most valuable blocked shots?',
    finding: 'The leaders block high-danger attempts from close ranges, but this is still a block profile.',
    whyItMatters: 'It gives a concrete shot-blocking lens without overstating net-front coverage.',
    graphic: 'blocks',
    caveat: 'Net-front prevention needs shift data and player positioning. Blocks are not the whole defensive picture.',
    summary: 'This rewards valuable blocked attempts without pretending blocks equal coverage.',
  },
]

const modelOne = {
  number: 1,
  title: 'Blue-Line And Entry Attempts',
  shortTitle: 'Entry Attempts',
  question: 'How often do power plays get across the line cleanly against the PK?',
  finding: 'Model 1 is part of the earlier analytics layer and should become the bridge between ingestion quality and the model-story site.',
  caveat: 'This page is staged until Model 1 is normalized into the same API payload as Models 2-10.',
}

const navItems = [
  ['Home', '#/'],
  ['Models', '#/models'],
  ['Scouting', '#/scouting'],
  ['About', '#/about'],
  ['Data Honesty', '#/data-honesty'],
] as const

const numberFormatter = new Intl.NumberFormat('en-US')

function currentRoute(): AppRoute {
  const hash = window.location.hash.replace(/^#\/?/, '')
  if (!hash) return { name: 'home' }
  if (hash === 'models') return { name: 'models' }
  if (hash === 'scouting') return { name: 'scouting' }
  if (hash === 'about') return { name: 'about' }
  if (hash === 'data-honesty') return { name: 'honesty' }

  const modelMatch = hash.match(/^models\/(\d+)/)
  if (modelMatch) return { name: 'model', modelNumber: Number(modelMatch[1]) }

  return { name: 'home' }
}

function useHashRoute() {
  const [route, setRoute] = useState<AppRoute>(() => currentRoute())

  useEffect(() => {
    const onHashChange = () => {
      setRoute(currentRoute())
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return route
}

function formatRate(value?: number) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'n/a'
}

function formatXg(value?: number) {
  return typeof value === 'number' ? value.toFixed(3) : 'n/a'
}

function modelHref(modelNumber: number) {
  return `#/models/${modelNumber}`
}

function storyForModel(modelNumber?: number) {
  if (modelNumber === 1) return null
  return modelStories.find((story) => story.number === modelNumber) ?? modelStories[0]
}

function playerSample(player: PlayerLeader) {
  return player.defensive_events ?? player.tagged_events ?? player.faceoffs ?? player.blocked_shots ?? 0
}

function playerMetric(player: PlayerLeader) {
  return (
    player.positive_event_rate ??
    player.disruption_rate ??
    player.faceoff_value_added ??
    player.high_danger_block_rate ??
    0
  )
}

function playerMetricLabel(player: PlayerLeader) {
  if (player.faceoff_value_added !== undefined) return formatXg(player.faceoff_value_added)
  return formatRate(playerMetric(player))
}

function slugLabel(value: string) {
  return value.replaceAll('_', ' ').toLowerCase()
}

function App() {
  const route = useHashRoute()
  const [dashboard, setDashboard] = useState<AnalyticsDashboard>(fallbackDashboard)
  const [apiState, setApiState] = useState<ApiState>('loading')
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    apiGet<AnalyticsDashboard>('/analytics/dashboard', { signal: controller.signal })
      .then((data) => {
        setDashboard(data)
        setApiState('live')
        setApiError(null)
      })
      .catch(async (error: unknown) => {
        if (controller.signal.aborted) return
        try {
          const snapshot = await fetch(`${import.meta.env.BASE_URL}data/dashboard.json`, {
            headers: { Accept: 'application/json' },
            signal: controller.signal,
          })
          if (!snapshot.ok) {
            throw new Error(`Snapshot request failed: ${snapshot.status} ${snapshot.statusText}`)
          }
          setDashboard(await snapshot.json() as AnalyticsDashboard)
          setApiState('snapshot')
          setApiError(null)
        } catch (snapshotError: unknown) {
          if (controller.signal.aborted) return
          setDashboard(fallbackDashboard)
          setApiState('fallback')
          setApiError(snapshotError instanceof Error ? snapshotError.message : error instanceof Error ? error.message : 'Unable to load analytics data')
        }
      })

    return () => controller.abort()
  }, [])

  return (
    <div className="site-shell">
      <SiteHeader apiState={apiState} route={route} />
      <main>
        {route.name === 'home' && <HomePage dashboard={dashboard} apiState={apiState} apiError={apiError} />}
        {route.name === 'models' && <ModelsPage dashboard={dashboard} apiState={apiState} />}
        {route.name === 'model' && <ModelPage dashboard={dashboard} modelNumber={route.modelNumber ?? 2} />}
        {route.name === 'scouting' && <ScoutingPage dashboard={dashboard} />}
        {route.name === 'about' && <AboutPage dashboard={dashboard} />}
        {route.name === 'honesty' && <DataHonestyPage dashboard={dashboard} />}
      </main>
      <SiteFooter />
    </div>
  )
}

function isActiveNav(route: AppRoute, href: string) {
  if (href === '#/') return route.name === 'home'
  if (href === '#/models') return route.name === 'models' || route.name === 'model'
  if (href === '#/scouting') return route.name === 'scouting'
  if (href === '#/about') return route.name === 'about'
  if (href === '#/data-honesty') return route.name === 'honesty'
  return false
}

function SiteHeader({ apiState, route }: { apiState: ApiState; route: AppRoute }) {
  return (
    <header className="site-header">
      <a className="brand-lockup" href="#/" aria-label="NHL PK Analytics home">
        <span className="brand-mark" aria-hidden="true">
          <span>P<span>K</span></span>
        </span>
        <span>NHL PK Analytics</span>
      </a>
      <nav className="site-nav" aria-label="Primary navigation">
        {navItems.map(([label, href]) => (
          <a className={isActiveNav(route, href) ? 'active' : undefined} href={href} key={href}>{label}</a>
        ))}
      </nav>
      <div className={`api-pill api-pill-${apiState}`}>
        {apiState === 'live' ? 'Live models' : apiState === 'snapshot' ? 'Snapshot models' : apiState === 'loading' ? 'Syncing' : 'API offline'}
      </div>
    </header>
  )
}

function HomePage({
  dashboard,
  apiState,
  apiError,
}: {
  dashboard: AnalyticsDashboard
  apiState: ApiState
  apiError: string | null
}) {
  const faceoffMetric = dashboard.metrics.find((metric) => metric.label.includes('Faceoff'))
  const forayMetric = dashboard.metrics.find((metric) => metric.label.includes('Forays'))

  return (
    <>
      <section className="hero-section">
        <div className="hero-copy">
          <h1>Decode the Penalty Kill.</h1>
          <p>
            The plays NHL penalty kills give up, translated into sharp model stories.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="#/models">Explore models <ArrowRight size={18} /></a>
          </div>
          <div className="run-strip">
            <span>{apiState === 'live' ? 'Latest run' : apiState === 'snapshot' ? 'Published snapshot' : 'API offline'}</span>
            <strong>{apiState === 'fallback' ? 'showing sample values until analytics data responds' : dashboard.latestRun.fileName}</strong>
            {apiError && <em>{apiError}</em>}
          </div>
        </div>
        <RinkTraceHero faceoffValue={faceoffMetric?.value ?? '-0.027'} forayCount={forayMetric?.value ?? '1,224'} />
      </section>

      <section className="story-grid">
        {dashboard.takeaways.map((takeaway) => (
          <article className={`story-panel story-${takeaway.tone}`} key={takeaway.title}>
            <div className="story-value">{takeaway.value}</div>
            <h2>{takeaway.title}</h2>
          <p>{takeaway.detail}</p>
          <span>{takeaway.tone === 'good' ? 'Immediate danger drops' : takeaway.tone === 'bad' ? 'Tradeoff, not reset' : 'Outcome comparison'}</span>
        </article>
      ))}
      </section>

      <section className="section-band model-lab-band">
        <div className="model-lab-copy">
          <h2>Start with a hockey question.</h2>
          <p>
            These are the cleanest entry points into the project. Each one opens a model page with the result,
            the supporting rows, and the line where the data stops.
          </p>
          <div className="definition-deck" aria-label="Model terminology">
            <DefinitionTerm
              term="Foray"
              body="A short-handed push into the offensive zone: a controlled carry, dump-in, faceoff sequence, or turnover chance."
            />
            <DefinitionTerm
              term="xG"
              body="Expected goals. A probability-weighted estimate of how dangerous a shot or short window was."
            />
            <DefinitionTerm
              term="Tagged event"
              body="A play-by-play event with a named participant. Useful for scouting, not the same as full on-ice impact."
            />
          </div>
        </div>
        <div className="model-preview-list">
          {modelStories.slice(0, 4).map((story) => (
            <a className="model-preview-row" href={modelHref(story.number)} key={story.number}>
              <span>{String(story.number).padStart(2, '0')}</span>
              <strong>{story.shortTitle}</strong>
              <em>{story.summary}</em>
            </a>
          ))}
        </div>
      </section>
    </>
  )
}

function RinkTraceHero({ faceoffValue, forayCount }: { faceoffValue: string; forayCount: string }) {
  return (
    <div className="rink-hero" aria-label="Animated rink trace model graphic">
      <svg viewBox="0 0 1000 520" role="img">
        <defs>
          <filter id="traceGlow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect className="ice-sheet" x="50" y="70" width="900" height="382" rx="42" />
        <line className="rink-line center" x1="500" y1="70" x2="500" y2="452" />
        <line className="rink-line blue" x1="388" y1="70" x2="388" y2="452" />
        <line className="rink-line blue" x1="612" y1="70" x2="612" y2="452" />
        <line className="rink-line goal" x1="108" y1="88" x2="108" y2="434" />
        <line className="rink-line goal" x1="892" y1="88" x2="892" y2="434" />
        <path className="crease" d="M108 231L108 291C132 291 147 279 147 261C147 243 132 231 108 231Z" />
        <path className="crease right" d="M892 231L892 291C868 291 853 279 853 261C853 243 868 231 892 231Z" />
        <circle className="faceoff-ring center" cx="500" cy="261" r="58" />
        <circle className="faceoff-dot" cx="500" cy="261" r="5" />
        <circle className="faceoff-ring small" cx="248" cy="160" r="38" />
        <circle className="faceoff-ring small" cx="248" cy="362" r="38" />
        <circle className="faceoff-ring small" cx="752" cy="160" r="38" />
        <circle className="faceoff-ring small" cx="752" cy="362" r="38" />
        <path className="trace trace-one" d="M249 362 C318 322 374 297 462 262 C553 225 642 190 752 160" />
        <path className="trace trace-two" d="M752 362 C690 329 635 311 552 295 C452 276 357 222 248 160" />
        <path className="trace trace-three" d="M389 261 C430 214 470 199 510 209 C554 220 580 244 612 261" />
        <path className="trace trace-clear" d="M110 300 C188 306 262 300 332 282 C392 267 445 262 500 261" />
        <circle className="puck puck-one" r="5">
          <animateMotion dur="5.8s" repeatCount="indefinite" path="M249 362 C318 322 374 297 462 262 C553 225 642 190 752 160" />
        </circle>
        <circle className="puck puck-two" r="5">
          <animateMotion dur="7.2s" begin="1.2s" repeatCount="indefinite" path="M752 362 C690 329 635 311 552 295 C452 276 357 222 248 160" />
        </circle>
        <g className="rink-badge">
          <rect x="68" y="24" width="318" height="34" rx="12" />
          <text x="86" y="46">DZ draw win: {faceoffValue} xGA next 20s</text>
        </g>
        <g className="rink-badge right">
          <rect x="606" y="462" width="326" height="34" rx="12" />
          <text x="624" y="484">Short-handed OZ touches: {forayCount}</text>
        </g>
      </svg>
    </div>
  )
}

function DefinitionTerm({ term, body }: { term: string; body: string }) {
  return (
    <article className="definition-term">
      <strong>{term}</strong>
      <p>{body}</p>
    </article>
  )
}

function ModelsPage({ dashboard, apiState }: { dashboard: AnalyticsDashboard; apiState: ApiState }) {
  return (
    <section className="page-section">
      <PageIntro
        title="Models as hockey arguments."
        body="Every page is written around one question, one supported finding, and one boundary. The point is to make the analysis readable before it becomes interactive."
      />
      <div className="model-index">
        <a className="model-index-row muted-row" href={modelHref(1)}>
          <span>01</span>
          <div>
            <h2>{modelOne.title}</h2>
            <p>{modelOne.finding}</p>
          </div>
          <ArrowRight size={20} />
        </a>
        {modelStories.map((story) => (
          <a className="model-index-row" href={modelHref(story.number)} key={story.number}>
            <span>{String(story.number).padStart(2, '0')}</span>
            <div>
              <h2>{story.title}</h2>
              <p>{story.summary}</p>
              <small>{story.question}</small>
            </div>
            <ArrowRight size={20} />
          </a>
        ))}
      </div>
      <ModelRunNote dashboard={dashboard} apiState={apiState} />
    </section>
  )
}

function ModelPage({ dashboard, modelNumber }: { dashboard: AnalyticsDashboard; modelNumber: number }) {
  const story = storyForModel(modelNumber)

  if (modelNumber === 1 || !story) {
    return (
      <section className="page-section">
        <PageIntro title={modelOne.title} body={modelOne.question} />
        <div className="detail-layout">
          <article className="article-copy">
            <h2>What it finds</h2>
            <p>{modelOne.finding}</p>
            <h2>What it needs next</h2>
            <p>{modelOne.caveat}</p>
          </article>
          <ModelCompass />
        </div>
      </section>
    )
  }

  return (
    <section className="page-section">
      <PageIntro title={story.title} body={story.question} />
      <div className="detail-layout">
        <article className="article-copy">
          {story.number === 2 && (
            <div className="definition-callout">
              <strong>Foray</strong>
              <span>A short-handed touch or possession that reaches the offensive zone.</span>
            </div>
          )}
          <h2>In one sentence</h2>
          <p>{story.summary}</p>
          <h2>What it found</h2>
          <p>{story.finding}</p>
          <h2>Why it matters</h2>
          <p>{story.whyItMatters}</p>
          <h2>What it cannot claim</h2>
          <p>{story.caveat}</p>
        </article>
        <div className="graphic-stack">
          <ModelGraphic dashboard={dashboard} story={story} />
          <ModelEvidence dashboard={dashboard} story={story} />
        </div>
      </div>
      <ModelNavigation current={story.number} />
    </section>
  )
}

function ModelGraphic({ dashboard, story }: { dashboard: AnalyticsDashboard; story: ModelStory }) {
  if (story.graphic === 'forays') return <ForayGraphic rows={dashboard.forayRows} />
  if (story.graphic === 'entries') return <EntryGraphic rows={dashboard.entryRows} />
  if (story.graphic === 'faceoffs') return <FaceoffGraphic dashboard={dashboard} />
  if (story.graphic === 'clearance') return <ClearanceGraphic dashboard={dashboard} />
  if (story.graphic === 'forwards') return <LeaderGraphic title="Forward event leaders" players={dashboard.playerLeaders.forwards} />
  if (story.graphic === 'defense') return <LeaderGraphic title="Defenseman disruption leaders" players={dashboard.playerLeaders.defensemen} />
  if (story.graphic === 'discipline') return <LeaderGraphic title="Forward discipline and blocks" players={dashboard.playerLeaders.forwards} />
  if (story.graphic === 'centers') return <LeaderGraphic title="Center faceoff value" players={dashboard.playerLeaders.centers} />
  return <LeaderGraphic title="Defenseman shot blocks" players={dashboard.playerLeaders.shotBlockers} />
}

function ForayGraphic({ rows }: { rows: ForayRow[] }) {
  const max = Math.max(...rows.map((row) => row.net_xg), 0.001)
  return (
    <div className="graphic-panel">
      <h2>Net xG by foray type</h2>
      {rows.map((row) => (
        <div className="bar-row" key={row.foray_type}>
          <span>{slugLabel(row.foray_type)}</span>
          <div><i style={{ width: `${(row.net_xg / max) * 100}%` }} /></div>
          <strong>{formatXg(row.net_xg)}</strong>
        </div>
      ))}
    </div>
  )
}

function EntryGraphic({ rows }: { rows: EntryRow[] }) {
  return (
    <div className="graphic-panel two-column-graphic">
      {rows.map((row) => (
        <div className="entry-card" key={row.entry_type}>
          <span>{row.entry_type.replace('_', ' ')}</span>
          <strong>{formatXg(row.avg_xga_per_entry)}</strong>
          <em>xGA per entry</em>
          <p>{numberFormatter.format(row.n_entries)} entries / {formatRate(row.goal_rate)} goal rate</p>
        </div>
      ))}
    </div>
  )
}

function FaceoffGraphic({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <div className="graphic-panel faceoff-graphic">
      <h2>Next 20 seconds after a DZ faceoff</h2>
      {dashboard.faceoffRows.map((row) => (
        <div className={`faceoff-split ${row.outcome.toLowerCase()}`} key={row.outcome}>
          <span>{row.outcome}</span>
          <strong>{formatXg(row.avg_xga_20)}</strong>
          <em>{formatRate(row.shot_rate_20)} shot rate</em>
        </div>
      ))}
    </div>
  )
}

function ClearanceGraphic({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const ozFaceoff = dashboard.metrics.find((metric) => metric.label.includes('OZ Faceoff'))
  return (
    <div className="graphic-panel clearance-graphic">
      <Target size={34} />
      <h2>OZ whistle expected value</h2>
      <strong>{ozFaceoff?.value ?? '-0.024'}</strong>
      <p>Forcing the offensive-zone faceoff looked worse than keeping play alive in the latest run.</p>
    </div>
  )
}

function LeaderGraphic({ title, players }: { title: string; players: PlayerLeader[] }) {
  return (
    <div className="graphic-panel">
      <h2>{title}</h2>
      <div className="leader-list">
        {players.slice(0, 5).map((player, index) => (
          <div className="leader-row" key={`${player.full_name}-${index}`}>
            <span>{index + 1}</span>
            <div>
              <strong>{player.full_name}</strong>
              <em>{player.position}{player.season ? ` / ${player.season}` : ''}</em>
            </div>
            <b>{playerMetricLabel(player)}</b>
          </div>
        ))}
      </div>
    </div>
  )
}

function ModelEvidence({ dashboard, story }: { dashboard: AnalyticsDashboard; story: ModelStory }) {
  if (story.graphic === 'entries') {
    return (
      <div className="evidence-panel">
        <h2>Second signal</h2>
        {dashboard.entryRows.map((row) => (
          <div className="evidence-row" key={row.entry_type}>
            <span>{row.entry_type.replace('_', ' ')}</span>
            <strong>{formatRate(row.clear_rate)}</strong>
            <em>clear rate after entry</em>
          </div>
        ))}
      </div>
    )
  }

  if (story.graphic === 'faceoffs') {
    return (
      <div className="evidence-panel evidence-split">
        <h2>Shot pressure split</h2>
        {dashboard.faceoffRows.map((row) => (
          <div className="mini-meter" key={row.outcome}>
            <span>{row.outcome}</span>
            <i style={{ width: `${Math.max(row.shot_rate_20 * 100, 4)}%` }} />
            <strong>{formatRate(row.shot_rate_20)}</strong>
          </div>
        ))}
      </div>
    )
  }

  if (story.graphic === 'forays') {
    return (
      <div className="evidence-panel">
        <h2>Risk check</h2>
        {dashboard.forayRows.slice(0, 4).map((row) => (
          <div className="evidence-row" key={row.foray_type}>
            <span>{slugLabel(row.foray_type)}</span>
            <strong>{formatRate(row.counterattack_rate)}</strong>
            <em>counterattack rate</em>
          </div>
        ))}
      </div>
    )
  }

  const players =
    story.graphic === 'centers'
      ? dashboard.playerLeaders.centers
      : story.graphic === 'blocks'
        ? dashboard.playerLeaders.shotBlockers
        : story.graphic === 'defense'
          ? dashboard.playerLeaders.defensemen
          : dashboard.playerLeaders.forwards

  return (
    <div className="evidence-panel">
      <h2>Sample behind the rank</h2>
      {players.slice(0, 4).map((player) => (
        <div className="evidence-row" key={`${story.number}-${player.full_name}-${player.season ?? ''}`}>
          <span>{player.full_name}</span>
          <strong>{numberFormatter.format(playerSample(player))}</strong>
          <em>tagged events</em>
        </div>
      ))}
    </div>
  )
}

function ScoutingPage({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const groups = [
    ['Forward event share', dashboard.playerLeaders.forwards],
    ['Defense disruption share', dashboard.playerLeaders.defensemen],
    ['Center faceoff value', dashboard.playerLeaders.centers],
    ['Shot-block danger share', dashboard.playerLeaders.shotBlockers],
  ] as const

  return (
    <section className="page-section">
      <PageIntro
        title="Player event profiles."
        body="These lists rank what happened when a player was directly tagged on a PK event. The percentages are shares of tagged events, not player ratings."
      />
      <div className="scouting-grid">
        {groups.map(([label, players]) => (
          <article className="scouting-panel" key={label}>
            <h2>{label}</h2>
            {players.slice(0, 5).map((player) => (
              <div className="leader-row" key={`${label}-${player.full_name}-${player.season ?? ''}`}>
                <div>
                  <strong>{player.full_name}</strong>
                  <em>{playerMetricDescription(player)} / {numberFormatter.format(playerSample(player))} tagged events</em>
                </div>
                <b>{playerMetricLabel(player)}</b>
              </div>
            ))}
          </article>
        ))}
      </div>
    </section>
  )
}

function playerMetricDescription(player: PlayerLeader) {
  if (player.faceoff_value_added !== undefined) return 'estimated faceoff value added'
  if (player.high_danger_block_rate !== undefined) return 'high-danger block share'
  if (player.disruption_rate !== undefined) return 'disruption-event share'
  return 'positive tagged-event share'
}

function AboutPage({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const modelCount = dashboard.modelCards.length || modelStories.length
  const playerRows = dashboard.metrics.find((metric) => metric.label.includes('Player Scouting'))?.value ?? '1,479'

  return (
    <section className="page-section about-page">
      <PageIntro
        title="Built from the play-by-play up."
        body="This project is a full stack hockey analytics system: ingest NHL game data, model penalty-kill events, serve the latest run through an API, and turn the results into readable model pages."
      />
      <div className="about-grid">
        <article className="about-feature">
          <span>01</span>
          <h2>Data collection</h2>
          <p>
            The ingestion layer pulls NHL play-by-play into Postgres, keeps event participants attached to each
            row, and preserves the timing needed for short-window penalty-kill questions.
          </p>
        </article>
        <article className="about-feature">
          <span>02</span>
          <h2>Model layer</h2>
          <p>
            The Python models convert raw events into faceoff windows, entry outcomes, clearance tradeoffs,
            short-handed forays, and tagged player-event profiles.
          </p>
        </article>
        <article className="about-feature">
          <span>03</span>
          <h2>API and frontend</h2>
          <p>
            The ASP.NET API reads the latest analytics JSON and exposes a frontend-ready contract, so the site can
            show real model output instead of hardcoded dashboard numbers.
          </p>
        </article>
      </div>
      <div className="about-proof-strip">
        <div>
          <strong>{modelCount}</strong>
          <span>model outputs surfaced</span>
        </div>
        <div>
          <strong>{playerRows}</strong>
          <span>player scouting rows exported</span>
        </div>
        <div>
          <strong>{dashboard.latestRun.fileName}</strong>
          <span>latest analytics payload</span>
        </div>
      </div>
    </section>
  )
}

function DataHonestyPage({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <section className="page-section honesty-page">
      <PageIntro
        title="The project is strongest when it says no."
        body="The current database can support possession outcomes, faceoff windows, entries, clears, and tagged event profiles. It cannot support tracking-style positioning claims yet."
      />
      <div className="honesty-columns">
        <article>
          <Database size={28} />
          <h2>Supported now</h2>
          <ul>
            <li>Possession-level PK outcomes</li>
            <li>Entry type outcomes</li>
            <li>xG windows after faceoffs and clears</li>
            <li>Tagged player-event scouting</li>
          </ul>
        </article>
        <article>
          <ListFilter size={28} />
          <h2>Not supported yet</h2>
          <ul>
            {dashboard.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
            <li>Forecheck count, gap control, or net-front coverage without tracking data.</li>
          </ul>
        </article>
      </div>
    </section>
  )
}

function PageIntro({ title, body }: { title: string; body: string }) {
  return (
    <div className="page-intro">
      <h1>{title}</h1>
      <p>{body}</p>
    </div>
  )
}

function ModelRunNote({ dashboard, apiState }: { dashboard: AnalyticsDashboard; apiState: ApiState }) {
  return (
    <div className="run-note">
      <Sparkles size={18} />
      <span>{apiState === 'live' ? 'Live model payload:' : apiState === 'snapshot' ? 'Published model snapshot:' : 'API offline:'}</span>
      <strong>{apiState === 'fallback' ? 'sample values are visible until analytics data responds' : dashboard.latestRun.fileName}</strong>
    </div>
  )
}

function ModelCompass() {
  return (
    <div className="graphic-panel model-compass">
      <Route size={40} />
      <h2>Bring Model 1 into the same contract</h2>
      <p>Once Model 1 exports a shared JSON shape, this page can use the same graphic and explanation framework.</p>
    </div>
  )
}

function ModelNavigation({ current }: { current: number }) {
  const previous = current > 2 ? current - 1 : 10
  const next = current < 10 ? current + 1 : 2

  return (
    <div className="model-nav">
      <a href={modelHref(previous)}>Previous model</a>
      <a href="#/models">All models</a>
      <a href={modelHref(next)}>Next model</a>
    </div>
  )
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>NHL PK Analytics</span>
      <span>Model stories over dashboard noise.</span>
      <span><Medal size={16} /> Built from live analytics output</span>
    </footer>
  )
}

export default App
