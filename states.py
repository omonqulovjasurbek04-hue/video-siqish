from aiogram.fsm.state import State, StatesGroup


class VideoStates(StatesGroup):
    waiting_video     = State()
    choosing_compress = State()
    custom_settings   = State()
    processing        = State()


class TrimStates(StatesGroup):
    waiting_video = State()
    waiting_start = State()
    waiting_end   = State()


class MergeStates(StatesGroup):
    waiting_first  = State()
    waiting_second = State()


class WatermarkStates(StatesGroup):
    waiting_video = State()
    waiting_text  = State()


class GifStates(StatesGroup):
    waiting_video  = State()
    waiting_choice = State()
    waiting_time   = State()
