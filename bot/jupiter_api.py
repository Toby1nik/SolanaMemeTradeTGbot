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
