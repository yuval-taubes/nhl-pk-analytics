import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import '@xyflow/react/dist/style.css'

import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import {
  Activity,
  BarChart3,
  Database,
  GitBranch,
  Goal,
  Layers3,
  Ruler,
  Shield,
} from 'lucide-react'
import { Badge, Button, Col, Container, Form, Nav, Row, Table } from 'react-bootstrap'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { API_BASE_URL } from './api/client'
import { clusters, metrics, shotPoints, trend } from './data/dashboard'

const flowNodes: Node[] = [
  { id: 'entry', position: { x: 0, y: 120 }, data: { label: 'ENTRY / FACEOFF' } },
  { id: 'setup', position: { x: 190, y: 60 }, data: { label: 'OZ SETUP' } },
  { id: 'turnover', position: { x: 190, y: 190 }, data: { label: 'FAILED CLEAR' } },
  { id: 'shot', position: { x: 390, y: 120 }, data: { label: 'SHOT / REBOUND' } },
  { id: 'goal', position: { x: 600, y: 120 }, data: { label: 'GOAL AGAINST' } },
]

const flowEdges: Edge[] = [
  { id: 'e1', source: 'entry', target: 'setup', animated: true },
  { id: 'e2', source: 'entry', target: 'turnover' },
  { id: 'e3', source: 'setup', target: 'shot', animated: true },
  { id: 'e4', source: 'turnover', target: 'shot', animated: true },
  { id: 'e5', source: 'shot', target: 'goal', animated: true },
]

