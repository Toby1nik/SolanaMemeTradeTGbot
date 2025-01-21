import requests

def get_quote(input_mint, output_mint, amount):
    """Fetch a swap quote."""
    url = f"https://quote-api.jup.ag/v6/quote"
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": 10,  # Example: 1% slippage
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_estimated_amount(input_mint, output_mint, amount_in_sol):
    """
    Get the estimated amount of tokens for a given amount of SOL.
    """
    try:
        # Convert SOL to lamports (1 SOL = 10^9 lamports)
        amount_in_lamports = int(amount_in_sol * 10**9)
        # Fetch the quote from Jupiter API
        quote = get_quote(input_mint, output_mint, amount_in_lamports)
        # Extract the output amount and convert it back to the token's decimal format
        amount_out =  int(quote['outAmount'])
        return amount_out
    except Exception as e:
        raise ValueError(f"Failed to fetch quote: {e}")

def get_swap_transaction(input_mint, output_mint, amount, user_wallet, slippage_bps=10):
    """
    Get transaction details for a swap from Jupiter API.

    Args:
        input_mint (str): Mint address of the input token.
        output_mint (str): Mint address of the output token.
        amount (int): Amount of input tokens (in lamports).
        user_wallet (str): Wallet address of the user.
        slippage_bps (int): Slippage tolerance in basis points (default: 10).

    Returns:
        dict: Response from Jupiter API containing the swap transaction.
    """
    url = "https://quote-api.jup.ag/v6/swap"
    payload = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": slippage_bps,
        "userPublicKey": user_wallet,
        "swapMode": "ExactIn",
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch swap transaction: {e}")

