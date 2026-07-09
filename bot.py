import asyncio
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"  # Замени на свой токен

# ========== ХРАНИЛИЩЕ ==========
user_sessions = {}

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Проверить цену", callback_data="check_price")],
        [InlineKeyboardButton(text="📈 Купить TON", callback_data="buy_ton")],
        [InlineKeyboardButton(text="📉 Продать TON", callback_data="sell_ton")],
        [InlineKeyboardButton(text="🤖 Авто-трейдинг", callback_data="auto_trade")],
        [InlineKeyboardButton(text="📋 Мои позиции", callback_data="positions")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="buy_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="buy_amount_0.5")],
        [InlineKeyboardButton(text="1 TON", callback_data="buy_amount_1.0")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])

def sell_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="sell_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="sell_amount_0.5")],
        [InlineKeyboardButton(text="1 TON", callback_data="sell_amount_1.0")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])

def auto_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Включить авто-трейдинг", callback_data="auto_on")],
        [InlineKeyboardButton(text="⏸ Выключить авто-трейдинг", callback_data="auto_off")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

# ========== ПОЛУЧЕНИЕ ЦЕНЫ ==========
async def get_ton_price():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd',
                timeout=10
            ) as resp:
                data = await resp.json()
                return data.get('the-open-network', {}).get('usd')
    except:
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
        'positions': [],
        'auto_trade': False,
        'buy_amount': 0.5
    }
    
    await message.answer(
        "🤖 *TON Trading Bot*\n\n"
        "Я помогаю торговать TON прямо в Telegram.\n\n"
        "• Слежу за ценой 24/7\n"
        "• Присылаю сигналы на покупку и продажу\n"
        "• Авто-трейдинг с подтверждением\n\n"
        "⚠️ *Важно:* Я только даю сигналы и рекомендации. "
        "Ты сам решаешь, совершать сделку или нет.\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПРОВЕРКА ЦЕНЫ ==========
@dp.callback_query(lambda c: c.data == "check_price")
async def check_price(callback: types.CallbackQuery):
    await callback.answer("Загружаю цену...")
    
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    if price:
        session = user_sessions.get(user_id, {})
        old_price = session.get('last_price')
        session['last_price'] = price
        user_sessions[user_id] = session
        
        change_text = ""
        if old_price:
            change = ((price - old_price) / old_price) * 100
            emoji = "🟢" if change >= 0 else "🔴"
            change_text = f"\nИзменение: {emoji} {change:+.2f}%"
        
        await callback.message.edit_text(
            f"💰 *TON / USD*\n\n"
            f"Текущая цена: *${price:.4f}*{change_text}\n"
            f"Обновлено: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"Выбери действие:",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось получить цену. Попробуй позже.",
            reply_markup=main_keyboard()
        )

# ========== КУПИТЬ TON ==========
@dp.callback_query(lambda c: c.data == "buy_ton")
async def buy_ton_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📈 *Покупка TON*\n\nВыбери сумму:",
        parse_mode="Markdown",
        reply_markup=buy_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("buy_amount_"))
