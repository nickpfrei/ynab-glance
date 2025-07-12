# YNAB Glance Integration

A clean, native integration between [YNAB (You Need A Budget)](https://www.ynab.com/) and [Glance](https://github.com/glanceapp/glance) dashboard that displays your top spending categories with amounts and percentages.

## Features

- **Real-time spending data** from YNAB API
- **Top 5 spending categories** grouped by category group
- **Clean, native styling** that matches your Glance dashboard theme
- **US number formatting** with comma separators (e.g., $4,554)
- **Intelligent caching** (15-minute cache) for fast response times
- **Dockerized service** for easy deployment
- **Last 30 days** spending analysis

## Demo

The widget displays your spending data in a clean, three-column format that seamlessly integrates with your Glance dashboard's native styling:

![YNAB Spending Widget](img/YNAB%20Spending%20Widget.jpg)

**Widget Features:**
- **Category Group** (left): Your YNAB category groups
- **Amount** (right): Dollar amount spent with comma formatting
- **Percentage** (right, smaller): Percentage of total spending
- **Native Glance styling**: No custom backgrounds, matches your dashboard theme

Example data structure:
```
🏠 Housing & Utilities         $2,150  35.2%
🛒 Groceries & Food           $1,325  21.7%
🚗 Transportation             $890    14.6%
💊 Healthcare                 $675    11.0%
🎬 Entertainment              $465    7.6%
```

## Prerequisites

- Docker and Docker Compose
- YNAB account with API access
- Glance dashboard running in Docker
- YNAB API token (Personal Access Token)

## Setup

### 1. Get Your YNAB API Token

1. Go to [YNAB Account Settings](https://app.ynab.com/settings/developer)
2. Generate a new Personal Access Token
3. Copy the token (you'll need it for the next step)

### 2. Configure Environment Variables

1. Copy the environment template:
   ```bash
   cp env_template.txt .env
   ```

2. Edit `.env` and add your YNAB API token:
   ```bash
   YNAB_API_TOKEN=your_api_token_here
   # YNAB_BUDGET_ID=optional_specific_budget_id
   ```

   **Note**: If you have multiple budgets, you can specify a particular budget ID. Otherwise, it will use your first budget.

### 3. Build and Run the Service

1. Build and start the Docker container:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

2. Verify the service is running:
   ```bash
   curl http://localhost:5001/health
   ```

3. Test the spending endpoint:
   ```bash
   curl http://localhost:5001/glance
   ```

### 4. Configure Glance Widget

Add the following widget to your Glance `home.yml` configuration:

```yaml
- type: custom-api
  title: YNAB Spending
  url: http://host.docker.internal:5001/glance
  cache: 60m
  request-timeout: 10
  template: |
    {{- if .JSON.Exists "error" }}
      <div>Error: {{ .JSON.String "error" }}</div>
    {{- else }}
      {{- range .JSON.Array "categories" }}
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div style="flex: 1;">
          <div>{{ .String "category_group" }}</div>
        </div>
        <div style="text-align: right;">
          <div>${{ .String "amount_formatted" }}</div>
          <div style="font-size: 0.8em; opacity: 0.7;">{{ printf "%.1f" (.Float "percentage") }}%</div>
        </div>
      </div>
      {{- end }}
    {{- end }}
```

### 5. Restart Glance

```bash
docker restart glance
```

## Service Endpoints

The YNAB service provides several endpoints:

- **`/glance`** - JSON data optimized for Glance widget
- **`/api/spending`** - Raw JSON spending data
- **`/widget`** - Standalone HTML widget
- **`/health`** - Health check with cache status
- **`/cache/clear`** - Clear the data cache

## Configuration

### Docker Compose

The service runs on port 5001 by default. You can modify `docker-compose.yml` to change the port or other settings.

### Caching

The service caches YNAB API responses for 15 minutes to ensure fast response times. The cache automatically refreshes when data expires.

### Network Configuration

- **For Docker-based Glance**: Use `host.docker.internal:5001` as the URL
- **For native Glance**: Use `localhost:5001` as the URL

## File Structure

```
├── ynab_service.py          # Main Flask service
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile               # Docker image configuration
├── requirements.txt         # Python dependencies
├── env_template.txt         # Environment variable template
├── img/                     # Screenshots and demo images
├── .env                     # Your environment variables (create this)
└── README.md               # This file
```

## Troubleshooting

### Service Not Starting

1. Check if port 5001 is available:
   ```bash
   lsof -i :5001
   ```

2. View service logs:
   ```bash
   docker-compose logs
   ```

### Connection Issues

1. Verify your YNAB API token is correct
2. Check that the service is accessible:
   ```bash
   curl http://localhost:5001/health
   ```

3. For Docker networking issues, ensure you're using the correct URL in your Glance configuration

### Cache Issues

If you need to force refresh the data:
```bash
curl http://localhost:5001/cache/clear
```

## Development

### Running Locally (without Docker)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the service:
   ```bash
   python ynab_service.py
   ```

### Service Architecture

- **Flask** web service for API endpoints
- **YNAB SDK** for API integration
- **Pandas** for data processing and analysis
- **In-memory caching** for performance
- **Docker** for containerization

## Contributing

Feel free to submit issues, feature requests, or pull requests. This integration is designed to be simple and focused on the core functionality of displaying YNAB spending data in Glance.

## Acknowledgments

- [YNAB](https://www.ynab.com/) for their excellent budgeting software and API
- [Glance](https://github.com/glanceapp/glance) for the beautiful dashboard framework
- [YNAB Python SDK](https://github.com/dmlerner/ynab-sdk-python) for easy API integration