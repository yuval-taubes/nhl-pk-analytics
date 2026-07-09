import { useEffect, useMemo, useState } from 'react'
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
  type AftershockTeam,
  type AttackProfileRow,
  type EntryRow,
  type FatigueRow,
  type ForayRow,
  type GoalieControlRow,
  type MatchupCard,
  type MovementRow,
  type PkTalentRow,
  type PlayerTag,
  type PlayerTagProfile,
  type PlayerSimilarityGroup,
  type PlayerLeader,
  type RushSetRow,
  type TeamShotMapBin,
  type TwoWayLeader,
} from './data/dashboard'

type ApiState = 'loading' | 'live' | 'snapshot' | 'fallback'
const SNAPSHOT_CACHE_KEY = 'moneypuck-v2-20260704-team-shot-map-tool'
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

type V2ModelStory = {
  number: number
  title: string
  question: string
  plainLanguage: string
  signal: string
  caveat: string
}

const v2ModelStories: V2ModelStory[] = [
  {
    number: 1,
    title: 'Pre-shot movement',
    question: 'Did the puck make the goalie or defenders move before the shot?',
    plainLanguage: 'A shot gets harder to stop when the defense has to turn, slide, or recover first.',
    signal: 'Rebounds, east-west passes, north-south downhill attacks, diagonals, and resets.',
    caveat: 'This uses shot and last-event coordinates, not full player tracking.',
  },
  {
    number: 2,
    title: 'After a blocked shot',
    question: 'Did the block end the play, or did the power play get another chance?',
    plainLanguage: 'A block only helps if the short-handed team wins the loose puck after it.',
    signal: 'Danger on the next shot after a blocked attempt.',
    caveat: 'It measures the next recorded shot, not every scramble without a shot.',
  },
  {
    number: 3,
    title: 'Goalie control',
    question: 'Which goalies stop the first shot and calm down the next play?',
    plainLanguage: 'This looks beyond saves: rebounds, freezes, and whether the puck stays dangerous.',
    signal: 'Goals saved, rebounds, freezes, and play continuation after PK shots.',
    caveat: 'Team defense still affects what happens after the save.',
  },
  {
    number: 4,
    title: 'Fatigue curve',
    question: 'Do shots get more dangerous when penalty killers are stuck out there?',
    plainLanguage: 'Tired defenders close lanes slower and lose more second races.',
    signal: 'Average xG by defending skater time-on-ice buckets.',
    caveat: 'It is a timing profile, not proof that one player caused the breakdown.',
  },
  {
    number: 5,
    title: 'Two-way PK skaters',
    question: 'Who helps the PK create pressure without giving it all back?',
    plainLanguage: 'The best PK skaters buy time, create exits, and sometimes create offense.',
    signal: 'On-ice short-handed xG for and xG against per 60.',
    caveat: 'Read these by season; PK roles can change quickly.',
  },
  {
    number: 6,
    title: 'Rush or settled play',
    question: 'Was the chance off a fast attack or an organized power play setup?',
    plainLanguage: 'This separates fast attacks from settled power-play shots.',
    signal: 'MoneyPuck rush flag compared with set offense.',
    caveat: 'The rush sample is small, so treat it as supporting context.',
  },
]

