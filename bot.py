import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    WebAppInfo
)
from aiogram.filters import Command

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
TONCONNECT_URL = "https://acewolfff.github.io/ton-trader-bot/tonconnect.html"

# Комиссии
NETWORK_FEE = 0.005       # Комиссия сети TON за одну транзакцию (в TON)

# ========== ХРАНИЛИЩЕ ==========
user_sessions = {}

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== ПОЛУЧЕНИЕ ЦЕНЫ TON ==========
async def get_ton_price():
    """Получает цену TON из нескольких источников"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd',
                timeout=15
            ) as resp:
                data = await resp.json()
                price = data.get('the-open-network', {}).get('usd')
                if price:
                    return price
    except:
        pass
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT',
                timeout=15
            ) as resp:
                data = await resp.json()
                return float(data.get('price', 0))
    except:
        pass
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.bybit.com/v5/market/tickers?category=spot&symbol=TONUSDT',
                timeout=15
            ) as resp:
                data = await resp.json()
                return float(data['result']['list'][0]['lastPrice'])
    except:
        pass
    
    return None


# ========== РАСЧЁТ БЕЗУБЫТОЧНОСТИ ==========
def calculate_breakeven(buy_price, amount, current_price=None):
    """Считает минимальную цену продажи для безубытка с учётом комиссий."""
    total_fee_ton = NETWORK_FEE * 2
    buy_cost = amount * buy_price
    fee_usd = total_fee_ton * (current_price or buy_price)
    breakeven_price = (buy_cost + fee_usd) / amount
    breakeven_percent = ((breakeven_price - buy_price) / buy_price) * 100
    
    return {
        "buy_price": buy_price,
        "amount": amount,
        "total_fee_ton": total_fee_ton,
        "fee_usd": round(fee_usd, 4),
        "breakeven_price": round(breakeven_price, 6),
        "breakeven_percent": round(breakeven_percent, 4),
        "buy_cost": round(buy_cost, 2)
    }

def calculate_net_profit(buy_price, sell_price, amount):
    """Считает чистую прибыль с учётом комиссий."""
    total_fee_ton = NETWORK_FEE * 2
    fee_usd = total_fee_ton * sell_price
    gross_profit = (sell_price - buy_price) * amount
    net_profit = gross_profit - fee_usd
    net_profit_percent = (net_profit / (buy_price * amount)) * 100
    
    return {
        "gross_profit": round(gross_profit, 4),
        "net_profit": round(net_profit, 4),
        "net_profit_percent": round(net_profit_percent, 4),
        "total_fee_ton": total_fee_ton,
        "fee_usd": round(fee_usd, 4),
        "is_profitable": net_profit > 0
    }


# ========== ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ ==========
class TechnicalIndicators:
    def __init__(self):
        self.price_history = []
    
    def add_price(self, price):
        self.price_history.append(price)
        if len(self.price_history) > 100:
            self.price_history = self.price_history[-100:]
    
    def calculate_rsi(self, periods=14):
        if len(self.price_history) < periods + 1:
            return None
        
        gains, losses = [], []
        for i in range(1, len(self.price_history)):
            change = self.price_history[i] - self.price_history[i-1]
            gains.append(change if change > 0 else 0)
            losses.append(abs(change) if change < 0 else 0)
        
        avg_gain = sum(gains[-periods:]) / periods
        avg_loss = sum(losses[-periods:]) / periods
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    
    def calculate_ema(self, periods):
        if len(self.price_history) < periods * 2:
            if len(self.price_history) >= periods:
                return round(sum(self.price_history[-periods:]) / periods, 6)
            return None
        
        prices = self.price_history
        sma = sum(prices[:periods]) / periods
        multiplier = 2 / (periods + 1)
        ema = sma
        
        for price in prices[periods:]:
            ema = (price - ema) * multiplier + ema
        
        return round(ema, 6)
    
    def get_signal(self, buy_price=None, amount=None):
        """Сигнал с учётом безубыточности."""
        if len(self.price_history) < 21:
            return None
        
        rsi = self.calculate_rsi()
        ema9 = self.calculate_ema(9)
        ema21 = self.calculate_ema(21)
        current_price = self.price_history[-1]
        
        min_move_percent = 0
        if buy_price and amount:
            be = calculate_breakeven(buy_price, amount, current_price)
            min_move_percent = be['breakeven_percent']
        
        signals = []
        
        if rsi and rsi >= 70:
            signals.append(("SELL", 1))
        elif rsi and rsi <= 30:
            signals.append(("BUY", 1))
        
        if ema9 and ema21:
            if current_price > ema9 > ema21:
                signals.append(("BUY", 2))
            elif current_price < ema9 < ema21:
                signals.append(("SELL", 2))
            elif ema9 > ema21:
                move = ((current_price - ema21) / ema21) * 100
                if move > min_move_percent:
                    signals.append(("BUY", 1))
            elif ema9 < ema21:
                move = ((ema21 - current_price) / ema21) * 100
                if move > min_move_percent:
                    signals.append(("SELL", 1))
        
        if not signals:
            return {"signal": "NEUTRAL", "confidence": 30, "rsi": rsi, "ema9": ema9, "ema21": ema21, "min_move": min_move_percent}
        
        buy_score = sum(s[1] for s in signals if s[0] == "BUY")
        sell_score = sum(s[1] for s in signals if s[0] == "SELL")
        total_score = buy_score - sell_score
        
        if total_score >= 2:
            return {"signal": "BUY", "confidence": min(60 + abs(total_score) * 15, 95), "rsi": rsi, "ema9": ema9, "ema21": ema21, "min_move": min_move_percent}
        elif total_score <= -2:
            return {"signal": "SELL", "confidence": min(60 + abs(total_score) * 15, 95), "rsi": rsi, "ema9": ema9, "ema21": ema21, "min_move": min_move_percent}
        else:
            return {"signal": "NEUTRAL", "confidence": 40 + abs(total_score) * 10, "rsi": rsi, "ema9": ema9, "ema21": ema21, "min_move": min_move_percent}


analyzer = TechnicalIndicators()


# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена TON", callback_data="check_price")],
        [InlineKeyboardButton(text="📊 Теханализ", callback_data="tech_analysis")],
        [InlineKeyboardButton(text="📈 Купить TON", callback_data="buy_ton")],
        [InlineKeyboardButton(text="📉 Продать TON", callback_data="sell_ton")],
        [InlineKeyboardButton(text="🤖 Авто-трейдинг", callback_data="auto_trade")],
        [InlineKeyboardButton(text="📋 Портфель", callback_data="positions")],
        [InlineKeyboardButton(text="💸 Безубыток", callback_data="breakeven_info")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="buy_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="buy_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="buy_amount_1.0")],
        [InlineKeyboardButton(text="2.0 TON", callback_data="buy_amount_2.0")],
        [InlineKeyboardButton(text="5.0 TON", callback_data="buy_amount_5.0")],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="buy_custom")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="buy_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def sell_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="sell_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="sell_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="sell_amount_1.0")],
        [InlineKeyboardButton(text="2.0 TON", callback_data="sell_amount_2.0")],
        [InlineKeyboardButton(text="5.0 TON", callback_data="sell_amount_5.0")],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="sell_custom")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="sell_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def auto_keyboard(user_id):
    session = user_sessions.get(user_id, {})
    auto_status = "✅" if session.get('auto_trade') else "❌"
    dca_status = "✅" if session.get('dca_enabled') else "❌"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Авто-сигналы: {auto_status}", callback_data="toggle_auto")],
        [InlineKeyboardButton(text=f"DCA: {dca_status}", callback_data="toggle_dca")],
        [InlineKeyboardButton(text="🎯 Тейк-профит: " + str(session.get('tp_percent', 3)) + "%", callback_data="setup_tp")],
        [InlineKeyboardButton(text="🛑 Стоп-лосс: " + str(session.get('sl_percent', 7)) + "%", callback_data="setup_sl")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])


# ========== /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    user_sessions[user_id] = {
        'last_price': None,
        'base_price': None,
        'positions': [],
        'auto_trade': False,
        'dca_enabled': False,
        'awaiting_input': None,
        'dca_config': {
            'total_amount': 1.0,
            'parts': 3,
            'drop_percent': 1.5,
            'bought_parts': 0,
            'buy_prices': []
        },
        'tp_percent': 3.0,
        'sl_percent': 7.0,
        'alerts_enabled': True
    }
    
    await message.answer(
        "🤖 *TON Trading Bot v4.3*\n\n"
        "✅ Учёт комиссий в торговых решениях\n"
        "✅ Сигналы только если сделка прибыльна\n"
        "✅ Своя сумма покупки/продажи\n\n"
        "• 💰 Цена TON\n"
        "• 📊 Теханализ\n"
        "• 📈/📉 Сделки\n"
        "• 🤖 Авто-трейдинг\n"
        "• 💸 Безубыток\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ИНФОРМАЦИЯ О БЕЗУБЫТКЕ ==========
@dp.callback_query(lambda c: c.data == "breakeven_info")
async def breakeven_info(callback: types.CallbackQuery):
    price = await get_ton_price()
    if not price:
        await callback.answer("❌ Нет данных о цене", show_alert=True)
        return
    
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    positions = session.get('positions', [])
    
    text = "💸 *БЕЗУБЫТОЧНОСТЬ С УЧЁТОМ КОМИССИЙ*\n\n"
    text += f"📡 Комиссия сети: *{NETWORK_FEE} TON* за транзакцию\n"
    text += f"🔄 Комиссия за сделку: *{NETWORK_FEE * 2} TON*\n"
    text += f"💵 Это примерно: *${NETWORK_FEE * 2 * price:.4f}*\n\n"
    
    for amount in [0.1, 0.5, 1.0, 5.0]:
        be = calculate_breakeven(price, amount, price)
        text += f"• Сумма *{amount} TON*:\n"
        text += f"  Безубыток при: *${be['breakeven_price']:.4f}* (+{be['breakeven_percent']:.2f}%)\n"
    
    text += "\n⚠️ *ВНИМАНИЕ:*\n"
    text += "• Чем меньше сумма сделки — тем выше нужен % для безубытка\n"
    text += "• При 0.1 TON нужен рост ~5% только для покрытия комиссии\n"
    text += "• Рекомендуемая минимальная сделка: *0.5 TON*\n\n"
    
    if positions:
        buy_positions = [p for p in positions if p['type'] == 'BUY']
        if buy_positions:
            text += "📊 *Ваши позиции:*\n"
            for pos in buy_positions[-3:]:
                be = calculate_breakeven(pos['price'], pos['amount'], price)
                current_move = ((price - pos['price']) / pos['price']) * 100
                text += f"• {pos['amount']} TON @ ${pos['price']:.4f}\n"
                text += f"  Безубыток: ${be['breakeven_price']:.4f} (+{be['breakeven_percent']:.2f}%)\n"
                if current_move >= be['breakeven_percent']:
                    text += f"  ✅ Сейчас: +{current_move:.2f}% (выше безубытка)\n"
                else:
                    text += f"  ❌ Сейчас: {current_move:+.2f}% (ниже безубытка, продажа = убыток)\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )


# ========== ЦЕНА ==========
@dp.callback_query(lambda c: c.data == "check_price")
async def check_price(callback: types.CallbackQuery):
    await callback.answer("⏳ Загружаю...")
    
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    if not price:
        await callback.message.edit_text("❌ Не удалось получить цену.", reply_markup=main_keyboard())
        return
    
    session = user_sessions.get(user_id, {})
    old_price = session.get('last_price')
    session['last_price'] = price
    user_sessions[user_id] = session
    
    analyzer.add_price(price)
    
    change_text = ""
    if old_price:
        change = ((price - old_price) / old_price) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        change_text = f"\nИзменение: {emoji} {change:+.2f}%"
    
    be = calculate_breakeven(price, 0.5, price)
    
    await callback.message.edit_text(
        f"💰 *TON / USD*\n\nТекущая цена: *${price:.4f}*{change_text}\n"
        f"Мин. для безубытка (0.5 TON): *+{be['breakeven_percent']:.2f}%*\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ТЕХАНАЛИЗ ==========
@dp.callback_query(lambda c: c.data == "tech_analysis")
async def tech_analysis(callback: types.CallbackQuery):
    await callback.answer("⏳ Анализирую...")
    
    price = await get_ton_price()
    if price:
        analyzer.add_price(price)
    
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
    last_buy = buy_positions[-1] if buy_positions else None
    
    signal = analyzer.get_signal(
        buy_price=last_buy['price'] if last_buy else None,
        amount=last_buy['amount'] if last_buy else None
    )
    
    if not signal:
        await callback.message.edit_text(
            "📊 Недостаточно данных. Нужно минимум 21 точка.",
            reply_markup=main_keyboard()
        )
        return
    
    rsi = signal.get('rsi')
    ema9 = signal.get('ema9')
    ema21 = signal.get('ema21')
    current = analyzer.price_history[-1]
    
    if signal['signal'] == 'BUY':
        sig_emoji = "🟢"
        sig_text = "ПОКУПКА"
    elif signal['signal'] == 'SELL':
        sig_emoji = "🔴"
        sig_text = "ПРОДАЖА"
    else:
        sig_emoji = "⚪"
        sig_text = "НЕЙТРАЛЬНО"
    
    text = f"📊 *ТЕХАНАЛИЗ TON*\n\n"
    text += f"Сигнал: {sig_emoji} *{sig_text}*\n"
    text += f"Уверенность: *{signal['confidence']:.0f}%*\n\n"
    text += f"💰 Цена: *${current:.4f}*\n"
    
    if rsi:
        rsi_emoji = "🔴" if rsi >= 70 else ("🟢" if rsi <= 30 else "⚪")
        text += f"📈 RSI(14): {rsi_emoji} *{rsi:.1f}*\n"
    
    if ema9 and ema21:
        text += f"📉 EMA9: *${ema9:.4f}*\n"
        text += f"📉 EMA21: *${ema21:.4f}*\n"
    
    text += f"\n💸 *Комиссия:* {NETWORK_FEE * 2} TON за сделку\n"
    
    if last_buy:
        be = calculate_breakeven(last_buy['price'], last_buy['amount'], current)
        current_move = ((current - last_buy['price']) / last_buy['price']) * 100
        text += f"\n📊 *Ваша позиция:*\n"
        text += f"• Куплено: {last_buy['amount']} TON @ ${last_buy['price']:.4f}\n"
        text += f"• Безубыток: ${be['breakeven_price']:.4f} (+{be['breakeven_percent']:.2f}%)\n"
        text += f"• Сейчас: {current_move:+.2f}%\n"
        
        if current_move >= be['breakeven_percent']:
            text += f"• ✅ Можно продавать с прибылью\n"
        else:
            text += f"• ❌ Продажа = убыток (нужно +{be['breakeven_percent']:.2f}%)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="tech_analysis")],
        [InlineKeyboardButton(text="💸 Безубыток", callback_data="breakeven_info")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ========== ПОКУПКА ==========
@dp.callback_query(lambda c: c.data == "buy_ton")
async def buy_ton_menu(callback: types.CallbackQuery):
    price = await get_ton_price()
    if price:
        analyzer.add_price(price)
    
    await callback.message.edit_text(
        f"📈 *Покупка TON*\n\nЦена: ${price:.4f}\n\n"
        f"💡 Безубыток для каждой суммы:\n"
        f"• 0.1 TON → нужно +{calculate_breakeven(price, 0.1, price)['breakeven_percent']:.1f}%\n"
        f"• 0.5 TON → нужно +{calculate_breakeven(price, 0.5, price)['breakeven_percent']:.1f}%\n"
        f"• 1.0 TON → нужно +{calculate_breakeven(price, 1.0, price)['breakeven_percent']:.1f}%\n\n"
        f"⚠️ Малые суммы невыгодны из-за комиссии!\n"
        f"✏️ Можно ввести свою сумму",
        parse_mode="Markdown",
        reply_markup=buy_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("buy_amount_"))
async def buy_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_amount_", ""))
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    be = calculate_breakeven(price, amount, price)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"buy_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📈 *ПОДТВЕРЖДЕНИЕ ПОКУПКИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Стоимость: *${price * amount:.2f}*\n\n"
        f"💸 *Для безубытка:*\n"
        f"• Нужна цена продажи: *${be['breakeven_price']:.4f}*\n"
        f"• Нужен рост: *+{be['breakeven_percent']:.2f}%*\n"
        f"• Комиссия за сделку: *{be['total_fee_ton']} TON*\n\n"
        f"{'⚠️ Для такой суммы нужен значительный рост!' if be['breakeven_percent'] > 2 else '✅ Приемлемый порог безубытка.'}",
        parse_mode="Markdown", reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("buy_confirm_"))
async def buy_confirm(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_confirm_", ""))
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    session = user_sessions.get(user_id, {'positions': []})
    session['positions'].append({
        'type': 'BUY',
        'amount': amount,
        'price': price,
        'time': datetime.now().isoformat(),
        'tp_percent': session.get('tp_percent', 3.0),
        'sl_percent': session.get('sl_percent', 7.0)
    })
    if not session.get('base_price'):
        session['base_price'] = price
    user_sessions[user_id] = session
    
    be = calculate_breakeven(price, amount, price)
    
    await callback.message.edit_text(
        f"✅ *КУПЛЕНО {amount} TON*\n\n"
        f"По цене: ${price:.4f}\n"
        f"Для безубытка: +{be['breakeven_percent']:.2f}% (${be['breakeven_price']:.4f})\n\n"
        f"Позиция в портфеле 📋",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "buy_wallet")
async def buy_wallet(callback: types.CallbackQuery):
    price = await get_ton_price()
    webapp_url = f"{TONCONNECT_URL}?action=buy&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть кошелёк", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПОКУПКА ЧЕРЕЗ КОШЕЛЁК*\n\n"
        f"Цена: ${price:.4f}\nСумма: 0.5 TON\n\n"
        f"Нажми кнопку и подтверди в кошельке.\n"
        f"🔐 Ключи только у тебя!",
        parse_mode="Markdown", reply_markup=keyboard
    )

# ========== СВОЯ СУММА ПОКУПКИ ==========
@dp.callback_query(lambda c: c.data == "buy_custom")
async def buy_custom_prompt(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['awaiting_input'] = 'buy_amount'
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        "✏️ *Введите сумму покупки в TON*\n\n"
        "Просто отправьте число, например: `0.75` или `2`\n\n"
        "⚠️ Минимум 0.1 TON\n"
        "⚠️ Помните о комиссии — малые суммы невыгодны",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="buy_ton")]
        ])
    )

@dp.message(lambda message: user_sessions.get(message.from_user.id, {}).get('awaiting_input') == 'buy_amount')
async def process_custom_buy(message: types.Message):
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("❌ Введите число, например: `0.5`", parse_mode="Markdown")
        return
    
    if amount < 0.1:
        await message.answer("❌ Минимальная сумма: 0.1 TON")
        return
    
    if amount > 100:
        await message.answer("❌ Максимальная сумма: 100 TON")
        return
    
    session = user_sessions.get(user_id, {})
    session['awaiting_input'] = None
    user_sessions[user_id] = session
    
    price = await get_ton_price()
    if not price:
        await message.answer("❌ Не удалось получить цену")
        return
    
    be = calculate_breakeven(price, amount, price)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"buy_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="buy_ton")]
    ])
    
    await message.answer(
        f"📈 *ПОДТВЕРЖДЕНИЕ ПОКУПКИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Стоимость: *${price * amount:.2f}*\n\n"
        f"💸 *Для безубытка:*\n"
        f"• Нужна цена продажи: *${be['breakeven_price']:.4f}*\n"
        f"• Нужен рост: *+{be['breakeven_percent']:.2f}%*\n\n"
        f"{'⚠️ Малый объём — большой % для безубытка!' if be['breakeven_percent'] > 3 else '✅ Приемлемый порог безубытка.'}",
        parse_mode="Markdown", reply_markup=keyboard
    )


# ========== ПРОДАЖА ==========
@dp.callback_query(lambda c: c.data == "sell_ton")
async def sell_ton_menu(callback: types.CallbackQuery):
    price = await get_ton_price()
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
    total_bought = sum(p['amount'] for p in buy_positions)
    sell_positions = [p for p in session.get('positions', []) if p['type'] == 'SELL']
    total_sold = sum(p['amount'] for p in sell_positions)
    balance = total_bought - total_sold
    
    warning = ""
    if buy_positions:
        last_buy = buy_positions[-1]
        be = calculate_breakeven(last_buy['price'], last_buy['amount'], price)
        current_move = ((price - last_buy['price']) / last_buy['price']) * 100
        if current_move < be['breakeven_percent']:
            warning = f"\n⚠️ Текущий рост {current_move:+.2f}% ниже безубытка {be['breakeven_percent']:.2f}%\nПродажа приведёт к убытку!\n"
        else:
            warning = f"\n✅ Текущий рост {current_move:+.2f}% выше безубытка\nМожно продавать с прибылью.\n"
    
    await callback.message.edit_text(
        f"📉 *Продажа TON*\n\nЦена: ${price:.4f}\nБаланс: {balance:.2f} TON\n{warning}\n"
        f"✏️ Можно ввести свою сумму\n"
        f"Выбери сумму:",
        parse_mode="Markdown", reply_markup=sell_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("sell_amount_"))
async def sell_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_amount_", ""))
    price = await get_ton_price()
    
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
    
    if buy_positions:
        last_buy = buy_positions[-1]
        profit_data = calculate_net_profit(last_buy['price'], price, amount)
        
        profit_text = (
            f"\n💸 *Результат с комиссией:*\n"
            f"• Валовая прибыль: ${profit_data['gross_profit']:.4f}\n"
            f"• Комиссия: {profit_data['total_fee_ton']} TON (${profit_data['fee_usd']:.4f})\n"
            f"• Чистая прибыль: *${profit_data['net_profit']:.4f}*\n"
            f"• {'✅ Прибыльно!' if profit_data['is_profitable'] else '❌ Убыточно!'}"
        )
    else:
        profit_text = ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📉 *ПОДТВЕРЖДЕНИЕ ПРОДАЖИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Получишь: *${price * amount:.2f}*\n"
        f"{profit_text}",
        parse_mode="Markdown", reply_markup=keyboard    )

@dp.callback_query(lambda c: c.data.startswith("sell_confirm_"))
async def sell_confirm(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_confirm_", ""))
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    session = user_sessions.get(user_id, {'positions': []})
    session['positions'].append({
        'type': 'SELL',
        'amount': amount,
        'price': price,
        'time': datetime.now().isoformat()
    })
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ПРОДАНО {amount} TON* по ${price:.4f}",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "sell_wallet")
async def sell_wallet(callback: types.CallbackQuery):
    price = await get_ton_price()
    webapp_url = f"{TONCONNECT_URL}?action=sell&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Открыть кошелёк", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПРОДАЖА ЧЕРЕЗ КОШЕЛЁК*\n\nЦена: ${price:.4f}\nСумма: 0.5 TON\n\n"
        f"Нажми кнопку и подтверди в кошельке.",
        parse_mode="Markdown", reply_markup=keyboard
    )

# ========== СВОЯ СУММА ПРОДАЖИ ==========
@dp.callback_query(lambda c: c.data == "sell_custom")
async def sell_custom_prompt(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['awaiting_input'] = 'sell_amount'
    user_sessions[user_id] = session
    
    buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
    sell_positions = [p for p in session.get('positions', []) if p['type'] == 'SELL']
    total_bought = sum(p['amount'] for p in buy_positions)
    total_sold = sum(p['amount'] for p in sell_positions)
    balance = total_bought - total_sold
    
    await callback.message.edit_text(
        f"✏️ *Введите сумму продажи в TON*\n\n"
        f"Ваш баланс: *{balance:.2f} TON*\n\n"
        f"Просто отправьте число, например: `0.75` или `1.5`\n\n"
        f"⚠️ Не больше вашего баланса",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="sell_ton")]
        ])
    )

@dp.message(lambda message: user_sessions.get(message.from_user.id, {}).get('awaiting_input') == 'sell_amount')
async def process_custom_sell(message: types.Message):
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("❌ Введите число, например: `0.5`", parse_mode="Markdown")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше нуля")
        return
    
    session = user_sessions.get(user_id, {})
    buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
    sell_positions = [p for p in session.get('positions', []) if p['type'] == 'SELL']
    balance = sum(p['amount'] for p in buy_positions) - sum(p['amount'] for p in sell_positions)
    
    if amount > balance:
        await message.answer(f"❌ Недостаточно TON. Ваш баланс: {balance:.2f} TON")
        return
    
    session['awaiting_input'] = None
    user_sessions[user_id] = session
    
    price = await get_ton_price()
    if not price:
        await message.answer("❌ Не удалось получить цену")
        return
    
    if buy_positions:
        last_buy = buy_positions[-1]
        profit_data = calculate_net_profit(last_buy['price'], price, amount)
        
        profit_text = (
            f"\n💸 *Результат с комиссией:*\n"
            f"• Валовая прибыль: ${profit_data['gross_profit']:.4f}\n"
            f"• Комиссия: {profit_data['total_fee_ton']} TON (${profit_data['fee_usd']:.4f})\n"
            f"• Чистая прибыль: *${profit_data['net_profit']:.4f}*\n"
            f"• {'✅ Прибыльно!' if profit_data['is_profitable'] else '❌ Убыточно!'}"
        )
    else:
        profit_text = ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="sell_ton")]
    ])
    
    await message.answer(
        f"📉 *ПОДТВЕРЖДЕНИЕ ПРОДАЖИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Получишь: *${price * amount:.2f}*\n"
        f"{profit_text}",
        parse_mode="Markdown", reply_markup=keyboard
    )


# ========== ПОРТФЕЛЬ ==========
@dp.callback_query(lambda c: c.data == "positions")
async def show_positions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    positions = session.get('positions', [])
    price = await get_ton_price()
    
    if not positions:
        await callback.message.edit_text("📋 Портфель пуст.", reply_markup=main_keyboard())
        return
    
    buy_positions = [p for p in positions if p['type'] == 'BUY']
    sell_positions = [p for p in positions if p['type'] == 'SELL']
    
    total_bought = sum(p['amount'] for p in buy_positions)
    total_sold = sum(p['amount'] for p in sell_positions)
    balance = total_bought - total_sold
    
    text = f"📋 *ПОРТФЕЛЬ*\n\n💰 Баланс: *{balance:.2f} TON* (${balance * price:.2f})\n"
    text += f"📈 Куплено: {total_bought:.2f} TON\n📉 Продано: {total_sold:.2f} TON\n\n"
    
    if buy_positions:
        last_buy = buy_positions[-1]
        be = calculate_breakeven(last_buy['price'], last_buy['amount'], price)
        current_move = ((price - last_buy['price']) / last_buy['price']) * 100
        
        text += f"📊 *Последняя покупка:*\n"
        text += f"• {last_buy['amount']} TON @ ${last_buy['price']:.4f}\n"
        text += f"• Безубыток: ${be['breakeven_price']:.4f} (+{be['breakeven_percent']:.2f}%)\n"
        text += f"• Сейчас: {current_move:+.2f}%\n"
        
        if current_move >= be['breakeven_percent']:
            net = calculate_net_profit(last_buy['price'], price, last_buy['amount'])
            text += f"• ✅ Чистая прибыль при продаже: *${net['net_profit']:.4f}*"
        else:
            net = calculate_net_profit(last_buy['price'], price, last_buy['amount'])
            text += f"• ❌ При продаже убыток: *${net['net_profit']:.4f}*"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Безубыток", callback_data="breakeven_info")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )


# ========== АВТО-ТРЕЙДИНГ ==========
@dp.callback_query(lambda c: c.data == "auto_trade")
async def auto_trade_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    await callback.message.edit_text(
        f"🤖 *АВТО-ТРЕЙДИНГ*\n\n"
        f"Авто-сигналы: {'✅' if session.get('auto_trade') else '❌'}\n"
        f"DCA: {'✅' if session.get('dca_enabled') else '❌'}\n"
        f"Тейк-профит: {session.get('tp_percent', 3)}%\n"
        f"Стоп-лосс: {session.get('sl_percent', 7)}%\n\n"
        f"⚠️ Сигналы учитывают комиссию.\n"
        f"Сделка только если прибыль > комиссии.",
        parse_mode="Markdown",
        reply_markup=auto_keyboard(user_id)
    )

@dp.callback_query(lambda c: c.data == "toggle_auto")
async def toggle_auto(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['auto_trade'] = not session.get('auto_trade', False)
    user_sessions[user_id] = session
    await callback.answer(f"Авто-сигналы {'включены' if session['auto_trade'] else 'выключены'}", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_dca")
async def toggle_dca(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['dca_enabled'] = not session.get('dca_enabled', False)
    if session['dca_enabled']:
        price = await get_ton_price()
        if price:
            session['base_price'] = price
    user_sessions[user_id] = session
    await callback.answer(f"DCA {'включен' if session['dca_enabled'] else 'выключен'}", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "setup_tp")
async def setup_tp(callback: types.CallbackQuery):
    price = await get_ton_price()
    be = calculate_breakeven(price or 2.5, 0.5, price or 2.5)
    min_tp = max(2.0, be['breakeven_percent'] + 0.5)
    
    await callback.message.edit_text(
        f"🎯 *ТЕЙК-ПРОФИТ*\n\n"
        f"При каком росте продавать?\n"
        f"⚠️ Минимум *{min_tp:.1f}%* (безубыток + буфер)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{max(2, int(min_tp))}%", callback_data=f"tp_{max(2, int(min_tp))}")],
            [InlineKeyboardButton(text="3%", callback_data="tp_3")],
            [InlineKeyboardButton(text="5%", callback_data="tp_5")],
            [InlineKeyboardButton(text="10%", callback_data="tp_10")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("tp_"))
async def set_tp(callback: types.CallbackQuery):
    tp = float(callback.data.replace("tp_", ""))
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['tp_percent'] = tp
    user_sessions[user_id] = session
    await callback.answer(f"Тейк-профит: {tp}%", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "setup_sl")
async def setup_sl(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🛑 *СТОП-ЛОСС*\n\nПри каком падении продавать?\n"
        "⚠️ Учитывайте, что комиссия увеличит убыток.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="5%", callback_data="sl_5"), 
             InlineKeyboardButton(text="7%", callback_data="sl_7")],
            [InlineKeyboardButton(text="10%", callback_data="sl_10"), 
             InlineKeyboardButton(text="15%", callback_data="sl_15")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("sl_"))
async def set_sl(callback: types.CallbackQuery):
    sl = float(callback.data.replace("sl_", ""))
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['sl_percent'] = sl
    user_sessions[user_id] = session
    await callback.answer(f"Стоп-лосс: {sl}%", show_alert=True)
    await auto_trade_menu(callback)


# ========== НАСТРОЙКИ ==========
@dp.callback_query(lambda c: c.data == "settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    await callback.message.edit_text(
        f"⚙️ *НАСТРОЙКИ*\n\n"
        f"🔔 Сигналы: {'✅' if session.get('alerts_enabled', True) else '❌'}\n"
        f"🤖 Авто-трейдинг: {'✅' if session.get('auto_trade') else '❌'}\n"
        f"📊 DCA: {'✅' if session.get('dca_enabled') else '❌'}\n"
        f"💸 Комиссия сети: {NETWORK_FEE} TON",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Сигналы вкл/выкл", callback_data="toggle_alerts")],
            [InlineKeyboardButton(text="💸 Безубыток", callback_data="breakeven_info")],
            [InlineKeyboardButton(text="🗑 Сбросить историю", callback_data="reset_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )

@dp.callback_query(lambda c: c.data == "toggle_alerts")
async def toggle_alerts(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['alerts_enabled'] = not session.get('alerts_enabled', True)
    user_sessions[user_id] = session
    await callback.answer(f"Сигналы {'включены' if session['alerts_enabled'] else 'выключены'}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "reset_history")
async def reset_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['positions'] = []
    session['base_price'] = None
    user_sessions[user_id] = session
    await callback.message.edit_text("🗑 История сброшена.", reply_markup=main_keyboard())


# ========== НАЗАД И ПОМОЩЬ ==========
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🤖 Главное меню:", reply_markup=main_keyboard())

@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *ПОМОЩЬ*\n\n"
        "• 💰 Цена — курс TON\n"
        "• 📊 Теханализ — с учётом безубытка\n"
        "• 📈/📉 Сделки — выбор суммы или своя\n"
        "• ✏️ Своя сумма — ввод любого числа\n"
        "• 💸 Безубыток — мин. цена для прибыли\n"
        "• 🤖 Авто — сигналы только если выгодно\n\n"
        f"Комиссия сети: {NETWORK_FEE} TON за транзакцию\n"
        "🔐 Ключи только у тебя!",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )


# ========== ФОНОВЫЙ МОНИТОРИНГ ==========
async def background_monitor():
    last_price = None
    
    while True:
        await asyncio.sleep(60)
        
        price = await get_ton_price()
        if not price:
            continue
        
        analyzer.add_price(price)
        
        if not last_price:
            last_price = price
            continue
        
        change_pct = ((price - last_price) / last_price) * 100
        
        for user_id, session in user_sessions.items():
            if not session.get('auto_trade'):
                continue
            
            buy_positions = [p for p in session.get('positions', []) if p['type'] == 'BUY']
            last_buy = buy_positions[-1] if buy_positions else None
            
            signal = analyzer.get_signal(
                buy_price=last_buy['price'] if last_buy else None,
                amount=last_buy['amount'] if last_buy else None
            )
            
            if signal and signal['signal'] == 'BUY' and signal['confidence'] >= 60:
                await send_signal(user_id, 'BUY', price, signal['confidence'], "теханализу")
            
            elif signal and signal['signal'] == 'SELL' and signal['confidence'] >= 60:
                if last_buy:
                    be = calculate_breakeven(last_buy['price'], last_buy['amount'], price)
                    if price >= be['breakeven_price']:
                        net = calculate_net_profit(last_buy['price'], price, last_buy['amount'])
                        await send_signal(user_id, 'SELL', price, signal['confidence'], 
                                        f"теханализу (чистая прибыль: ${net['net_profit']:.4f})")
            
            elif change_pct <= -1:
                await send_signal(user_id, 'BUY', price, 70, f"падению на {abs(change_pct):.1f}%")
            
            elif change_pct >= 2:
                if last_buy:
                    be = calculate_breakeven(last_buy['price'], last_buy['amount'], price)
                    if price >= be['breakeven_price']:
                        await send_signal(user_id, 'SELL', price, 70, f"росту на {change_pct:.1f}%")
            
            # DCA
            if session.get('dca_enabled'):
                base_price = session.get('base_price', price)
                drop = ((base_price - price) / base_price) * 100
                dca = session.get('dca_config', {})
                
                min_drop = dca.get('drop_percent', 1.5) + 0.5
                
                if drop >= min_drop * (dca.get('bought_parts', 0) + 1):
                    if dca.get('bought_parts', 0) < dca.get('parts', 3):
                        part_amount = dca.get('total_amount', 1.0) / dca.get('parts', 3)
                        be = calculate_breakeven(price, part_amount, price)
                        try:
                            await bot.send_message(
                                user_id,
                                f"📊 *DCA СИГНАЛ*\nПадение на {drop:.1f}%\n"
                                f"Покупка части {dca['bought_parts'] + 1}/{dca['parts']}: *{part_amount:.2f} TON*\n"
                                f"Цена: ${price:.4f}\n"
                                f"Безубыток: +{be['breakeven_percent']:.2f}%",
                                parse_mode="Markdown"
                            )
                            dca['bought_parts'] += 1
                            dca['buy_prices'].append(price)
                            session['dca_config'] = dca
                        except:
                            pass
            
            # Тейк-профит и стоп-лосс
            for pos in session.get('positions', []):
                if pos['type'] != 'BUY':
                    continue
                
                net = calculate_net_profit(pos['price'], price, pos['amount'])
                
                if net['net_profit_percent'] >= session.get('tp_percent', 3):
                    try:
                        await bot.send_message(
                            user_id,
                            f"🎯 *ТЕЙК-ПРОФИТ!*\n\n"
                            f"Чистая прибыль: *+{net['net_profit_percent']:.2f}%*\n"
                            f"Комиссия учтена: {net['total_fee_ton']} TON\n"
                            f"Прибыль: *${net['net_profit']:.4f}*\n"
                            f"Цена: ${pos['price']:.4f} → ${price:.4f}",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💰 Продать", callback_data=f"sell_amount_{pos['amount']}")]
                            ])
                        )
                    except:
                        pass
                
                elif net['net_profit_percent'] <= -session.get('sl_percent', 7):
                    try:
                        await bot.send_message(
                            user_id,
                            f"🛑 *СТОП-ЛОСС!*\n\n"
                            f"Чистый убыток: *{net['net_profit_percent']:.2f}%*\n"
                            f"С учётом комиссии: {net['total_fee_ton']} TON\n"
                            f"Убыток: *${net['net_profit']:.4f}*",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🛑 Продать", callback_data=f"sell_amount_{pos['amount']}")]
                            ])
                        )
                    except:
                        pass
        
        last_price = price


async def send_signal(user_id, signal_type, price, confidence, reason):
    emoji = "🟢" if signal_type == 'BUY' else "🔴"
    action = "ПОКУПКУ" if signal_type == 'BUY' else "ПРОДАЖУ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'💎 Купить' if signal_type == 'BUY' else '💰 Продать'} 0.5 TON",
            callback_data=f"{'buy' if signal_type == 'BUY' else 'sell'}_amount_0.5"
        )],
        [InlineKeyboardButton(text="📊 Теханализ", callback_data="tech_analysis")],
        [InlineKeyboardButton(text="💸 Безубыток", callback_data="breakeven_info")],
        [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🔔 *СИГНАЛ НА {action}*\n\n"
            f"{emoji} По {reason}\n"
            f"Цена: *${price:.4f}*\n"
            f"Уверенность: *{confidence:.0f}%*\n"
            f"Комиссия учтена в сигнале ✅",
            parse_mode="Markdown", reply_markup=keyboard
        )
    except:
        pass


# ========== ЗАПУСК ==========
async def main():
    print("🤖 TON Trading Bot v4.3 запущен!")
    print(f"💸 Комиссия сети: {NETWORK_FEE} TON")
    print("📊 Сигналы с учётом безубытка")
    print("✏️ Своя сумма покупки/продажи")
    print("✅ Сделки только если прибыль > комиссии")
    
    for _ in range(20):
        price = await get_ton_price()
        if price:
            analyzer.add_price(price)
        await asyncio.sleep(1)
    
    print(f"✅ Загружено {len(analyzer.price_history)} точек данных")
    
    asyncio.create_task(background_monitor())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