async def confirm_buy(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_amount_", ""))
    price = await get_ton_price()
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    total = price * amount
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"buy_exec_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📈 *ПОДТВЕРЖДЕНИЕ ПОКУПКИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Итого: *${total:.2f}*\n\n"
        f"Для подтверждения открой кошелёк Tonkeeper "
        f"и отправь {amount} TON на адрес:\n"
        f"`EQD...твой_адрес_для_покупки...`\n\n"
        f"Нажми «Подтверждаю» когда отправишь.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("buy_exec_"))
async def execute_buy(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_exec_", ""))
    price = await get_ton_price()
    user_id = callback.from_user.id
    
    # Записываем позицию
    session = user_sessions.get(user_id, {'positions': []})
    session['positions'].append({
        'type': 'BUY',
        'amount': amount,
        'price': price,
        'time': datetime.now().isoformat()
    })
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ПОКУПКА СОВЕРШЕНА*\n\n"
        f"Куплено: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Сумма: *${price * amount:.2f}*\n\n"
        f"Позиция добавлена в портфель 📋",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПРОДАТЬ TON ==========
@dp.callback_query(lambda c: c.data == "sell_ton")
async def sell_ton_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📉 *Продажа TON*\n\nВыбери сумму:",
        parse_mode="Markdown",
        reply_markup=sell_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("sell_amount_"))
async def confirm_sell(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_amount_", ""))
    price = await get_ton_price()
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    total = price * amount
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_exec_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📉 *ПОДТВЕРЖДЕНИЕ ПРОДАЖИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Ты получишь: *${total:.2f}*\n\n"
        f"Для продажи отправь {amount} TON на адрес биржи.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("sell_exec_"))
async def execute_sell(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_exec_", ""))
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
        f"✅ *ПРОДАЖА СОВЕРШЕНА*\n\n"
        f"Продано: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Получено: *${price * amount:.2f}*\n\n"
        f"Позиция закрыта 📋",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== АВТО-ТРЕЙДИНГ ==========
@dp.callback_query(lambda c: c.data == "auto_trade")
async def auto_trade_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    status = "включен ✅" if session.get('auto_trade') else "выключен ❌"
    
    await callback.message.edit_text(
        f"🤖 *Авто-трейдинг*\n\nСтатус: {status}\n\n"
        f"Когда включен, бот отслеживает цену и присылает сигналы:\n"
        f"• 📈 Покупка при падении на 1%\n"
        f"• 📉 Продажа при росте на 2%\n\n"
        f"Ты подтверждаешь каждую сделку.",
        parse_mode="Markdown",
        reply_markup=auto_keyboard()
    )

@dp.callback_query(lambda c: c.data == "auto_on")
async def auto_on(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['auto_trade'] = True
    user_sessions[user_id] = session
    
    await callback.answer("✅ Авто-трейдинг включен", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "auto_off")
async def auto_off(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['auto_trade'] = False
    user_sessions[user_id] = session
    
    await callback.answer("❌ Авто-трейдинг выключен", show_alert=True)
    await auto_trade_menu(callback)

# ========== ПОЗИЦИИ ==========
@dp.callback_query(lambda c: c.data == "positions")
async def show_positions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    positions = session.get('positions', [])
    price = await get_ton_price()
    
    if not positions:
        text = "📋 У тебя нет открытых позиций."
    else:
        text = "📋 *История сделок:*\n\n"
        
        buy_positions = [p for p in positions if p['type'] == 'BUY']
        sell_positions = [p for p in positions if p['type'] == 'SELL']
        
        total_bought = sum(p['amount'] for p in buy_positions)
        total_sold = sum(p['amount'] for p in sell_positions)
        balance = total_bought - total_sold
        
        text += f"Куплено всего: {total_bought:.2f} TON\n"
        text += f"Продано всего: {total_sold:.2f} TON\n"
        text += f"Баланс: {balance:.2f} TON\n\n"
        
        if positions:
            text += "Последние сделки:\n"
            for pos in positions[-5:]:
                emoji = "🟢" if pos['type'] == 'BUY' else "🔴"
                text += f"{emoji} {pos['type']}: {pos['amount']} TON @ ${pos['price']:.4f}\n"
                text += f"   {pos['time'][:19]}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== НАЗАД ==========
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤖 Главное меню. Выбери действие:",
        reply_markup=main_keyboard()
    )

# ========== ПОМОЩЬ ==========
@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *Как пользоваться ботом*\n\n"
        "1. Нажми «Проверить цену» чтобы узнать курс TON\n"
        "2. Нажми «Купить TON» или «Продать TON» для сделки\n"
        "3. Включи «Авто-трейдинг» для автоматических сигналов\n"
        "4. Смотри «Мои позиции» для истории\n\n"
        "⚠️ Бот даёт сигналы на основе изменения цены.\n"
        "Это не финансовая рекомендация. Торгуй с умом.\n\n"
        "🔐 Бот не имеет доступа к твоему кошельку.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== АВТО-МОНИТОРИНГ ==========
async def price_monitor():
    last_price = None
    
    while True:
        await asyncio.sleep(60)
        price = await get_ton_price()
        
        if not price or not last_price:
            last_price = price
            continue
        
        change_pct = ((price - last_price) / last_price) * 100
        last_price = price
        
        for user_id, session in user_sessions.items():
            if not session.get('auto_trade'):
                continue
            
            if change_pct <= -1:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Купить 0.5 TON", callback_data="buy_amount_0.5")],
                    [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
                ])
                
                try:
                    await bot.send_message(
                        user_id,
                        f"🔔 *СИГНАЛ НА ПОКУПКУ*\n\n"
                        f"📉 Цена упала на *{change_pct:.2f}%*\n"
                        f"💰 Текущая цена: *${price:.4f}*\n\n"
                        f"Рекомендация: купить TON",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                except:
                    pass
            
            elif change_pct >= 2:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Продать 0.5 TON", callback_data="sell_amount_0.5")],
                    [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
                ])
                
                try:
                    await bot.send_message(
                        user_id,
                        f"🔔 *СИГНАЛ НА ПРОДАЖУ*\n\n"
                        f"📈 Цена выросла на *+{change_pct:.2f}%*\n"
                        f"💰 Текущая цена: *${price:.4f}*\n\n"
                        f"Рекомендация: продать TON",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                except:
                    pass

# ========== ЗАПУСК ==========
async def main():
    # Запускаем мониторинг в фоне
    asyncio.create_task(price_monitor())
    
    # Запускаем бота
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
