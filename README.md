# YNAB Glance Integration

A clean, native integration between [YNAB (You Need A Budget)](https://www.ynab.com/) and [Glance](https://github.com/glanceapp/glance) dashboard that displays your spending data in two complementary widgets.

## Features

- **Real-time spending data** from YNAB API
- **Two dashboard widgets**:
  - **Monthly Budget Remaining**: Shows assigned vs spent for specific categories this month
  - **30-Day Spending Trends**: Top 5 spending category groups over last 30 days
- **Clean, native styling** that matches your Glance dashboard theme
- **US number formatting** with comma separators (e.g., $4,554)
- **Intelligent caching** (15-minute cache) for fast response times
- **Dockerized service** for easy deployment
- **Custom category filtering** for monthly budget tracking

## Demo

The integration provides two complementary widgets that display your YNAB data in clean, native styling:

### 1. Monthly Budget Remaining
Shows how much money you have left in each category for the current month:
```
Groceries                     $125.50
Gas / Fuel Expenses           $87.25
Fun Spending                  $45.00
Personal Care                 $32.75
Eating Out                    $15.25
Entertainment                 $-8.50
Baby Items                    $0.00
Unexpected Expenses           $0.00
Clothing                      $0.00
```

### 2. 30-Day Spending Trends
Shows your top spending category groups over the last 30 days:
```
🏠 Housing & Utilities         $2,150  35.2%
🛒 Groceries & Food           $1,325  21.7%
🚗 Transportation             $890    14.6%
💊 Healthcare                 $675    11.0%
🎬 Entertainment              $465    7.6%
```

![YNAB Spending Widget](img/YNAB%20Spending%20Widget.jpg)

**Widget Features:**
- **Native Glance styling**: No custom backgrounds, matches your dashboard theme
- **US number formatting**: Dollar signs and comma separators
- **Real-time updates**: 5-minute cache for responsive data

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
   # YNAB_MONTHLY_CATEGORIES=Groceries,Transportation,Entertainment,Dining Out
   ```

   **Notes**: 
   - If you have multiple budgets, you can specify a particular budget ID. Otherwise, it will use your first budget.
   - Customize `YNAB_MONTHLY_CATEGORIES` with your own category names in your desired order
   - If you don't set `YNAB_MONTHLY_CATEGORIES`, it will use the default categories

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

3. Test both endpoints:
   ```bash
   # Test 30-day spending trends
   curl http://localhost:5001/glance
   
   # Test monthly budget remaining
   curl http://localhost:5001/monthly-goals
   ```

### 4. Configure Glance Widgets

Add both widgets to your Glance `home.yml` configuration:

```yaml
# Monthly Budget Remaining Widget
- type: custom-api
  title: Budget Remaining (This Month)
  url: http://host.docker.internal:5001/monthly-goals
  cache: 5m
  request-timeout: 10
  template: |
    {{- if .JSON.Exists "error" }}
      <div>Error: {{ .JSON.String "error" }}</div>
    {{- else }}
      {{- range .JSON.Array "categories" }}
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div style="flex: 1;">
          <div>{{ .String "category_name" }}</div>
        </div>
        <div style="text-align: right;">
          <div>${{ .String "difference_formatted" }}</div>
        </div>
      </div>
      {{- end }}
    {{- end }}

# 30-Day Spending Trends Widget
- type: custom-api
  title: Spending (30d Trailing)
  url: http://host.docker.internal:5001/glance
  cache: 5m
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

### Primary Endpoints
- **`/glance`** - JSON data for 30-day spending trends widget
- **`/monthly-goals`** - JSON data for monthly budget remaining widget

### API Endpoints
- **`/api/spending`** - Raw JSON spending data (30-day trends)
- **`/api/monthly-goals`** - Raw JSON monthly budget data

### Utility Endpoints
- **`/health`** - Health check with cache status
- **`/cache/clear`** - Clear the data cache
- **`/debug/monthly-goals-order`** - Debug endpoint to verify category order

## Configuration

### Docker Compose

The service runs on port 5001 by default. You can modify `docker-compose.yml` to change the port or other settings.

### Monthly Goals Categories

The monthly budget widget tracks a specific whitelist of categories in a predefined order. You can customize which categories are tracked by setting the `YNAB_MONTHLY_CATEGORIES` environment variable in your `.env` file:

```bash
# Comma-separated list of category names (in desired order)
YNAB_MONTHLY_CATEGORIES=Groceries,Transportation,Entertainment,Dining Out,Personal Care
```

**Configuration Tips:**
- Categories appear in the exact order you specify in the environment variable
- Category names must match exactly as they appear in your YNAB budget
- Use the debug endpoint to verify exact category names:
  ```bash
  curl http://localhost:5001/debug/category-groups
  ```
- If you don't set this variable, the service will use the default categories
- This keeps your personal category names out of the code repository

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

### Monthly Goals Widget Issues

1. **Categories not appearing**: Verify category names match exactly using the debug endpoint:
   ```bash
   curl http://localhost:5001/debug/category-groups
   ```

2. **Wrong order**: Categories appear in the order specified in the `whitelist_categories` list in `ynab_service.py`

3. **Negative assigned amounts**: The widget handles money transfers correctly:
   - If assigned amount is negative (money moved out) and available is $0, shows $0.00
   - Otherwise shows the difference between assigned and spent amounts

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