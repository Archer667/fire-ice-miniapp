"""Official market: integer unit prices follow stock, never random ticks."""
def stock_price(listing, qty=None):
    base = max(1, int(listing.get('base_price', listing['price'])))
    reference = max(1, int(listing.get('reference_qty', max(1, listing['qty']))))
    stock = max(0, listing['qty'] if qty is None else qty)
    shortage = max(0, reference - stock)
    # Round half up; depletion adds at most 100% to the administrator's base.
    return base + (2 * base * shortage + reference) // (2 * reference)
