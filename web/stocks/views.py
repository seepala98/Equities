from django.http import JsonResponse
from .models import Stock


def latest(request, symbol):
    item = Stock.objects.filter(symbol=symbol).order_by('-scraped_at').first()
    if not item:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse({'symbol': item.symbol, 'close_price': str(item.close_price)})


from django.shortcuts import render, redirect
from .utils import fetch_and_save


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

