# YNAB Glance Integration

A clean, native integration between [YNAB (You Need A Budget)](https://www.ynab.com/) and [Glance](https://github.com/glanceapp/glance) dashboard that displays your spending data in two complementary widgets.

## Features

- **Real-time spending data** from YNAB API
- **Four comprehensive widgets**:
  - **30-Day Spending Trends**: Top 5 spending category groups over last 30 days  
  - **Monthly Budget Remaining**: Shows assigned vs spent for specific categories this month
  - **Savings Rate Tracker**: Monitor your monthly savings rate against income
  - **Net Worth Calculator**: Complete financial overview with assets vs liabilities breakdown
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
# SAMPLE DATA
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
# SAMPLE DATA
🏠 Housing & Utilities         $2,150  35.2%
🛒 Groceries & Food           $1,325  21.7%
🚗 Transportation             $890    14.6%
💊 Healthcare                 $675    11.0%
🎬 Entertainment              $465    7.6%
```

### 3. Savings Rate Tracker
Shows your monthly savings rate and total amount saved:
```
# SAMPLE DATA
Monthly Income: $6,500.00
Monthly Savings: $975.00
Savings Rate: 15.0%
```

### 4. Net Worth Overview
Shows your complete financial picture with asset and liability breakdown:
```
# SAMPLE DATA
Net Worth: $87,420.50

Assets: $102,150.75
  Retirement Accounts         $35,250.00
  Cash & Savings              $28,900.75
  Vehicles & Property         $35,000.00
  Investments                 $3,000.00

Liabilities: $14,730.25
  Credit Cards                $3,250.00
  Loans                       $11,480.25
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
   # YNAB_MONTHLY_CATEGORIES=your_ynab_categories
   # YNAB_MONTHLY_INCOME=your_monthly_income
   # YNAB_SAVINGS_ACCOUNTS=your_savings_account_names
   ```

   **Notes**: 
   - If you have multiple budgets, you can specify a particular budget ID. Otherwise, it will use your first budget.
   - Customize `YNAB_MONTHLY_CATEGORIES` with your own category names in your desired order
   - If you don't set `YNAB_MONTHLY_CATEGORIES`, it will use the default categories
   - Set `YNAB_MONTHLY_INCOME` to your monthly income (in dollars, no commas) for savings rate calculation
   - Configure `YNAB_SAVINGS_ACCOUNTS` with comma-separated account names to track for savings rate

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
   curl http://localhost:5001/spending-trends
   
   # Test monthly budget remaining
   curl http://localhost:5001/monthly-goals
   
   # Test savings rate tracking
   curl http://localhost:5001/savings-rate
   
   # Test net worth calculation
   curl http://localhost:5001/net-worth
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
  url: http://host.docker.internal:5001/spending-trends
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

# Savings Rate Tracker Widget
- type: custom-api
  title: Savings Rate
  url: http://host.docker.internal:5001/savings-rate
  cache: 5m
  request-timeout: 10
  template: |
    {{- if .JSON.Exists "error" }}
      <div>Error: {{ .JSON.String "error" }}</div>
    {{- else }}
      {{- with .JSON.Get "savings_data" }}
      <div style="margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between;">
          <span>Monthly Income:</span>
          <span>${{ .String "monthly_income_formatted" }}</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>Monthly Savings:</span>
          <span>${{ .String "monthly_savings_formatted" }}</span>
        </div>
        <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 8px; margin-top: 8px;">
          <span class="color-highlight size-h3">Savings Rate:</span>
          <span class="color-highlight size-h3">{{ .String "savings_rate" }}%</span>
        </div>
      </div>
      {{- end }}
    {{- end }}

# Net Worth Overview Widget
- type: custom-api
  title: Net Worth
  url: http://host.docker.internal:5001/net-worth
  cache: 5m
  request-timeout: 10
  template: |
    {{- if .JSON.Exists "error" }}
      <div>Error: {{ .JSON.String "error" }}</div>
    {{- else }}
      {{- with .JSON.Get "net_worth_data" }}
      <div style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
          <span class="color-highlight size-h3">Net Worth:</span>
          <span class="color-highlight size-h3">${{ .String "net_worth_formatted" }}</span>
        </div>
        
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">
          <span style="color: #4ade80; font-weight: bold;">Assets:</span>
          <span style="color: #4ade80; font-weight: bold;">${{ .String "total_assets_formatted" }}</span>
        </div>
        
        <div style="margin-left: 16px; margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>💰 Retirement:</span>
            <span>${{ .String "assets.retirement.total_formatted" }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>🏦 Checking:</span>
            <span>${{ .String "assets.checking.total_formatted" }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>💵 Savings:</span>
            <span>${{ .String "assets.savings.total_formatted" }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>📈 Investments:</span>
            <span>${{ .String "assets.investment.total_formatted" }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>🏠 Other Assets:</span>
            <span>${{ .String "assets.other_assets.total_formatted" }}</span>
          </div>
        </div>
        
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">
          <span style="color: #f87171; font-weight: bold;">Liabilities:</span>
          <span style="color: #f87171; font-weight: bold;">${{ .String "total_liabilities_formatted" }}</span>
        </div>
        
        <div style="margin-left: 16px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>💳 Credit Cards:</span>
            <span>-${{ .String "liabilities.credit_cards.total_formatted" }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.9em;">
            <span>🏦 Loans:</span>
            <span>-${{ .String "liabilities.loans.total_formatted" }}</span>
          </div>
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
- **`/spending-trends`** - JSON data for 30-day spending trends widget
- **`/monthly-goals`** - JSON data for monthly budget remaining widget
- **`/savings-rate`** - JSON data for savings rate tracker widget
- **`/net-worth`** - JSON data for net worth overview widget
- **`/glance`** - (deprecated) Use `/spending-trends` instead

### API Endpoints
- **`/api/spending`** - Raw JSON spending data (30-day trends)
- **`/api/monthly-goals`** - Raw JSON monthly budget data
- **`/api/savings-rate`** - Raw JSON savings rate data
- **`/api/net-worth`** - Raw JSON net worth data

### Utility Endpoints
- **`/health`** - Health check with cache status
- **`/cache/clear`** - Clear the data cache
- **`/debug/monthly-goals-order`** - Debug endpoint to verify category order
- **`/debug/accounts`** - Debug endpoint to list all account names and balances

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

### Service Issues

**Service won't start:**
```bash
# Check if port 5001 is in use
lsof -i :5001

# View service logs
docker-compose logs
```

**Connection problems:**
1. Verify your YNAB API token in `.env`
2. Test service health: `curl http://localhost:5001/health`
3. For Docker Glance: Use `host.docker.internal:5001` in widget URLs

**Force cache refresh:**
```bash
curl http://localhost:5001/cache/clear
```

### Widget Configuration

**Missing or incorrect data:**
```bash
# Debug account names and types
curl http://localhost:5001/debug/accounts

# Debug category names (for monthly budget widget)
curl http://localhost:5001/debug/category-groups
```

**Monthly budget widget:**
- Categories must match YNAB names exactly
- Set custom categories in `YNAB_MONTHLY_CATEGORIES` environment variable
- Categories display in the order specified

**Savings rate widget:**
- Set `YNAB_MONTHLY_INCOME` as a number (no commas)
- Configure `YNAB_SAVINGS_ACCOUNTS` with comma-separated account names

**Net worth widget:**
- Account categorization is automatic based on YNAB account types
- Retirement accounts detected by keywords: 401k, 403b, IRA, Roth, pension  
- Investment accounts detected by keywords: investment, brokerage, stock, ETF, mutual
- All categories show even with $0.00 balances for complete overview

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