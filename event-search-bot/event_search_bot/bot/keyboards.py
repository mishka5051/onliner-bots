from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

EMPTY_INLINE_MARKUP = InlineKeyboardMarkup(inline_keyboard=[])

from event_search_bot.bot.access import is_staff
from event_search_bot.pipeline.filters import ExportFilters

BTN_SEARCH = "🔍 Поиск"
BTN_QUICK = "🔍 Быстрый"
BTN_DEEP = "🔬 Глубокий"
BTN_JOBS_LEGACY = "📋 Мои задания"
BTN_LEADS = "📥 Заявки"
BTN_APPROVED = "✅ Одобренные"
BTN_HISTORY = "🕐 История"
BTN_HELP = "❓ Справка"
BTN_MENU = "🏠 Главное меню"
BTN_BACK = "◀️ Назад"

MODE_QUICK = "quick"
MODE_DEEP = "deep"

NAV_BACK = "nav:menu"

QUERY_TEMPLATES: dict[str, str] = {
    "it": "IT конференция Минск 2026",
    "ecom": "e-commerce конференция Беларусь 2026",
    "expo": "выставка Беларусь 2026",
}

BTN_TPL_IT = "📌 IT Минск"
BTN_TPL_ECOM = "📌 E-commerce"
BTN_TPL_EXPO = "📌 Выставки 2026"

TEMPLATE_REPLY_BUTTONS: dict[str, str] = {
    BTN_TPL_IT: QUERY_TEMPLATES["it"],
    BTN_TPL_ECOM: QUERY_TEMPLATES["ecom"],
    BTN_TPL_EXPO: QUERY_TEMPLATES["expo"],
}


def main_menu_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_SEARCH)],
    ]
    if user_id is not None and is_staff(user_id):
        rows.append([KeyboardButton(text=BTN_LEADS)])
        rows.append([KeyboardButton(text=BTN_APPROVED), KeyboardButton(text=BTN_HISTORY)])
    else:
        rows.append([KeyboardButton(text=BTN_HISTORY)])
    rows.append([KeyboardButton(text=BTN_HELP)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
    )


def mode_search_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_TPL_IT), KeyboardButton(text=BTN_TPL_ECOM)],
        [KeyboardButton(text=BTN_TPL_EXPO)],
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MENU)],
    ]
    if user_id is not None and is_staff(user_id):
        rows.append([KeyboardButton(text=BTN_LEADS)])
        rows.append([KeyboardButton(text=BTN_APPROVED), KeyboardButton(text=BTN_HISTORY)])
    else:
        rows.append([KeyboardButton(text=BTN_HISTORY)])
    rows.append([KeyboardButton(text=BTN_HELP)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Запрос или шаблон…",
    )


def sub_screen_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MENU)],
    ]
    if user_id is not None and is_staff(user_id):
        rows.append([KeyboardButton(text=BTN_LEADS)])
        rows.append([KeyboardButton(text=BTN_APPROVED), KeyboardButton(text=BTN_HISTORY)])
    else:
        rows.append([KeyboardButton(text=BTN_HISTORY)])
    rows.append([KeyboardButton(text=BTN_HELP)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Введите запрос или вернитесь назад…",
    )


def search_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Быстрый поиск", callback_data="mode:quick"),
                InlineKeyboardButton(text="🔬 Глубокий поиск", callback_data="mode:deep"),
            ],
            [InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)],
        ]
    )


def search_mode_switch_keyboard(active_mode: str) -> InlineKeyboardMarkup:
    quick_label = "✅ Быстрый" if active_mode == MODE_QUICK else "🔍 Быстрый"
    deep_label = "✅ Глубокий" if active_mode == MODE_DEEP else "🔬 Глубокий"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=quick_label, callback_data="mode:quick"),
                InlineKeyboardButton(text=deep_label, callback_data="mode:deep"),
            ],
            [InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)],
        ]
    )


def _with_nav_back(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)],
    ]
    if markup is not None:
        rows.extend(markup.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def jobs_list_keyboard(jobs: list) -> InlineKeyboardMarkup:
    from event_search_bot.pipeline.jobs import DeepSearchJob

    rows: list[list[InlineKeyboardButton]] = []
    for job in reversed(jobs[-5:]):
        if not isinstance(job, DeepSearchJob) or not job.is_active():
            continue
        label = job.query[:24] + ("…" if len(job.query) > 24 else "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📊 {job.job_id} · {label}",
                    callback_data=f"status:{job.job_id}",
                ),
                InlineKeyboardButton(text="⏹", callback_data=f"cancel:{job.job_id}"),
            ]
        )
    return _with_nav_back(InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)


def job_view_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return _with_nav_back(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статус", callback_data=f"status:{job_id}")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data=f"cancel:{job_id}")],
            ]
        )
    )


