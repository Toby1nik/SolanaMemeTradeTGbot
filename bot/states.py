from aiogram.fsm.state import State, StatesGroup

class BuyState(StatesGroup):
    waiting_for_token_address = State()
    waiting_for_sol_amount = State()
    waiting_for_confirmation = State()
    waiting_for_token_out_amount = State()
