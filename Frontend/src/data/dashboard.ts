export type Metric = {
  label: string
  value: string
  delta: string
  intent: 'up' | 'down' | 'flat'
  helper: string
}

export type LatestRun = {
  startedAt: string
  completedAt: string
  fileName: string
}

export type Takeaway = {
  title: string
  value: string
  detail: string
  tone: 'good' | 'bad' | 'warn' | 'neutral'
}

export type ForayRow = {
  foray_type: string
  n: number
  avg_pk_xg_benefit: number
  avg_counter_xg_risk: number
  net_xg: number
  counterattack_rate: number
  shot_rate: number
}

export type EntryRow = {
  entry_type: string
  n_entries: number
  clear_rate: number
  goal_rate: number
  avg_xga_per_entry: number
  xga_per_60_observed_duration: number
}

export type FaceoffRow = {
  outcome: string
  n: number
  avg_xga_20: number
  shot_rate_20: number
}

export type PlayerLeader = {
  full_name: string
  position: string
  season?: string
  defensive_events?: number
  tagged_events?: number
  faceoffs?: number
  blocked_shots?: number
  positive_event_rate?: number
  disruption_rate?: number
  faceoff_value_added?: number
  high_danger_block_rate?: number
}

export type PlayerLeaders = {
  forwards: PlayerLeader[]
  defensemen: PlayerLeader[]
  centers: PlayerLeader[]
  shotBlockers: PlayerLeader[]
}

export type ModelCard = {
  key: string
  name: string
  outputFile: string
  computedAt: string
  sample?: Record<string, string | null>
}

export type AnalyticsDashboard = {
  latestRun: LatestRun
  metrics: Metric[]
  takeaways: Takeaway[]
  forayRows: ForayRow[]
  entryRows: EntryRow[]
  faceoffRows: FaceoffRow[]
  playerLeaders: PlayerLeaders
  modelCards: ModelCard[]
  caveats: string[]
}

export type TrendPoint = {
  game: string
  xga: number
  clears: number
  entries: number
}

export type ShotPoint = {
  x: number
  y: number
  xg: number
}