def job_complete_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return _with_nav_back(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📎 Выгрузка", callback_data=f"exp:{job_id}"),
                    InlineKeyboardButton(text="📊 Аналитика", callback_data=f"ana:{job_id}"),
                ],
                [
                    InlineKeyboardButton(text="📇 Карточки", callback_data=f"evl:{job_id}:0"),
                    InlineKeyboardButton(text="📤 Коллеге", callback_data=f"shr:{job_id}"),
                ],
                [InlineKeyboardButton(text="🔄 Повторить поиск", callback_data=f"hist:rerun_job:{job_id}")],
            ]
        )
    )


def _toggle_label(enabled: bool, text: str) -> str:
    return f"{'✅' if enabled else '◻️'} {text}"


def export_filters_keyboard(job_id: str, filters: ExportFilters) -> InlineKeyboardMarkup:
    return _with_nav_back(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_toggle_label(filters.minsk_only, "Только Минск"),
                        callback_data=f"efx:{job_id}:m",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=_toggle_label(filters.min_score_50, "Score ≥ 50"),
                        callback_data=f"efx:{job_id}:s",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=_toggle_label(filters.partnership_only, "Партнёрство"),
                        callback_data=f"efx:{job_id}:p",
                    ),
                ],
                [
                    InlineKeyboardButton(text="📄 CSV", callback_data=f"efx:{job_id}:csv"),
                    InlineKeyboardButton(text="🌐 HTML", callback_data=f"efx:{job_id}:html"),
                ],
                [InlineKeyboardButton(text="◀️ К отчёту", callback_data=f"act:{job_id}")],
            ]
        )
    )


def event_list_keyboard(job_id: str, page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    start = page * page_size
    end = min(start + page_size, total)
    for index in range(start, end):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{index + 1}",
                    callback_data=f"evt:{job_id}:{index}",
                )
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="«", callback_data=f"evl:{job_id}:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="»", callback_data=f"evl:{job_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ К отчёту", callback_data=f"act:{job_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_card_keyboard(job_id: str, url: str, index: int) -> InlineKeyboardMarkup:
    return _with_nav_back(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Открыть сайт", url=url)],
                [InlineKeyboardButton(text="◀️ К списку", callback_data=f"evl:{job_id}:0")],
                [
                    InlineKeyboardButton(text="«", callback_data=f"evt:{job_id}:{max(0, index - 1)}"),
                    InlineKeyboardButton(text="»", callback_data=f"evt:{job_id}:{index + 1}"),
                ],
            ]
        )
    )


def history_view_keyboard(entry_id: int, *, can_rerun: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_rerun:
        rows.append([InlineKeyboardButton(text="🔄 Повторить поиск", callback_data=f"hist:rerun:{entry_id}")])
    rows.append([InlineKeyboardButton(text="◀️ К истории", callback_data="hist:list")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_keyboard(entries: list) -> InlineKeyboardMarkup:
    from event_search_bot.storage.user_storage import HistoryEntry

    rows: list[list[InlineKeyboardButton]] = []
    for entry in entries:
        if not isinstance(entry, HistoryEntry):
            continue
        label = entry.query[:28] + ("…" if len(entry.query) > 28 else "")
        icon = "🔍" if entry.mode == MODE_QUICK else "🔬"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {label}",
                    callback_data=f"hist:view:{entry.id}",
                )
            ]
        )
    if rows:
        rows.append([InlineKeyboardButton(text="🗑 Очистить историю", callback_data="hist:clear")])
    return _with_nav_back(InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)


def leads_dashboard_keyboard(new_count: int, approved_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🆕 Новые ({new_count})", callback_data="ls:new:0")],
            [InlineKeyboardButton(text=f"✅ Одобренные ({approved_count})", callback_data="ls:events:0")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="leads:refresh")],
            [InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)],
        ]
    )


def leads_list_keyboard(section: str, items: list, page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        short_id = getattr(item, "short_id", "")
        title = getattr(item, "event_title", "")[:22]
        if len(getattr(item, "event_title", "")) > 22:
            title += "…"
        icon = "📌" if section == "events" else "📄"
        rows.append([InlineKeyboardButton(text=f"{icon} {short_id} · {title}", callback_data=f"ld:{short_id}:{section}:{page}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="«", callback_data=f"ls:{section}:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="»", callback_data=f"ls:{section}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"ls:{section}:{page}")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_card_keyboard(lead_short_id: str, url: str | None, section: str, page: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if section == "new":
        rows.append(
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"lm:approve:{lead_short_id}:{section}:{page}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"lm:delete:{lead_short_id}:{section}:{page}"),
            ]
        )
    elif section == "approved":
        rows.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"lm:delete:{lead_short_id}:{section}:{page}")])
    if url:
        rows.append([InlineKeyboardButton(text="🌐 Открыть сайт", url=url)])
    rows.append([InlineKeyboardButton(text="◀️ К списку", callback_data=f"ls:{section}:{page}")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approved_event_card_keyboard(lead_short_id: str, url: str | None, page: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if url:
        rows.append([InlineKeyboardButton(text="🌐 Открыть сайт", url=url)])
    rows.append([InlineKeyboardButton(text="◀️ К списку", callback_data=f"ls:events:{page}")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data=NAV_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
