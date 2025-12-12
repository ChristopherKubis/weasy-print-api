# WeasyPrint API - React Monitoring Dashboard

React-based real-time monitoring dashboard for the WeasyPrint API.

## Features

- Real-time CPU and Memory monitoring
- API statistics (total requests, successful/failed conversions)
- Interactive charts with historical data
- Responsive design
- Auto-refresh every 2 seconds

## Running with Docker

The frontend is included in the main `docker-compose.yml`. Just run:

```bash
cd ..
docker-compose up --build
```

Access the dashboard at: http://localhost:3000

## Local Development

```bash
npm install
npm start
```

The app will open at http://localhost:3000 and proxy API requests to http://localhost:8000

## Technologies

- React 18
- Recharts (for data visualization)
- Axios (for API calls)
- Nginx (for production serving)
