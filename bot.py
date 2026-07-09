import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from strategies import get_strategy, user_strategies

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"
TONCONNECT_URL = "https://acewolfff.github.io/ton-trader-bot/"

# ========== ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ ==========
user_sessions = {}  # user_id -> настройки и позиции

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена TON", callback_data="check_price")],
        [InlineKeyboardButton(text="📈 Купить TON", callback_data="buy_ton")],
        [InlineKeyboardButton(text="📉 Продать TON", callback_data="sell_ton")],
        [InlineKeyboardButton(text="🤖 Авто-трейдинг", callback_data="auto_trade")],
        [InlineKeyboardButton(text="📊 Стратегии", callback_data="strategies")],
        [InlineKeyboardButton(text="📋 Портфель", callback_data="positions")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def buy_keyboard(price=None):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="buy_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="buy_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="buy_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="buy_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def sell_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="sell_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="sell_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="sell_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="sell_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def auto_keyboard(user_id):
    session = user_sessions.get(user_id, {})
    auto_status = "✅ Включен" if session.get('auto_trade') else "❌ Выключен"
    dca_status = "✅ Включен" if session.get('dca_enabled') else "❌ Выключен"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Авто-сигналы: {auto_status}", 
            callback_data="toggle_auto"
        )],
        [InlineKeyboardButton(
            text=f"DCA стратегия: {dca_status}", 
            callback_data="toggle_dca"
        )],
        [InlineKeyboardButton(text="⚙️ Настроить DCA", callback_data="setup_dca")],
        [InlineKeyboardButton(text="⚙️ Настроить тейк-профит", callback_data="setup_tp")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def strategies_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 DCA (усреднение)", callback_data="strategy_dca")],
        [InlineKeyboardButton(text="🎯 Тейк-профит", callback_data="strategy_tp")],
        [InlineKeyboardButton(text="🛑 Стоп-лосс", callback_data="strategy_sl")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

# ========== ПОЛУЧЕНИЕ ЦЕНЫ ==========
async def get_ton_price():
    """Получает цену TON из нескольких источников"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd',
                timeout=10
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
                'https://api.ston.fi/v1/markets/EQCG2Dw1-Pk9b0mQKhn-GYkUNq2jRm5SGL5aJJhkNWQEiIpr',
                timeout=10
            ) as resp:
                data = await resp.json()
                return float(data.get('rate', 0))
    except:
        return None

# ========== КОМАНДА /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    user_sessions[user_id] = {
        'last_price': None,
        'base_price': None,  # Цена для DCA отсчёта
        'positions': [],
        'auto_trade': False,
        'dca_enabled': False,
        'dca_config': {
            'total_amount': 1.0,
            'parts': 3,
            'drop_percent': 1.5,
            'bought_parts': 0,
            'buy_prices': []
        },
        'tp_percent': 3.0,
        'sl_percent': 7.0,
        'alerts_enabled': True,
        'sudden_move_alerts': True
    }
    
    await message.answer(
        "🤖 *TON Trading Bot v2.0*\n\n"
        "Теперь с поддержкой кошелька TonConnect и продвинутыми стратегиями!\n\n"
        "🚀 *Новые функции:*\n"
        "• 📱 Подтверждение сделок через кошелёк\n"
        "• 📊 DCA — усреднение при падении\n"
        "• 🎯 Тейк-профит и стоп-лосс\n"
        "• ⚡ Алерты о резких движениях\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ЦЕНА ==========
@dp.callback_query(lambda c: c.data == "check_price")
async def check_price(callback: types.CallbackQuery):
    await callback.answer("⏳ Загружаю...")
    
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    if not price:
        await callback.message.edit_text(
            "❌ Не удалось получить цену. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return
    
    session = user_sessions.get(user_id, {})
    old_price = session.get('last_price')
    session['last_price'] = price
    
    # Обновляем историю цен в стратегии
    strategy = get_strategy(user_id)
    strategy.add_price(price)
    
    user_sessions[user_id] = session
    
    change_text = ""
    if old_price:
        change = ((price - old_price) / old_price) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        change_text = f"\nИзменение: {emoji} {change:+.2f}%"
    
    # Проверяем резкие движения
    alert = strategy.check_sudden_move()
    alert_text = ""
    if alert:
        severity_emoji = "🔴" if alert['severity'] == 'high' else "🟡"
        alert_text = (
            f"\n\n{severity_emoji} *ВНИМАНИЕ! Резкое движение!*\n"
            f"{'📈 Рост' if alert['direction'] == 'up' else '📉 Падение'} "
            f"на {abs(alert['change_pct']):.1f}% за 5 минут!"
        )
    
    await callback.message.edit_text(
        f"💰 *TON / USD*\n\n"
        f"Текущая цена: *${price:.4f}*{change_text}{alert_text}\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПОКУПКА ==========
@dp.callback_query(lambda c: c.data == "buy_ton")
async def buy_ton_menu(callback: types.CallbackQuery):
    price = await get_ton_price()
    await callback.message.edit_text(
        f"📈 *Покупка TON*\n\n"
        f"Текущая цена: ${price:.4f}\n\n"
        f"Выбери сумму или купи через кошелёк:",
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
    
    total = price * amount
    
    # Показываем подтверждение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"buy_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📈 *ПОДТВЕРЖДЕНИЕ ПОКУПКИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f} за TON*\n"
        f"Итого: *${total:.2f}*\n\n"
        f"Нажми «Подтверждаю» чтобы записать сделку.",
        parse_mode="Markdown",
        reply_markup=keyboard
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
    
    # Если это первая покупка, сохраняем как базовую цену для DCA
    if not session.get('base_price'):
        session['base_price'] = price
    
    user_sessions[user_id] = session
    
    total = price * amount
    
    await callback.message.edit_text(
        f"✅ *ПОКУПКА СОВЕРШЕНА*\n\n"
        f"Куплено: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Сумма: *${total:.2f}*\n\n"
        f"💡 *Совет:* Включи тейк-профит чтобы "
        f"автоматически зафиксировать прибыль при росте.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "buy_wallet")
async def buy_wallet(callback: types.CallbackQuery):
    """Покупка через кошелёк TonConnect"""
    price = await get_ton_price()
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    # Кнопка открывает Mini App
    webapp_url = f"{TONCONNECT_URL}?action=buy&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💎 Открыть кошелёк для покупки",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПОКУПКА ЧЕРЕЗ КОШЕЛЁК*\n\n"
        f"Нажми кнопку ниже чтобы открыть Mini App.\n"
        f"Там ты подключишь кошелёк и подтвердишь транзакцию.\n\n"
        f"Цена: *${price:.4f}*\n"
        f"Сумма: *0.5 TON*\n\n"
        f"🔐 Твои ключи остаются только в кошельке!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ========== ПРОДАЖА ==========
@dp.callback_query(lambda c: c.data == "sell_ton")
async def sell_ton_menu(callback: types.CallbackQuery):
    price = await get_ton_price()
    await callback.message.edit_text(
        f"📉 *Продажа TON*\n\n"
        f"Текущая цена: ${price:.4f}\n\n"
        f"Выбери сумму:",
        parse_mode="Markdown",
        reply_markup=sell_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("sell_amount_"))
async def sell_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_amount_", ""))
    price = await get_ton_price()
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    total = price * amount
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📉 *ПОДТВЕРЖДЕНИЕ ПРОДАЖИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f} за TON*\n"
        f"Ты получишь: *${total:.2f}*\n\n"
        f"Нажми «Подтверждаю» чтобы записать сделку.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

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
    
    # Сбрасываем DCA если всё продано
    buy_positions = [p for p in session['positions'] if p['type'] == 'BUY']
    total_bought = sum(p['amount'] for p in buy_positions)
    total_sold = sum(p['amount'] for p in session['positions'] if p['type'] == 'SELL')
    
    if total_sold >= total_bought:
        session['base_price'] = None
        session['dca_config']['bought_parts'] = 0
        session['dca_config']['buy_prices'] = []
    
    user_sessions[user_id] = session
    
    total = price * amount
    
    await callback.message.edit_text(
        f"✅ *ПРОДАЖА СОВЕРШЕНА*\n\n"
        f"Продано: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Получено: *${total:.2f}*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "sell_wallet")
async def sell_wallet(callback: types.CallbackQuery):
    """Продажа через кошелёк"""
    price = await get_ton_price()
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    webapp_url = f"{TONCONNECT_URL}?action=sell&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💰 Открыть кошелёк для продажи",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПРОДАЖА ЧЕРЕЗ КОШЕЛЁК*\n\n"
        f"Нажми кнопку ниже чтобы открыть Mini App.\n"
        f"Подтверди транзакцию в кошельке.\n\n"
        f"Цена: *${price:.4f}*\n"
        f"Сумма: *0.5 TON*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ========== АВТО-ТРЕЙДИНГ ==========
@dp.callback_query(lambda c: c.data == "auto_trade")
async def auto_trade_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    auto_status = "✅ Включен" if session.get('auto_trade') else "❌ Выключен"
    dca_status = "✅ Включен" if session.get('dca_enabled') else "❌ Выключен"
    
    await callback.message.edit_text(
        f"🤖 *АВТО-ТРЕЙДИНГ*\n\n"
        f"Авто-сигналы: {auto_status}\n"
        f"DCA стратегия: {dca_status}\n"
        f"Тейк-профит: {session.get('tp_percent', 3.0)}%\n"
        f"Стоп-лосс: {session.get('sl_percent', 7.0)}%\n\n"
        f"Выбери настройку:",
        parse_mode="Markdown",
        reply_markup=auto_keyboard(user_id)
    )

@dp.callback_query(lambda c: c.data == "toggle_auto")
async def toggle_auto(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['auto_trade'] = not session.get('auto_trade', False)
    user_sessions[user_id] = session
    
    await callback.answer(
        f"Авто-сигналы {'включены' if session['auto_trade'] else 'выключены'} ✅",
        show_alert=True
    )
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_dca")
async def toggle_dca(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['dca_enabled'] = not session.get('dca_enabled', False)
    
    if session['dca_enabled']:
        # Сохраняем текущую цену как базовую для DCA
        price = await get_ton_price()
        if price:
            session['base_price'] = price
    
    user_sessions[user_id] = session
    
    await callback.answer(
        f"DCA {'включен' if session['dca_enabled'] else 'выключен'} ✅",
        show_alert=True
    )
    await auto_trade_menu(callback)

# ========== СТРАТЕГИИ ==========
@dp.callback_query(lambda c: c.data == "strategies")
async def strategies_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📊 *ТОРГОВЫЕ СТРАТЕГИИ*\n\n"
        "• *DCA* — усреднение цены при падении\n"
        "  Покупает частями при каждом снижении на X%\n\n"
        "• *Тейк-профит* — фиксация прибыли\n"
        "  Сигнал на продажу при росте на X%\n\n"
        "• *Стоп-лосс* — ограничение убытков\n"
        "  Сигнал на продажу при падении на X%",
        parse_mode="Markdown",
        reply_markup=strategies_keyboard()
    )

@dp.callback_query(lambda c: c.data == "strategy_dca")
async def strategy_dca_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    dca = session.get('dca_config', {})
    
    await callback.message.edit_text(
        f"📊 *DCA (Dollar Cost Averaging)*\n\n"
        f"Стратегия усреднения цены:\n"
        f"• Общая сумма: *{dca.get('total_amount', 1.0)} TON*\n"
        f"• Количество частей: *{dca.get('parts', 3)}*\n"
        f"• Покупка при падении на каждые: *{dca.get('drop_percent', 1.5)}%*\n"
        f"• Куплено частей: *{dca.get('bought_parts', 0)}*\n\n"
        f"*Как работает:*\n"
        f"Цена упала на 1.5% → покупка 1/3\n"
        f"Цена упала на 3.0% → покупка 2/3\n"
        f"Цена упала на 4.5% → покупка 3/3\n\n"
        f"Средняя цена будет ниже рыночной 📉",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настроить", callback_data="setup_dca")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="strategies")]
        ])
    )

@dp.callback_query(lambda c: c.data == "strategy_tp")
async def strategy_tp_info(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🎯 *ТЕЙК-ПРОФИТ*\n\n"
        f"Автоматическая фиксация прибыли.\n\n"
        f"*Как работает:*\n"
        f"Ты купил TON по $2.00\n"
        f"Тейк-профит установлен на 5%\n"
        f"Когда цена достигнет $2.10 → сигнал на продажу\n\n"
        f"*Рекомендации:*\n"
        f"• Консервативно: 2-3%\n"
        f"• Умеренно: 5-7%\n"
        f"• Агрессивно: 10%+\n\n"
        f"Настрой в разделе «Авто-трейдинг»",
        parse_mode="Markdown",
        reply_markup=strategies_keyboard()
    )

@dp.callback_query(lambda c: c.data == "strategy_sl")
async def strategy_sl_info(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🛑 *СТОП-ЛОСС*\n\n"
        f"Защита от больших потерь.\n\n"
        f"*Как работает:*\n"
        f"Ты купил TON по $2.00\n"
        f"Стоп-лосс установлен на 5%\n"
        f"Когда цена упадёт до $1.90 → сигнал на продажу\n\n"
        f"*Рекомендации:*\n"
        f"• Всегда использовать!\n"
        f"• Оптимально: 5-10%\n"
        f"• Максимум: 15%\n\n"
        f"Настрой в разделе «Авто-трейдинг»",
        parse_mode="Markdown",
        reply_markup=strategies_keyboard()
    )

# ========== НАСТРОЙКА DCA ==========
@dp.callback_query(lambda c: c.data == "setup_dca")
async def setup_dca(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ *НАСТРОЙКА DCA*\n\n"
        "Выбери общую сумму для стратегии:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="0.5 TON (3 части)", callback_data="dca_set_0.5_3")],
            [InlineKeyboardButton(text="1.0 TON (3 части)", callback_data="dca_set_1.0_3")],
            [InlineKeyboardButton(text="1.0 TON (5 частей)", callback_data="dca_set_1.0_5")],
            [InlineKeyboardButton(text="2.0 TON (4 части)", callback_data="dca_set_2.0_4")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("dca_set_"))
async def dca_set(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    total = float(parts[2])
    parts_count = int(parts[3])
    
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['dca_config'] = {
        'total_amount': total,
        'parts': parts_count,
        'drop_percent': 1.5,
        'bought_parts': 0,
        'buy_prices': []
    }
    session['dca_enabled'] = True
    
    # Устанавливаем базовую цену
    price = await get_ton_price()
    if price:
        session['base_price'] = price
    
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *DCA НАСТРОЕН*\n\n"
        f"Сумма: *{total} TON*\n"
        f"Частей: *{parts_count}*\n"
        f"По: *{total/parts_count:.2f} TON* каждая\n"
        f"Покупка при падении на каждые 1.5%\n\n"
        f"Базовая цена: *${price:.4f}*\n\n"
        f"Стратегия активирована! 🤖",
        parse_mode="Markdown",
        reply_markup=auto_keyboard(user_id)
    )

# ========== НАСТРОЙКА ТЕЙК-ПРОФИТ ==========
@dp.callback_query(lambda c: c.data == "setup_tp")
async def setup_tp(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎯 *НАСТРОЙКА ТЕЙК-ПРОФИТА*\n\n"
        "При каком росте сигнализировать о продаже?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="2% (консервативно)", callback_data="tp_set_2")],
            [InlineKeyboardButton(text="3% (умеренно)", callback_data="tp_set_3")],
            [InlineKeyboardButton(text="5% (агрессивно)", callback_data="tp_set_5")],
            [InlineKeyboardButton(text="10% (очень агрессивно)", callback_data="tp_set_10")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("tp_set_"))
async def tp_set(callback: types.CallbackQuery):
    tp = float(callback.data.replace("tp_set_", ""))
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['tp_percent'] = tp
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ТЕЙК-ПРОФИТ УСТАНОВЛЕН*\n\n"
        f"Продажа при росте на: *{tp}%*\n\n"
        f"Бот будет присылать сигнал когда цена вырастет на {tp}% "
        f"от цены покупки.",
        parse_mode="Markdown",
        reply_markup=auto_keyboard(user_id)
    )

# ========== ПОРТФЕЛЬ ==========
@dp.callback_query(lambda c: c.data == "positions")
async def show_positions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    positions = session.get('positions', [])
    price = await get_ton_price()
    
    if not positions:
        await callback.message.edit_text(
            "📋 *ПОРТФЕЛЬ ПУСТ*\n\n"
            "У тебя нет открытых позиций.\n"
            "Начни с покупки TON! 📈",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return
    
    # Считаем статистику
    buy_positions = [p for p in positions if p['type'] == 'BUY']
    sell_positions = [p for p in positions if p['type'] == 'SELL']
    
    total_bought = sum(p['amount'] for p in buy_positions)
    total_spent = sum(p['amount'] * p['price'] for p in buy_positions)
    avg_buy_price = total_spent / total_bought if total_bought > 0 else 0
    
    total_sold = sum(p['amount'] for p in sell_positions)
    total_received = sum(p['amount'] * p['price'] for p in sell_positions)
    
    balance = total_bought - total_sold
    current_value = balance * price if price else 0
    
    # P&L
    realized_pnl = total_received - (sum(p['amount'] * avg_buy_price for p in sell_positions) if sell_positions else 0)
    unrealized_pnl = (price - avg_buy_price) * balance if price and balance > 0 else 0
    
    text = "📋 *ПОРТФЕЛЬ*\n\n"
    text += f"💰 Баланс: *{balance:.2f} TON*\n"
    text += f"💵 Текущая стоимость: *${current_value:.2f}*\n\n"
    
    text += "📈 *Статистика покупок:*\n"
    text += f"• Куплено: {total_bought:.2f} TON\n"
    text += f"• Средняя цена: ${avg_buy_price:.4f}\n"
    text += f"• Потрачено: ${total_spent:.2f}\n\n"
    
    text += "📉 *Статистика продаж:*\n"
    text += f"• Продано: {total_sold:.2f} TON\n"
    text += f"• Получено: ${total_received:.2f}\n\n"
    
    if realized_pnl != 0:
        emoji = "🟢" if realized_pnl >= 0 else "🔴"
        text += f"📊 Реализованный P&L: {emoji} ${realized_pnl:+.2f}\n"
    
    if unrealized_pnl != 0:
        emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
        text += f"📊 Нереализованный P&L: {emoji} ${unrealized_pnl:+.2f}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== НАСТРОЙКИ ==========
@dp.callback_query(lambda c: c.data == "settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    alerts_status = "✅" if session.get('alerts_enabled', True) else "❌"
    sudden_status = "✅" if session.get('sudden_move_alerts', True) else "❌"
    
    await callback.message.edit_text(
        f"⚙️ *НАСТРОЙКИ*\n\n"
        f"🔔 Обычные сигналы: {alerts_status}\n"
        f"⚡ Алерты резких движений: {sudden_status}\n"
        f"🎯 Тейк-профит: {session.get('tp_percent', 3.0)}%\n"
        f"🛑 Стоп-лосс: {session.get('sl_percent', 7.0)}%\n\n"
        f"Выбери что настроить:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Вкл/выкл сигналы", callback_data="toggle_alerts")],
            [InlineKeyboardButton(text="⚡ Вкл/выкл резкие алерты", callback_data="toggle_sudden")],
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
    
    await callback.answer(
        f"Сигналы {'включены' if session['alerts_enabled'] else 'выключены'}",
        show_alert=True
    )
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_sudden")
async def toggle_sudden(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['sudden_move_alerts'] = not session.get('sudden_move_alerts', True)
    user_sessions[user_id] = session
    
    await callback.answer(
        f"Резкие алерты {'включены' if session['sudden_move_alerts'] else 'выключены'}",
        show_alert=True
    )
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "reset_history")
async def reset_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['positions'] = []
    session['base_price'] = None
    session['dca_config']['bought_parts'] = 0
    session['dca_config']['buy_prices'] = []
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        "🗑 *ИСТОРИЯ СБРОШЕНА*\n\n"
        "Все позиции удалены. Можно начинать заново!",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== НАЗАД ==========
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤖 *Главное меню*\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПОМОЩЬ ==========
@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *ПОМОЩЬ*\n\n"
        "*Основные функции:*\n"
        "• 💰 Цена TON — текущий курс\n"
        "• 📈 Купить TON — покупка вручную или через кошелёк\n"
        "• 📉 Продать TON — продажа вручную или через кошелёк\n\n"
        "*Авто-трейдинг:*\n"
        "• 🤖 Авто-сигналы — бот мониторит цену и присылает сигналы\n"
        "• 📊 DCA — автоматическая покупка частями при падении\n"
        "• 🎯 Тейк-профит — сигнал при достижении прибыли\n"
        "• 🛑 Стоп-лосс — сигнал при убытке\n\n"
        "*Безопасность:*\n"
        "• Бот не имеет доступа к кошельку\n"
        "• Сделки через кошелёк подтверждаешь ты\n"
        "• Ключи хранятся только у тебя 🔐\n\n"
        "По вопросам: @your_support",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ФОНОВЫЙ МОНИТОРИНГ ==========
async def background_monitor():
    """Фоновый мониторинг для всех пользователей"""
    last_price = None
    
    while True:
        await asyncio.sleep(45)  # Проверка каждые 45 секунд
        price = await get_ton_price()
        
        if not price:
            continue
        
        if not last_price:
            last_price = price
            continue
        
        change_pct = ((price - last_price) / last_price) * 100
        
        for user_id, session in user_sessions.items():
            strategy = get_strategy(user_id)
            strategy.add_price(price)
            
            # 1. Проверка резких движений
            if session.get('sudden_move_alerts', True):
                alert = strategy.check_sudden_move()
                if alert:
                    await send_sudden_alert(user_id, alert)
            
            # 2. Обычные сигналы (авто-трейдинг)
            if session.get('auto_trade'):
                if change_pct <= -1:
                    await send_trade_signal(user_id, 'BUY', price, abs(change_pct))
                elif change_pct >= 2:
                    await send_trade_signal(user_id, 'SELL', price, change_pct)
            
            # 3. DCA стратегия
            if session.get('dca_enabled'):
                dca_signal = strategy.check_dca_signal(
                    session.get('base_price', price),
                    price,
                    session.get('dca_config', {})
                )
                if dca_signal:
                    await send_dca_signal(user_id, dca_signal)
                    # Обновляем конфиг DCA
                    session['dca_config']['bought_parts'] += 1
                    session['dca_config']['buy_prices'].append(price)
            
            # 4. Тейк-профит и стоп-лосс
            for position in session.get('positions', []):
                if position['type'] != 'BUY':
                    continue
                
                tp_signal = strategy.check_take_profit(
                    position, price, session.get('tp_percent', 3.0)
                )
                if tp_signal:
                    await send_tp_signal(user_id, tp_signal)
                
                sl_signal = strategy.check_stop_loss(
                    position, price, session.get('sl_percent', 7.0)
                )
                if sl_signal:
                    await send_sl_signal(user_id, sl_signal)
        
        last_price = price

async def send_sudden_alert(user_id, alert):
    """Отправляет экстренное уведомление"""
    emoji = "🔴🔴🔴" if alert['severity'] == 'high' else "🟡"
    direction = "📈 РОСТ" if alert['direction'] == 'up' else "📉 ПАДЕНИЕ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Проверить цену", callback_data="check_price")],
        [InlineKeyboardButton(
            text="📈 Купить" if alert['direction'] == 'down' else "📉 Продать",
            callback_data="buy_ton" if alert['direction'] == 'down' else "sell_ton"
        )]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"{emoji} *ЭКСТРЕННОЕ УВЕДОМЛЕНИЕ*\n\n"
            f"{direction} на *{abs(alert['change_pct']):.1f}%* за 5 минут!\n\n"
            f"Было: ${alert['old_price']:.4f}\n"
            f"Стало: ${alert['current_price']:.4f}\n\n"
            f"⚠️ Рекомендуется проверить позиции!",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_trade_signal(user_id, signal_type, price, change_pct):
    """Отправляет обычный торговый сигнал"""
    emoji = "📈" if signal_type == 'BUY' else "📉"
    action_text = "ПОКУПКУ" if signal_type == 'BUY' else "ПРОДАЖУ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'💎 Купить' if signal_type == 'BUY' else '💰 Продать'} 0.5 TON",
            callback_data=f"{'buy' if signal_type == 'BUY' else 'sell'}_amount_0.5"
        )],
        [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🔔 *СИГНАЛ НА {action_text}*\n\n"
            f"{emoji} Цена изменилась на *{change_pct:+.1f}%*\n"
            f"Текущая цена: *${price:.4f}*\n\n"
            f"Рекомендация: {'купить' if signal_type == 'BUY' else 'продать'} TON",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_dca_signal(user_id, signal):
    """Отправляет сигнал DCA"""
    try:
        await bot.send_message(
            user_id,
            f"📊 *DCA СИГНАЛ*\n\n"
            f"Цена упала на *{signal['drop_percent']:.1f}%*\n"
            f"Покупка части *{signal['part']}/{signal['total_parts']}*\n"
            f"Сумма: *{signal['amount']} TON*\n"
            f"Цена: *${signal['price']:.4f}*\n\n"
            f"Средняя цена снижается 📉",
            parse_mode="Markdown"
        )
    except:
        pass

async def send_tp_signal(user_id, signal):
    """Отправляет сигнал тейк-профита"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💰 Зафиксировать прибыль",
            callback_data=f"sell_amount_{signal['amount']}"
        )]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🎯 *ТЕЙК-ПРОФИТ!*\n\n"
            f"Цена выросла на *{signal['profit_pct']:.1f}%*\n"
            f"Куплено по: ${signal['buy_price']:.4f}\n"
            f"Текущая цена: ${signal['sell_price']:.4f}\n"
            f"Прибыль: *${signal['profit_ton']:.2f}*\n\n"
            f"Рекомендация: продать {signal['amount']} TON",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_sl_signal(user_id, signal):
    """Отправляет сигнал стоп-лосса"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛑 Продать сейчас",
            callback_data=f"sell_amount_{signal['amount']}"
        )]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🛑 *СТОП-ЛОСС!*\n\n"
            f"Цена упала на *{signal['loss_pct']:.1f}%*\n"
            f"Куплено по: ${signal['buy_price']:.4f}\n"
            f"Текущая цена: ${signal['sell_price']:.4f}\n"
            f"Убыток: *${signal['loss_ton']:.2f}*\n\n"
            f"Рекомендация: продать чтобы ограничить потери",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

# ========== ЗАПУСК ==========
async def main():
    print("🤖 TON Trading Bot v2.0 запускается...")
    print("📊 Стратегии: DCA, Take Profit, Stop Loss")
    print("🔐 TonConnect для безопасных транзакций")
    print("⚡ Алерты резких движений активированы")
    
    # Запускаем фоновый мониторинг
    asyncio.create_task(background_monitor())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
