export type Metric = {
  label: string
  value: string
  delta: string
  intent: 'up' | 'down' | 'flat'
  helper: string
}

export type TrendPoint = {
  game: string
  xga: number
  clears: number
  entries: number
}

export type ClusterSummary = {
  id: number
  label: string
  share: number
  sample: string
  origin: string
}

export type ShotPoint = {
  x: number
  y: number
  xg: number
}

export const metrics: Metric[] = [
  {
    label: 'PK xGA / 60',
    value: '6.42',
    delta: '+0.38',
    intent: 'up',
    helper: 'Last 10 games vs season baseline',
  },
  {
    label: 'Clear Rate',
    value: '71.8%',
    delta: '-3.1%',
    intent: 'up',
    helper: 'Successful exits per DZ recovery',
  },
  {
    label: 'Controlled Entries Against',
    value: '18.4',
    delta: '-2.0',
    intent: 'down',
    helper: 'Allowed per 60 PK minutes',
  },
  {
    label: 'GA Sequence Clusters',
    value: '7',
    delta: 'stable',
    intent: 'flat',
    helper: 'Patterns above minimum support',
  },
]

export const trend: TrendPoint[] = [
  { game: 'G1', xga: 4.8, clears: 76, entries: 14 },
  { game: 'G2', xga: 5.3, clears: 72, entries: 16 },
  { game: 'G3', xga: 7.1, clears: 68, entries: 21 },
  { game: 'G4', xga: 6.4, clears: 70, entries: 18 },
  { game: 'G5', xga: 5.8, clears: 74, entries: 15 },
  { game: 'G6', xga: 8.2, clears: 64, entries: 24 },
  { game: 'G7', xga: 6.7, clears: 69, entries: 19 },
]

export const clusters: ClusterSummary[] = [
  {
    id: 1,
    label: 'Failed clear to point rotation',
    share: 26,
    sample: 'TURNOVER_DZ -> SHOT_OZ -> BLOCKED_OZ -> GOAL_OZ',
    origin: 'DZ turnover',
  },
  {
    id: 2,
    label: 'Faceoff loss, low-to-high setup',
    share: 19,
    sample: 'FACEOFF_DZ -> SHOT_OZ -> REBOUND_OZ -> GOAL_OZ',
    origin: 'DZ faceoff',
  },
  {
    id: 3,
    label: 'Controlled entry rush chance',
    share: 14,
    sample: 'ENTRY_CONTROLLED_NZ -> SHOT_SLOT -> GOAL_OZ',
    origin: 'NZ entry',
  },
]

export const shotPoints: ShotPoint[] = [
  { x: 78, y: 48, xg: 0.22 },
  { x: 82, y: 34, xg: 0.18 },
  { x: 72, y: 61, xg: 0.08 },
  { x: 86, y: 43, xg: 0.31 },
  { x: 66, y: 23, xg: 0.05 },
  { x: 90, y: 52, xg: 0.42 },
]