export const fallbackDashboard: AnalyticsDashboard = {
  latestRun: {
    startedAt: '',
    completedAt: '',
    fileName: 'API offline - sample values',
  },
  metrics: [
    {
      label: 'DZ Faceoff xGA Saved',
      value: '-0.027',
      delta: 'next 20s',
      intent: 'down',
      helper: 'Matched PK win vs loss effect',
    },
    {
      label: 'OZ Faceoff EV',
      value: '-0.024',
      delta: 'net xG',
      intent: 'up',
      helper: 'Forcing whistle/OZ faceoff',
    },
    {
      label: 'PK OZ Forays',
      value: '1,224',
      delta: 'sample',
      intent: 'flat',
      helper: 'Short-handed OZ possessions',
    },
    {
      label: 'Player Scouting Rows',
      value: '1,479',
      delta: 'exported',
      intent: 'flat',
      helper: 'Event-participant metrics',
    },
  ],
  takeaways: [
    {
      title: 'DZ PK faceoff wins sharply reduce danger',
      value: '-0.027',
      detail: 'Estimated xGA change in the next 20 seconds for a PK faceoff win relative to a matched loss.',
      tone: 'good',
    },
    {
      title: 'OZ whistle is not a free reset',
      value: '-0.015',
      detail: 'Maintain-play net xG was +0.001 over the same short window.',
      tone: 'bad',
    },
    {
      title: 'Dump-ins were more dangerous in this run',
      value: '0.189',
      detail: 'Controlled entries averaged 0.110 xGA per entry.',
      tone: 'warn',
    },
  ],
  forayRows: [
    { foray_type: 'controlled_foray', n: 31, avg_pk_xg_benefit: 0.056, avg_counter_xg_risk: 0.003, net_xg: 0.053, counterattack_rate: 0.065, shot_rate: 1 },
    { foray_type: 'dump_in_foray', n: 19, avg_pk_xg_benefit: 0.177, avg_counter_xg_risk: 0.001, net_xg: 0.176, counterattack_rate: 0.053, shot_rate: 1 },
    { foray_type: 'oz_faceoff_foray', n: 882, avg_pk_xg_benefit: 0.073, avg_counter_xg_risk: 0.007, net_xg: 0.066, counterattack_rate: 0.068, shot_rate: 1 },
    { foray_type: 'turnover_foray', n: 292, avg_pk_xg_benefit: 0.097, avg_counter_xg_risk: 0.003, net_xg: 0.094, counterattack_rate: 0.041, shot_rate: 1 },
  ],
  entryRows: [
    { entry_type: 'CONTROLLED', n_entries: 151, clear_rate: 0.066, goal_rate: 0.079, avg_xga_per_entry: 0.110, xga_per_60_observed_duration: 0.187 },
    { entry_type: 'DUMP_IN', n_entries: 234, clear_rate: 0.081, goal_rate: 0.137, avg_xga_per_entry: 0.189, xga_per_60_observed_duration: 0.376 },
  ],
  faceoffRows: [
    { outcome: 'LOSS', n: 9606, avg_xga_20: 0.049, shot_rate_20: 0.595 },
    { outcome: 'WIN', n: 8059, avg_xga_20: 0.021, shot_rate_20: 0.259 },
  ],
  playerLeaders: {
    forwards: [
      { full_name: 'Aleksander Barkov', position: 'C', defensive_events: 73, positive_event_rate: 0.945 },
      { full_name: 'Alex Tuch', position: 'R', defensive_events: 100, positive_event_rate: 0.94 },
      { full_name: 'Chandler Stephenson', position: 'C', defensive_events: 56, positive_event_rate: 0.929 },
    ],
    defensemen: [
      { full_name: 'Chad Ruhwedel', position: 'D', defensive_events: 66, disruption_rate: 0.97 },
      { full_name: 'Noah Juulsen', position: 'D', defensive_events: 80, disruption_rate: 0.963 },
      { full_name: 'Alexandre Carrier', position: 'D', defensive_events: 115, disruption_rate: 0.939 },
    ],
    centers: [
      { full_name: 'Kevin Stenlund', position: 'C', season: '20242025', faceoffs: 154, faceoff_value_added: 0.0128 },
      { full_name: 'Colton Sissons', position: 'C', season: '20222023', faceoffs: 215, faceoff_value_added: 0.0087 },
      { full_name: 'Patrice Bergeron', position: 'C', season: '20222023', faceoffs: 148, faceoff_value_added: 0.0078 },
    ],
    shotBlockers: [
      { full_name: 'Ryan McDonagh', position: 'D', blocked_shots: 99, high_danger_block_rate: 0.98 },
      { full_name: 'MacKenzie Weegar', position: 'D', blocked_shots: 99, high_danger_block_rate: 0.97 },
      { full_name: 'Rasmus Andersson', position: 'D', blocked_shots: 79, high_danger_block_rate: 0.962 },
    ],
  },
  modelCards: [],
  caveats: [
    'Player tables are tagged event-participant scouting, not true on-ice impact.',
    'Forecheck shape, gap control, and net-front coverage need shift/tracking data.',
    'Generated analytics JSON is a local artifact; rerun the Python models to refresh it.',
  ],
}

export const trend: TrendPoint[] = [
  { game: 'G1', xga: 4.8, clears: 76, entries: 14 },
  { game: 'G2', xga: 5.3, clears: 72, entries: 16 },
  { game: 'G3', xga: 7.1, clears: 68, entries: 21 },
  { game: 'G4', xga: 6.4, clears: 70, entries: 18 },
  { game: 'G5', xga: 5.8, clears: 74, entries: 15 },
  { game: 'G6', xga: 8.2, clears: 64, entries: 24 },
  { game: 'G7', xga: 6.7, clears: 69, entries: 19 },
]

export const shotPoints: ShotPoint[] = [
  { x: 78, y: 48, xg: 0.22 },
  { x: 82, y: 34, xg: 0.18 },
  { x: 72, y: 61, xg: 0.08 },
  { x: 86, y: 43, xg: 0.31 },
  { x: 66, y: 23, xg: 0.05 },
  { x: 90, y: 52, xg: 0.42 },
]
