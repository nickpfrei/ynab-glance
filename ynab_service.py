from flask import Flask, jsonify, render_template_string
import pandas as pd
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from ynab_sdk import YNAB
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Simple in-memory cache
cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 900  # 15 minutes in seconds
}

def get_ynab_spending_data():
    """Get top 5 spending categories from last 30 days"""
    
    # Check cache first
    current_time = time.time()
    if cache['data'] and (current_time - cache['timestamp']) < cache['ttl']:
        return cache['data'], None
    
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return None, "API token not found"
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return None, "No budgets found"
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get transactions
        transactions_response = ynab.transactions.get_transactions(budget_id)
        
        # Get categories
        categories_response = ynab.categories.get_categories(budget_id)
        
        # Process transactions
        tx_data = []
        for tx in transactions_response.data.transactions:
            tx_data.append({
                'date': tx.date,
                'amount': tx.amount / 1000,  # Convert from milliunits
                'category_id': tx.category_id,
                'category_name': tx.category_name,
                'payee_name': tx.payee_name
            })
        
        df = pd.DataFrame(tx_data)
        
        if df.empty:
            return None, "No transactions found"
        
        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Filter to last 30 days and expenses only
        thirty_days_ago = datetime.now() - timedelta(days=30)
        df = df[df['date'] >= thirty_days_ago]
        df = df[df['amount'] < 0]  # Only expenses
        df = df[df['category_name'] != 'Uncategorized']  # Remove uncategorized
        df['amount'] = df['amount'].abs()  # Make amounts positive
        
        # Add category groups
        category_groups = {}
        for group in categories_response.data.category_groups:
            for category in group.categories:
                category_groups[category.id] = group.name
        
        df['category_group'] = df['category_id'].map(category_groups)
        
        # Calculate spending by category group
        category_spending = df.groupby('category_group')['amount'].sum().reset_index()
        category_spending = category_spending.sort_values('amount', ascending=False)
        
        # Get top 5
        top_5 = category_spending.head(5)
        
        # Calculate percentages
        total_spending = df['amount'].sum()
        top_5['percentage'] = (top_5['amount'] / total_spending * 100).round(1)
        
        # Format for display
        result = []
        for _, row in top_5.iterrows():
            result.append({
                'category_group': row['category_group'],
                'amount': row['amount'],
                'amount_formatted': f"{row['amount']:,.0f}",  # US format with commas
                'percentage': row['percentage']
            })
        
        # Cache the result
        cache['data'] = result
        cache['timestamp'] = current_time
        
        return result, None
        
    except Exception as e:
        return None, str(e)

@app.route('/api/spending')
def api_spending():
    """JSON API endpoint"""
    data, error = get_ynab_spending_data()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/widget')
def widget():
    """HTML widget endpoint for embedding in Glance"""
    data, error = get_ynab_spending_data()
    
    if error:
        return f"<div style='color: red; padding: 10px;'>Error: {error}</div>"
    
    # HTML template for the widget
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 15px;
                background-color: #f8f9fa;
                color: #333;
            }
            .spending-widget {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                text-align: center;
                font-weight: bold;
                font-size: 16px;
            }
            .spending-list {
                padding: 0;
                margin: 0;
                list-style: none;
            }
            .spending-item {
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .spending-item:last-child {
                border-bottom: none;
            }
            .category-info {
                flex: 1;
            }
            .category-group {
                font-size: 11px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .category-name {
                font-size: 14px;
                font-weight: 500;
                color: #333;
                margin-top: 2px;
            }
            .amount-info {
                text-align: right;
            }
            .amount {
                font-size: 14px;
                font-weight: 600;
                color: #e74c3c;
            }
            .percentage {
                font-size: 12px;
                color: #666;
                margin-top: 2px;
            }
            .last-updated {
                text-align: center;
                font-size: 11px;
                color: #999;
                padding: 10px;
                background: #f8f9fa;
                border-top: 1px solid #eee;
            }
        </style>
    </head>
    <body>
        <div class="spending-widget">
            <div class="header">
                💰 Top Spending (Last 30 Days)
            </div>
            <ul class="spending-list">
                {% for item in data %}
                <li class="spending-item">
                    <div class="category-info">
                        <div class="category-group">{{ item.category_group }}</div>
                        <div class="category-name">{{ item.category_name }}</div>
                    </div>
                    <div class="amount-info">
                        <div class="amount">${{ "%.2f"|format(item.amount) }}</div>
                        <div class="percentage">{{ item.percentage }}%</div>
                    </div>
                </li>
                {% endfor %}
            </ul>
            <div class="last-updated">
                Updated: {{ now.strftime('%I:%M %p') }}
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_template, data=data, now=datetime.now())

@app.route('/glance')
def glance_data():
    """Simplified endpoint optimized for Glance custom-api widget"""
    data, error = get_ynab_spending_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'categories': data,
        'updated': datetime.now().strftime('%I:%M %p'),
        'total_categories': len(data)
    }
    
    return jsonify(response)

@app.route('/health')
def health():
    """Health check endpoint"""
    cache_age = time.time() - cache['timestamp'] if cache['data'] else 0
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'cache_age_seconds': cache_age,
        'cache_valid': cache_age < cache['ttl'] if cache['data'] else False
    })

@app.route('/cache/clear')
def clear_cache():
    """Clear the cache"""
    cache['data'] = None
    cache['timestamp'] = 0
    return jsonify({'message': 'Cache cleared', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 