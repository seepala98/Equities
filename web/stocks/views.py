from django.http import JsonResponse
from .models import Stock


def latest(request, symbol):
    item = Stock.objects.filter(symbol=symbol).order_by('-scraped_at').first()
    if not item:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse({'symbol': item.symbol, 'close_price': str(item.close_price)})


from django.shortcuts import render, redirect
from .utils import fetch_and_save
from .etf_utils import calculate_investment_performance, compare_etf_performance, get_popular_canadian_etfs
from .etf_holdings_utils import fetch_and_store_etf, get_etf_holdings_summary
from .models import ETFInfo, ETFHolding, Sector, GeographicRegion, Listing
from .asset_classifier import AssetClassifier
from .sector_analysis_utils import SectorAnalyzer
from django.db.models import Count


def home(request):
    message = None
    if request.method == 'POST':
        symbol = request.POST.get('symbol')
        if symbol:
            try:
                rec = fetch_and_save(symbol)
                message = f'Fetched {symbol}: price={rec.close_price} volume={rec.volume}'
            except Exception as exc:
                message = f'Error: {exc}'
        else:
            message = 'Please provide a symbol.'

    latest = Stock.objects.all().order_by('-scraped_at')[:10]
    return render(request, 'stocks/home.html', {'message': message, 'latest': latest})


def etf_analysis(request):
    """ETF Performance Analysis view."""
    results = None
    error_message = None
    popular_etfs = get_popular_canadian_etfs()
    
    if request.method == 'POST':
        symbol = request.POST.get('symbol', '').strip().upper()
        investment_amount = request.POST.get('investment_amount', '')
        start_date = request.POST.get('start_date', '')
        end_date = request.POST.get('end_date', '')
        
        if symbol and investment_amount and start_date:
            try:
                investment_amount = float(investment_amount)
                results = calculate_investment_performance(
                    symbol=symbol,
                    investment_amount=investment_amount,
                    start_date=start_date,
                    end_date=end_date if end_date else None
                )
            except ValueError as e:
                error_message = f'Error: {str(e)}'
            except Exception as e:
                error_message = f'Unexpected error: {str(e)}'
        else:
            error_message = 'Please provide symbol, investment amount, and start date.'
    
    context = {
        'results': results,
        'error_message': error_message,
        'popular_etfs': popular_etfs,
    }
    
    return render(request, 'stocks/etf_analysis.html', context)


def etf_holdings(request):
    """ETF Holdings Analysis view."""
    etf_list = ETFInfo.objects.all().order_by('symbol')
    selected_etf = None
    holdings_data = None
    error_message = None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        symbol = request.POST.get('symbol', '').strip().upper()
        
        if action == 'fetch_etf' and symbol:
            # Fetch new ETF data
            try:
                result = fetch_and_store_etf(symbol)
                if result['success']:
                    return redirect('etf_holdings')  # Redirect to avoid resubmission
                else:
                    error_message = result.get('message', 'Error fetching ETF data')
            except Exception as e:
                error_message = f'Error: {str(e)}'
        
        elif action == 'view_holdings' and symbol:
            # View existing ETF holdings
            try:
                selected_etf = ETFInfo.objects.get(symbol=symbol)
                holdings_data = get_etf_holdings_summary(symbol)
                if not holdings_data['success']:
                    error_message = holdings_data.get('error', 'Error loading holdings')
            except ETFInfo.DoesNotExist:
                error_message = f'ETF {symbol} not found. Please fetch it first.'
            except Exception as e:
                error_message = f'Error: {str(e)}'
    
    # Get ETF with some basic stats
    etfs_with_stats = []
    for etf in etf_list:
        holdings_count = ETFHolding.objects.filter(etf=etf).count()
        etfs_with_stats.append({
            'etf': etf,
            'holdings_count': holdings_count
        })
    
    context = {
        'etfs_with_stats': etfs_with_stats,
        'selected_etf': selected_etf,
        'holdings_data': holdings_data,
        'error_message': error_message,
        'popular_etfs': get_popular_canadian_etfs(),
    }
    
    return render(request, 'stocks/etf_holdings.html', context)