const modelStories: ModelStory[] = [
  {
    number: 2,
    slug: 'pk-foray-risk-reward',
    title: 'PK Offensive-Zone Foray Risk-Reward',
    shortTitle: 'OZ Forays',
    question: 'When a penalty kill gets up ice, does the reward survive the counterattack risk?',
    finding: 'Short-handed offensive-zone forays were positive in the short window, with small measured immediate counterattack risk.',
    whyItMatters: 'This makes short-handed offense a possession choice, not just an aggression label.',
    graphic: 'forays',
    caveat: 'The model does not know how many skaters committed up ice because tracking and shift data are not present.',
    summary: 'Short-handed offense can buy value, but this still cannot tell whether a unit sent too many skaters up ice.',
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
    summary: 'This compares outcomes after entry types. It does not identify the PK formation.',
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
    whyItMatters: 'This is the cleanest player model in the legacy suite.',
    graphic: 'centers',
    caveat: 'Faceoff participants are inferred from tagged event players and may include non-center support in edge cases.',
    summary: 'This is the most trustworthy legacy player view because faceoff participants are directly observable.',
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
  finding: 'Model 1 is part of the earlier analytics layer and tracks how cleanly power plays enter the zone.',
  caveat: 'This page is staged until Model 1 is shaped into the same API format as the other legacy pages.',
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

function formatDecimal(value?: number, digits = 2) {
  return typeof value === 'number' ? value.toFixed(digits) : 'n/a'
}

function formatSignedDecimal(value?: number, digits = 2) {
  if (typeof value !== 'number') return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function formatImpactRange(lower?: number | null, upper?: number | null, digits = 1) {
  if (typeof lower !== 'number' || typeof upper !== 'number') return 'range pending'
  return `${formatSignedDecimal(lower, digits)} to ${formatSignedDecimal(upper, digits)}`
}

function formatPercentPoint(value?: number) {
  return typeof value === 'number' ? `${(value * 100).toFixed(0)}%` : 'n/a'
}

function formatMinutes(value?: number) {
  return typeof value === 'number' ? `${Math.round(value / 60)} min` : 'n/a'
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

    apiGet<AnalyticsDashboard>('/analytics/v2/dashboard', { signal: controller.signal })
      .catch(() => apiGet<AnalyticsDashboard>('/analytics/dashboard', { signal: controller.signal }))
      .then((data) => {
        setDashboard(data)
        setApiState('live')
        setApiError(null)
      })
      .catch(async (error: unknown) => {
        if (controller.signal.aborted) return
        try {
          const snapshotUrl = new URL(`${import.meta.env.BASE_URL}data/dashboard.json`, window.location.href)
          snapshotUrl.searchParams.set('v', SNAPSHOT_CACHE_KEY)
          const snapshot = await fetch(snapshotUrl, {
            cache: 'no-store',
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
        {apiState === 'live' ? 'Live models' : apiState === 'snapshot' ? 'MoneyPuck v2 snapshot' : apiState === 'loading' ? 'Syncing' : 'API offline'}
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
            The plays NHL penalty kills give up, translated into clear hockey answers.
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
          <span>{takeawayFooter(takeaway, dashboard.version)}</span>
        </article>
      ))}
      </section>

      <V2DecisionLab dashboard={dashboard} />

      <section className="section-band model-lab-band">
        <div className="model-lab-copy">
          {dashboard.version === 'moneypuck_v2' && <span className="legacy-kicker">Legacy model archive</span>}
          <h2>Earlier NHL API questions.</h2>
          <p>
            These pages came before the MoneyPuck rebuild. They are still useful background, but they are not
            the main model set anymore.
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

function takeawayFooter(takeaway: { tone: string; title: string }, version?: string) {
  if (version === 'moneypuck_v2') {
    if (takeaway.title.toLowerCase().includes('rebound')) return 'Look for second shots'
    if (takeaway.title.toLowerCase().includes('block')) return 'Look after the block'
    if (takeaway.title.toLowerCase().includes('goalie')) return 'Look beyond saves'
    return 'Read this first'
  }

  return takeaway.tone === 'good' ? 'Immediate danger drops' : takeaway.tone === 'bad' ? 'Tradeoff, not reset' : 'Outcome comparison'
}

function V2DecisionLab({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const movementRows = dashboard.movementRows ?? []
  const aftershockRows = dashboard.aftershockTeams ?? []
  const goalieRows = dashboard.goalieControl ?? []
  const fatigueRows = dashboard.fatigueRows ?? []
  const twoWayRows = dashboard.twoWayLeaders ?? []
  const rushRows = dashboard.rushSetSummary ?? []
  const reboundRow = movementRows.find((row) => row.movement_bucket === 'rebound')
  const northSouthRow = movementRows.find((row) => row.movement_bucket === 'north_south_downhill')
  const diagonalRow = movementRows.find((row) => row.movement_bucket === 'diagonal')
  const lateFatigue = fatigueRows[fatigueRows.length - 1]
  const earlyFatigue = fatigueRows[0]
  const hasV2 = dashboard.version === 'moneypuck_v2'
  if (!hasV2) return null

  return (
    <section className="v2-lab" id="moneypuck-v2">
      <div className="v2-lab-heading">
        <span>MoneyPuck v2</span>
        <h2>What creates PK danger?</h2>
        <p>
          Start with the simple question: what happened before the shot? The MoneyPuck rebuild points to the
          repeat situations that break penalty kills: loose rebounds, failed recoveries after blocks, tired
          defenders, and goalies forced to manage the next play.
        </p>
        {dashboard.source && (
          <a href={dashboard.source.url} target="_blank" rel="noreferrer">{dashboard.source.credit}</a>
        )}
      </div>

      <div className="v2-plain-language" aria-label="Plain language model guide">
        <DefinitionTerm
          term="PK"
          body="Penalty kill. One team has fewer skaters and is trying to survive until the penalty ends."
        />
        <DefinitionTerm
          term="xG"
          body="Expected goals. A 0.100 xG shot goes in about one time out of ten."
        />
        <DefinitionTerm
          term="Slot-line pass"
          body="A pass or rebound across the middle of the ice. It usually forces the goalie to move laterally."
        />
      </div>

      <div className="v2-feature-grid">
        <MovementModelCard rows={movementRows} reboundRow={reboundRow} northSouthRow={northSouthRow} diagonalRow={diagonalRow} />
        <AftershockModelCard rows={aftershockRows} />
        <GoalieControlModelCard rows={goalieRows} />
        <FatigueModelCard rows={fatigueRows} early={earlyFatigue} late={lateFatigue} />
        <TwoWayModelCard rows={twoWayRows} />
        <RushSetModelCard rows={rushRows} />
      </div>
    </section>
  )
}

function MovementModelCard({
  rows,
  reboundRow,
  northSouthRow,
  diagonalRow,
}: {
  rows: MovementRow[]
  reboundRow?: MovementRow
  northSouthRow?: MovementRow
  diagonalRow?: MovementRow
}) {
  const maxXg = Math.max(...rows.map((row) => row.avg_xg), 0.001)
  return (
    <article className="v2-model-card v2-model-card-wide">
      <div className="movement-copy-stack">
        <div className="v2-card-copy">
          <span className="v2-model-number">01</span>
          <h3>Pre-shot movement</h3>
          <p>
            Each tile shows one movement type before the shot. The attacking net is on the right. Use the bars
            to compare which path produced the most danger per shot.
          </p>
        </div>
        <div className="v2-insight-row">
          <strong>{formatXg(reboundRow?.avg_xg)}</strong>
          <span>Rebound shots were the highest-danger group. The first save or block did not finish the play.</span>
        </div>
        <div className="v2-comparison-grid">
          <MiniFact label="North-south downhill" value={formatXg(northSouthRow?.avg_xg)} helper="Downhill movement into the slot" />
          <MiniFact label="Diagonal" value={formatXg(diagonalRow?.avg_xg)} helper="Both lane and depth changed before release" />
          <MiniFact label="Slot-line rebound" value={formatPercentPoint(reboundRow?.royal_road_rate)} helper="Rebounds that crossed the middle" />
        </div>
        <div className="v2-evidence-list">
          {rows.slice(0, 7).map((row) => (
            <div className="v2-meter-row" key={row.movement_bucket}>
              <span>{plainBucketLabel(row.movement_bucket)}</span>
              <i><b style={{ width: `${Math.max((row.avg_xg / maxXg) * 100, 4)}%` }} /></i>
              <strong>{formatXg(row.avg_xg)}</strong>
              <em>{numberFormatter.format(row.shots)} shots</em>
            </div>
          ))}
        </div>
      </div>
      <div className="movement-data-stack">
        <MovementPathLegend />
      </div>
    </article>
  )
}

type MovementPathTileProps = {
  className: string
  label: string
  helper: string
  path: string
  secondaryPath?: string
}

function MovementPathLegend() {
  return (
    <div className="movement-legend" aria-label="Mini rink legend for pre-shot movement paths">
      <MovementPathTile
        className="north"
        label="North-south downhill"
        helper="Downhill toward the slot or crease."
        path="M62 86C105 82 150 81 198 84"
      />
      <MovementPathTile
        className="east"
        label="East-west"
        helper="Across the slot before the shot."
        path="M168 42C150 62 149 110 170 132"
      />
      <MovementPathTile
        className="diagonal"
        label="Diagonal"
        helper="Changes lane and depth."
        path="M62 130C100 108 142 83 196 58"
      />
      <MovementPathTile
        className="rebound"
        label="Rebound"
        helper="First attempt, then loose puck."
        path="M152 86C174 84 191 84 209 85"
        secondaryPath="M210 91C194 108 174 118 151 121"
      />
      <MovementPathTile
        className="backtrack"
        label="Point reset"
        helper="Back away from the net."
        path="M190 62C152 51 103 49 58 60"
      />
    </div>
  )
}

function MovementPathTile({ className, label, helper, path, secondaryPath }: MovementPathTileProps) {
  return (
    <article className={`movement-tile ${className}`}>
      <svg viewBox="0 0 260 170" role="img" aria-label={`${label} movement path`}>
        <defs>
          <marker id={`tileArrow-${className}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0 0L8 4L0 8Z" />
          </marker>
        </defs>
        <rect className="tile-rink" x="14" y="18" width="232" height="126" rx="20" />
        <line className="tile-blue-line" x1="48" y1="24" x2="48" y2="138" />
        <line className="tile-goal-line" x1="218" y1="44" x2="218" y2="120" />
        <path className="tile-crease" d="M218 63L218 101C202 101 191 94 191 82C191 70 202 63 218 63Z" />
        <rect className="tile-slot" x="154" y="48" width="48" height="68" rx="12" />
        <rect className="tile-net" x="224" y="70" width="15" height="26" rx="4" />
        <path className="tile-path" d={path} />
        {secondaryPath && <path className="tile-path secondary" d={secondaryPath} />}
      </svg>
      <div>
        <strong>{label}</strong>
        <span>{helper}</span>
      </div>
    </article>
  )
}

function AftershockModelCard({ rows }: { rows: AftershockTeam[] }) {
  const top = rows[0]
  return (
    <article className="v2-model-card">
      <div className="v2-card-copy">
        <span className="v2-model-number">02</span>
        <h3>After a blocked shot</h3>
        <p>
          The important part is not the block. It is the next race. This ranks teams by the danger they allowed
          on the next shot after a blocked attempt.
        </p>
      </div>
      <div className="v2-insight-row warning">
        <strong>{top ? formatXg(top.avg_xg_after_block) : 'n/a'}</strong>
        <span>{top ? `${top.team} allowed the most dangerous follow-up shots after blocks.` : 'Refresh MoneyPuck v2 to show team after-block leaders.'}</span>
      </div>
      <div className="v2-evidence-list">
        {rows.slice(0, 5).map((row) => (
          <div className="v2-row" key={row.team}>
            <span>{row.team}</span>
            <strong>{formatXg(row.avg_xg_after_block)}</strong>
            <em>{numberFormatter.format(row.after_block_shots)} follow-up shots / {formatRate(row.high_danger_after_block_rate)} high danger</em>
          </div>
        ))}
      </div>
    </article>
  )
}

function GoalieControlModelCard({ rows }: { rows: GoalieControlRow[] }) {
  const top = rows[0]
  return (
    <article className="v2-model-card">
      <div className="v2-card-copy">
        <span className="v2-model-number">03</span>
        <h3>Goalie control</h3>
        <p>
          Saves are only the first part. This checks whether the goalie also settles the play: fewer dangerous
          rebounds, more freezes, and fewer second chances.
        </p>
      </div>
      <div className="v2-insight-row good">
        <strong>{top ? formatDecimal(top.control_score, 1) : 'n/a'}</strong>
        <span>{top ? `${top.goalie} led the control score. Higher means stronger saves plus cleaner next plays.` : 'Refresh MoneyPuck v2 to show goalie control leaders.'}</span>
      </div>
      <div className="v2-evidence-list">
        {rows.slice(0, 5).map((row) => (
          <div className="v2-row" key={row.goalie}>
            <span>{row.goalie}</span>
            <strong>{formatDecimal(row.control_score, 1)}</strong>
            <em>{numberFormatter.format(row.pk_shots_faced)} PK shots / {formatSignedDecimal(row.gsax, 1)} goals saved above expected</em>
          </div>
        ))}
      </div>
    </article>
  )
}

function FatigueModelCard({
  rows,
  early,
  late,
}: {
  rows: FatigueRow[]
  early?: FatigueRow
  late?: FatigueRow
}) {
  const maxXg = Math.max(...rows.map((row) => row.avg_xg), 0.001)
  const lift = typeof early?.avg_xg === 'number' && typeof late?.avg_xg === 'number'
    ? late.avg_xg - early.avg_xg
    : undefined
  return (
    <article className="v2-model-card">
      <div className="v2-card-copy">
        <span className="v2-model-number">04</span>
        <h3>Fatigue curve</h3>
        <p>
          Read left to right. The bars show whether shot danger rises as the same penalty killers stay on the ice.
        </p>
      </div>
      <div className="v2-insight-row warning">
        <strong>{formatSignedDecimal(lift, 3)}</strong>
        <span>Difference between the freshest group and the most tired group. Positive means tired shifts gave up harder shots.</span>
      </div>
      <div className="fatigue-curve" aria-label="Fatigue curve by defender average time on ice">
        {rows.map((row) => (
          <div className="fatigue-bar" key={row.bucket}>
            <i style={{ height: `${Math.max((row.avg_xg / maxXg) * 100, 12)}%` }} />
            <span>{row.bucket}</span>
            <strong>{formatXg(row.avg_xg)}</strong>
          </div>
        ))}
      </div>
    </article>
  )
}

function TwoWayModelCard({ rows }: { rows: TwoWayLeader[] }) {
  const top = rows[0]
  return (
    <article className="v2-model-card">
      <div className="v2-card-copy">
        <span className="v2-model-number">05</span>
        <h3>Two-way PK skaters</h3>
        <p>
          The PK usually loses the shot-quality battle. This looks for skaters who make that gap smaller by
          creating pressure while limiting what comes back.
        </p>
      </div>
      <div className="v2-insight-row good">
        <strong>{top ? formatSignedDecimal(top.two_way_net_xg_per60, 2) : 'n/a'}</strong>
        <span>{top ? `${top.name} leads this run. Closer to zero is better because short-handed teams usually lose the xG battle.` : 'Refresh MoneyPuck v2 to show player leaders.'}</span>
      </div>
      <div className="v2-evidence-list">
        {rows.slice(0, 5).map((row) => (
          <div className="v2-row" key={`${row.name}-${row.teams}`}>
            <span>{row.name}</span>
            <strong>{formatSignedDecimal(row.two_way_net_xg_per60, 2)}</strong>
            <em>{row.position} / for {formatDecimal(row.on_ice_sh_xg_for_per60, 2)} xG, against {formatDecimal(row.on_ice_xga_per60, 2)} xG per 60</em>
          </div>
        ))}
      </div>
    </article>
  )
}

function RushSetModelCard({ rows }: { rows: RushSetRow[] }) {
  const rush = rows.find((row) => row.shot_context === 'rush')
  const set = rows.find((row) => row.shot_context === 'set')
  return (
    <article className="v2-model-card v2-diagnostic-card">
      <div className="v2-card-copy">
        <span className="v2-model-number">06</span>
        <h3>Rush or settled play</h3>
        <p>
          Rush chances are fast attacks; settled chances come after the power play is already set up. The rush
          sample is small, so use this as context rather than a headline.
        </p>
      </div>
      <div className="v2-comparison-grid">
        <MiniFact label="Rush shots" value={numberFormatter.format(rush?.shots ?? 0)} helper={`${formatXg(rush?.avg_xg)} average xG`} />
        <MiniFact label="Set shots" value={numberFormatter.format(set?.shots ?? 0)} helper={`${formatXg(set?.avg_xg)} average xG`} />
      </div>
    </article>
  )
}

function MiniFact({ label, value, helper }: { label: string; value: string; helper: string }) {
  return (
    <div className="mini-fact">
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{helper}</em>
    </div>
  )
}

function plainBucketLabel(value: string) {
  const labels: Record<string, string> = {
    rebound: 'Rebound',
    north_south_downhill: 'North-south downhill',
    small_area: 'Small-area pressure',
    east_west: 'East-west',
    slow_reset: 'Slow reset',
    diagonal: 'Diagonal',
    point_reset_backtrack: 'Point reset or backtrack',
  }

  return labels[value] ?? slugLabel(value)
}

function attackTypeLabel(value: string) {
  const labels: Record<string, string> = {
    net_front_rebound: 'Net-front rebound',
    east_west_seam: 'East-west seam',
    downhill: 'Downhill slot push',
    diagonal_seam: 'Diagonal seam',
    bumper_slot: 'Bumper or slot',
    point_reset: 'Point reset',
    reset: 'Reset pressure',
    unknown: 'Unknown',
  }

  return labels[value] ?? slugLabel(value)
}

function zoneIdForAttackType(value: string) {
  const zones: Record<string, string> = {
    net_front_rebound: 'netfront',
    east_west_seam: 'backdoor',
    downhill: 'low_slot',
    diagonal_seam: 'backdoor',
    bumper_slot: 'bumper',
    point_reset: 'point',
    reset: 'point',
  }

  return zones[value] ?? 'low_slot'
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
  const hasV2 = dashboard.version === 'moneypuck_v2'

  return (
    <section className="page-section">
      <PageIntro
        title="Models as hockey arguments."
        body={hasV2
          ? 'The MoneyPuck rebuild is the main model suite. Each model starts with a hockey question, explains the idea in plain language, and then shows the number behind it.'
          : 'Every page is written around one question, one supported finding, and one boundary. The point is to make the analysis readable before it becomes interactive.'}
      />
      {hasV2 && (
        <div className="v2-model-index" aria-label="Current MoneyPuck model suite">
          <div className="model-index-heading">
            <span>Current suite</span>
            <h2>MoneyPuck v2 models</h2>
            <p>These are the current project models. The older NHL API pages remain below for context.</p>
          </div>
          {v2ModelStories.map((story) => (
            <article className="v2-model-index-row" key={story.title}>
              <span>{String(story.number).padStart(2, '0')}</span>
              <div>
                <h3>{story.title}</h3>
                <p>{story.question}</p>
                <em>{story.plainLanguage}</em>
                <small>{story.caveat}</small>
              </div>
              <strong>{story.signal}</strong>
            </article>
          ))}
        </div>
      )}
      <div className="model-index">
        {hasV2 && (
          <div className="model-index-heading legacy-heading">
            <span>Legacy context</span>
            <h2>NHL API model archive</h2>
            <p>Earlier work from the original play-by-play pipeline.</p>
          </div>
        )}
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
  if (dashboard.version === 'moneypuck_v2') {
    return <V2ScoutingPage dashboard={dashboard} />
  }

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

function V2ScoutingPage({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const seasons = useMemo(() => {
    const explicit = dashboard.scoutingSeasons ?? []
    const derived = [
      ...(dashboard.twoWayLeaders ?? []).map((row) => row.season),
      ...(dashboard.goalieControl ?? []).map((row) => row.season),
      ...(dashboard.trustedPkImpact ?? []).map((row) => row.season),
      ...(dashboard.highUpsideNoisy ?? []).map((row) => row.season),
      ...(dashboard.playerSimilarityGroups ?? []).map((row) => row.season),
    ].filter((season): season is number => typeof season === 'number')

    return [...new Set([...explicit, ...derived])].sort((a, b) => b - a)
  }, [dashboard])

  const [selectedSeason, setSelectedSeason] = useState<number | undefined>(() => seasons[0])
  const activeSeason = selectedSeason && seasons.includes(selectedSeason) ? selectedSeason : seasons[0]

  const twoWay = useMemo(() => {
    return (dashboard.twoWayLeaders ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.two_way_net_xg_per60 - a.two_way_net_xg_per60)
  }, [dashboard.twoWayLeaders, activeSeason])

  const offense = useMemo(() => {
    return (dashboard.offenseWithoutLeakage ?? [])
      .filter((row) => row.season === activeSeason)
      .filter((row) => (row.offense_percentile ?? 0) >= 70 && (row.defense_percentile ?? 0) >= 45)
      .sort((a, b) => b.two_way_net_xg_per60 - a.two_way_net_xg_per60)
  }, [dashboard.offenseWithoutLeakage, activeSeason])

  const goalies = useMemo(() => {
    return (dashboard.goalieControl ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.control_score - a.control_score)
  }, [dashboard.goalieControl, activeSeason])

  const reboundWatch = useMemo(() => {
    return (dashboard.reboundLeakWatch ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => (b.rebounds_allowed_above_expected_per100 ?? b.rebounds_allowed_above_expected) - (a.rebounds_allowed_above_expected_per100 ?? a.rebounds_allowed_above_expected))
  }, [dashboard.reboundLeakWatch, activeSeason])

  const trustedTalent = useMemo(() => {
    return (dashboard.trustedPkImpact ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.true_talent_pk_impact_per60 - a.true_talent_pk_impact_per60)
  }, [dashboard.trustedPkImpact, activeSeason])

  const noisyUpside = useMemo(() => {
    return (dashboard.highUpsideNoisy ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.true_talent_pk_impact_per60 - a.true_talent_pk_impact_per60)
  }, [dashboard.highUpsideNoisy, activeSeason])

  const similarityGroups = useMemo(() => {
    return (dashboard.playerSimilarityGroups ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.true_talent_pk_impact_per60 - a.true_talent_pk_impact_per60)
  }, [dashboard.playerSimilarityGroups, activeSeason])

  const playerPassports = useMemo(() => {
    return (dashboard.playerTagProfiles ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => {
        const trustOrder = { high: 3, medium: 2, low: 1 }
        const trustDiff = trustOrder[b.trust_level] - trustOrder[a.trust_level]
        return trustDiff || b.true_talent_pk_impact_per60 - a.true_talent_pk_impact_per60
      })
  }, [dashboard.playerTagProfiles, activeSeason])

  const matchupCards = useMemo(() => {
    return (dashboard.matchupCards ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.matchup_score - a.matchup_score)
  }, [dashboard.matchupCards, activeSeason])

  const attackTypes = useMemo(() => {
    return (dashboard.leagueAttackTypes ?? [])
      .filter((row) => row.season === activeSeason)
      .sort((a, b) => b.xg - a.xg)
  }, [dashboard.leagueAttackTypes, activeSeason])

  return (
    <section className="page-section">
      <PageIntro
        title="Special Teams Scouting Lab"
        body="Compare PP attack tendencies, PK leak profiles, player passports, and goalie rebound/control signals in one game-prep workflow."
      />
      <nav className="scouting-workflow-nav" aria-label="Scouting workflow sections">
        <a href="#matchup-lab">1 Matchup</a>
        <a href="#scouting-brief">2 Brief</a>
        <a href="#player-passports">3 Players</a>
        <a href="#discovery">More Discovery</a>
      </nav>

      <section className="workflow-section primary" id="matchup-lab">
        <div className="workflow-heading">
          <span>Step 1</span>
          <h2>Build the matchup read</h2>
          <p>Select the season and special-teams matchup, then use the rink and generated brief as the game-prep output.</p>
        </div>
        <ScoutingLab
          matchups={matchupCards.slice(0, 5)}
          attackTypes={attackTypes.slice(0, 5)}
          shotMaps={dashboard.teamShotMaps ?? []}
          playerPassports={playerPassports}
          activeSeason={activeSeason}
          seasons={seasons}
          onSeasonChange={setSelectedSeason}
        />
      </section>

      <section className="workflow-section" id="player-passports">
        <div className="workflow-heading">
          <span>Step 3</span>
          <h2>Check player passports</h2>
          <p>Use the season's player tags to understand which PK profiles are stable, which are directional, and where sample trust matters.</p>
        </div>
        <PlayerPassportPanel profiles={playerPassports.slice(0, 6)} />
      </section>

      <section className="workflow-section discovery" id="discovery">
        <div className="workflow-heading">
          <span>Secondary</span>
          <h2>Player + goalie discovery</h2>
          <p>Broader leaderboards for finding PK talent, noisy upside, similar players, two-way profiles, and goalie rebound/control signals.</p>
        </div>
        <div className="scouting-feature-grid">
          <TalentPanel
            title="Trusted PK impact"
            body="Best sample-adjusted estimates. Bigger minutes get more credit; small samples get pulled back."
            rows={trustedTalent.slice(0, 5)}
          />
          <TalentPanel
            title="Interesting but noisy"
            body="Good early signs, but the sample is still thin."
            rows={noisyUpside.slice(0, 5)}
            muted
          />
          <SimilarityPanel groups={similarityGroups.slice(0, 3)} />
        </div>
        <div className="scouting-grid">
          <article className="scouting-panel">
            <h2>Two-way penalty killers</h2>
            {twoWay.slice(0, 5).map((row) => (
              <div className="leader-row" key={`two-way-${row.season}-${row.name}-${row.teams}`}>
                <div>
                  <strong>{row.name}</strong>
                  <em>{row.position} / {row.teams} / closer to zero is better on the PK</em>
                </div>
                <b>{formatSignedDecimal(row.two_way_net_xg_per60, 2)}</b>
              </div>
            ))}
          </article>
          <article className="scouting-panel">
            <h2>Offense without leakage</h2>
            {offense.slice(0, 5).map((row) => (
              <div className="leader-row" key={`offense-${row.season}-${row.name}-${row.teams}`}>
                <div>
                  <strong>{row.name}</strong>
                  <em>{row.teams} / {formatDecimal(row.on_ice_sh_xg_for_per60, 2)} xG for / {formatDecimal(row.on_ice_xga_per60, 2)} xG against per 60</em>
                </div>
                <b>{formatPercentPoint(row.shot_attempt_share)}</b>
              </div>
            ))}
          </article>
          <article className="scouting-panel">
            <h2>Goalie control leaders</h2>
            {goalies.slice(0, 5).map((row) => (
              <div className="leader-row" key={`goalie-${row.season}-${row.goalie}`}>
                <div>
                  <strong>{row.goalie}</strong>
                  <em>{numberFormatter.format(row.pk_shots_faced)} PK shots faced</em>
                </div>
                <b>{formatDecimal(row.control_score, 1)}</b>
              </div>
            ))}
          </article>
          <article className="scouting-panel">
            <h2>Rebound rate watch</h2>
            {reboundWatch.slice(0, 5).map((row) => (
              <div className="leader-row" key={`rebound-${row.season}-${row.goalie}`}>
                <div>
                  <strong>{row.goalie}</strong>
                  <em>Extra rebounds per 100 PK shots; lower is cleaner</em>
                </div>
                <b>{formatSignedDecimal(row.rebounds_allowed_above_expected_per100 ?? row.rebounds_allowed_above_expected, 1)}</b>
              </div>
            ))}
          </article>
        </div>
      </section>
    </section>
  )
}

function ScoutingLab({
  matchups,
  attackTypes,
  shotMaps,
  playerPassports,
  activeSeason,
  seasons,
  onSeasonChange,
}: {
  matchups: MatchupCard[]
  attackTypes: AttackProfileRow[]
  shotMaps: TeamShotMapBin[]
  playerPassports: PlayerTagProfile[]
  activeSeason?: number
  seasons: number[]
  onSeasonChange: (season: number) => void
}) {
  const [mapMode, setMapMode] = useState<TacticalMapMode>('mismatch')
  const [selectedZoneId, setSelectedZoneId] = useState<string | undefined>()
  const ppTeamOptions = useMemo(() => teamOptionsForShotMaps(shotMaps, activeSeason, 'pp_attack'), [activeSeason, shotMaps])
  const pkTeamOptions = useMemo(() => teamOptionsForShotMaps(shotMaps, activeSeason, 'pk_leak'), [activeSeason, shotMaps])
  const [selectedPpTeam, setSelectedPpTeam] = useState('')
  const [selectedPkTeam, setSelectedPkTeam] = useState('')
  const activePpTeam = ppTeamOptions.includes(selectedPpTeam) ? selectedPpTeam : ppTeamOptions[0] ?? ''
  const activePkTeam = pkTeamOptions.includes(selectedPkTeam) ? selectedPkTeam : pkTeamOptions[0] ?? ''
  const seasonShotMaps = useMemo(() => shotMaps.filter((row) => row.season === activeSeason), [activeSeason, shotMaps])
  const ppBins = useMemo(
    () => seasonShotMaps.filter((row) => row.team === activePpTeam && row.profile_type === 'pp_attack'),
    [activePpTeam, seasonShotMaps],
  )
  const pkBins = useMemo(
    () => seasonShotMaps.filter((row) => row.team === activePkTeam && row.profile_type === 'pk_leak'),
    [activePkTeam, seasonShotMaps],
  )
  const mapState = useMemo(
    () => buildTacticalMapState({
      mode: mapMode,
      season: activeSeason,
      ppTeam: activePpTeam,
      pkTeam: activePkTeam,
      ppBins,
      pkBins,
      leagueBins: seasonShotMaps,
      selectedZoneId,
    }),
    [activeSeason, activePkTeam, activePpTeam, mapMode, pkBins, ppBins, seasonShotMaps, selectedZoneId],
  )
  const matchupPassports = useMemo(
    () => selectMatchupPassports(playerPassports, activePkTeam, mapState.primaryPocket?.id),
    [activePkTeam, mapState.primaryPocket?.id, playerPassports],
  )
  const loadMatchupCard = (matchup: MatchupCard) => {
    setSelectedPpTeam(matchup.pp_team)
    setSelectedPkTeam(matchup.pk_team)
    setSelectedZoneId(zoneIdForAttackType(matchup.attack_type))
    setMapMode('mismatch')
  }

  return (
    <section className="scouting-lab" aria-label="Special teams matchup lab">
      <div className="lab-copy">
        <div>
          <span>Matchup lab</span>
          <h2>Where the edge is.</h2>
        </div>
        <p>
          Compare where a PP creates danger against where a PK allows it. The default view is the exploit,
          not a raw shot cloud: PP tendency plus PK leak against the season baseline.
        </p>
      </div>
      <TeamLookMap
        state={mapState}
        mode={mapMode}
        ppTeams={ppTeamOptions}
        pkTeams={pkTeamOptions}
        seasons={seasons}
        activeSeason={activeSeason}
        selectedPpTeam={activePpTeam}
        selectedPkTeam={activePkTeam}
        onSeasonChange={onSeasonChange}
        onModeChange={setMapMode}
        onPpTeamChange={setSelectedPpTeam}
        onPkTeamChange={setSelectedPkTeam}
        onZoneSelect={setSelectedZoneId}
      />
      <div className="matchup-stack">
        <div className="matchup-heading">
          <span>Other league examples</span>
          <strong>{matchups.length ? `${matchups.length} surfaced` : 'No current cards'}</strong>
        </div>
        {matchups.length === 0 && (
          <div className="empty-panel-note">Mismatch cards are generated for the latest season only; the heat map remains a league danger view.</div>
        )}
        {matchups.slice(0, 3).map((matchup) => {
          const canLoad = ppTeamOptions.includes(matchup.pp_team) && pkTeamOptions.includes(matchup.pk_team)
          return (
          <article className="matchup-card" key={`${matchup.season}-${matchup.pp_team}-${matchup.pk_team}-${matchup.attack_type}`}>
            <div>
              <span>{attackTypeLabel(matchup.attack_type)}</span>
              <strong>{matchup.pp_team} PP vs {matchup.pk_team} PK</strong>
              <p>{matchup.note}</p>
            </div>
            <dl>
              <div>
                <dt>PP style</dt>
                <dd>{formatDecimal(matchup.pp_style_index, 2)}x</dd>
              </div>
              <div>
                <dt>PK leak</dt>
                <dd>{formatDecimal(matchup.pk_leak_index, 2)}x</dd>
              </div>
            </dl>
            <button type="button" onClick={() => loadMatchupCard(matchup)} disabled={!canLoad}>
              {canLoad ? 'Load read' : 'Outside selectors'}
            </button>
          </article>
        )})}
        {attackTypes.length > 0 && (
          <div className="attack-type-strip">
            {attackTypes.map((row) => (
              <div key={`${row.attack_type}-${row.xg}`}>
                <span>{attackTypeLabel(row.attack_type)}</span>
                <strong>{formatXg(row.avg_xg)}</strong>
                <em>{numberFormatter.format(row.shots)} shots</em>
              </div>
            ))}
          </div>
        )}
      </div>
      <ScoutingBriefPanel
        mapState={mapState}
        mode={mapMode}
        season={activeSeason}
        playerPassports={matchupPassports}
      />
    </section>
  )
}

function ScoutingBriefPanel({
  mapState,
  mode,
  season,
  playerPassports,
}: {
  mapState: TacticalMapState
  mode: TacticalMapMode
  season?: number
  playerPassports: PlayerTagProfile[]
}) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const brief = useMemo(
    () => buildScoutingBrief(mapState, mode, season, playerPassports),
    [mapState, mode, playerPassports, season],
  )

  const copyBrief = async () => {
    try {
      await copyPlainText(brief.text)
      setCopyState('copied')
      window.setTimeout(() => setCopyState('idle'), 1800)
    } catch {
      setCopyState('failed')
      window.setTimeout(() => setCopyState('idle'), 2200)
    }
  }

  const downloadBrief = () => {
    const blob = new Blob([brief.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${brief.fileSlug}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <article className="scouting-brief" id="scouting-brief" aria-label="Generated scouting brief">
      <div className="brief-topline">
        <div>
          <span>Scouting brief</span>
          <h3>{brief.title}</h3>
        </div>
        <div className="brief-actions">
          <button type="button" onClick={copyBrief}>{copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy brief'}</button>
          <button type="button" onClick={downloadBrief}>Download .txt</button>
        </div>
      </div>

      <div className="brief-report-grid">
        <section>
          <span>Main conclusion</span>
          <strong>{brief.mainConclusion.heading}</strong>
          <p>{brief.mainConclusion.body}</p>
        </section>
        <section>
          <span>Recommended attack</span>
          <strong>{brief.recommendedAttack.heading}</strong>
          <p>{brief.recommendedAttack.body}</p>
        </section>
      </div>

      <section className="brief-evidence">
        <span>Supporting evidence</span>
        <dl>
          {brief.evidence.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="brief-passports">
        <span>{brief.playerNoteHeading}</span>
        {brief.playerNotes.length === 0 ? (
          <p>{brief.playerNoteEmpty}</p>
        ) : (
          <ul>
            {brief.playerNotes.map((note) => (
              <li key={note.name}>
                <strong>{note.name}</strong>
                <span>{note.meta}</span>
                <p>{note.read}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="brief-caveats">
        <span>Caveats</span>
        <ul>
          {brief.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      </section>
    </article>
  )
}

async function copyPlainText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return
  } catch {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.setAttribute('readonly', '')
    textArea.style.position = 'fixed'
    textArea.style.left = '-9999px'
    textArea.style.top = '0'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textArea)
    if (!copied) {
      throw new Error('Unable to copy scouting brief')
    }
  }
}

function TeamLookMap({
  state,
  mode,
  ppTeams,
  pkTeams,
  seasons,
  activeSeason,
  selectedPpTeam,
  selectedPkTeam,
  onSeasonChange,
  onModeChange,
  onPpTeamChange,
  onPkTeamChange,
  onZoneSelect,
}: {
  state: TacticalMapState
  mode: TacticalMapMode
  ppTeams: string[]
  pkTeams: string[]
  seasons: number[]
  activeSeason?: number
  selectedPpTeam: string
  selectedPkTeam: string
  onSeasonChange: (season: number) => void
  onModeChange: (mode: TacticalMapMode) => void
  onPpTeamChange: (team: string) => void
  onPkTeamChange: (team: string) => void
  onZoneSelect: (zoneId: string) => void
}) {
  const hasData = ppTeams.length > 0 && pkTeams.length > 0 && state.primaryPocket
  const recommendedAttack = recommendedAttackForZone(state.primaryPocket?.id, state.ppTeam)
  const seasonLabel = activeSeason ? formatSeasonLabel(activeSeason) : 'Season pending'
  const modeLabel = mode === 'mismatch' ? 'Exploit view' : mode === 'pp_attack' ? 'PP creation' : 'PK allowed danger'

  return (
    <div className="danger-heatmap" aria-label="Power play and penalty kill matchup map">
      <div className="heatmap-toolbar">
        <div>
          <label htmlFor="scouting-season">Season</label>
          <select
            id="scouting-season"
            value={activeSeason ?? ''}
            onChange={(event) => onSeasonChange(Number(event.target.value))}
          >
            {seasons.map((season) => (
              <option key={season} value={season}>
                {formatSeasonLabel(season)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="pp-team-select">PP team</label>
          <select id="pp-team-select" value={selectedPpTeam} onChange={(event) => onPpTeamChange(event.target.value)} disabled={ppTeams.length === 0}>
            {ppTeams.map((team) => (
              <option key={team} value={team}>{team}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="pk-team-select">PK team</label>
          <select id="pk-team-select" value={selectedPkTeam} onChange={(event) => onPkTeamChange(event.target.value)} disabled={pkTeams.length === 0}>
            {pkTeams.map((team) => (
              <option key={team} value={team}>{team}</option>
            ))}
          </select>
        </div>
        <div className="map-mode-toggle" aria-label="Shot map mode">
          <button className={mode === 'mismatch' ? 'active' : ''} type="button" onClick={() => onModeChange('mismatch')}>Mismatch</button>
          <button className={mode === 'pp_attack' ? 'active' : ''} type="button" onClick={() => onModeChange('pp_attack')}>PP creates</button>
          <button className={mode === 'pk_leak' ? 'active' : ''} type="button" onClick={() => onModeChange('pk_leak')}>PK allows</button>
        </div>
      </div>
      {!hasData && (
        <div className="empty-panel-note">Run the MoneyPuck v2 model refresh to populate team-season shot maps for this mode.</div>
      )}
      {state.primaryPocket && (
        <div className="heatmap-callout">
          <span>{mode === 'mismatch' ? 'Main conclusion' : mode === 'pp_attack' ? 'Primary PP area' : 'Primary PK leak'}</span>
          <strong>{state.primaryPocket.label}</strong>
          <div className="edge-summary">
            <b>{state.edgeLabel}</b>
            <em>{state.callout}</em>
            <small>{state.edgeSource}</small>
          </div>
        </div>
      )}
      <div className="matchup-read-strip" aria-label="Current matchup read">
        <div>
          <span>Current read</span>
          <strong>{state.ppTeam || 'PP'} PP vs {state.pkTeam || 'PK'} PK</strong>
          <em>{seasonLabel} / {modeLabel}</em>
        </div>
        <div>
          <span>Primary edge</span>
          <strong>{state.primaryPocket?.label ?? 'No zone selected'}</strong>
          <em>{state.edgeLabel} / {cleanEdgeSource(state.edgeSource)}</em>
        </div>
        <div>
          <span>Shape check</span>
          <strong>{state.primaryPocket ? `${sentenceCase(state.primaryPocket.ppTendencyLabel)} PP / ${sentenceCase(state.primaryPocket.pkLeakLabel)} PK` : 'Pending'}</strong>
          <em>{state.primaryPocket ? `${formatDecimal(state.primaryPocket.mismatchScore, 2)} exploit index` : 'Select teams with map data'}</em>
        </div>
        <div>
          <span>Next action</span>
          <strong>{recommendedAttack.heading}</strong>
          <em>{recommendedAttack.body}</em>
        </div>
      </div>
      {hasData && (
        <>
          <AnimatedPatternBoard state={state} mode={mode} />
          <div className="look-map-bottom">
            <div className="heatmap-zone-list">
              {state.zoneCards.map((zone, index) => (
                <button className={zone.id === state.selectedZoneId ? 'active' : ''} type="button" key={zone.id} onClick={() => onZoneSelect(zone.id)}>
                  <span>{index + 1}. {zone.label}</span>
                  <strong>{zone.edgeLabel}</strong>
                  <em>{zone.edgeSource}</em>
                </button>
              ))}
            </div>
            <div className="structure-read">
              <span>Tactical read</span>
              <strong>{state.route.title}</strong>
              <p>{state.tacticalSentence}</p>
              <details className="formula-details">
                <summary>Formula and debug</summary>
                <p>{state.formulaExplanation}</p>
                <code>{state.debugLine}</code>
              </details>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function AnimatedPatternBoard({ state, mode }: { state: TacticalMapState; mode: TacticalMapMode }) {
  return (
    <div className="pattern-board" aria-label={`${state.ppTeam} power play versus ${state.pkTeam} penalty kill tactical map`}>
      <svg viewBox="0 0 920 460" role="img">
        <defs>
          <filter id="patternGlow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="patternArrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
            <path d="M0 0 L8 4.5 L0 9 Z" />
          </marker>
          <marker id="patternShotArrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
            <path d="M0 0 L9 5 L0 10 Z" />
          </marker>
        </defs>
        <rect className="pattern-ice" x="30" y="38" width="860" height="384" rx="18" />
        <line className="pattern-blue-line" x1="132" y1="38" x2="132" y2="422" />
        <line className="pattern-goal-line" x1="814" y1="38" x2="814" y2="422" />
        <rect className="pattern-net" x="852" y="198" width="10" height="64" rx="5" />
        <path className="pattern-crease" d="M814 176 L814 284 L758 284 C724 276 706 256 706 230 C706 204 724 184 758 176 Z" />
        <circle className="pattern-dot" cx="612" cy="128" r="5" />
        <circle className="pattern-dot" cx="612" cy="332" r="5" />
        {state.zoneCards.slice(0, 7).map((zone) => (
          <g className={`tactical-zone ${mode === 'mismatch' ? 'mismatch' : mode === 'pp_attack' ? 'pp' : 'pk'} ${zone.id === state.selectedZoneId ? 'active' : ''}`} key={zone.id}>
            <ellipse
              cx={zone.x}
              cy={zone.y}
              rx={zone.radiusX}
              ry={zone.radiusY}
            />
          </g>
        ))}
        {state.route.lanes.map((lane, index) => (
          <line className={`pattern-lane ${lane.kind ?? 'pass'}`} x1={lane.from.x} y1={lane.from.y} x2={lane.to.x} y2={lane.to.y} key={`${lane.from.x}-${lane.to.x}-${index}`} />
        ))}
        {state.route.shotLane && (
          <line className="pattern-shot-lane" x1={state.route.shotLane.from.x} y1={state.route.shotLane.from.y} x2={state.route.shotLane.to.x} y2={state.route.shotLane.to.y} />
        )}
        {state.route.touchPoints.map((point, index) => (
          <g className={`pattern-touch ${index === state.route.touchPoints.length - 1 ? 'finish' : ''}`} key={`${point.x}-${point.y}-${index}`}>
            <circle cx={point.x} cy={point.y} r={index === 0 ? 8 : 6} />
            {index === 1 && <circle className="pattern-touch-ring" cx={point.x} cy={point.y} r="14" />}
          </g>
        ))}
        {state.skaters.map((skater) => (
          <g className={`pattern-player ${skater.side} ${skater.active ? 'active' : ''}`} transform={`translate(${skater.x} ${skater.y})`} key={skater.label}>
            <circle className="pattern-player-halo" r={skater.active ? 28 : 23} />
            {skater.side === 'pp' ? (
              <circle className="pattern-player-token" r={skater.active ? 17 : 15} />
            ) : (
              <rect className="pattern-player-token" x="-13" y="-13" width="26" height="26" rx="5" transform="rotate(45)" />
            )}
            {skater.active && <circle className="pattern-player-core" r="4" />}
            <text y="5">{skater.label}</text>
          </g>
        ))}
        <circle className="pattern-touch-point-ring" cx={state.route.touchPoint.x} cy={state.route.touchPoint.y} r="18" />
        <circle className="pattern-touch-point" cx={state.route.touchPoint.x} cy={state.route.touchPoint.y} r="8" filter="url(#patternGlow)" />
        <text className="pattern-touch-point-label" x={state.route.touchPoint.x} y={state.route.touchPoint.y - 25}>TOUCH POINT</text>
      </svg>
      <div className="pattern-caption">
        <div className="pattern-play-header">
          <strong>{state.route.title}</strong>
          <span>Suggested touch sequence</span>
        </div>
        <p className="pattern-play-copy">{state.route.detail}</p>
        <div className="pattern-key-row" aria-label="Tactical route and role legend">
          <span className="pattern-key-title">Play key</span>
          <div className="pattern-key-groups">
            <div className="pattern-legend">
              <span><i className="legend-line carry" /> Carry lane</span>
              <span><i className="legend-line pass" /> Pass lane</span>
              <span><i className="legend-line shot" /> Shot lane</span>
              <span><i className="legend-touch" /> Touch point</span>
            </div>
            <div className="pattern-roles">
              <span><b>PP</b> P LF RF B NF</span>
              <span><b>PK</b> F1 F2 D1 D2</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

type TacticalMapMode = 'mismatch' | 'pp_attack' | 'pk_leak'

type TacticalPocket = {
  id: string
  label: string
  shortLabel: string
  x: number
  y: number
  radiusX: number
  radiusY: number
  shots: number
  xg: number
  avgXg: number
  ppShare: number
  pkShare: number
  ppIndex: number
  pkIndex: number
  xgValueIndex: number
  mismatchScore: number
  edgeLabel: string
  edgeSource: string
  ppTendencyLabel: string
  pkLeakLabel: string
  weight: number
}

type TacticalSkater = {
  label: string
  role: 'point' | 'left_flank' | 'right_flank' | 'bumper' | 'net_front' | 'f1' | 'f2' | 'd1' | 'd2'
  side: 'pp' | 'pk'
  x: number
  y: number
  active: boolean
}

type TacticalRoute = {
  title: string
  detail: string
  lanes: { from: { x: number; y: number }; to: { x: number; y: number }; kind?: 'carry' | 'pass' }[]
  shotLane?: { from: { x: number; y: number }; to: { x: number; y: number } }
  touchPoint: { x: number; y: number }
  touchPoints: { x: number; y: number }[]
  involvedPpRoles: TacticalSkater['role'][]
  stressedPkRoles: TacticalSkater['role'][]
}

type TacticalMapState = {
  mode: TacticalMapMode
  season?: number
  ppTeam: string
  pkTeam: string
  primaryPocket?: TacticalPocket
  selectedZoneId?: string
  supportPockets: TacticalPocket[]
  zoneCards: TacticalPocket[]
  skaters: TacticalSkater[]
  route: TacticalRoute
  callout: string
  edgeLabel: string
  edgeSource: string
  tacticalSentence: string
  debugLine: string
  formulaExplanation: string
}

type TacticalZoneDefinition = {
  id: string
  label: string
  shortLabel: string
  x: number
  y: number
  radiusX: number
  radiusY: number
}

const TACTICAL_ZONES: TacticalZoneDefinition[] = [
  { id: 'netfront', label: 'Net-front rebounds', shortLabel: 'NET', x: 756, y: 230, radiusX: 58, radiusY: 46 },
  { id: 'low_slot', label: 'Low slot', shortLabel: 'SLOT', x: 682, y: 230, radiusX: 68, radiusY: 50 },
  { id: 'bumper', label: 'Bumper pocket', shortLabel: 'BUM', x: 598, y: 230, radiusX: 62, radiusY: 46 },
  { id: 'left_flank', label: 'Left flank', shortLabel: 'L-FLK', x: 548, y: 138, radiusX: 82, radiusY: 48 },
  { id: 'right_flank', label: 'Right flank', shortLabel: 'R-FLK', x: 548, y: 322, radiusX: 82, radiusY: 48 },
  { id: 'point', label: 'Point reset', shortLabel: 'POINT', x: 260, y: 230, radiusX: 78, radiusY: 50 },
  { id: 'backdoor', label: 'East-west seam', shortLabel: 'SEAM', x: 740, y: 318, radiusX: 64, radiusY: 42 },
]

const TACTICAL_ZONE_LOOKUP = new Map(TACTICAL_ZONES.map((zone) => [zone.id, zone]))

function buildScoutingBrief(
  state: TacticalMapState,
  mode: TacticalMapMode,
  season: number | undefined,
  playerPassports: PlayerTagProfile[],
) {
  const seasonLabel = season ? formatSeasonLabel(season) : 'Latest season'
  const zone = state.primaryPocket
  const title = `${seasonLabel} ${state.ppTeam || 'PP'} PP vs ${state.pkTeam || 'PK'} PK Scouting Brief`
  const zoneLabel = zone?.label ?? 'Selected zone'
  const edgeSource = cleanEdgeSource(zone?.edgeSource ?? state.edgeSource)
  const attack = recommendedAttackForZone(zone?.id, state.ppTeam)
  const modeLabel = mode === 'mismatch' ? 'Mismatch view' : mode === 'pp_attack' ? 'PP creation view' : 'PK allowed-danger view'
  const mainBody = zone
    ? `${state.ppTeam} creates ${zone.ppTendencyLabel} danger around ${zoneLabel.toLowerCase()} and ${state.pkTeam}'s PK is ${zone.pkLeakLabel} there, making this a ${state.edgeLabel.toLowerCase()} (${edgeSource}).`
    : 'No selected PP/PK shot pocket is available for this season and matchup.'
  const evidence = zone
    ? [
        { label: 'PP tendency', value: `${sentenceCase(zone.ppTendencyLabel)} (${formatDecimal(zone.ppIndex, 2)}x season baseline)` },
        { label: 'PK leak', value: `${sentenceCase(zone.pkLeakLabel)} (${formatDecimal(zone.pkIndex, 2)}x season baseline)` },
        { label: 'Exploit score', value: `${formatDecimal(zone.mismatchScore, 2)} (${state.edgeLabel.toLowerCase()})` },
        { label: 'Zone volume', value: `${numberFormatter.format(zone.shots)} PP/PK shot events in this zone` },
        { label: 'Baseline note', value: `${modeLabel}; scores are normalized to the selected season.` },
      ]
    : [{ label: 'Evidence', value: 'No zone evidence is available for this selected state.' }]
  const playerNotes = playerPassports.map((profile) => {
    const primaryTags = profile.tags.filter((tag) => tag.category !== 'trust').slice(0, 4)
    const strength = profile.top_strengths[0] ?? profile.tags.find((tag) => tag.category === 'strength' || tag.category === 'style')
    const risk = profile.main_risks[0] ?? profile.tags.find((tag) => tag.category === 'risk')
    const archetype = strength?.label ?? primaryTags[0]?.label ?? 'Role profile pending'
    const sample = sampleTrustForProfile(profile)
    return {
      name: profile.name,
      meta: `${archetype} / ${sample.label}`,
      read: passportScoutingRead(profile, sample, archetype, strength, risk),
    }
  })
  const playerNoteHeading = `${state.pkTeam || 'PK'} PK player passport notes`
  const playerNoteEmpty = state.pkTeam
    ? `No ${state.pkTeam} PK player passports matched this selected season and team context.`
    : 'No PK player passports are available for this selected matchup.'
  const caveats = [
    'Based on shot and last-event geometry, not full player tracking.',
    'The tactical route is a simplified touch sequence, not a tracked puck path.',
    'Low-sample player tags are directional.',
    'Matchup scores are season-relative.',
  ]
  const zoneRankings = state.zoneCards
    .slice(0, 7)
    .map((rankedZone, index) => `${index + 1}. ${rankedZone.label} - ${rankedZone.edgeLabel}; ${cleanEdgeSource(rankedZone.edgeSource)}.`)

  const text = [
    title,
    '',
    'MAIN CONCLUSION',
    `Main edge: ${zoneLabel}.`,
    mainBody,
    '',
    'RECOMMENDED ATTACK',
    `${attack.heading}: ${attack.body}`,
    '',
    'SUPPORTING EVIDENCE',
    ...evidence.map((item) => `- ${item.label}: ${item.value}`),
    '',
    'ZONE RANKINGS',
    ...zoneRankings,
    '',
    'PLAYER PASSPORT NOTES',
    ...(playerNotes.length ? playerNotes.map((note) => `- ${note.name} (${note.meta}): ${note.read}`) : [`- ${playerNoteEmpty}`]),
    '',
    'CAVEATS',
    ...caveats.map((caveat) => `- ${caveat}`),
  ].join('\n')

  return {
    title,
    fileSlug: `${seasonLabel}-${state.ppTeam || 'pp'}-pp-vs-${state.pkTeam || 'pk'}-pk-scouting-brief`.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''),
    mainConclusion: {
      heading: `Main edge: ${zoneLabel}`,
      body: mainBody,
    },
    recommendedAttack: attack,
    evidence,
    playerNoteHeading,
    playerNoteEmpty,
    playerNotes,
    caveats,
    text,
  }
}

function cleanEdgeSource(value: string) {
  return value.replace(/^Edge source:\s*/i, '').trim() || 'source unclear'
}

function recommendedAttackForZone(zoneId: string | undefined, ppTeam: string) {
  const team = ppTeam || 'The PP'
  if (zoneId === 'netfront') {
    return {
      heading: 'Create second contact',
      body: `${team} should use a point or flank shot lane with traffic, then hunt the rebound and net-front second touch.`,
    }
  }
  if (zoneId === 'low_slot') {
    return {
      heading: 'Touch into the middle',
      body: `${team} should move from the half-wall into the bumper or low slot before the PK can collapse.`,
    }
  }
  if (zoneId === 'bumper') {
    return {
      heading: 'Trigger the bumper release',
      body: `${team} should use a flank or point entry into the bumper, then release quickly through the middle defender.`,
    }
  }
  if (zoneId === 'left_flank' || zoneId === 'right_flank') {
    return {
      heading: 'Open the flank lane',
      body: `${team} should look for the weak-side one-timer or catch-and-release flank lane after moving the PK laterally.`,
    }
  }
  if (zoneId === 'backdoor') {
    return {
      heading: 'Hit the east-west seam',
      body: `${team} should pull the PK toward the strong side, then make the lateral seam pass before the shot lane closes.`,
    }
  }
  return {
    heading: 'Reset high, attack downhill',
    body: `${team} should use the point reset to expand the PK shape, then attack the next lane into the middle.`,
  }
}

function teamOptionsForShotMaps(shotMaps: TeamShotMapBin[], season: number | undefined, profileType: TeamShotMapBin['profile_type']) {
  const teamScores = new Map<string, number>()
  shotMaps
    .filter((row) => row.season === season && row.profile_type === profileType && row.team)
    .forEach((row) => {
      teamScores.set(row.team, (teamScores.get(row.team) ?? 0) + (row.map_score ?? row.xg ?? 0))
    })
  return [...teamScores.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 16)
    .map(([team]) => team)
}

function selectMatchupPassports(profiles: PlayerTagProfile[], pkTeam: string, zoneId?: string) {
  return profiles
    .filter((profile) => profileBelongsToTeam(profile, pkTeam))
    .sort((a, b) => {
      const zoneDiff = exploitRelevanceScore(b, zoneId) - exploitRelevanceScore(a, zoneId)
      const sampleDiff = sampleTrustScore(b) - sampleTrustScore(a)
      const signalDiff = (b.supporting_signal_count ?? b.tags.length) - (a.supporting_signal_count ?? a.tags.length)
      const minutesDiff = (b.ice_time ?? 0) - (a.ice_time ?? 0)
      const impactDiff = b.true_talent_pk_impact_per60 - a.true_talent_pk_impact_per60
      return zoneDiff || sampleDiff || signalDiff || minutesDiff || impactDiff
    })
    .slice(0, 5)
}

function profileBelongsToTeam(profile: PlayerTagProfile, team: string) {
  if (!team) return false
  return profile.teams
    .split(/[/,| ]+/)
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean)
    .includes(team.toUpperCase())
}

function sampleTrustScore(profile: PlayerTagProfile) {
  const trust = sampleTrustForProfile(profile)
  if (trust.trustLevel === 'high') return 3
  if (trust.trustLevel === 'medium') return 2
  return 1
}

function exploitRelevanceScore(profile: PlayerTagProfile, zoneId?: string) {
  const zoneTerms: Record<string, string[]> = {
    netfront: ['block', 'clear', 'low-event', 'penalty', 'risk', 'defender'],
    low_slot: ['low-event', 'slot', 'block', 'clear', 'pressure', 'defender'],
    bumper: ['low-event', 'slot', 'pressure', 'defender', 'block'],
    left_flank: ['pressure', 'counterattack', 'low-event', 'penalty'],
    right_flank: ['pressure', 'counterattack', 'low-event', 'penalty'],
    backdoor: ['pressure', 'counterattack', 'low-event', 'penalty', 'defender'],
    point: ['block', 'clear', 'pressure', 'low-event'],
  }
  const terms = zoneTerms[zoneId ?? ''] ?? []
  if (terms.length === 0) return 0
  const haystack = profile.tags
    .map((tag) => `${tag.tag_id} ${tag.label} ${tag.category} ${tag.reason}`)
    .join(' ')
    .toLowerCase()
  return terms.reduce((score, term) => score + (haystack.includes(term) ? 1 : 0), 0)
}

function ppTendencyLabelFor(index: number) {
  if (index < 0.9) return 'weak'
  if (index < 1.12) return 'average'
  return 'strong'
}

function pkLeakLabelFor(index: number) {
  if (index < 0.9) return 'sealed'
  if (index < 1.12) return 'average'
  return 'vulnerable'
}

function sentenceCase(value: string) {
  return value ? `${value[0].toUpperCase()}${value.slice(1)}` : value
}

function edgeLevelLabel(score: number, mode: TacticalMapMode) {
  if (mode === 'pp_attack') return `${sentenceCase(ppTendencyLabelFor(score))} PP tendency`
  if (mode === 'pk_leak') return `${sentenceCase(pkLeakLabelFor(score))} PK leak`
  if (score < 0.95) return 'No clear edge'
  if (score < 1.15) return 'Small edge'
  if (score < 1.45) return 'Moderate edge'
  return 'Major edge'
}

function edgeSourceLabel(ppIndex: number, pkIndex: number, score: number) {
  if (score < 0.95) return 'Edge source: no clean overlap'
  const ppStrong = ppIndex >= 1.12
  const pkVulnerable = pkIndex >= 1.12
  if (ppStrong && pkVulnerable) return 'Edge source: mutual overlap'
  if (ppStrong) return 'Edge source: PP-driven'
  if (pkVulnerable) return 'Edge source: PK-driven'
  return 'Edge source: xG-value driven'
}

function buildTacticalMapState({
  mode,
  season,
  ppTeam,
  pkTeam,
  ppBins,
  pkBins,
  leagueBins,
  selectedZoneId,
}: {
  mode: TacticalMapMode
  season?: number
  ppTeam: string
  pkTeam: string
  ppBins: TeamShotMapBin[]
  pkBins: TeamShotMapBin[]
  leagueBins: TeamShotMapBin[]
  selectedZoneId?: string
}): TacticalMapState {
  const ppZones = aggregateTacticalZones(ppBins)
  const pkZones = aggregateTacticalZones(pkBins)
  const leaguePpZones = aggregateTacticalZones(leagueBins.filter((row) => row.profile_type === 'pp_attack'))
  const leaguePkZones = aggregateTacticalZones(leagueBins.filter((row) => row.profile_type === 'pk_leak'))
  const pockets = TACTICAL_ZONES.map((zone) => {
    const pp = ppZones.get(zone.id)
    const pk = pkZones.get(zone.id)
    const leaguePp = leaguePpZones.get(zone.id)
    const leaguePk = leaguePkZones.get(zone.id)
    const ppShare = pp?.share ?? 0
    const pkShare = pk?.share ?? 0
    const ppIndex = ppShare / Math.max(leaguePp?.share ?? 0.04, 0.025)
    const pkIndex = pkShare / Math.max(leaguePk?.share ?? 0.04, 0.025)
    const avgXg = weightedAverage([
      { value: pp?.avgXg ?? 0, weight: pp?.shots ?? 0 },
      { value: pk?.avgXg ?? 0, weight: pk?.shots ?? 0 },
    ])
    const leagueAvgXg = weightedAverage([
      { value: leaguePp?.avgXg ?? 0, weight: leaguePp?.shots ?? 0 },
      { value: leaguePk?.avgXg ?? 0, weight: leaguePk?.shots ?? 0 },
    ])
    const xgValueIndex = avgXg / Math.max(leagueAvgXg || 0.08, 0.04)
    const mismatchScore = mode === 'pp_attack'
      ? ppIndex
      : mode === 'pk_leak'
        ? pkIndex
        : ppIndex * pkIndex * xgValueIndex
    const edgeLabel = edgeLevelLabel(mismatchScore, mode)
    const ppTendencyLabel = ppTendencyLabelFor(ppIndex)
    const pkLeakLabel = pkLeakLabelFor(pkIndex)
    const edgeSource = edgeSourceLabel(ppIndex, pkIndex, mismatchScore)
    const x = weightedAverage([
      { value: pp?.x ?? zone.x, weight: mode === 'pk_leak' ? 1 : pp?.xg ?? 0 },
      { value: pk?.x ?? zone.x, weight: mode === 'pp_attack' ? 1 : pk?.xg ?? 0 },
      { value: zone.x, weight: 3 },
    ])
    const y = weightedAverage([
      { value: pp?.y ?? zone.y, weight: mode === 'pk_leak' ? 1 : pp?.xg ?? 0 },
      { value: pk?.y ?? zone.y, weight: mode === 'pp_attack' ? 1 : pk?.xg ?? 0 },
      { value: zone.y, weight: 3 },
    ])
    return {
      ...zone,
      x: clampNumber(x, 170, 790),
      y: clampNumber(y, 92, 368),
      shots: (pp?.shots ?? 0) + (pk?.shots ?? 0),
      xg: (pp?.xg ?? 0) + (pk?.xg ?? 0),
      avgXg,
      ppShare,
      pkShare,
      ppIndex,
      pkIndex,
      xgValueIndex,
      mismatchScore,
      edgeLabel,
      edgeSource,
      ppTendencyLabel,
      pkLeakLabel,
      weight: clampNumber(mismatchScore / 2.7, 0.12, 1),
    }
  }).sort((left, right) => right.mismatchScore - left.mismatchScore)

  const primaryPocket = pockets.find((pocket) => pocket.id === selectedZoneId) ?? pockets[0]
  const activeZoneId = primaryPocket?.id
  const supportPockets = enforcePocketSpacing(pockets.filter((pocket) => pocket.id !== primaryPocket?.id).slice(0, 4), primaryPocket)
  const route = buildTacticalRoute(primaryPocket, mode, ppTeam, pkTeam)
  const skaters = buildTacticalSkaters(route)
  const callout = primaryPocket
    ? `${ppTeam} has ${primaryPocket.ppTendencyLabel} creation here, while ${pkTeam}'s PK is ${primaryPocket.pkLeakLabel}. ${primaryPocket.edgeLabel}.`
    : 'No matched PP/PK pockets in the selected season payload.'
  const edgeLabel = primaryPocket?.edgeLabel ?? 'No edge'
  const edgeSource = primaryPocket?.edgeSource ?? 'No matched source'
  const tacticalSentence = primaryPocket
    ? `${ppTeam} should test ${primaryPocket.label.toLowerCase()} because the selected PP profile and ${pkTeam}'s allowed-danger profile overlap there after season-baseline adjustment. ${primaryPocket.edgeSource}.`
    : 'Select a season and teams with exported shot-map bins to build a tactical read.'
  const debugLine = primaryPocket
    ? `season=${season ?? 'n/a'} mode=${mode} pp=${ppTeam} pk=${pkTeam} zone=${primaryPocket.id} ppIndex=${formatDecimal(primaryPocket.ppIndex, 2)} pkIndex=${formatDecimal(primaryPocket.pkIndex, 2)} xgValue=${formatDecimal(primaryPocket.xgValueIndex, 2)} exploit=${formatDecimal(primaryPocket.mismatchScore, 2)} primary=(${Math.round(primaryPocket.x)},${Math.round(primaryPocket.y)}) route=${route.touchPoints.map((point) => `${Math.round(point.x)},${Math.round(point.y)}`).join(' -> ')}`
    : `season=${season ?? 'n/a'} mode=${mode} pp=${ppTeam} pk=${pkTeam} no-pockets`
  const formulaExplanation = 'Scores are normalized against the selected season baseline. PP tendency = selected PP zone xG share divided by league PP zone xG share. PK leak = selected PK allowed xG share divided by league PK allowed share. Mismatch mode ranks zones by PP tendency x PK leak x zone xG value, where 1.00 is league-average overlap. The top zone is selected because it has the highest exploit index after that adjustment.'

  return {
    mode,
    season,
    ppTeam,
    pkTeam,
    primaryPocket,
    selectedZoneId: activeZoneId,
    supportPockets,
    zoneCards: pockets.slice(0, 7),
    skaters,
    route,
    callout,
    edgeLabel,
    edgeSource,
    tacticalSentence,
    debugLine,
    formulaExplanation,
  }
}

function aggregateTacticalZones(bins: TeamShotMapBin[]) {
  const totalXg = bins.reduce((sum, bin) => sum + bin.xg, 0)
  const grouped = new Map<string, {
    id: string
    label: string
    shortLabel: string
    shots: number
    xg: number
    weightedX: number
    weightedY: number
  }>()
  bins.forEach((bin) => {
    const point = toBoardPoint(bin)
    const zone = tacticalZoneForBin(bin)
    const current = grouped.get(zone.id) ?? {
      id: zone.id,
      label: zone.label,
      shortLabel: zone.shortLabel,
      shots: 0,
      xg: 0,
      weightedX: 0,
      weightedY: 0,
    }
    current.shots += bin.shots
    current.xg += bin.xg
    current.weightedX += point.x * bin.xg
    current.weightedY += point.y * bin.xg
    grouped.set(zone.id, current)
  })

  return new Map([...grouped.entries()].map(([id, zone]) => [id, {
    ...zone,
    share: totalXg ? zone.xg / totalXg : 0,
    avgXg: zone.shots ? zone.xg / zone.shots : 0,
    x: zone.xg ? zone.weightedX / zone.xg : TACTICAL_ZONE_LOOKUP.get(id)?.x ?? 460,
    y: zone.xg ? zone.weightedY / zone.xg : TACTICAL_ZONE_LOOKUP.get(id)?.y ?? 230,
  }]))
}

function tacticalZoneForBin(bin: TeamShotMapBin) {
  const rinkX = typeof bin.rink_x === 'number' ? bin.rink_x : (bin.x_bin / 16) * 100
  const rinkY = typeof bin.rink_y === 'number' ? bin.rink_y : ((bin.y_bin / 12) * 85) - 42.5
  const absY = Math.abs(rinkY)
  if (rinkX >= 84 && absY <= 15) return TACTICAL_ZONE_LOOKUP.get('netfront')!
  if (rinkX >= 78 && absY > 18) return TACTICAL_ZONE_LOOKUP.get('backdoor')!
  if (rinkX >= 68 && absY <= 18) return TACTICAL_ZONE_LOOKUP.get('low_slot')!
  if (rinkX >= 48 && rinkX < 72 && absY <= 18) return TACTICAL_ZONE_LOOKUP.get('bumper')!
  if (rinkX < 46) return TACTICAL_ZONE_LOOKUP.get('point')!
  if (rinkY < 0) return TACTICAL_ZONE_LOOKUP.get('left_flank')!
  return TACTICAL_ZONE_LOOKUP.get('right_flank')!
}

function buildTacticalRoute(primary: TacticalPocket | undefined, mode: TacticalMapMode, ppTeam: string, pkTeam: string): TacticalRoute {
  const point = { x: 292, y: 230 }
  const leftFlank = { x: 480, y: 126 }
  const rightFlank = { x: 480, y: 334 }
  const bumper = { x: 610, y: 230 }
  const lowSlot = { x: 686, y: 230 }
  const netFront = { x: 758, y: 230 }
  const backdoor = { x: 742, y: 316 }
  const net = { x: 824, y: 230 }
  const highWall = { x: 560, y: 104 }
  const lowWall = { x: 560, y: 356 }
  const highGap = { x: 710, y: 138 }
  const lowGap = { x: 710, y: 322 }
  const highMiddle = { x: 642, y: 158 }
  const lowMiddle = { x: 642, y: 302 }
  const highBoardSeam = { x: 728, y: 104 }
  const lowBoardSeam = { x: 728, y: 356 }
  if (!primary) {
    const fallbackPoints = [leftFlank, bumper, netFront]
    return {
      title: 'Profile pending',
      detail: 'No exported shot pockets are available for this matchup state.',
      lanes: lanesFromPoints(fallbackPoints),
      shotLane: { from: fallbackPoints[2], to: { x: 824, y: 230 } },
      touchPoint: fallbackPoints[1],
      touchPoints: fallbackPoints,
      involvedPpRoles: ['left_flank', 'bumper', 'net_front'],
      stressedPkRoles: ['d1', 'd2'],
    }
  }

  const weakSide = primary.y < 230 ? rightFlank : leftFlank
  const strongSide = primary.y < 230 ? leftFlank : rightFlank
  const finish = { x: clampNumber(primary.x, 500, 778), y: clampNumber(primary.y, 112, 348) }
  let routeCandidates: { x: number; y: number }[][]
  let involvedPpRoles: TacticalSkater['role'][]
  let stressedPkRoles: TacticalSkater['role'][]
  const title = mode === 'mismatch' ? 'Exploit play' : mode === 'pp_attack' ? 'Creation look' : 'Allowed-danger look'
  let detail: string

  if (primary.id === 'netfront') {
    routeCandidates = strongSide === leftFlank
      ? [[point, strongSide, netFront], [point, highWall, highGap, netFront], [point, lowWall, lowGap, netFront]]
      : [[point, strongSide, netFront], [point, lowWall, lowGap, netFront], [point, highWall, highGap, netFront]]
    involvedPpRoles = ['point', strongSide === leftFlank ? 'left_flank' : 'right_flank', 'net_front']
    stressedPkRoles = ['d1', 'd2']
    detail = `${ppTeam} can use a point or flank shot lane to create second contact at the net-front rebound area.`
  } else if (primary.id === 'low_slot') {
    routeCandidates = strongSide === leftFlank
      ? [[strongSide, bumper, lowSlot], [strongSide, highWall, bumper, lowSlot], [strongSide, highMiddle, lowSlot], [strongSide, lowMiddle, lowSlot]]
      : [[strongSide, bumper, lowSlot], [strongSide, lowWall, bumper, lowSlot], [strongSide, lowMiddle, lowSlot], [strongSide, highMiddle, lowSlot]]
    involvedPpRoles = [strongSide === leftFlank ? 'left_flank' : 'right_flank', 'bumper', 'net_front']
    stressedPkRoles = ['f1', 'd1', 'd2']
    detail = `${ppTeam} should work from the half-wall into the bumper or low slot before the PK can collapse.`
  } else if (primary.id === 'bumper') {
    routeCandidates = strongSide === leftFlank
      ? [[point, strongSide, bumper], [point, highWall, bumper], [point, lowWall, bumper]]
      : [[point, strongSide, bumper], [point, lowWall, bumper], [point, highWall, bumper]]
    involvedPpRoles = ['point', strongSide === leftFlank ? 'left_flank' : 'right_flank', 'bumper']
    stressedPkRoles = ['f1', 'f2']
    detail = `${ppTeam} can use the flank-to-bumper touch as the trigger, then shoot before the middle defender resets.`
  } else if (primary.id === 'left_flank' || primary.id === 'right_flank') {
    routeCandidates = [
      [weakSide, point, finish],
      [weakSide, { x: 382, y: weakSide.y }, { x: 382, y: finish.y }, finish],
      [weakSide, { x: 612, y: weakSide.y < 230 ? 100 : 360 }, finish],
    ]
    involvedPpRoles = [weakSide === leftFlank ? 'left_flank' : 'right_flank', 'point', primary.id === 'left_flank' ? 'left_flank' : 'right_flank']
    stressedPkRoles = primary.id === 'left_flank' ? ['f1', 'd1'] : ['f2', 'd2']
    detail = `${ppTeam} can stress the box with a lateral seam into the ${primary.label.toLowerCase()} one-timer lane.`
  } else if (primary.id === 'backdoor') {
    routeCandidates = strongSide === leftFlank
      ? [[strongSide, bumper, backdoor], [strongSide, highWall, highBoardSeam, backdoor], [strongSide, highMiddle, backdoor], [strongSide, lowMiddle, backdoor]]
      : [[strongSide, bumper, backdoor], [strongSide, lowWall, lowBoardSeam, backdoor], [strongSide, lowMiddle, backdoor], [strongSide, highMiddle, backdoor]]
    involvedPpRoles = [strongSide === leftFlank ? 'left_flank' : 'right_flank', 'bumper', 'net_front']
    stressedPkRoles = primary.y < 230 ? ['f2', 'd2'] : ['f1', 'd1']
    detail = `${ppTeam} can pull the PK toward the strong side, then hit the weak-side seam before the low defender recovers.`
  } else {
    routeCandidates = [
      [strongSide, point, finish],
      [strongSide, strongSide === leftFlank ? highWall : lowWall, finish],
      [strongSide, strongSide === leftFlank ? lowWall : highWall, finish],
    ]
    involvedPpRoles = [strongSide === leftFlank ? 'left_flank' : 'right_flank', 'point', 'bumper']
    stressedPkRoles = ['f1', 'f2']
    detail = `${ppTeam} can reset high, force the PK box to expand, and attack the next seam off the point.`
  }
  const routePoints = chooseTacticalRouteCandidate(routeCandidates, net)

  return {
    title,
    detail: mode === 'pk_leak'
      ? `${detail} For ${pkTeam}, this is the allowed-danger pocket the shape has to seal first.`
      : detail,
    lanes: lanesFromPoints(routePoints),
    shotLane: { from: routePoints[routePoints.length - 1], to: net },
    touchPoint: routePoints[Math.min(1, routePoints.length - 1)],
    touchPoints: routePoints,
    involvedPpRoles,
    stressedPkRoles,
  }
}

function lanesFromPoints(points: { x: number; y: number }[]) {
  return points.slice(0, -1).map((point, index) => ({ from: point, to: points[index + 1], kind: index === 0 ? 'carry' as const : 'pass' as const }))
}

const PK_ROUTE_AVOIDANCE = [
  { x: 540, y: 176, radius: 32 },
  { x: 540, y: 284, radius: 32 },
  { x: 686, y: 176, radius: 34 },
  { x: 686, y: 284, radius: 34 },
]

function chooseTacticalRouteCandidate(candidates: { x: number; y: number }[][], shotTarget: { x: number; y: number }) {
  return candidates
    .map((points, index) => ({ points, score: routeCollisionScore(points, shotTarget) + index * 0.01 }))
    .sort((a, b) => a.score - b.score)[0]?.points ?? candidates[0] ?? []
}

function routeCollisionScore(points: { x: number; y: number }[], shotTarget: { x: number; y: number }) {
  const passScore = points.slice(0, -1).reduce((score, point, index) => (
    score + segmentCollisionScore(point, points[index + 1], 1)
  ), 0)
  const shotScore = points.length > 0
    ? segmentCollisionScore(points[points.length - 1], shotTarget, 0.8)
    : 0
  return passScore + shotScore
}

function segmentCollisionScore(from: { x: number; y: number }, to: { x: number; y: number }, weight: number) {
  return PK_ROUTE_AVOIDANCE.reduce((score, defender) => {
    const distance = distancePointToSegment(defender, from, to)
    if (distance >= defender.radius) return score
    return score + (defender.radius - distance + 20) * weight
  }, 0)
}

function distancePointToSegment(
  point: { x: number; y: number },
  from: { x: number; y: number },
  to: { x: number; y: number },
) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  if (dx === 0 && dy === 0) return Math.hypot(point.x - from.x, point.y - from.y)
  const t = clampNumber(((point.x - from.x) * dx + (point.y - from.y) * dy) / (dx * dx + dy * dy), 0, 1)
  return Math.hypot(point.x - (from.x + t * dx), point.y - (from.y + t * dy))
}

function buildTacticalSkaters(route: TacticalRoute): TacticalSkater[] {
  const activePp = new Set(route.involvedPpRoles)
  const activePk = new Set(route.stressedPkRoles)
  const rawSkaters: TacticalSkater[] = [
    { label: 'P', role: 'point', side: 'pp', x: 292, y: 230, active: activePp.has('point') },
    { label: 'LF', role: 'left_flank', side: 'pp', x: 480, y: 126, active: activePp.has('left_flank') },
    { label: 'RF', role: 'right_flank', side: 'pp', x: 480, y: 334, active: activePp.has('right_flank') },
    { label: 'B', role: 'bumper', side: 'pp', x: 610, y: 230, active: activePp.has('bumper') },
    { label: 'NF', role: 'net_front', side: 'pp', x: 758, y: 230, active: activePp.has('net_front') },
    { label: 'F1', role: 'f1', side: 'pk', x: 540, y: 176, active: activePk.has('f1') },
    { label: 'F2', role: 'f2', side: 'pk', x: 540, y: 284, active: activePk.has('f2') },
    { label: 'D1', role: 'd1', side: 'pk', x: 686, y: 176, active: activePk.has('d1') },
    { label: 'D2', role: 'd2', side: 'pk', x: 686, y: 284, active: activePk.has('d2') },
  ]
  return enforceSkaterSpacing(rawSkaters)
}

function enforcePocketSpacing(pockets: TacticalPocket[], primary?: TacticalPocket) {
  if (!primary) return pockets
  return pockets.map((pocket, index) => {
    const dx = pocket.x - primary.x
    const dy = pocket.y - primary.y
    const distance = Math.hypot(dx, dy)
    if (distance >= 72) return pocket
    const angle = Math.atan2(dy || (index % 2 === 0 ? -1 : 1), dx || -1)
    return {
      ...pocket,
      x: clampNumber(primary.x + Math.cos(angle) * 72, 170, 790),
      y: clampNumber(primary.y + Math.sin(angle) * 72, 92, 368),
    }
  })
}

function enforceSkaterSpacing(skaters: TacticalSkater[]) {
  const output: TacticalSkater[] = []
  skaters.forEach((skater) => {
    let x = skater.x
    let y = skater.y
    output.forEach((other) => {
      const distance = Math.hypot(x - other.x, y - other.y)
      if (distance < 62) {
        y += y >= other.y ? 38 : -38
        x += x >= other.x ? 26 : -26
      }
    })
    output.push({ ...skater, x: clampNumber(x, 176, 790), y: clampNumber(y, 92, 368) })
  })
  return output
}

function weightedAverage(items: { value: number; weight: number }[]) {
  const totalWeight = items.reduce((sum, item) => sum + Math.max(0, item.weight), 0)
  if (!totalWeight) return items[0]?.value ?? 0
  return items.reduce((sum, item) => sum + item.value * Math.max(0, item.weight), 0) / totalWeight
}

function toBoardPoint(bin: TeamShotMapBin) {
  const rinkX = typeof bin.rink_x === 'number' ? bin.rink_x : (bin.x_bin / 16) * 100
  const rinkY = typeof bin.rink_y === 'number' ? bin.rink_y : ((bin.y_bin / 12) * 85) - 42.5
  return {
    x: 132 + (Math.max(0, Math.min(100, rinkX)) / 100) * (814 - 132),
    y: 230 + (Math.max(-42.5, Math.min(42.5, rinkY)) / 42.5) * 176,
    weight: Math.max(bin.xg_share ?? 0, bin.shot_share ?? 0, 0.02),
    bin,
  }
}

function clampNumber(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function PlayerPassportPanel({ profiles }: { profiles: PlayerTagProfile[] }) {
  return (
    <section className="player-passport-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Player passports</h2>
          <p>Selected-season PK tags, with trust labels, plain-English reads, and evidence notes kept behind details.</p>
        </div>
        <span>{profiles.length} shown</span>
      </div>
      {profiles.length === 0 && (
        <div className="empty-panel-note">Refresh MoneyPuck v2 to show player passports.</div>
      )}
      <div className="player-passport-grid">
        {profiles.map((profile) => (
          <PlayerPassportCard key={`${profile.season}-${profile.player_id}`} profile={profile} />
        ))}
      </div>
    </section>
  )
}

function PlayerPassportCard({ profile }: { profile: PlayerTagProfile }) {
  const primaryTags = profile.tags
    .filter((tag) => tag.category !== 'trust')
    .slice(0, 4)
  const detailTags = profile.tags.slice(4, 8)
  const strength = profile.top_strengths[0] ?? profile.tags.find((tag) => tag.category === 'strength' || tag.category === 'style')
  const risk = profile.main_risks[0] ?? profile.tags.find((tag) => tag.category === 'risk')
  const archetype = strength?.label ?? primaryTags[0]?.label ?? 'Role profile pending'
  const sample = sampleTrustForProfile(profile)
  const trustLevel = sample.trustLevel
  const supportingSignals = profile.supporting_signal_count ?? primaryTags.length
  const scoutingRead = passportScoutingRead(profile, sample, archetype, strength, risk)

  return (
    <section className={`player-passport-card trust-${trustLevel}`}>
      <div className="passport-topline">
        <div>
          <strong>{profile.name}</strong>
          <em>{profile.position} / {profile.teams} / {formatMinutes(profile.ice_time)}</em>
        </div>
        <div className="passport-status">
          <span>{sample.label}</span>
          <b>{archetype}</b>
        </div>
      </div>
      <p className="passport-trust-note">{sample.sentence}</p>
      <p className="passport-scout-read">{scoutingRead}</p>
      <div className="passport-metrics">
        <div>
          <span>Adjusted impact</span>
          <b>{formatSignedDecimal(profile.true_talent_pk_impact_per60, 2)}</b>
        </div>
        <div>
          <span>Signals</span>
          <b>{supportingSignals} tags</b>
        </div>
      </div>
      <div className="passport-read-row">
        <div>
          <span>Strength</span>
          <b>{strength?.label ?? 'No clear strength tag'}</b>
        </div>
        <div>
          <span>Risk</span>
          <b>{risk?.label ?? 'No major risk flagged'}</b>
        </div>
      </div>
      <div className="passport-tag-list">
        {primaryTags.map((tag) => (
          <PlayerTagBadge key={`${profile.player_id}-${tag.tag_id}`} tag={tag} />
        ))}
      </div>
      {profile.tags.length > 0 && (
        <details className="passport-details">
          <summary>Evidence notes</summary>
          <p>{sample.sentence}</p>
          <p>{profile.summary_sentence}</p>
          <TagReasonList title={detailTags.length > 0 ? 'Full tag notes' : 'Tag notes'} tags={profile.tags.slice(0, 8)} />
        </details>
      )}
    </section>
  )
}

function PlayerTagBadge({ tag }: { tag: PlayerTag }) {
  const strength = tag.tag_strength ?? tagStrengthFromPercentile(tag)
  const sampleConfidence = tag.sample_confidence ?? tag.confidence
  return (
    <span className={`player-tag tag-${tag.category}`}>
      {tag.label}
      <small>{strength} / {sampleConfidence} sample</small>
    </span>
  )
}

function sampleTrustForProfile(profile: PlayerTagProfile) {
  const minutes = Math.round((profile.ice_time ?? 0) / 60)
  const supportingSignals = profile.supporting_signal_count ?? profile.tags.filter((tag) => tag.category !== 'trust').length
  if (profile.sample_trust && profile.sample_trust_label && profile.sample_trust_sentence) {
    return {
      label: profile.sample_trust_label,
      sentence: profile.sample_trust_sentence,
      trustLevel: profile.trust_level,
    }
  }
  if (minutes < 40) {
    return {
      label: 'Low sample',
      sentence: `Low sample: only ${minutes} PK minutes, treat as directional.`,
      trustLevel: 'low' as const,
    }
  }
  if (minutes < 80) {
    return {
      label: 'Limited sample',
      sentence: `Limited sample: ${minutes} PK minutes and ${supportingSignals} supporting tag events.`,
      trustLevel: 'low' as const,
    }
  }
  if (minutes < 150) {
    return {
      label: 'Medium sample',
      sentence: `Medium signal: ${minutes} PK minutes and ${supportingSignals} supporting tag events.`,
      trustLevel: 'medium' as const,
    }
  }
  return {
    label: 'Strong sample',
    sentence: `Strong sample: ${minutes} PK minutes and ${supportingSignals} supporting tag events.`,
    trustLevel: profile.trust_level === 'high' ? 'high' as const : 'medium' as const,
  }
}

function passportScoutingRead(
  profile: PlayerTagProfile,
  sample: ReturnType<typeof sampleTrustForProfile>,
  archetype: string,
  strength?: PlayerTag,
  risk?: PlayerTag,
) {
  const minutes = Math.round((profile.ice_time ?? 0) / 60)
  const lastName = profile.name.split(' ').slice(-1)[0] || profile.name
  if (minutes < 40 || sample.trustLevel === 'low' && sample.label.toLowerCase().includes('low')) {
    return `Directional profile only; ${minutes} PK minutes is too thin to treat as stable.`
  }

  const role = hockeyPhrase(archetype)
  const strengthLabel = strength?.label ? hockeyPhrase(strength.label) : ''
  const strengthText = strengthLabel && strengthLabel !== role ? ` with ${strengthLabel}` : ''
  const riskText = risk?.label ? `; watch ${hockeyPhrase(risk.label)}` : ''
  const sampleText = sample.label.toLowerCase()
  return `${lastName} profiles as a usable ${role}${strengthText}, backed by a ${sampleText}${riskText}.`
}

function hockeyPhrase(value: string) {
  return value
    .toLowerCase()
    .replace(/\bpk\b/g, 'PK')
    .replace(/\bpp\b/g, 'PP')
    .replace(/\bxg\b/g, 'xG')
}

function tagStrengthFromPercentile(tag: PlayerTag) {
  if (typeof tag.league_percentile !== 'number') return 'medium'
  const score = tag.higher_is_better ? tag.league_percentile : 1 - tag.league_percentile
  if (score >= 0.8) return 'strong'
  if (score >= 0.6) return 'medium'
  return 'weak'
}

function TagReasonList({ title, tags }: { title: string; tags: PlayerTag[] }) {
  if (tags.length === 0) {
    return null
  }

  return (
    <div className="tag-reason-list">
      <h3>{title}</h3>
      {tags.map((tag) => (
        <div className="tag-reason" key={`${title}-${tag.tag_id}`}>
          <strong>{tag.label}</strong>
          <span>{tag.reason}</span>
          <em>{tag.sample_size_note}</em>
        </div>
      ))}
    </div>
  )
}

function TalentPanel({
  title,
  body,
  rows,
  muted = false,
}: {
  title: string
  body: string
  rows: PkTalentRow[]
  muted?: boolean
}) {
  return (
    <article className={`scouting-panel talent-panel${muted ? ' muted-talent' : ''}`}>
      <h2>{title}</h2>
      <p>{body}</p>
      {rows.length === 0 && (
        <div className="empty-panel-note">Refresh MoneyPuck v2 to show this season.</div>
      )}
      {rows.map((row) => (
        <div className="talent-row" key={`${title}-${row.season}-${row.player_id}`}>
          <div>
            <strong>{row.name}</strong>
            <em>{row.position} / {row.teams} / {formatMinutes(row.ice_time)} / {row.trust_label}</em>
            <span>
              90% {formatImpactRange(row.impact_lower_90, row.impact_upper_90, 2)}
            </span>
          </div>
          <b>{formatSignedDecimal(row.true_talent_pk_impact_per60, 2)}</b>
        </div>
      ))}
    </article>
  )
}

function SimilarityPanel({ groups }: { groups: PlayerSimilarityGroup[] }) {
  return (
    <article className="scouting-panel similarity-panel">
      <h2>Similar player finder</h2>
      <p>Role and outcome matches from PK minutes, offense, xGA, blocks, penalties, and adjusted impact.</p>
      {groups.length === 0 && (
        <div className="empty-panel-note">Refresh MoneyPuck v2 to show similar-player groups.</div>
      )}
      {groups.map((group) => (
        <div className="similarity-group" key={`${group.season}-${group.player_id}`}>
          <div className="similarity-anchor">
            <strong>{group.name}</strong>
            <em>{group.position} / {group.teams} / {formatSignedDecimal(group.true_talent_pk_impact_per60, 2)}</em>
          </div>
          <div className="similarity-matches">
            {group.matches.slice(0, 3).map((match) => (
              <span key={`${group.player_id}-${match.player_id}`}>
                {match.name} <b>{formatDecimal(match.similarity_score, 0)}</b>
              </span>
            ))}
          </div>
        </div>
      ))}
    </article>
  )
}

function formatSeasonLabel(season: number) {
  return `${season}-${String((season + 1) % 100).padStart(2, '0')}`
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
            The ASP.NET API reads the latest analytics JSON and shapes it for the site, so the frontend can show
            real model output instead of hardcoded numbers.
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
          <span>latest analytics run</span>
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
      <span>{apiState === 'live' ? 'Live model data:' : apiState === 'snapshot' ? 'Published model snapshot:' : 'API offline:'}</span>
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