function App() {
  return (
    <div className="app-shell d-flex flex-column flex-lg-row">
      <aside className="sidebar p-3 p-lg-4">
        <div className="d-flex align-items-center gap-3 mb-4">
          <div className="brand-mark d-flex align-items-center justify-content-center">
            <Shield size={24} />
          </div>
          <div>
            <div className="fw-semibold">NHL PK Analytics</div>
            <div className="small label-muted">Special teams workstation</div>
          </div>
        </div>

        <Nav className="flex-lg-column gap-2">
          {[
            ['Overview', Activity],
            ['Team Profile', Shield],
            ['Possessions', Ruler],
            ['Sequences', GitBranch],
            ['Model Diagnostics', Database],
          ].map(([label, Icon], index) => (
            <Button
              className={`nav-button d-flex align-items-center gap-2 px-3 py-2 ${index === 0 ? 'active' : ''}`}
              key={String(label)}
            >
              <Icon size={18} />
              <span>{String(label)}</span>
            </Button>
          ))}
        </Nav>

        <div className="panel p-3 mt-4">
          <div className="small text-uppercase label-muted">API target</div>
          <code className="small d-block text-info text-wrap mt-2">{API_BASE_URL}</code>
        </div>
      </aside>

      <main className="work-area flex-grow-1">
        <div className="topbar sticky-top px-3 px-xl-4 py-3">
          <div className="d-flex flex-column flex-xl-row gap-3 align-items-xl-center justify-content-between">
            <div>
              <h1 className="h3 mb-1">Penalty Kill Command Center</h1>
              <div className="label-muted">Monitor tactical breakdowns, xG pressure, and goal-against sequences.</div>
            </div>
            <div className="d-flex flex-wrap gap-2">
              <Form.Select aria-label="Team filter">
                <option>All teams</option>
                <option>Winnipeg Jets</option>
                <option>Carolina Hurricanes</option>
              </Form.Select>
              <Form.Select aria-label="Strength filter">
                <option>4v5 and 3v5</option>
                <option>4v5 only</option>
                <option>3v5 only</option>
              </Form.Select>
              <Form.Select aria-label="Season filter">
                <option>Last 3 seasons</option>
                <option>2025-26</option>
                <option>2024-25</option>
              </Form.Select>
            </div>
          </div>
        </div>

        <Container fluid className="p-3 p-xl-4">
          <Row className="g-3 mb-3">
            {metrics.map((metric) => (
              <Col sm={6} xl={3} key={metric.label}>
                <section className="panel metric-panel p-3">
                  <div className="d-flex align-items-center justify-content-between mb-3">
                    <span className="label-muted small text-uppercase">{metric.label}</span>
                    <Badge className="badge-soft" bg="transparent">
                      Live
                    </Badge>
                  </div>
                  <div className="metric-value fw-semibold">{metric.value}</div>
                  <div className="d-flex align-items-center gap-2 mt-2 small">
                    <span className={metric.intent === 'down' ? 'trend-down' : metric.intent === 'up' ? 'trend-up' : 'label-muted'}>
                      {metric.delta}
                    </span>
                    <span className="label-muted">{metric.helper}</span>
                  </div>
                </section>
              </Col>
            ))}
          </Row>

          <Row className="g-3">
            <Col xl={7}>
              <section className="panel p-3 h-100">
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <div>
                    <h2 className="h5 mb-1">PK Pressure Trend</h2>
                    <div className="small label-muted">xGA, clears, and entries allowed by game window</div>
                  </div>
                  <BarChart3 className="text-info" size={22} />
                </div>
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trend}>
                      <CartesianGrid stroke="#263546" strokeDasharray="3 3" />
                      <XAxis dataKey="game" stroke="#91a2b5" />
                      <YAxis stroke="#91a2b5" />
                      <Tooltip
                        contentStyle={{
                          background: '#101821',
                          border: '1px solid #263546',
                          borderRadius: 8,
                          color: '#e7eef7',
                        }}
                      />
                      <Line type="monotone" dataKey="xga" stroke="#ff5d6c" strokeWidth={3} dot={false} />
                      <Line type="monotone" dataKey="entries" stroke="#ffc857" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="clears" stroke="#39d98a" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </Col>

            <Col xl={5}>
              <section className="panel p-3 h-100">
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <div>
                    <h2 className="h5 mb-1">Shot Danger Rink</h2>
                    <div className="small label-muted">Goal-against looks weighted by xG</div>
                  </div>
                  <Goal className="text-danger" size={22} />
                </div>
                <div className="rink">
                  {shotPoints.map((shot) => (
                    <span
                      aria-label={`Shot xG ${shot.xg}`}
                      className="shot-dot"
                      key={`${shot.x}-${shot.y}`}
                      style={{
                        left: `${shot.x}%`,
                        top: `${shot.y}%`,
                        transform: `scale(${0.75 + shot.xg * 1.9})`,
                      }}
                    />
                  ))}
                </div>
              </section>
            </Col>

            <Col xl={7}>
              <section className="panel p-3">
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <div>
                    <h2 className="h5 mb-1">Goal-Against Sequence Flow</h2>
                    <div className="small label-muted">Placeholder flow until clustered sequence data lands</div>
                  </div>
                  <Layers3 className="text-info" size={22} />
                </div>
                <div className="sequence-flow">
                  <ReactFlow nodes={flowNodes} edges={flowEdges} fitView proOptions={{ hideAttribution: true }}>
                    <Background color="#263546" gap={18} />
                    <Controls />
                  </ReactFlow>
                </div>
              </section>
            </Col>

            <Col xl={5}>
              <section className="panel p-3">
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <div>
                    <h2 className="h5 mb-1">Top Breakdown Clusters</h2>
                    <div className="small label-muted">Manual labels can override model suggestions later</div>
                  </div>
                  <GitBranch className="text-info" size={22} />
                </div>
                <Table responsive borderless hover variant="dark" className="align-middle mb-0">
                  <thead>
                    <tr className="label-muted">
                      <th>Cluster</th>
                      <th>Share</th>
                      <th>Origin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clusters.map((cluster) => (
                      <tr key={cluster.id}>
                        <td>
                          <div className="fw-semibold">{cluster.label}</div>
                          <div className="small label-muted">{cluster.sample}</div>
                        </td>
                        <td>{cluster.share}%</td>
                        <td>{cluster.origin}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </section>
            </Col>
          </Row>
        </Container>
      </main>
    </div>
  )
}

export default App