def asset_classification(request):
    """Asset Classification Analysis view."""
    classifier = AssetClassifier()
    stats = None
    classification_results = None
    error_message = None
    
    # Get current classification statistics
    asset_stats = Listing.objects.values('asset_type').annotate(
        count=Count('asset_type')
    ).order_by('-count')
    
    total_listings = Listing.objects.count()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'classify_batch':
            # Classify a batch of unclassified entries
            limit = int(request.POST.get('limit', 100))
            
            try:
                # Focus on entries that are still marked as 'STOCK' (default)
                unclassified = Listing.objects.filter(asset_type='STOCK')[:limit]
                
                results = {
                    'total_processed': 0,
                    'classifications': {},
                    'errors': []
                }
                
                for listing in unclassified:
                    try:
                        asset_type = classifier.classify_listing(listing)
                        
                        # Only update if classification changed
                        if asset_type != listing.asset_type:
                            listing.asset_type = asset_type
                            listing.save(update_fields=['asset_type'])
                            results['total_processed'] += 1
                            
                            if asset_type not in results['classifications']:
                                results['classifications'][asset_type] = 0
                            results['classifications'][asset_type] += 1
                            
                    except Exception as e:
                        results['errors'].append(f"{listing.symbol}: {str(e)}")
                
                classification_results = results
                
                # Refresh stats after classification
                asset_stats = Listing.objects.values('asset_type').annotate(
                    count=Count('asset_type')
                ).order_by('-count')
                
            except Exception as e:
                error_message = f'Classification error: {str(e)}'
        
        elif action == 'classify_specific':
            # Classify specific symbols or exchanges
            symbols = request.POST.get('symbols', '').strip().upper()
            exchange = request.POST.get('exchange', '').strip().upper()
            
            if symbols or exchange:
                try:
                    query = Listing.objects.all()
                    
                    if symbols:
                        symbol_list = [s.strip() for s in symbols.split(',')]
                        query = query.filter(symbol__in=symbol_list)
                    
                    if exchange:
                        query = query.filter(exchange=exchange)
                    
                    count = 0
                    for listing in query:
                        asset_type = classifier.classify_listing(listing)
                        if asset_type != listing.asset_type:
                            listing.asset_type = asset_type
                            listing.save(update_fields=['asset_type'])
                            count += 1
                    
                    classification_results = {
                        'total_processed': count,
                        'message': f'Updated {count} classifications'
                    }
                    
                    # Refresh stats
                    asset_stats = Listing.objects.values('asset_type').annotate(
                        count=Count('asset_type')
                    ).order_by('-count')
                    
                except Exception as e:
                    error_message = f'Error: {str(e)}'
            else:
                error_message = 'Please provide symbols or select an exchange'
    
    # Sample of each asset type for display
    asset_samples = {}
    for stat in asset_stats:
        asset_type = stat['asset_type']
        if asset_type:
            samples = Listing.objects.filter(asset_type=asset_type)[:5]
            asset_samples[asset_type] = samples
    
    context = {
        'asset_stats': asset_stats,
        'total_listings': total_listings,
        'asset_samples': asset_samples,
        'classification_results': classification_results,
        'error_message': error_message,
        'asset_type_choices': Listing.ASSET_TYPE_CHOICES,
    }
    
    return render(request, 'stocks/asset_classification.html', context)


def sector_analysis(request):
    """Sector Analysis view using official yfinance Sector/Industry modules."""
    analyzer = SectorAnalyzer()
    sector_data = None
    stock_analysis = None
    error_message = None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'analyze_sector':
            sector_key = request.POST.get('sector_key', '').strip().lower()
            
            if sector_key:
                try:
                    sector_data = analyzer.get_sector_data(sector_key)
                    if not sector_data['success']:
                        error_message = sector_data.get('error', 'Failed to fetch sector data')
                        
                except Exception as e:
                    error_message = f'Error analyzing sector: {str(e)}'
            else:
                error_message = 'Please select a sector to analyze'
        
        elif action == 'analyze_stock':
            symbol = request.POST.get('symbol', '').strip().upper()
            
            if symbol:
                try:
                    # Add .TO suffix for Canadian stocks if not present
                    if not symbol.endswith('.TO') and not '.' in symbol:
                        test_symbol = f"{symbol}.TO"
                    else:
                        test_symbol = symbol
                    
                    stock_analysis = analyzer.enhance_stock_with_sector_data(test_symbol)
                    
                    if not stock_analysis['success']:
                        # Try without .TO suffix
                        if test_symbol != symbol:
                            stock_analysis = analyzer.enhance_stock_with_sector_data(symbol)
                        
                        if not stock_analysis['success']:
                            error_message = stock_analysis.get('error', 'Failed to analyze stock')
                            
                except Exception as e:
                    error_message = f'Error analyzing stock: {str(e)}'
            else:
                error_message = 'Please provide a stock symbol'
    
    # Get some stats from our database for context
    stock_count = Listing.objects.filter(asset_type='STOCK').count()
    etf_count = Listing.objects.filter(asset_type='ETF').count()
    
    context = {
        'sector_keys': analyzer.SECTOR_KEYS,
        'sector_data': sector_data,
        'stock_analysis': stock_analysis,
        'error_message': error_message,
        'stock_count': stock_count,
        'etf_count': etf_count,
    }
    
    return render(request, 'stocks/sector_analysis.html', context)

