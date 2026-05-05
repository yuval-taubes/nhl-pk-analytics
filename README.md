# nhl-pk-analytics

Here's a README.md you can drop in your project root:

```markdown
# NHL Penalty Kill Analytics

A full-stack analytics application for NHL penalty kill tactical analysis.

## Stack

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 17 |
| Data Pipeline | .NET 8 Console App |
| Analytics | Python (scikit-learn, DoWhy, statsmodels) |
| API | ASP.NET Core Web API |
| Frontend | React + TypeScript + Tailwind |

## Setup

### Prerequisites
- .NET 8 SDK
- Python 3.11+
- Node.js 20+
- PostgreSQL 17

### Database
```bash
# Create database
createdb nhl_pk_analytics
```

### Data Pipeline
```bash
cd Data_ingestion/NhlPkIngest
cp appsettings.template.json appsettings.json
# Edit appsettings.json with your PostgreSQL connection string
dotnet run
```

### Python Analytics
```bash
cd analytics
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### API + Frontend
```bash
cd api
dotnet run

cd frontend
npm install
npm run dev
```

## Status

- [x] PostgreSQL schema
- [ ] Data pipeline (in progress - fixing schedule API parsing)
- [ ] xG model
- [ ] Causal analysis models (5 tactical models)
- [ ] Web API
- [ ] Frontend dashboard

## Data Sources

NHL API endpoints:
- Play-by-play: `https://api.nhle.com/stats/rest/en/game/{gameId}/play-by-play`
- Schedule: `https://api-web.nhle.com/v1/schedule/{date}`

Seasons: 2022-23, 2023-24, 2024-25
```

---

Just change `YOUR_USERNAME` in the git remote command to your actual GitHub username, and push.
